"""Agent calls: prompt assembly, security check, caching/replay and adapters.

Every call goes through AgentRunner.call(), which:
  1. checks the confidentiality gate for that agent (security.check);
  2. builds the prompt = common rules + role prompt + output contract + input;
  3. replays a cached reply if the identical request was already answered
     (so runs are resumable and reproducible);
  4. otherwise dispatches to the adapter for the run mode:
       mock   - canned fixtures, no transmission (for dry runs and tests)
       manual - writes the prompt to runs/<id>/manual/ and waits for you to
                paste the chatbot's reply next to it (no API needed)
       live   - HTTPS call to the provider API
  5. validates the reply against the role's contract and logs the call.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

from . import contracts, security
from .audit_log import AuditLog, sha256
from .config import Config


class PendingManual(Exception):
    """Raised when a manual-mode prompt is waiting for a pasted reply."""

    def __init__(self, paths: list[Path]):
        super().__init__(f"{len(paths)} manual step(s) pending")
        self.paths = paths


class AgentRunner:
    def __init__(self, cfg: Config, run_dir: Path, mode: str, confidentiality: str,
                 log: AuditLog, mock_dir: Path | None = None):
        self.cfg = cfg
        self.run_dir = run_dir
        self.mode = mode
        self.confidentiality = confidentiality
        self.log = log
        self.mock = MockProvider(mock_dir) if mode == "mock" else None
        (run_dir / "calls").mkdir(parents=True, exist_ok=True)
        if mode == "manual":
            (run_dir / "manual").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ prompt
    def build_prompt(self, role: str, payload: dict) -> tuple[str, str]:
        common = (self.cfg.prompts_dir / "_common.md").read_text(encoding="utf-8")
        role_prompt = (self.cfg.prompts_dir / f"{role}.md").read_text(encoding="utf-8")
        system = common + "\n\n" + role_prompt
        user = (contracts.contract_text(role) + "\n\nINPUT:\n```json\n"
                + json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n```")
        return system, user

    # -------------------------------------------------------------------- call
    def call(self, role: str, agent: str, call_id: str, payload: dict, stage: str) -> dict:
        security.check(self.cfg, self.confidentiality, agent, self.mode)
        system, user = self.build_prompt(role, payload)
        req_hash = sha256(agent + "\n" + system + "\n" + user)
        cache = self.run_dir / "calls" / f"{call_id}.json"
        if cache.exists():
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if cached.get("request_sha256") == req_hash:
                return cached["parsed"]

        spec = self.cfg.agents[agent]
        started = time.time()
        if self.mode == "mock":
            reply = self.mock.reply(role, agent, payload)
            usage = {}
        elif self.mode == "manual" or spec["adapter"] == "manual":
            reply, usage = self._manual(call_id, agent, role, system, user), {}
        else:
            reply, usage = _dispatch(spec, system, user)

        try:
            parsed = contracts.parse(role, reply)
        except contracts.ContractError as err:
            self.log.write("contract_error", call_id=call_id, agent=agent, role=role, error=str(err))
            if self.mode != "live":
                raise
            # one repair attempt, then fail loudly
            reply, usage = _dispatch(spec, system, user + "\n\nYour previous reply was invalid: "
                                     + str(err) + "\nReturn only the JSON object.")
            parsed = contracts.parse(role, reply)

        cache.write_text(json.dumps({"call_id": call_id, "agent": agent, "role": role,
                                     "request_sha256": req_hash, "reply": reply if isinstance(reply, str) else json.dumps(reply),
                                     "parsed": parsed}, indent=2, ensure_ascii=False), encoding="utf-8")
        self.log.write("model_call", call_id=call_id, stage=stage, role=role, agent=agent,
                       family=spec["family"], provider=spec["provider"], model=spec.get("model"),
                       mode=self.mode, temperature=spec.get("temperature"),
                       request_sha256=req_hash, input_fields=sorted(payload.keys()),
                       latency_s=round(time.time() - started, 2), usage=usage)
        return parsed

    def call_many(self, jobs: list[tuple], stage: str) -> dict:
        """Run independent calls; collect all pending manual steps before stopping.

        jobs: [(key, role, agent, call_id, payload)]. Calls run sequentially so
        the audit log is ordered; independence comes from input isolation, not
        concurrency.
        """
        results, pending = {}, []
        for key, role, agent, call_id, payload in jobs:
            try:
                results[key] = self.call(role, agent, call_id, payload, stage)
            except PendingManual as p:
                pending.extend(p.paths)
        if pending:
            raise PendingManual(pending)
        return results

    def _manual(self, call_id: str, agent: str, role: str, system: str, user: str) -> str:
        prompt_path = self.run_dir / "manual" / f"{call_id}.prompt.md"
        reply_path = self.run_dir / "manual" / f"{call_id}.reply.md"
        if reply_path.exists() and reply_path.read_text(encoding="utf-8").strip():
            return reply_path.read_text(encoding="utf-8")
        prompt_path.write_text(
            f"<!-- Paste into {agent} as role '{role}'. Save the full reply to {reply_path.name} -->\n\n"
            f"## SYSTEM / INSTRUCTIONS\n\n{system}\n\n## TASK\n\n{user}\n", encoding="utf-8")
        reply_path.touch()
        raise PendingManual([prompt_path])


# ---------------------------------------------------------------- adapters
def _post(url: str, headers: dict, body: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _key(spec: dict) -> str:
    key = os.environ.get(spec.get("api_key_env", ""), "")
    if not key:
        raise RuntimeError(f"environment variable {spec.get('api_key_env')} is not set")
    if spec.get("model", "SET_ME") == "SET_ME":
        raise RuntimeError("model not configured in config/agents.yaml (still SET_ME)")
    return key


def _dispatch(spec: dict, system: str, user: str) -> tuple[str, dict]:
    adapter = spec["adapter"]
    temp = spec.get("temperature", 0.2)
    if adapter == "openai_compatible":
        out = _post(spec["base_url"].rstrip("/") + "/chat/completions",
                    {"Authorization": f"Bearer {_key(spec)}"},
                    {"model": spec["model"], "temperature": temp,
                     "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        return out["choices"][0]["message"]["content"], out.get("usage", {})
    if adapter == "anthropic":
        out = _post(spec["base_url"].rstrip("/") + "/messages",
                    {"x-api-key": _key(spec), "anthropic-version": "2023-06-01"},
                    {"model": spec["model"], "max_tokens": spec.get("max_tokens", 16000), "temperature": temp,
                     "system": system, "messages": [{"role": "user", "content": user}]})
        return "".join(b.get("text", "") for b in out["content"]), out.get("usage", {})
    if adapter == "gemini":
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": temp}}
        if spec.get("web_search"):
            body["tools"] = [{"google_search": {}}]
        out = _post(f"{spec['base_url'].rstrip('/')}/models/{spec['model']}:generateContent",
                    {"x-goog-api-key": _key(spec)}, body)
        parts = out["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts), out.get("usageMetadata", {})
    raise RuntimeError(f"no live adapter for '{adapter}' (use --mode manual)")


# ------------------------------------------------------------------- mock
class MockProvider:
    """Canned replies for dry runs. Fixtures live in <case>/mock/<role>.json and
    may be keyed by agent name (with a "default" fallback)."""

    def __init__(self, mock_dir: Path | None):
        self.dir = mock_dir

    def _fixture(self, role: str, agent: str):
        if not self.dir:
            return None
        path = self.dir / f"{role}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and ("default" in data or agent in data):
            return data.get(agent, data.get("default"))
        return data

    def reply(self, role: str, agent: str, payload: dict) -> dict:
        fx = self._fixture(role, agent)
        if role == "grader":
            table = fx or {}
            return {"grades": [{"claim_id": c["claim_id"], **table.get(c["claim_id"], {"S": "S3", "E": "E3", "C": None}),
                                "rationale": "mock"} for c in payload.get("claims_to_grade", [])]}
        if role == "source_auditor":
            # Echo the first cited excerpt; the code-level quote check decides.
            out = []
            for c in payload.get("claims_to_audit", []):
                ev = (c.get("evidence") or [{}])[0]
                out.append({"claim_id": c["claim_id"], "status": "VERIFIED" if ev.get("excerpt") else "NOT_VERIFIED",
                            "source_id": ev.get("source_id", ""), "excerpt": ev.get("excerpt", ""),
                            "locator": ev.get("locator", ""), "wording_stronger_than_source": False,
                            "recommended_wording": "", "note": "mock"})
            return {"audited_claims": out}
        if role == "synthesizer" and fx is not None:
            fx = dict(fx)
            fx["dispositions"] = [{"issue_id": i["issue_id"], "decision": "ACCEPTED",
                                   "rationale": "mock: accepted"} for i in payload.get("issues_for_disposition", [])]
            return fx
        if role == "reviser":
            base = dict(fx) if fx else {"draft_markdown": payload.get("draft", "")}
            base["dispositions"] = [{"issue_id": i["issue_id"], "decision": "ACCEPTED", "rationale": "mock"}
                                    for i in payload.get("issues_for_disposition", [])]
            return base
        if role == "critic_rebuttal":
            return {"verdict": "UPHELD", "rationale": "mock"}
        if role == "adjudicator":
            return {"verdict": "ESCALATE", "rationale": "mock"}
        if role == "targeted":
            return fx if fx is not None else {"updates": []}
        if fx is not None:
            return fx
        empty = {k: [] for k in contracts.CONTRACTS[role]["required"]}
        if role == "framer":
            empty.update({"research_question": payload.get("research_question", "")})
        if role in ("adversarial_reviewer",):
            empty.update({"overall": "mock", "would_sign_off": True})
        if role in ("structure_reviewer", "editorial_reviewer"):
            empty.update({"score": 80})
        if role == "analyst":
            empty.update({"diagnosis": "mock"})
        return empty
