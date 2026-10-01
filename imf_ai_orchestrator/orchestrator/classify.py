"""Task classification by rules, not by a model.

The level is max(requested level, rule-based minimum): the system may
escalate scrutiny but never lets anyone (human or model) downgrade below the
rule-based floor without editing config/routing.yaml.
"""
from __future__ import annotations

import re


def classify(cfg, question: str, document_type: str, requested: int) -> tuple[int, list[str]]:
    rules = cfg.routing["classification_rules"]
    basis = [f"requested level {requested}"]
    level = requested
    q = question.lower()
    for lvl, words in sorted(rules["keywords"].items()):
        hits = [w for w in words if re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", q)]
        if hits and lvl > level:
            level = lvl
            basis.append(f"keywords {hits} -> at least level {lvl}")
    dt_min = rules["document_types"].get(document_type)
    if dt_min is not None and dt_min > level:
        level = dt_min
        basis.append(f"document type '{document_type}' -> at least level {dt_min}")
    return level, basis
