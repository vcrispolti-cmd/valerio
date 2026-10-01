"""Disposition of critiques: the drafter/synthesizer cannot quietly dismiss them.

Flow for every RED or YELLOW issue:
  1. the synthesizer records ACCEPTED / PARTIAL / REJECTED with a rationale;
  2. ACCEPTED/PARTIAL -> routed for a targeted fix (iteration);
  3. REJECTED -> the critic who raised it sees the rationale and either
     WITHDRAWS (only if the rationale cites evidence that resolves it) or
     UPHOLDS;
  4. UPHELD -> an adjudicator from a third family rules FOR_CRITIC,
     FOR_SYNTHESIZER or ESCALATE; ESCALATE (or any unresolved RED) goes to
     the human as HUMAN_REQUIRED.
Majority voting is never used: the adjudicator rules on the evidence cited.
"""
from __future__ import annotations

from .model import now


def record_dispositions(state, synthesizer: str, dispositions: list[dict]) -> None:
    by_id = {d.get("issue_id"): d for d in dispositions}
    for issue in state.issues:
        if issue.status != "OPEN" or issue.severity not in ("RED", "YELLOW"):
            continue
        d = by_id.get(issue.issue_id)
        if not d:
            continue
        issue.disposition = {"decision": d.get("decision", "").upper(), "by": synthesizer,
                             "rationale": d.get("rationale", ""), "at": now()}


def needs_rebuttal(state) -> list:
    return [i for i in state.issues if i.status == "OPEN" and i.disposition.get("decision") == "REJECTED"
            and i.raised_by not in ("system", "") and not i.rebuttal]


def apply_rebuttal(issue, critic: str, reply: dict) -> None:
    verdict = reply.get("verdict", "UPHELD").upper()
    issue.rebuttal = {"verdict": verdict, "by": critic, "rationale": reply.get("rationale", "")}
    if verdict == "WITHDRAWN":
        issue.status = "RESOLVED"


def apply_ruling(issue, adjudicator: str, reply: dict) -> None:
    verdict = reply.get("verdict", "ESCALATE").upper()
    issue.ruling = {"verdict": verdict, "by": adjudicator, "rationale": reply.get("rationale", "")}
    if verdict == "FOR_SYNTHESIZER":
        issue.status = "RESOLVED"
    elif verdict == "FOR_CRITIC":
        issue.disposition["decision"] = "ACCEPTED_ON_RULING"      # must now be fixed
    else:
        issue.status = "HUMAN_REQUIRED"


def close_system_rejections(state) -> None:
    """A rejected system-raised issue (from code checks) cannot be argued away."""
    for i in state.issues:
        if i.raised_by == "system" and i.status == "OPEN" and i.disposition.get("decision") == "REJECTED":
            i.status = "HUMAN_REQUIRED"
