"""Claim-strengthening detector and final draft audit (deterministic).

Compares each tagged draft sentence with the approved wording of the claim(s)
it cites, and flags any change that makes the sentence say more than the
register approved: causal, epistemic, probability, scope, precision,
attribution, number, date, unit and negation changes. Untagged sentences that
carry material content (numbers, dates, causal or certainty language) are
flagged as claims outside the register.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

TAG_RE = re.compile(r"\[(C\d{3,}(?:\s*,\s*C\d{3,})*)\]")
NUM_RE = re.compile(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
UNIT_TERMS = ["percent of gdp", "percentage points", "percentage point", "basis points", "percent",
              "billion", "million", "trillion", "per capita", "nominal", "real", "year-on-year", "annualized"]

# finding code -> RED condition (None = YELLOW only)
SEVERITY = {
    "CAUSAL_STRENGTHENED": "RED-8", "EPISTEMIC_STRENGTHENED": "RED-8", "PROBABILITY_STRENGTHENED": "RED-8",
    "SCOPE_WIDENED": "RED-8", "PRECISION_INFLATED": "RED-8", "ATTRIBUTION_CHANGED": "RED-8",
    "NUMBER_CHANGED": "RED-8", "DATE_CHANGED": "RED-8", "UNIT_CHANGED": "RED-8", "NEGATION_CHANGED": "RED-8",
    "UNMAPPED_MATERIAL": "RED-7", "TAG_TO_UNAPPROVED": "RED-7", "APPRAISAL_NEW_CLAIM": "RED-9",
    "INFLATION_TERM_ADDED": "RED-8", "REWORDED": None,
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("–", "-").replace("—", "-")).strip().lower()


def _has(text: str, phrase: str) -> bool:
    return re.search(r"(?<![\w'])" + re.escape(phrase.lower()) + r"(?![\w'])", text) is not None


def ladder_level(text: str, ladder: dict) -> int:
    """Strongest level present. Longer phrases are matched first and masked, so
    "appears to have contributed to" counts as a hedge, not as "contributed to"."""
    t = _norm(text)
    best = 0
    for phrase, lvl in sorted(((p.lower(), int(l)) for l, ps in ladder.items() for p in ps),
                              key=lambda x: -len(x[0])):
        pattern = r"(?<![\w'])" + re.escape(phrase) + r"(?![\w'])"
        if re.search(pattern, t):
            best = max(best, lvl)
            t = re.sub(pattern, " # ", t)
    return best

# Codes that mean "stronger than approved" (as opposed to content changes).
STRENGTH_CODES = ("CAUSAL_STRENGTHENED", "EPISTEMIC_STRENGTHENED", "PROBABILITY_STRENGTHENED",
                  "SCOPE_WIDENED", "PRECISION_INFLATED", "NEGATION_CHANGED", "ATTRIBUTION_CHANGED")


def _numbers(text: str) -> list[str]:
    t = YEAR_RE.sub(" ", text)
    return sorted(n.replace(",", "") for n in NUM_RE.findall(t))


def _years(text: str) -> list[str]:
    return sorted(YEAR_RE.findall(text))


def _units(text: str) -> set[str]:
    t, found = _norm(text), set()
    for u in UNIT_TERMS:
        if _has(t, u):
            found.add(u)
            t = t.replace(u, " ")
    return found


def _attribution(text: str, groups: dict) -> set[str]:
    t = _norm(text)
    return {g for g, phrases in groups.items() if any(_has(t, p) for p in phrases)}


def _negations(text: str, words: list[str]) -> int:
    t, count = _norm(text), 0
    for w in sorted(words, key=len, reverse=True):
        pattern = r"(?<![\w'])" + re.escape(w) + r"(?![\w'])"
        count += len(re.findall(pattern, t))
        t = re.sub(pattern, " # ", t)
    return count


def compare(approved: str, final: str, strength_cfg: dict, claim_type: str = "") -> list[str]:
    """Return finding codes for how `final` departs from `approved`."""
    lad = strength_cfg["ladders"]
    findings: list[str] = []
    a_c, f_c = ladder_level(approved, lad["causal"]), ladder_level(final, lad["causal"])
    if f_c > a_c and (a_c > 0 or claim_type == "CAU" or f_c >= 3):
        findings.append("CAUSAL_STRENGTHENED")      # stronger, or causal language added to a non-causal claim
    elif claim_type == "CAU" and 0 < a_c <= 4 and f_c == 0:
        findings.append("CAUSAL_STRENGTHENED")      # hedge dropped from a causal claim
    for name, code in (("epistemic", "EPISTEMIC_STRENGTHENED"), ("probability", "PROBABILITY_STRENGTHENED"),
                       ("scope", "SCOPE_WIDENED")):
        a, f = ladder_level(approved, lad[name]), ladder_level(final, lad[name])
        top = max(int(k) for k in lad[name])
        if f > a and (a > 0 or f == top):
            findings.append(code)
        elif name == "probability" and a in (1, 2) and f == 0 and claim_type in ("FOR", "RSK"):
            findings.append(code)                   # "could" dropped from a forecast or risk
    if ladder_level(approved, lad["precision"]) and not ladder_level(final, lad["precision"]) and _numbers(final):
        findings.append("PRECISION_INFLATED")
    if set(_numbers(final)) - set(_numbers(approved)):
        findings.append("NUMBER_CHANGED")
    if set(_years(final)) - set(_years(approved)):
        findings.append("DATE_CHANGED")
    if _units(final) - _units(approved):
        findings.append("UNIT_CHANGED")
    a_att, f_att = _attribution(approved, strength_cfg["attribution"]), _attribution(final, strength_cfg["attribution"])
    # Adding "staff assesses" to an unattributed claim is normal; anything else is a change of voice.
    if (a_att and f_att != a_att) or (not a_att and f_att - {"staff"}):
        findings.append("ATTRIBUTION_CHANGED")
    if _negations(approved, strength_cfg["negation"]) != _negations(final, strength_cfg["negation"]):
        findings.append("NEGATION_CHANGED")
    infl = strength_cfg["inflation_terms"]
    if any(_has(_norm(final), w) and not _has(_norm(approved), w) for w in infl):
        findings.append("INFLATION_TERM_ADDED")
    if SequenceMatcher(None, _norm(approved), _norm(final)).ratio() < 0.55:
        findings.append("REWORDED")
    return findings


def is_material(text: str, strength_cfg: dict) -> bool:
    lad = strength_cfg["ladders"]
    return bool(_numbers(text) or _years(text)
                or ladder_level(text, lad["causal"]) >= 3
                or ladder_level(text, lad["epistemic"]) >= 2
                or ladder_level(text, lad["probability"]) >= 2
                or any(_has(_norm(text), w) for w in strength_cfg["inflation_terms"]))


# ---------------------------------------------------------------- drafts
@dataclass
class Sentence:
    index: int
    section: str
    text: str           # without tags
    tags: list = field(default_factory=list)


def split_draft(markdown: str) -> list[Sentence]:
    out, section, idx = [], "", 0
    for block in re.split(r"\n\s*\n", markdown):
        block = block.strip()
        if not block or block.startswith("<!--"):
            continue
        if block.startswith("#"):
            section = block.lstrip("#").strip().splitlines()[0]
            rest = "\n".join(block.splitlines()[1:]).strip()
            if not rest:
                continue
            block = rest
        block = re.sub(r"^\s*[-*]\s+", "", block, flags=re.M).replace("\n", " ")
        for raw in re.findall(r".+?(?:[.!?](?=\s|$)(?:\s*\[[C\d,\s]+\])?|\[[C\d,\s]+\](?=\s|$)|$)", block):
            raw = raw.strip()
            if not raw:
                continue
            tags = [t.strip() for m in TAG_RE.findall(raw) for t in m.split(",")]
            text = TAG_RE.sub("", raw).strip()
            if text in (".", ""):
                continue
            out.append(Sentence(idx, section, text, tags))
            idx += 1
    return out


APPRAISAL_RE = re.compile(r"staff appraisal|conclusions?|summary of staff views", re.I)


def audit_draft(markdown: str, claims: dict, strength_cfg: dict, approved_statuses=("VERIFIED", "QUALIFIED")) -> list[dict]:
    """Return one record per sentence: outcome, findings and RED codes."""
    records, seen_before_appraisal = [], set()
    for s in split_draft(markdown):
        findings: list[str] = []
        in_appraisal = bool(APPRAISAL_RE.search(s.section))
        if s.tags:
            known = [claims[t] for t in s.tags if t in claims]
            if len(known) < len(s.tags) or any(c.status not in approved_statuses for c in known):
                findings.append("TAG_TO_UNAPPROVED")
            if known:
                approved = " ".join(c.wording() for c in known)
                ctype = "CAU" if any(c.claim_type == "CAU" for c in known) else known[0].claim_type
                findings += compare(approved, s.text, strength_cfg, ctype)
            # A recommendation may first appear in the appraisal if everything it rests on was established earlier.
            if in_appraisal and any(t not in seen_before_appraisal and not (
                    t in claims and claims[t].claim_type == "REC" and claims[t].depends_on
                    and set(claims[t].depends_on) <= seen_before_appraisal) for t in s.tags):
                findings.append("APPRAISAL_NEW_CLAIM")
            if not in_appraisal:
                seen_before_appraisal.update(s.tags)
        elif is_material(s.text, strength_cfg):
            findings.append("UNMAPPED_MATERIAL")
        reds = sorted({SEVERITY[f] for f in findings if SEVERITY.get(f)})
        if not findings:
            outcome = "UNCHANGED" if s.tags else "CONNECTIVE"
        elif reds:
            outcome = "STRENGTHENED_OR_UNSUPPORTED"
        else:
            outcome = "REVIEW"
        records.append({"index": s.index, "section": s.section, "text": s.text, "tags": s.tags,
                        "findings": findings, "red_codes": reds, "outcome": outcome})
    return records
