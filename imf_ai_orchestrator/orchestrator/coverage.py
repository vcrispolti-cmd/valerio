"""Omission audit: a coverage map checked by a model AND by code."""
from __future__ import annotations

APPROVED = ("VERIFIED", "QUALIFIED")


def checklist(cfg, document_type: str) -> list[dict]:
    return cfg.coverage.get(document_type) or cfg.coverage["analytical_question"]


def apply(state, cfg, auditor: str, reply: dict) -> None:
    items = {i["id"]: dict(i) for i in checklist(cfg, state.document_type)}
    reported = {r.get("id"): r for r in reply.get("items", [])}
    for item_id, item in items.items():
        r = reported.get(item_id, {})
        status = r.get("status", "MISSING")
        note = r.get("note", "")
        if status == "NOT_APPLICABLE" and not note:
            status, note = "MISSING", "marked not applicable without a reason"
        types = item.get("requires_claim_types")
        if types and status != "NOT_APPLICABLE":
            have = [c.claim_id for c in state.claims.values() if c.claim_type in types and c.status in APPROVED]
            if not have:
                status, note = "MISSING", (note + "; " if note else "") + f"no approved claim of type {types}"
        items[item_id].update({"status": status, "note": note, "claim_ids": r.get("claim_ids", []),
                               "checked_by": auditor})
    state.coverage = items
    for om in reply.get("additional_omissions", []):
        state.add_issue(raised_by=auditor, stage="omissions", category="coverage",
                        severity=om.get("severity", "YELLOW"), description=om.get("description", ""))
