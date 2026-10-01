"""Human decision dashboard: the compact view the responsible economist signs off on."""
from __future__ import annotations

import json
from collections import Counter

from .gate import APPROVED, claim_failures


def write_dashboard(p) -> None:
    st, cfg = p.state, p.cfg
    last = st.gates.get("final_gate") or st.gates.get("gate") or {}
    claims = list(st.claims.values())
    lines = [f"# Review Dashboard — {st.run_id}", "",
             f"**Question:** {st.research_question}  ",
             f"**Document type:** {st.document_type} · **Level:** {st.level} "
             f"({cfg.routing['levels'][st.level]['label']}) · **Confidentiality:** {st.confidentiality} · **Mode:** {st.mode}", ""]
    if last:
        lines += [f"## Status: {last['status']}  (score {last['score']}/100, gate '{last['stage']}')", ""]
    else:
        lines += ["## Status: NOT EVALUATED (run stopped before the gate)", ""]
    for n in st.notes:
        lines.append(f"> {n}")
    lines += ["", "**FINAL HUMAN REVIEW REQUIRED: YES**" if last.get("human_signoff_required", True) else "", ""]

    if last.get("automatic_reds"):
        lines += ["### Blocking items (automatic RED)", "", "| Code | Where | Why |", "|---|---|---|"]
        for r in last["automatic_reds"]:
            where = r.get("claim_id") or (f"sentence {r['sentence']}" if "sentence" in r else r.get("issue_id") or r.get("coverage", ""))
            lines.append(f"| {r['code']} | {where} | {_esc(r['why'])} |")
        lines.append("")
    if last.get("yellow_items"):
        lines += ["### Items needing attention (YELLOW)", ""]
        for y in last["yellow_items"][:40]:
            where = y.get("claim_id") or y.get("issue_id") or f"sentence {y.get('sentence')}"
            lines.append(f"- **{where}**: {_esc(y['why'])}")
        lines.append("")

    if last.get("dimensions"):
        lines += ["### Score by dimension", "", "| Dimension | Score | Basis |", "|---|---|---|"]
        for k, v in last["dimensions"].items():
            lines.append(f"| {k} | {'n/a' if v['score'] is None else v['score']} | {v['kind']} |")
        lines.append("")

    by_imp = {imp: [c for c in claims if c.importance == imp] for imp in ("CRITICAL", "MATERIAL")}
    lines += ["### Claims", ""]
    for imp, cl in by_imp.items():
        cnt = Counter(c.status for c in cl)
        lines.append(f"- **{imp}: {len(cl)}** — " + ", ".join(f"{k}: {v}" for k, v in sorted(cnt.items())))
    causal = [c for c in claims if c.claim_type == "CAU"]
    if causal:
        lines.append("- **Causal claims by grade:** " + ", ".join(
            f"{k}: {v}" for k, v in sorted(Counter(c.consensus("C") or "ungraded" for c in causal).items())))
    cited = {e.source_id for c in claims for e in c.evidence}
    srcs = [st.sources[s] for s in cited if s in st.sources]
    if srcs:
        lines.append("- **Sources by authority:** " + ", ".join(
            f"{k}: {v}" for k, v in sorted(Counter(s.authority_grade or "ungraded" for s in srcs).items(), reverse=True)))
        lines.append("- **Source retrieval:** " + ", ".join(f"{k}: {v}" for k, v in Counter(s.status for s in srcs).items()))
    strengthened = [r for r in st.final_audit if r["red_codes"]]
    lines += [f"- **Claim-strengthening / unmapped sentences in final draft:** {len(strengthened)}", ""]

    lines += ["### Claim register", "", "| ID | Type | Imp. | Status | S/E/C | Evidence check | Approved wording | Open problems |",
              "|---|---|---|---|---|---|---|---|"]
    for c in claims:
        sec = "/".join(x or "–" for x in (c.consensus("S"), c.consensus("E"), c.consensus("C")))
        ev = ", ".join(sorted({e.quote_check for e in c.evidence})) or "none"
        probs = ", ".join(claim_failures(c, st, cfg)) if c.status != "REJECTED" else "rejected"
        lines.append(f"| {c.claim_id} | {c.claim_type} | {c.importance[:4]} | {c.status} | {sec} | {ev} | "
                     f"{_esc(c.wording())} | {_esc(probs)} |")
    lines.append("")

    unresolved = [i for i in st.issues if i.status != "RESOLVED" and i.severity in ("RED", "YELLOW")]
    lines += [f"### Unresolved issues ({len(unresolved)})", ""]
    for i in unresolved:
        disp = i.disposition.get("decision", "no disposition")
        extra = f"; critic {i.rebuttal['verdict']}" if i.rebuttal else ""
        extra += f"; ruling {i.ruling['verdict']} by {i.ruling['by']}" if i.ruling else ""
        lines.append(f"- **{i.issue_id}** [{i.severity}/{i.category}] {i.status} — raised by {i.raised_by}: "
                     f"{_esc(i.description)} _(disposition: {disp}{extra})_")
    if st.coverage:
        lines += ["", "### Coverage map", "", "| Item | Status | Note |", "|---|---|---|"]
        for k, v in st.coverage.items():
            lines.append(f"| {k} {'(mandatory)' if v.get('mandatory') else ''} — {v.get('label', '')} | {v.get('status')} | {_esc(v.get('note', ''))} |")
    if st.reliability:
        lines += ["", "### Agent reliability this run", "", "| Agent | Counters |", "|---|---|"]
        for a, ctr in st.reliability.items():
            lines.append(f"| {a} | {', '.join(f'{k}: {v}' for k, v in ctr.items())} |")
    lines += ["", "### Role assignments", ""]
    for role, agents in st.assignments.items():
        lines.append(f"- {role}: {', '.join(agents)}")
    lines += ["", "---", "", "## Human sign-off", "",
              "- [ ] I have reviewed every blocking and unresolved item above.",
              "- [ ] I accept the remaining uncertainty as stated in the claim register.",
              "", "Name: ____________________  Date: __________  Decision: APPROVE / RETURN", ""]
    p.out("19_dashboard.md", "\n".join(lines))
    p.out("18_final_audit.json", {
        "run_id": st.run_id, "status": last.get("status"), "score": last.get("score"),
        "automatic_reds": last.get("automatic_reds", []),
        "claims": {c.claim_id: {"status": c.status, "approved_wording": c.wording(),
                                "grades": {"S": c.consensus("S"), "E": c.consensus("E"), "C": c.consensus("C")},
                                "failures": claim_failures(c, st, cfg)} for c in claims},
        "sentence_audit": st.final_audit, "approved_claim_ids": [c.claim_id for c in claims if c.status in APPROVED]})


def _esc(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")
