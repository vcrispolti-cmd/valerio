"""Deterministic quality gate.

Principle: the product may not RELY on a failing claim. A claim fails if any
automatic-RED condition applies to it. A failing CRITICAL claim, or any
failing claim the thesis or draft relies on, makes the gate RED. A failing
MATERIAL claim that nothing relies on is kept in the register as UNRESOLVED
and makes the gate at most YELLOW (targeted iteration).
"""
from __future__ import annotations

from .model import grade_value
from .strength import ladder_level

APPROVED = ("VERIFIED", "QUALIFIED")
# Staff judgments rest on other claims (depends_on), not on an external excerpt.
JUDGMENT_TYPES = ("REC", "INT", "RSK", "FOR")
WEIGHT = {"CRITICAL": 3, "MATERIAL": 2, "SUPPORTING": 1, "MINOR": 0.5}


def claim_failures(claim, state, cfg) -> list[str]:
    qg = cfg.quality_gates
    codes = []
    imp = claim.importance
    verified_ev = [e for e in claim.evidence
                   if e.quote_check in ("FOUND", "FOUND_APPROX") and e.relation != "contradicts"]
    S, E, C = claim.consensus("S"), claim.consensus("E"), claim.consensus("C")
    th = qg["claim_thresholds"].get(imp)
    if imp == "CRITICAL" and grade_value(E) <= 1:
        codes.append("RED-1")
    if th and (grade_value(S) < grade_value(th["source_authority_min"])
               or grade_value(E) < grade_value(th["evidence_support_min"])):
        codes.append("BELOW_THRESHOLD")
    if any(f.startswith("NUMBER_NOT_IN_EVIDENCE") for f in claim.flags) or \
            any(n.data_check in ("MISMATCH", "DERIVED_MISMATCH") for n in claim.numbers):
        codes.append("RED-2")
    judgment = claim.claim_type in JUDGMENT_TYPES
    if any(f.startswith("UNKNOWN_SOURCE") for f in claim.flags):
        codes.append("RED-3")
    elif imp in ("CRITICAL", "MATERIAL") and not verified_ev and not (judgment and claim.depends_on):
        codes.append("RED-3")
    if claim.claim_type in ("CAU", "INT", "REL", "REC"):
        lvl = ladder_level(claim.wording(), cfg.strength["ladders"]["causal"])
        need = qg["causal_wording_requirements"].get(lvl) if lvl else None
        if need and grade_value(C) < grade_value(need):
            codes.append("RED-4")
    if judgment:
        for dep in claim.depends_on:
            d = state.claims.get(dep)
            if d is None or d.status not in APPROVED:
                codes.append("RED-5")
                break
    if any(f.startswith("UNRESOLVED_CONTRADICTION") for f in claim.flags):
        codes.append("RED-6")
    if any(f.startswith("OUTDATED") for f in claim.flags):
        codes.append("RED-10")
    if "SELF_CERT_UNAVOIDABLE" in claim.flags:
        codes.append("RED-12")
    if any(a.get("status") in ("CONTRADICTED",) for a in claim.audit.values()):
        codes.append("AUDIT_CONTRADICTED")
    if imp in ("CRITICAL", "MATERIAL") and claim.spread("E") >= qg["grade_disagreement_notches"]:
        codes.append("GRADE_DISAGREEMENT")
    return codes


def update_statuses(state, cfg) -> None:
    """Set each claim's status from evidence, grades and failures (never from a model's say-so)."""
    for claim in state.claims.values():
        if claim.status == "REJECTED":
            continue
        fails = claim_failures(claim, state, cfg)
        blocking = [f for f in fails if f != "GRADE_DISAGREEMENT"]
        verified_ev = any(e.quote_check in ("FOUND", "FOUND_APPROX") for e in claim.evidence) or \
            (claim.claim_type in JUDGMENT_TYPES and claim.depends_on)
        if blocking or not verified_ev and claim.importance in ("CRITICAL", "MATERIAL"):
            new = "UNRESOLVED"
        elif claim.approved_wording and claim.approved_wording.strip() != claim.text.strip() or claim.qualifications \
                or any(a.get("status") == "PARTIALLY_VERIFIED" for a in claim.audit.values()) \
                or "GRADE_DISAGREEMENT" in fails:
            new = "QUALIFIED"
        else:
            new = "VERIFIED"
        if new != claim.status:
            claim.log(f"status {claim.status} -> {new} ({', '.join(fails) or 'checks passed'})")
            claim.status = new


def relied_upon(state) -> set[str]:
    ids = set()
    f = state.synthesis.get("findings", {}) if state.synthesis else {}
    for k in ("confirmed", "qualified"):
        ids.update(f.get(k, []))
    for pi in (state.synthesis or {}).get("policy_implications", []):
        ids.update(pi.get("claim_ids", []))
    for rec in state.final_audit:
        ids.update(rec.get("tags", []))
    return ids


def evaluate(state, cfg, stage: str) -> dict:
    qg = cfg.quality_gates
    reds, yellows = [], []
    relied = relied_upon(state)
    for claim in state.claims.values():
        if claim.status == "REJECTED":
            if claim.claim_id in relied:
                reds.append({"code": "RED-7", "claim_id": claim.claim_id, "why": "rejected claim is relied upon"})
            continue
        fails = claim_failures(claim, state, cfg)
        red_codes = [f for f in fails if f.startswith("RED-")]
        other = [f for f in fails if not f.startswith("RED-")]
        if red_codes and (claim.importance == "CRITICAL" or claim.claim_id in relied):
            for code in red_codes:
                reds.append({"code": code, "claim_id": claim.claim_id, "why": qg["automatic_red_conditions"][code]})
        elif (red_codes or "BELOW_THRESHOLD" in other) and claim.claim_id in relied:
            reds.append({"code": "RED-5" if claim.claim_type == "REC" else "RED-1",
                         "claim_id": claim.claim_id, "why": "relied-upon claim below evidence threshold"})
        elif fails and claim.importance in ("CRITICAL", "MATERIAL"):
            yellows.append({"claim_id": claim.claim_id, "why": ", ".join(fails)})
    for rec in state.final_audit:
        for code in rec["red_codes"]:
            reds.append({"code": code, "sentence": rec["index"], "why": f"{', '.join(rec['findings'])}: {rec['text'][:120]}"})
        if not rec["red_codes"] and rec["findings"]:
            yellows.append({"sentence": rec["index"], "why": ", ".join(rec["findings"])})
    for issue in state.issues:
        if issue.severity == "RED" and issue.status != "RESOLVED":
            reds.append({"code": "RED-11", "issue_id": issue.issue_id, "why": issue.description[:160]})
        elif issue.severity in ("RED", "YELLOW") and issue.status != "RESOLVED":
            yellows.append({"issue_id": issue.issue_id, "why": issue.description[:160]})
    for item_id, item in state.coverage.items():
        if item.get("status") == "MISSING" and item.get("mandatory"):
            reds.append({"code": "RED-13", "coverage": item_id, "why": item.get("label", "")})

    dims = dimensions(state, cfg)
    score = weighted(dims, qg["score_weights"])
    if reds or score < qg["thresholds"]["yellow"]:
        status = "RED"
    elif score < qg["thresholds"]["green"] or yellows:
        status = "YELLOW"
    else:
        status = "GREEN"
    result = {"stage": stage, "status": status, "score": score, "dimensions": dims,
              "automatic_reds": reds, "yellow_items": yellows,
              "human_signoff_required": state.level >= qg["human_signoff_required_from_level"]}
    state.gates[stage] = result
    return result


def dimensions(state, cfg) -> dict:
    live = [c for c in state.claims.values() if c.status != "REJECTED"]
    d: dict[str, dict] = {}

    def put(name, value, kind="DETERMINISTIC"):
        d[name] = {"score": None if value is None else round(value), "kind": kind}

    tot = sum(WEIGHT[c.importance] for c in live) or 1
    put("evidence_integrity", 100 * sum(WEIGHT[c.importance] for c in live
                                        if not [f for f in claim_failures(c, state, cfg) if f != "GRADE_DISAGREEMENT"]) / tot if live else 0)
    cited = {e.source_id for c in live for e in c.evidence}
    srcs = [state.sources[s] for s in cited if s in state.sources]
    put("source_quality", 100 * sum((grade_value(s.authority_grade) / 5 if s.status == "CONFIRMED" else 0) for s in srcs)
        / len(srcs) if srcs else 0)
    causal = [c for c in live if c.claim_type in ("CAU", "INT", "REL")]
    open_analytic = sum(1 for i in state.issues if i.severity == "RED" and i.status != "RESOLVED"
                        and i.category in ("causal", "alternative", "analytical"))
    if causal:
        ok = sum(1 for c in causal if c.alternatives and "RED-4" not in claim_failures(c, state, cfg))
        put("analytical_validity", max(0.0, 100 * ok / len(causal) - 15 * open_analytic))
    else:
        put("analytical_validity", max(0.0, 100.0 - 15 * open_analytic))
    if state.final_audit:
        material = [r for r in state.final_audit if r["tags"] or r["findings"]]
        put("internal_consistency", 100 * sum(1 for r in material if not r["red_codes"]) / len(material) if material else 100)
    else:
        put("internal_consistency", None)
    scores = [v for v in state.drafts.get("review_scores", {}).values() if isinstance(v, (int, float))]
    put("imf_drafting_quality", sum(scores) / len(scores) if scores else None, "MODEL_JUDGED")
    raised = [i for i in state.issues if i.severity in ("RED", "YELLOW")]
    put("counterargument_robustness", 100 * sum(1 for i in raised if i.status == "RESOLVED") / len(raised) if raised else 100)
    mat = [c for c in live if c.importance in ("CRITICAL", "MATERIAL")]
    a1 = sum(1 for c in mat if any(e.quote_check in ("FOUND", "FOUND_APPROX") for e in c.evidence)) / len(mat) if mat else 1
    if state.final_audit:
        sents = [r for r in state.final_audit if r["tags"] or "UNMAPPED_MATERIAL" in r["findings"]]
        a2 = sum(1 for r in sents if r["tags"]) / len(sents) if sents else 1
        put("auditability", 100 * (a1 + a2) / 2)
    else:
        put("auditability", 100 * a1)
    return d


def weighted(dims: dict, weights: dict) -> int:
    used = {k: w for k, w in weights.items() if dims.get(k, {}).get("score") is not None}
    tot = sum(used.values())
    return round(sum(dims[k]["score"] * w for k, w in used.items()) / tot) if tot else 0
