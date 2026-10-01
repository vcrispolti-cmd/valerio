"""The orchestration state machine.

Python controls the workflow; models never call each other. Every stage reads
the run state, sends each role only what the exposure rules allow, validates
the reply, and writes its output to the run folder. Re-running a run replays
cached replies, so manual-mode and interrupted runs resume where they stopped.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from . import adjudication, coverage, gate, roles, security, strength, verify
from .agents import AgentRunner, PendingManual
from .audit_log import AuditLog
from .classify import classify
from .config import Config
from .exposure import build_input
from .model import Claim, Evidence, NumberFact, RunState, Source


class StopRun(RuntimeError):
    pass


def claim_view(c: Claim, detail: bool = True) -> dict:
    v = {"claim_id": c.claim_id, "text": c.text, "approved_wording": c.wording(), "claim_type": c.claim_type,
         "importance": c.importance, "status": c.status}
    if detail:
        v.update({"evidence": [{"source_id": e.source_id, "excerpt": e.excerpt, "locator": e.locator,
                                "relation": e.relation, "quote_check": e.quote_check} for e in c.evidence],
                  "numbers": [{"value": n.value, "unit": n.unit, "series": n.series, "period": n.period,
                               "data_check": n.data_check} for n in c.numbers],
                  "grades": {"S": c.consensus("S"), "E": c.consensus("E"), "C": c.consensus("C")},
                  "alternatives": c.alternatives, "flags": c.flags, "depends_on": c.depends_on})
    return v


def source_view(s: Source) -> dict:
    return {k: v for k, v in asdict(s).items() if k in
            ("source_id", "title", "institution", "publication_date", "data_vintage", "url", "authority_grade", "status")}


class Pipeline:
    def __init__(self, cfg: Config, run_dir: Path, spec: dict):
        self.cfg = cfg
        self.dir = run_dir
        self.spec = spec
        self.log = AuditLog(run_dir / "audit_log.jsonl")
        level, basis = classify(cfg, spec["question"], spec["document_type"], spec["level"])
        self.state = RunState(run_id=spec["run_id"], research_question=spec["question"],
                              document_type=spec["document_type"], confidentiality=spec["confidentiality"],
                              mode=spec["mode"], requested_level=spec["level"], level=level, level_basis=basis,
                              country=spec.get("country", ""), as_of=spec.get("as_of", ""),
                              context=spec.get("context", ""))
        case_dir = Path(spec["case_dir"]) if spec.get("case_dir") else None
        self.runner = AgentRunner(cfg, run_dir, spec["mode"], spec["confidentiality"], self.log,
                                  mock_dir=(case_dir / "mock") if case_dir else None)
        bases = [p for p in [case_dir, Path(spec["documents_dir"]) if spec.get("documents_dir") else None] if p]
        self.store = verify.SourceStore(bases, run_dir / "source_cache", allow_network=spec["mode"] == "live")
        csvs = [Path(p) for p in spec.get("data_csv", [])]
        if case_dir and (case_dir / "data.csv").exists():
            csvs.append(case_dir / "data.csv")
        self.data = verify.DataConnectors(csvs, allow_network=spec["mode"] == "live")
        self.candidates: list[dict] = []
        self.permitted: list[str] = []
        self.drafting_standard = (cfg.prompts_dir / "drafting_standard.md").read_text(encoding="utf-8")

    # ============================================================== helpers
    def out(self, name: str, obj) -> None:
        path = self.dir / name
        if isinstance(obj, str):
            path.write_text(obj, encoding="utf-8")
        else:
            path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    def agent(self, role: str, i: int = 0) -> str:
        return self.state.assignments[role][i]

    def call(self, role: str, agent: str, key: str, available: dict, stage: str, prompt_role: str | None = None) -> dict:
        prompt_role = prompt_role or role
        payload = build_input(self.cfg, prompt_role, available)
        call_id = f"{stage}-it{self.state.iteration}-{prompt_role}-{agent}{('-' + key) if key else ''}"
        return self.runner.call(prompt_role, agent, call_id, payload, stage)

    def issue(self, key: str = "", **kw):
        if key:
            for i in self.state.issues:
                if i.key == key:
                    if i.status == "RESOLVED" and i.raised_by == "system":
                        i.status, i.disposition = "OPEN", {}
                    return i
        return self.state.add_issue(key=key, **kw)

    def register_source(self, d: dict, proposed_by: str) -> str:
        for s in self.state.sources.values():
            if (d.get("url") and s.url == d.get("url")) or (d.get("local_path") and s.local_path == d.get("local_path")) \
                    or (d.get("title") and s.title == d.get("title") and s.institution == d.get("institution", "")):
                return s.source_id
        sid = f"S{len(self.state.sources) + 1:03d}"
        src = Source.from_dict({**d, "source_id": sid, "proposed_by": proposed_by})
        self.state.sources[sid] = src
        return sid

    def available(self, **extra) -> dict:
        st = self.state
        return {"research_question": st.research_question, "document_type": st.document_type, "country": st.country,
                "context": st.context, "constraints": self.spec.get("constraints", []),
                "source_policy": {"primary_sources_required": True, "as_of": st.as_of, "citation_required": True,
                                  "verbatim_excerpts_required": True},
                "documents": self.spec.get("documents", []), "neutral_subquestions": st.neutral_subquestions,
                "framing": st.framing, "as_of": st.as_of, **extra}

    # =============================================================== run
    def run(self) -> RunState:
        st = self.state
        self.out("00_input.json", self.spec)
        self.out("01_classification.json", {"level": st.level, "basis": st.level_basis,
                                            "label": self.cfg.routing["levels"][st.level]["label"]})
        self.permitted = security.permitted_agents(self.cfg, st.confidentiality, st.mode)
        sec = {"confidentiality": st.confidentiality, "mode": st.mode, "permitted_agents": self.permitted}
        if not self.permitted:
            sec["result"] = "BLOCKED: no external model is approved for this confidentiality class"
            self.out("02_security.json", sec)
            raise StopRun(sec["result"])
        st.assignments = roles.assign(self.cfg, self.permitted, self.spec.get("rotation_seed"),
                                      self.spec.get("role_overrides"))
        sec["assignments"] = st.assignments
        sec["result"] = "PASSED"
        self.out("02_security.json", sec)
        self.log.write("assignments", assignments=st.assignments, permitted=self.permitted)
        try:
            for stage in self.cfg.stages_for_level(st.level):
                getattr(self, f"stage_{stage}")()
                st.stages_done.append(stage)
                st.save(self.dir / "state.json")
        except PendingManual as p:
            st.notes.append(f"waiting for {len(p.paths)} manual reply(ies)")
            st.save(self.dir / "state.json")
            raise
        except StopRun as s:
            st.notes.append(str(s))
        from .dashboard import write_dashboard
        write_dashboard(self)
        st.save(self.dir / "state.json")
        return st

    # ============================================================= stages
    def stage_frame(self):
        agent = self.agent("framer")
        r = self.call("framer", agent, "", self.available(), "frame")
        self.state.framing = r
        self.state.neutral_subquestions = list(r.get("neutral_subquestions", []))
        for p in r.get("premise_check", []):
            if str(p.get("established", "")).lower() in ("no", "unclear"):
                self.issue(raised_by=agent, stage="frame", category="framing",
                           severity="RED" if str(p.get("established")).lower() == "no" else "YELLOW",
                           description=f"Premise not established: {p.get('premise')} {p.get('note', '')}".strip())
        self.out("03_framing.json", r)

    def stage_challenge_framing(self):
        agent = self.agent("framing_challenger")
        r = self.call("framing_challenger", agent, "", self.available(), "challenge_framing")
        for lp in r.get("loaded_premises", []):
            self.issue(raised_by=agent, stage="challenge_framing", category="framing",
                       severity=lp.get("severity", "YELLOW"),
                       description=f"Loaded premise: {lp.get('premise')} - {lp.get('why_loaded', '')}")
        self.state.neutral_subquestions += [q for q in r.get("missing_subquestions", [])
                                            if q not in self.state.neutral_subquestions]
        self.state.framing.setdefault("hypotheses", [])
        for h in r.get("missing_hypotheses", []):
            self.state.framing["hypotheses"].append({**h, "added_by": agent})
        self.out("03b_framing_challenge.json", r)

    def _tracks(self, role: str, stage: str):
        jobs = [(a, role, a, f"{stage}-it{self.state.iteration}-{role}-{a}",
                 build_input(self.cfg, role, self.available())) for a in self.state.assignments[role]]
        results = self.runner.call_many(jobs, stage)
        for agent, r in results.items():
            self.state.track_outputs[f"{role}:{agent}"] = {k: v for k, v in r.items() if k != "candidate_claims"}
            idmap = {}
            for s in r.get("sources", []):
                idmap[s.get("source_id")] = self.register_source(s, agent)
            for c in r.get("candidate_claims", []):
                c = dict(c)
                c["author"] = agent
                for e in c.get("evidence", []):
                    e["source_id"] = idmap.get(e.get("source_id"), e.get("source_id"))
                    e["proposed_by"] = agent
                self.candidates.append(c)
        (self.dir / "04_independent_tracks").mkdir(exist_ok=True)
        for agent, r in results.items():
            self.out(f"04_independent_tracks/{role}_{agent}.json", r)

    def stage_research(self):
        self._tracks("researcher", "research")

    def stage_analysis(self):
        self._tracks("analyst", "analysis")

    def stage_register(self):
        agent = self.agent("registrar")
        r = self.call("registrar", agent, "", self.available(
            candidate_claims=self.candidates, sources=[source_view(s) for s in self.state.sources.values()],
            track_outputs=self.state.track_outputs), "register")
        cand_text = {c["text"].strip().lower(): c for c in self.candidates}
        for d in r.get("claims", []):
            d = dict(d)
            d.setdefault("claim_id", self.state.next_claim_id())
            if d["claim_id"] in self.state.claims:
                d["claim_id"] = self.state.next_claim_id()
            match = cand_text.get(d.get("text", "").strip().lower())
            if not d.get("author") or d["author"] not in self.cfg.agents:
                d["author"] = match["author"] if match else agent
            claim = Claim.from_dict(d)
            if not match and not any(d.get("text", "").strip().lower() in t or t in d.get("text", "").strip().lower()
                                     for t in cand_text):
                self.issue(raised_by="system", stage="register", category="synthesis", severity="YELLOW",
                           claim_ids=[claim.claim_id], key=f"registrar-new:{claim.claim_id}",
                           description=f"Registrar ({agent}) introduced a claim not proposed by any track.")
            # approved wording may never be stronger than the claim as proposed
            if claim.approved_wording:
                found = [f for f in strength.compare(claim.text, claim.approved_wording, self.cfg.strength, claim.claim_type)
                         if f in strength.STRENGTH_CODES]
                if found:
                    claim.log(f"approved wording rejected ({found}); reverted to proposed text")
                    claim.approved_wording = claim.text
            claim.log(f"registered by {agent}; author {claim.author}")
            self.state.claims[claim.claim_id] = claim
        self.out("05_claim_register_initial.json", {k: asdict(v) for k, v in self.state.claims.items()})

    def stage_verify(self):
        report = verify.verify_claims(self.state, self.store, self.data, self.cfg.quality_gates)
        live_keys = set()
        for rec in report:
            c = self.state.claims[rec["claim_id"]]
            if c.importance not in ("CRITICAL", "MATERIAL") or c.status == "REJECTED":
                continue
            problems = list(rec["flags"]) + [f"QUOTE_{q['result']}:{q['source_id']}" for q in rec["quotes"]
                                            if q["result"] in ("NOT_FOUND", "SOURCE_UNAVAILABLE")] \
                       + [f"DATA_{n['result']}:{n['series']}" for n in rec["numbers"]
                          if n["result"] in ("MISMATCH", "DERIVED_MISMATCH")]
            for p in problems:
                key = f"verify:{c.claim_id}:{p}"
                live_keys.add(key)
                cat = "numeric" if p.startswith(("NUMBER", "DATA")) else "source_gap" if p.startswith(("QUOTE", "UNKNOWN", "OUTDATED")) else "factual"
                self.issue(key=key, raised_by="system", stage="verify", category=cat,
                           severity="RED" if c.importance == "CRITICAL" else "YELLOW", claim_ids=[c.claim_id],
                           description=f"Mechanical check on {c.claim_id}: {p}")
        for i in self.state.issues:
            if i.key.startswith("verify:") and i.key not in live_keys and i.status != "RESOLVED":
                i.status, i.resolution_note = "RESOLVED", "mechanical check now passes"
        self.out("06_source_register.json", {k: asdict(v) for k, v in self.state.sources.items()})
        self.out(f"07_mechanical_verification_it{self.state.iteration}.json", report)

    def _per_claim(self, role: str, claims: list[Claim]) -> dict[str, list[Claim]]:
        groups: dict[str, list[Claim]] = {}
        for c in claims:
            agents = roles.for_claim(self.cfg, role, self.state.assignments, self.permitted, c.author)
            if not agents:
                if "SELF_CERT_UNAVOIDABLE" not in c.flags:
                    c.flags.append("SELF_CERT_UNAVOIDABLE")
                continue
            for a in agents:
                groups.setdefault(a, []).append(c)
        return groups

    def stage_audit(self, only: list[str] | None = None):
        claims = [c for c in self.state.claims.values() if c.status != "REJECTED" and (not only or c.claim_id in only)]
        groups = self._per_claim("source_auditor", claims)
        results = {}
        for agent, cl in groups.items():
            cited = {e.source_id for c in cl for e in c.evidence}
            results[agent] = (cl, self.call("source_auditor", agent, "-".join(c.claim_id for c in cl)[:60], self.available(
                claims_to_audit=[claim_view(c) for c in cl],
                sources=[source_view(self.state.sources[s]) for s in cited if s in self.state.sources]), "audit"))
        thr = self.cfg.quality_gates["quote_match_threshold"]
        new_evidence = False
        for agent, (cl, r) in results.items():
            ids = {c.claim_id for c in cl}
            for a in r.get("audited_claims", []):
                cid = a.get("claim_id")
                if cid not in ids:
                    continue
                claim = self.state.claims[cid]
                if a.get("source_id") not in self.state.sources and a.get("url"):
                    a["source_id"] = self.register_source({"title": a.get("source_title", a["url"]), "url": a["url"],
                                                           "authority_grade": a.get("authority_grade", "")}, agent)
                res = verify.check_auditor_excerpt(self.state, self.store, claim, agent, a, thr)
                claim.audit[agent] = {**{k: a.get(k) for k in ("source_id", "excerpt", "locator", "note", "recommended_wording")}, **res}
                if res["status"] in ("VERIFIED", "PARTIALLY_VERIFIED") and a.get("excerpt") and \
                        not any(e.excerpt == a["excerpt"] for e in claim.evidence):
                    claim.evidence.append(Evidence(source_id=a["source_id"], excerpt=a["excerpt"],
                                                   locator=a.get("locator", ""), proposed_by=agent))
                    new_evidence = True
                if a.get("wording_stronger_than_source"):
                    self.issue(key=f"audit-strong:{agent}:{cid}", raised_by=agent, stage="audit", category="factual",
                               severity="RED" if claim.importance == "CRITICAL" else "YELLOW", claim_ids=[cid],
                               description=f"Wording of {cid} is stronger than its source.",
                               proposed_resolution=a.get("recommended_wording", ""))
                if res["status"] in ("CONTRADICTED", "OUTDATED"):
                    self.issue(key=f"audit-status:{agent}:{cid}", raised_by=agent, stage="audit", category="factual",
                               severity="RED" if claim.importance in ("CRITICAL", "MATERIAL") else "YELLOW",
                               claim_ids=[cid], description=f"Auditor status {res['status']} for {cid}: {a.get('note', '')}")
        if new_evidence:
            self.stage_verify()
        self.out(f"08_source_audit_it{self.state.iteration}.json",
                 {cid: c.audit for cid, c in self.state.claims.items()})

    def stage_grade(self, only: list[str] | None = None):
        claims = [c for c in self.state.claims.values() if c.status != "REJECTED" and (not only or c.claim_id in only)]
        groups = self._per_claim("grader", claims)
        for agent, cl in groups.items():
            cited = {e.source_id for c in cl for e in c.evidence}
            r = self.call("grader", agent, "-".join(c.claim_id for c in cl)[:60], self.available(
                claims_to_grade=[claim_view(c) for c in cl],
                sources=[source_view(self.state.sources[s]) for s in cited if s in self.state.sources],
                grading_scale=self.cfg.taxonomy), "grade")
            ids = {c.claim_id for c in cl}
            for g in r.get("grades", []):
                if g.get("claim_id") in ids:
                    self.state.claims[g["claim_id"]].grades[agent] = {k: g.get(k) for k in ("S", "E", "C")}
        notches = self.cfg.quality_gates["grade_disagreement_notches"]
        for c in claims:
            if c.spread("E") >= notches or c.spread("C") >= notches:
                self.issue(key=f"grade-spread:{c.claim_id}", raised_by="system", stage="grade", category="grading",
                           severity="YELLOW", claim_ids=[c.claim_id],
                           description=f"Graders disagree on {c.claim_id}: {c.grades}. Conservative grade used.")
        gate.update_statuses(self.state, self.cfg)
        self.out(f"09_grades_it{self.state.iteration}.json", {cid: {"grades": c.grades, "status": c.status}
                                                              for cid, c in self.state.claims.items()})

    def _review(self, agent: str, stage: str):
        r = self.call("adversarial_reviewer", agent, "", self.available(
            claim_register=[claim_view(c) for c in self.state.claims.values()],
            sources=[source_view(s) for s in self.state.sources.values()],
            track_outputs=self.state.track_outputs,
            issues_so_far=[{"issue_id": i.issue_id, "description": i.description, "status": i.status}
                           for i in self.state.issues]), stage)
        for it in r.get("issues", []):
            self.issue(raised_by=agent, stage=stage, category=it.get("category", "analytical"),
                       severity=it.get("severity", "YELLOW"), claim_ids=it.get("claim_ids", []),
                       description=it.get("description", ""), proposed_resolution=it.get("proposed_resolution", ""))
        if not r.get("would_sign_off", False):
            self.state.notes.append(f"{agent} would not sign off: {r.get('overall', '')}")
        self.out(f"10_review_{stage}_{agent}.json", r)

    def stage_review(self):
        self._review(self.agent("adversarial_reviewer"), "review")

    def stage_review_second(self):
        first = self.agent("adversarial_reviewer")
        banned = {self.cfg.family(first)} | {self.cfg.family(self.agent(r)) for r in ("synthesizer", "drafter", "registrar")}
        for a in self.cfg.roles["adversarial_reviewer"]["prefer"] + list(self.cfg.agents):
            if a in self.permitted and self.cfg.family(a) not in banned:
                return self._review(a, "review_second")
        self.state.notes.append("second independent review impossible with permitted agents")

    def stage_omissions(self):
        agent = self.agent("omission_auditor")
        r = self.call("omission_auditor", agent, "", self.available(
            coverage_checklist=coverage.checklist(self.cfg, self.state.document_type),
            claim_register=[claim_view(c, detail=False) for c in self.state.claims.values()]), "omissions")
        coverage.apply(self.state, self.cfg, agent, r)
        self.out("10c_coverage.json", self.state.coverage)

    def stage_synthesize(self):
        agent = self.agent("synthesizer")
        open_issues = [{"issue_id": i.issue_id, "raised_by": i.raised_by, "category": i.category, "severity": i.severity,
                        "claim_ids": i.claim_ids, "description": i.description, "proposed_resolution": i.proposed_resolution}
                       for i in self.state.issues if i.status == "OPEN" and i.severity in ("RED", "YELLOW")]
        r = self.call("synthesizer", agent, "", self.available(
            claim_register=[claim_view(c) for c in self.state.claims.values()],
            sources=[source_view(s) for s in self.state.sources.values()],
            issues_for_disposition=open_issues, track_outputs=self.state.track_outputs), "synthesize")
        self.state.synthesis = r
        adjudication.record_dispositions(self.state, agent, r.get("dispositions", []))
        for cid in r.get("findings", {}).get("rejected", []):
            if cid in self.state.claims:
                self.state.claims[cid].status = "REJECTED"
                self.state.claims[cid].log(f"rejected by synthesizer {agent}")
        self._close_moot_issues()
        for k in ("confirmed", "qualified"):
            for cid in r.get("findings", {}).get(k, []):
                c = self.state.claims.get(cid)
                if c is None or c.status not in gate.APPROVED:
                    self.issue(key=f"synth-relies:{cid}", raised_by="system", stage="synthesize", category="synthesis",
                               severity="RED", claim_ids=[cid],
                               description=f"Synthesis lists {cid} as {k} but the register status is "
                                           f"{c.status if c else 'MISSING'}.")
        self.out("11_synthesis.json", r)

    def stage_adjudicate(self):
        adjudication.close_system_rejections(self.state)
        synth = self.agent("synthesizer")
        for issue in adjudication.needs_rebuttal(self.state):
            critic = issue.raised_by
            if critic not in self.permitted:
                issue.status = "HUMAN_REQUIRED"
                continue
            ctx = self.available(disputed_issue=asdict(issue),
                                 relevant_claims=[claim_view(self.state.claims[c]) for c in issue.claim_ids if c in self.state.claims],
                                 sources=[source_view(s) for s in self.state.sources.values()])
            rb = self.call("critic_rebuttal", critic, issue.issue_id, ctx, "adjudicate", prompt_role="critic_rebuttal")
            adjudication.apply_rebuttal(issue, critic, rb)
            if issue.status == "RESOLVED":
                continue
            banned = {self.cfg.family(critic), self.cfg.family(synth)}
            judge = next((a for a in self.cfg.roles["adjudicator"]["prefer"] + list(self.cfg.agents)
                          if a in self.permitted and self.cfg.family(a) not in banned), None)
            if judge is None:
                issue.status = "HUMAN_REQUIRED"
                continue
            ru = self.call("adjudicator", judge, issue.issue_id, ctx, "adjudicate")
            adjudication.apply_ruling(issue, judge, ru)
        self.out("12_issues.json", [asdict(i) for i in self.state.issues])

    def _close_moot_issues(self):
        """Issues about rejected claims are moot; 'synthesis relies on X' closes once X is approved."""
        for i in self.state.issues:
            if i.status == "RESOLVED" or not i.claim_ids:
                continue
            claims = [self.state.claims.get(c) for c in i.claim_ids]
            if all(c is not None and c.status == "REJECTED" for c in claims):
                i.status, i.resolution_note = "RESOLVED", "claim(s) rejected; nothing relies on them"
            elif i.key.startswith("synth-relies:") and all(c is not None and c.status in gate.APPROVED for c in claims):
                i.status, i.resolution_note = "RESOLVED", "claim now approved by the register"

    # ------------------------------------------------------- gate + iterate
    def _targeted_cycle(self) -> bool:
        """Route each open, accepted issue to the roles in routing.yaml. Returns True if anything was sent."""
        routes = self.cfg.routing["routes"]
        sent, touched = False, set()
        for issue in [i for i in self.state.issues if i.status == "OPEN" and i.severity in ("RED", "YELLOW")]:
            if issue.disposition.get("decision") == "REJECTED" and issue.raised_by != "system":
                continue      # handled by adjudication
            claims = [self.state.claims[c] for c in issue.claim_ids if c in self.state.claims]
            for role in routes.get(issue.category, ["synthesizer"]):
                if role in ("source_auditor", "grader") and claims:
                    touched.update(c.claim_id for c in claims)
                    continue  # re-run below with per-claim independence
                agent = self.state.assignments[role][0]
                r = self.call(role, agent, issue.issue_id, self.available(
                    targeted_claims=[claim_view(c) for c in claims],
                    sources=[source_view(s) for s in self.state.sources.values()],
                    issue=asdict(issue)), "targeted", prompt_role="targeted")
                sent = True
                for u in r.get("updates", []):
                    c = self.state.claims.get(u.get("claim_id"))
                    if c is None:
                        continue
                    idmap = {s.get("source_id"): self.register_source(s, agent) for s in u.get("new_sources", [])}
                    for e in u.get("new_evidence", []):
                        fields_ = {k: v for k, v in e.items() if k in Evidence.__dataclass_fields__}
                        fields_["source_id"] = idmap.get(fields_.get("source_id"), fields_.get("source_id", ""))
                        fields_["proposed_by"] = fields_.get("proposed_by") or agent
                        fields_["quote_check"], fields_["match_score"] = "NOT_CHECKED", 0.0
                        c.evidence.append(Evidence(**fields_))
                    if u.get("proposed_wording"):
                        bad = [f for f in strength.compare(c.wording(), u["proposed_wording"], self.cfg.strength, c.claim_type)
                               if strength.SEVERITY.get(f)]
                        if bad and not u.get("new_evidence"):
                            c.log(f"{agent} proposed stronger wording without new evidence ({bad}); refused")
                        else:
                            c.log(f"wording revised by {agent}")
                            c.approved_wording = u["proposed_wording"]
                    c.alternatives += [a for a in u.get("alternatives", []) if a not in c.alternatives]
                    touched.add(c.claim_id)
                # An issue with no claims is resolved only by an explicit, general response to it.
                general = [u for u in r.get("updates", []) if not u.get("claim_id") and u.get("note")]
                if not claims and general:
                    issue.status = "RESOLVED"
                    issue.resolution_note = f"addressed by {agent}: " + "; ".join(u["note"] for u in general)
        if touched:
            self.stage_verify()
            self.stage_audit(only=sorted(touched))
            self.stage_grade(only=sorted(touched))
            sent = True
        # model-raised issues on claims resolve when their claims now pass
        for issue in self.state.issues:
            known = [self.state.claims[c] for c in issue.claim_ids if c in self.state.claims]
            if issue.status == "OPEN" and issue.raised_by != "system" and known and \
                    {c.claim_id for c in known} <= touched and \
                    all(c.status in gate.APPROVED and not gate.claim_failures(c, self.state, self.cfg) for c in known):
                issue.status, issue.resolution_note = "RESOLVED", "claims revised and independently re-verified"
        self._close_moot_issues()
        return sent

    def _gate_loop(self, stage: str):
        maxc = self.cfg.quality_gates["iteration"]["max_substantive_cycles"]
        res = gate.evaluate(self.state, self.cfg, stage)
        cycles = 1
        while res["status"] != "GREEN" and cycles < maxc:
            cycles += 1
            self.state.iteration += 1
            if stage == "final_gate":
                if not self._redraft_flagged():
                    break
            elif not self._targeted_cycle():
                break
            res = gate.evaluate(self.state, self.cfg, stage)
        res["cycles"] = cycles
        if res["status"] != "GREEN" and cycles >= maxc:
            self.state.notes.append(f"{stage}: stopped after {maxc} cycles - material issues remain unresolved")
        self.out(f"13_gate_{stage}.json", res)
        return res

    def stage_gate(self):
        res = self._gate_loop("gate")
        if res["status"] == "RED" and "draft" in self.cfg.stages_for_level(self.state.level):
            raise StopRun("Analytical core is RED: drafting blocked. See dashboard for the blocking items.")

    # -------------------------------------------------------------- drafting
    def _drafting_inputs(self) -> dict:
        approved = [claim_view(c, detail=False) for c in self.state.claims.values() if c.status in gate.APPROVED]
        dna = [{"claim_id": c.claim_id, "text": c.text, "status": c.status} for c in self.state.claims.values()
               if c.status not in gate.APPROVED]
        return {"approved_claims": approved, "do_not_assert": dna, "synthesis": self.state.synthesis,
                "drafting_standard": self.drafting_standard}

    def stage_draft(self):
        r = self.call("drafter", self.agent("drafter"), "", self.available(**self._drafting_inputs()), "draft")
        self.state.drafts["v1"] = r["draft_markdown"]
        self.out("14_draft_v1.md", r["draft_markdown"])

    def stage_draft_review(self):
        draft = self.state.drafts["v1"]
        scores = {}
        for role in ("substance_reviewer", "structure_reviewer", "editorial_reviewer"):
            agent = self.agent(role)
            r = self.call(role, agent, "", self.available(draft=draft, **self._drafting_inputs()), "draft_review")
            for it in r.get("issues", []):
                self.issue(raised_by=agent, stage="draft_review", category=it.get("category", "drafting"),
                           severity=it.get("severity", "YELLOW"), claim_ids=it.get("claim_ids", []),
                           description=it.get("description", ""), proposed_resolution=it.get("proposed_resolution", ""))
            if "score" in r:
                try:
                    scores[f"{role}:{agent}"] = float(r["score"])
                except (TypeError, ValueError):
                    pass
            (self.dir / "15_draft_reviews").mkdir(exist_ok=True)
            self.out(f"15_draft_reviews/{role}_{agent}.json", r)
        self.state.drafts["review_scores"] = scores

    def stage_revise(self):
        drafter = self.agent("drafter")
        draft_issues = [{"issue_id": i.issue_id, "raised_by": i.raised_by, "severity": i.severity, "claim_ids": i.claim_ids,
                         "description": i.description, "proposed_resolution": i.proposed_resolution}
                        for i in self.state.issues if i.stage == "draft_review" and i.status == "OPEN"]
        r = self.call("drafter", drafter, "", self.available(draft=self.state.drafts["v1"],
                      issues_for_disposition=draft_issues, **self._drafting_inputs()), "revise", prompt_role="reviser")
        adjudication.record_dispositions(self.state, drafter, r.get("dispositions", []))
        for i in self.state.issues:
            if i.stage == "draft_review" and i.disposition.get("decision") in ("ACCEPTED", "PARTIAL"):
                i.status, i.resolution_note = "RESOLVED", "applied in revision (verified by final claim audit)"
        self.state.drafts["final"] = r["draft_markdown"]
        self.stage_adjudicate()
        self.out("16_draft_final.md", r["draft_markdown"])

    def stage_final_audit(self):
        self.state.final_audit = strength.audit_draft(self.state.drafts["final"], self.state.claims, self.cfg.strength)
        self.out(f"17_final_claim_audit_it{self.state.iteration}.json", self.state.final_audit)

    def _redraft_flagged(self) -> bool:
        flagged = [r for r in self.state.final_audit if r["red_codes"]]
        if not flagged:
            return False
        issues = [{"issue_id": f"AUDIT-{r['index']}", "severity": "RED", "claim_ids": r["tags"],
                   "description": f"Sentence '{r['text']}' failed the claim audit: {r['findings']}. Restore the approved "
                                  f"wording or tag it to an approved claim; do not add new claims.",
                   "proposed_resolution": " ".join(self.state.claims[t].wording() for t in r["tags"] if t in self.state.claims)}
                  for r in flagged]
        r = self.call("drafter", self.agent("drafter"), "fix", self.available(
            draft=self.state.drafts["final"], issues_for_disposition=issues, **self._drafting_inputs()),
            "final_fix", prompt_role="reviser")
        self.state.drafts["final"] = r["draft_markdown"]
        self.out("16_draft_final.md", r["draft_markdown"])
        self.stage_final_audit()
        return True

    def stage_final_gate(self):
        self._gate_loop("final_gate")
