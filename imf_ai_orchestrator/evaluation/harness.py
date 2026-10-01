"""Planted-error benchmark.

Takes a clean, approved case (claim register + sources + data + tagged draft),
plants one known error per trial, and records which controls catch it:

  code checks   - claim-strengthening audit, quote matching, data checks,
                  vintage checks, coverage rules (deterministic, free)
  model reviews - optional: any agents you list are asked to review the
                  mutated draft as substance reviewers (live mode)

The result is a detection-rate table per error type and per control, plus the
false-positive rate on the clean case. Use it to decide, on evidence, which
roles and which models actually add scrutiny, and to re-test when models or
prompts change.
"""
from __future__ import annotations

import copy
import json
import random
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from orchestrator import gate, verify
from orchestrator.config import load_config
from orchestrator.model import Claim, RunState, Source
from orchestrator.strength import audit_draft

# ------------------------------------------------------------------ case
def load_case(root: Path, case: Path):
    cfg = load_config(root)
    mock = case / "mock"
    researcher = json.loads((mock / "researcher.json").read_text())["default"]
    st = RunState(run_id="bench", research_question="", document_type="analytical_question",
                  confidentiality="PUBLIC", mode="mock", requested_level=3, level=3, as_of="2026-09-30")
    for i, s in enumerate(researcher["sources"], 1):
        st.sources[f"S{i:03d}"] = Source.from_dict({**s, "source_id": f"S{i:03d}"})
    for d in json.loads((mock / "registrar.json").read_text())["claims"]:
        st.claims[d["claim_id"]] = Claim.from_dict(d)
    grades = json.loads((mock / "grader.json").read_text())
    for cid, c in st.claims.items():
        c.grades = {"grader_a": grades["default"][cid], "grader_b": grades.get("gemini", grades["default"])[cid]}
    draft = (case / "draft_clean.md").read_text()
    return cfg, st, draft


def check_register(cfg, st, case: Path, tmp: Path) -> dict[str, list[str]]:
    store = verify.SourceStore([case], tmp, allow_network=False)
    data = verify.DataConnectors([case / "data.csv"], allow_network=False)
    verify.verify_claims(st, store, data, cfg.quality_gates)
    for c in st.claims.values():
        c.status = "PROPOSED" if c.status != "REJECTED" else c.status
    gate.update_statuses(st, cfg)
    out = {cid: sorted(set(gate.claim_failures(c, st, cfg)) | set(c.flags)) for cid, c in st.claims.items()}
    # coverage rule: risks must be represented by an approved RSK claim
    if not any(c.claim_type == "RSK" and c.status in gate.APPROVED for c in st.claims.values()):
        out["_coverage"] = ["COV-RISK missing"]
    return out


# ---------------------------------------------------------------- mutators
def _sent(draft, tag):
    m = re.search(r"(?:^|\]|\n)\s*([^\[\]\n]+?)\s*\[" + tag + r"\]", draft)
    return m.group(1).strip() if m else None


def m_number_change(draft, st, rng):
    cid = rng.choice(["C001", "C002", "C004", "C006"])
    s = _sent(draft, cid)
    nums = [n for n in re.findall(r"\d+(?:\.\d+)?", s) if not re.fullmatch(r"(19|20)\d\d", n)]
    n = rng.choice(nums)
    new = str(round(float(n) * rng.choice([0.8, 1.15, 1.3]), 1)).rstrip("0").rstrip(".")
    return draft.replace(s, s.replace(n, new, 1)), None


def m_date_shift(draft, st, rng):
    cid = rng.choice(["C001", "C002", "C003", "C004", "C006"])
    s = _sent(draft, cid)
    y = rng.choice(re.findall(r"20\d\d", s))
    return draft.replace(s, s.replace(y, str(int(y) + rng.choice([-1, 1])), 1)), None


def m_causal_strengthening(draft, st, rng):
    rep = rng.choice(["contributed to", "drove", "was the key driver of", "caused", "explains", "was largely responsible for"])
    return draft.replace("appears to have contributed to", rep, 1), None


def m_hedge_removal(draft, st, rng):
    if rng.random() < 0.5:
        return draft.replace("appears to have contributed to the reduction", "reduced", 1), None
    return draft.replace("remained about 20 percent", "remained 20 percent", 1), None


def m_probability_strengthening(draft, st, rng):
    return draft.replace("Arrears could re-emerge", rng.choice(["Arrears will re-emerge", "Arrears are certain to re-emerge"]), 1), None


def m_scope_widening(draft, st, rng):
    return draft.replace("Collection rates rose", "Collection rates rose across all distributors", 1), None


def m_attribution_swap(draft, st, rng):
    return draft.replace("Staff recommends", rng.choice(["The authorities committed to", "The authorities recommend"]), 1), None


def m_untagged_new_claim(draft, st, rng):
    extra = rng.choice(["The sector's operating deficit narrowed by 1.5 percent of GDP in 2025.",
                        "This clearly demonstrates that the reform has succeeded.",
                        "Independent power producers were paid in full in 2025."])
    return draft.replace("## Tariffs and risks", extra + "\n\n## Tariffs and risks", 1), None


def m_tag_to_unapproved(draft, st, rng):
    s = rng.choice(["Tariff shortfalls accounted for roughly half of sector losses in 2025. [C009]",
                    "The regional review found that the cash waterfall eliminated arrears to independent power producers. [C010]"])
    return draft.replace("## Tariffs and risks", s + "\n\n## Tariffs and risks", 1), None


def m_appraisal_overreach(draft, st, rng):
    return draft.rstrip() + "\n\nStaff assesses that higher collections were the main driver of lower arrears. [C002]\n", None


def m_inflation_term(draft, st, rng):
    return draft.replace("arrears fell from", rng.choice(["arrears fell dramatically from", "arrears fell, in an unprecedented improvement, from"]), 1), None


def m_negation_flip(draft, st, rng):
    return draft.replace("Arrears could re-emerge", "Arrears could not re-emerge", 1), None


def r_fabricated_quote(draft, st, rng):
    cid = rng.choice(["C001", "C002", "C003", "C004", "C006"])
    ev = st.claims[cid].evidence[0]
    words = ev.excerpt.split()
    i = rng.randrange(len(words))
    words[i] = rng.choice(["significantly", "entirely", "2019", "doubled", "national"])
    ev.excerpt = " ".join(words)
    return draft, cid


def r_fabricated_source(draft, st, rng):
    cid = rng.choice(["C001", "C002", "C003", "C004", "C006"])
    st.claims[cid].evidence[0].source_id = "S999"
    return draft, cid


def r_number_not_in_evidence(draft, st, rng):
    cid = rng.choice(["C001", "C002", "C004"])
    c = st.claims[cid]
    n = [x for x in re.findall(r"\d+(?:\.\d+)?", c.approved_wording) if not re.fullmatch(r"(19|20)\d\d", x)][0]
    c.approved_wording = c.approved_wording.replace(n, str(round(float(n) + 0.7, 1)), 1)
    return draft, cid


def r_data_mismatch(draft, st, rng):
    cid = rng.choice(["C001", "C002", "C004"])
    n = st.claims[cid].numbers[0]
    n.value = round(n.value * 1.25, 1)
    return draft, cid


def r_outdated_source(draft, st, rng):
    st.sources["S001"].publication_date = "2021-06-30"
    return draft, "C001"


def r_missing_risk(draft, st, rng):
    del st.claims["C008"]
    return draft.replace("Arrears could re-emerge if collection gains are not sustained. [C008]", ""), "_coverage"


DRAFT_MUTATORS = {k[2:]: v for k, v in globals().items() if k.startswith("m_")}
REGISTER_MUTATORS = {k[2:]: v for k, v in globals().items() if k.startswith("r_")}


# ---------------------------------------------------------------- run
def run_benchmark(root: Path, case: Path, n: int = 200, seed: int = 7, mode: str = "mock",
                  reviewers: list[str] | None = None, confidentiality: str = "PUBLIC", write_report: bool = True) -> str:
    rng = random.Random(seed)
    cfg, base_state, clean = load_case(root, case)
    tmp = root / "runs" / "_bench_cache"
    base_register = check_register(cfg, copy.deepcopy(base_state), case, tmp)
    approved_state = copy.deepcopy(base_state)
    check_register(cfg, approved_state, case, tmp)
    base_audit = audit_draft(clean, approved_state.claims, cfg.strength)
    fp_draft = sum(1 for r in base_audit if r["findings"])

    runner = None
    if reviewers and mode == "live":
        from orchestrator.agents import AgentRunner
        from orchestrator.audit_log import AuditLog
        bench_dir = root / "runs" / f"_bench_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
        runner = AgentRunner(cfg, bench_dir, "live", confidentiality, AuditLog(bench_dir / "audit_log.jsonl"))

    stats = defaultdict(lambda: defaultdict(int))
    names = list(DRAFT_MUTATORS) + list(REGISTER_MUTATORS)
    for trial in range(n):
        name = names[trial % len(names)] if trial < len(names) else rng.choice(names)
        st = copy.deepcopy(base_state)
        stats[name]["trials"] += 1
        if name in DRAFT_MUTATORS:
            mutated, _ = DRAFT_MUTATORS[name](clean, st, rng)
            if mutated == clean:
                stats[name]["not_applicable"] += 1
                continue
            check_register(cfg, st, case, tmp)
            audit = audit_draft(mutated, st.claims, cfg.strength)
            base_keys = {(r["text"], tuple(r["findings"])) for r in base_audit}
            new = [r for r in audit if r["findings"] and (r["text"], tuple(r["findings"])) not in base_keys]
            if new:
                stats[name]["code_any"] += 1
            if any(r["red_codes"] for r in new):
                stats[name]["code_blocking"] += 1
            if runner:
                for agent in reviewers:
                    if _model_detects(runner, cfg, agent, mutated, st, clean, trial, name):
                        stats[name][f"model:{agent}"] += 1
        else:
            mutated, target = REGISTER_MUTATORS[name](clean, st, rng)
            result = check_register(cfg, st, case, tmp)
            before = set(base_register.get(target, []))
            after = set(result.get(target, []))
            if after - before:
                stats[name]["code_any"] += 1
                if any(x.startswith(("RED-", "UNKNOWN_SOURCE", "NUMBER_NOT", "OUTDATED", "COV-")) for x in after - before):
                    stats[name]["code_blocking"] += 1
    return _report(stats, n, seed, fp_draft, base_register, reviewers if runner else [], root, write_report)


def _model_detects(runner, cfg, agent, mutated, st, clean, trial, name) -> bool:
    approved = [{"claim_id": c.claim_id, "approved_wording": c.wording(), "claim_type": c.claim_type}
                for c in st.claims.values() if c.status in gate.APPROVED]
    payload = {"draft": mutated, "approved_claims": approved,
               "do_not_assert": [c.claim_id for c in st.claims.values() if c.status not in gate.APPROVED]}
    reply = runner.call("substance_reviewer", agent, f"bench-{trial}-{name}-{agent}", payload, "benchmark")
    changed = {s.strip() for s in mutated.split("\n") if s.strip()} - {s.strip() for s in clean.split("\n") if s.strip()}
    blob = json.dumps(reply.get("issues", [])).lower()
    return any(re.sub(r"\s*\[.*?\]", "", line).lower()[:40] in blob for line in changed) or \
        any(t.lower() in blob for line in changed for t in re.findall(r"C\d{3}", line))


def _report(stats, n, seed, fp_draft, base_register, reviewers, root, write_report=True) -> str:
    lines = [f"# Planted-error benchmark (n={n}, seed={seed})", "",
             f"False positives on the clean draft: {fp_draft} flagged sentence(s).",
             "Baseline register failures (planted defects in the sample case, excluded from scoring): "
             + ", ".join(f"{k}: {v}" for k, v in base_register.items() if v), "",
             "| Planted error | Trials | Caught by code (any) | Caught by code (blocking) | "
             + " | ".join(f"Model: {r}" for r in reviewers) + (" |" if reviewers else ""),
             "|---|---|---|---|" + "---|" * len(reviewers)]
    tot = defaultdict(int)
    for name, s in sorted(stats.items()):
        t = s["trials"] - s["not_applicable"]
        row = f"| {name} | {t} | {_pct(s['code_any'], t)} | {_pct(s['code_blocking'], t)} |"
        row += "".join(f" {_pct(s[f'model:{r}'], t)} |" for r in reviewers)
        lines.append(row)
        tot["t"] += t
        tot["any"] += s["code_any"]
        tot["blk"] += s["code_blocking"]
    lines += [f"| **All** | {tot['t']} | {_pct(tot['any'], tot['t'])} | {_pct(tot['blk'], tot['t'])} |" + " |" * len(reviewers), "",
              "Code checks are deterministic. Errors they miss are what model reviewers must be tested on: "
              "run with `--mode live --reviewers claude,gemini,...` to compare reviewers on the same planted errors."]
    out = "\n".join(lines)
    if not write_report:
        return out
    rep_dir = root / "evaluation" / "reports"
    rep_dir.mkdir(exist_ok=True)
    (rep_dir / f"benchmark_seed{seed}_n{n}.md").write_text(out, encoding="utf-8")
    return out


def _pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "n/a"
