"""Mechanical verification: code, not models, decides whether evidence exists.

- Source retrieval: every cited source is opened (local file or URL) and hashed.
- Quote matching: every excerpt must actually occur in the source text (exact
  or near-exact, with numbers required to match exactly).
- Data checks: numbers are compared with data connectors (local CSV extracts
  of WEO/IFS/GFS/authorities' data, or live public APIs).
- Derived numbers: recomputed from their stated formula.
- Number provenance: every number in a claim must appear in a verified excerpt
  or a matching data point.
- Vintage: sources too old for a claim presented as current are flagged.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import operator
import re
import unicodedata
import urllib.request
from datetime import date
from html import unescape
from pathlib import Path

from .model import Claim, NumberFact, Source, grade_value, now
from .strength import _numbers

TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")


def tokens(text: str) -> list[str]:
    # NFKC folds PDF ligatures and full-width characters.
    text = unicodedata.normalize("NFKC", unescape(text)).lower().replace("’", "'").replace("-\n", "")
    return TOKEN_RE.findall(text)



# Tokens whose substitution does not change meaning (text-extraction noise).
NOISE_TOKENS = {"the", "a", "an", "of", "and", "in", "on", "at", "to", "s"}

# ------------------------------------------------------------- sources
class SourceStore:
    def __init__(self, base_dirs: list[Path], cache_dir: Path, allow_network: bool):
        self.base_dirs = base_dirs
        self.cache_dir = cache_dir
        self.allow_network = allow_network
        self._text: dict[str, str | None] = {}
        cache_dir.mkdir(parents=True, exist_ok=True)

    def text(self, src: Source) -> str | None:
        if src.source_id in self._text:
            return self._text[src.source_id]
        txt = None
        if src.local_path:
            for base in self.base_dirs:
                p = (base / src.local_path)
                if p.exists():
                    txt = _read_file(p)
                    break
        if txt is None and src.url:
            cached = self.cache_dir / (hashlib.sha1(src.url.encode()).hexdigest() + ".txt")
            if cached.exists():
                txt = cached.read_text(encoding="utf-8")
            elif self.allow_network:
                txt = _fetch(src.url)
                if txt:
                    cached.write_text(txt, encoding="utf-8")
        if txt is None:
            src.status = "UNAVAILABLE"
        elif not txt.strip():
            src.status, txt = "UNREADABLE", None
        else:
            src.status = "CONFIRMED"
            src.sha256 = hashlib.sha256(txt.encode("utf-8")).hexdigest()
            src.retrieved_at = now()
        self._text[src.source_id] = txt
        return txt


def _read_file(p: Path) -> str:
    if p.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader  # optional dependency
        except ImportError:
            return ""
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(p)).pages)
    raw = p.read_text(encoding="utf-8", errors="replace")
    return _strip_html(raw) if p.suffix.lower() in (".html", ".htm") else raw


def _strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return unescape(re.sub(r"<[^>]+>", " ", raw))


def _fetch(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "imf-orchestrator-verifier/1.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
    except Exception:
        return None
    if "pdf" in ctype:
        try:
            import io
            from pypdf import PdfReader
            return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(body)).pages)
        except Exception:
            return ""
    text = body.decode("utf-8", errors="replace")
    return _strip_html(text) if "html" in ctype else text


# --------------------------------------------------------- quote matching
def match_quote(quote: str, source_text: str, threshold: float) -> tuple[str, float]:
    """Return (FOUND | FOUND_APPROX | NOT_FOUND, score).

    Score = share of quote tokens matched in order inside the best window of
    the source. Numbers in the quote must appear verbatim in that window.
    """
    q, s = tokens(quote), tokens(source_text)
    if not q:
        return "NOT_FOUND", 0.0
    if f" {' '.join(q)} " in f" {' '.join(s)} ":
        return "FOUND", 1.0
    freq: dict[str, int] = {}
    for t in s:
        freq[t] = freq.get(t, 0) + 1
    present = [t for t in q if t in freq]
    if not present:
        return "NOT_FOUND", 0.0
    anchor = min(present, key=lambda t: freq[t])
    anchor_pos = q.index(anchor)
    best, best_window = 0.0, []
    from difflib import SequenceMatcher
    for i, t in enumerate(s):
        if t != anchor:
            continue
        lo = max(0, i - anchor_pos - len(q) // 4)
        window = s[lo: lo + len(q) + len(q) // 2 + 1]
        sm = SequenceMatcher(None, window, q, autojunk=False)
        score = sum(b.size for b in sm.get_matching_blocks()) / len(q)
        if score > best:
            best, best_window = score, window
    if best < threshold:
        return "NOT_FOUND", round(best, 3)
    # Near-matches are tolerated only for extraction noise: every quote token that
    # differs from the source must be a function word. A changed content word or
    # number means the quote was altered (paraphrase, error or fabrication).
    sm = SequenceMatcher(None, best_window, q, autojunk=False)
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert") and any(t not in NOISE_TOKENS for t in q[j1:j2]):
            return "NOT_FOUND", round(best, 3)
    return "FOUND_APPROX", round(best, 3)


# ------------------------------------------------------------ data
class DataConnectors:
    """Lookup of (connector, series, country, period) -> value.

    local_csv: CSV files with columns series,country,period,value[,unit,vintage,source_id]
               (export WEO/IFS/GFS/authorities' series here for reproducibility)
    worldbank: World Bank Indicators API (public), series = indicator code,
               country = ISO3, period = year
    imf:       configure an approved IMF data endpoint before use (the IMF data
               portal and its API have changed over time; do not hard-code)
    """

    def __init__(self, csv_paths: list[Path], allow_network: bool):
        self.rows: dict[tuple, dict] = {}
        self.allow_network = allow_network
        for p in csv_paths:
            with open(p, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    self.rows[(r["series"], r["country"], str(r["period"]))] = r

    def lookup(self, n: NumberFact) -> float | None:
        conn = n.connector or "local_csv"
        if conn == "local_csv":
            r = self.rows.get((n.series, n.country, str(n.period)))
            return float(r["value"]) if r else None
        if conn == "worldbank" and self.allow_network:
            url = (f"https://api.worldbank.org/v2/country/{n.country}/indicator/{n.series}"
                   f"?format=json&date={n.period}")
            txt = _fetch(url)
            try:
                data = json.loads(txt)[1]
                vals = [d["value"] for d in data if d.get("value") is not None]
                return float(vals[0]) if vals else None
            except Exception:
                return None
        return None


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.USub: operator.neg, ast.Pow: operator.pow}


def safe_eval(expr: str, env: dict) -> float:
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and node.id in env:
            return float(env[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError(f"unsupported expression element in '{expr}'")
    return ev(ast.parse(expr, mode="eval"))


def _close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= max(abs(b) * tol, 0.051 if abs(b) < 100 else 0.0)


# ------------------------------------------------------------ driver
def verify_claims(state, store: SourceStore, data: DataConnectors, qg: dict) -> list[dict]:
    """Run every mechanical check; update claims in place; return a report."""
    threshold = qg["quote_match_threshold"]
    tol = qg["numeric_tolerance"]
    report = []
    as_of = date.fromisoformat(state.as_of) if state.as_of else date.today()
    for claim in state.claims.values():
        rec = {"claim_id": claim.claim_id, "quotes": [], "numbers": [], "flags": []}
        # 1. quotes
        for ev in claim.evidence:
            src = state.sources.get(ev.source_id)
            if src is None:
                ev.quote_check, ev.match_score = "SOURCE_UNAVAILABLE", 0.0
                rec["flags"].append(f"UNKNOWN_SOURCE:{ev.source_id}")
            else:
                txt = store.text(src)
                if txt is None:
                    ev.quote_check, ev.match_score = "SOURCE_UNAVAILABLE", 0.0
                else:
                    ev.quote_check, ev.match_score = match_quote(ev.excerpt, txt, threshold)
            rec["quotes"].append({"source_id": ev.source_id, "result": ev.quote_check, "score": ev.match_score})
        # 2. numbers against data / formulas
        for n in claim.numbers:
            if n.formula:
                try:
                    v = safe_eval(n.formula, n.inputs)
                    n.observed, n.data_check = round(v, 6), "DERIVED_OK" if _close(n.value, v, tol) else "DERIVED_MISMATCH"
                except ValueError:
                    n.data_check = "DERIVED_MISMATCH"
            elif n.series:
                v = data.lookup(n)
                if v is None:
                    n.data_check = "NOT_FOUND"
                else:
                    n.observed, n.data_check = v, "MATCH" if _close(n.value, v, tol) else "MISMATCH"
            rec["numbers"].append({"value": n.value, "series": n.series, "period": n.period,
                                   "result": n.data_check, "observed": n.observed})
        # 3. provenance of every number in the wording
        good_text = " ".join(e.excerpt for e in claim.evidence if e.quote_check in ("FOUND", "FOUND_APPROX"))
        good_nums = set(_numbers(good_text)) | {_fmt(n.value) for n in claim.numbers
                                               if n.data_check in ("MATCH", "DERIVED_OK")}
        missing = [x for x in _numbers(claim.wording()) if x not in good_nums and _fmt(float(x)) not in good_nums]
        if missing:
            rec["flags"].append("NUMBER_NOT_IN_EVIDENCE:" + ",".join(missing))
        # 4. vintage
        if claim.current:
            max_age = qg["vintage_max_age_days"].get(claim.claim_type, qg["vintage_max_age_days"]["default"])
            supporting = [state.sources.get(e.source_id) for e in claim.evidence if e.relation != "contradicts"]
            ages = [(as_of - date.fromisoformat(s.publication_date)).days
                    for s in supporting if s and s.publication_date]
            if ages and min(ages) > max_age:
                rec["flags"].append(f"OUTDATED:{min(ages)}d>{max_age}d")
        # 5. contradictions from authoritative sources
        for e in claim.evidence:
            src = state.sources.get(e.source_id)
            if e.relation == "contradicts" and src and grade_value(src.authority_grade) >= 4:
                if not any(c.get("source_id") == e.source_id and c.get("resolved") for c in claim.contradictions):
                    rec["flags"].append(f"UNRESOLVED_CONTRADICTION:{e.source_id}")
        for c in claim.contradictions:
            src = state.sources.get(c.get("source_id", ""))
            if not c.get("resolved") and src and grade_value(src.authority_grade) >= 4:
                rec["flags"].append(f"UNRESOLVED_CONTRADICTION:{src.source_id}")
        claim.flags = sorted(set(f for f in claim.flags if not f.startswith(_MECH_PREFIXES)) | set(rec["flags"]))
        report.append(rec)
    return report


_MECH_PREFIXES = ("UNKNOWN_SOURCE", "NUMBER_NOT_IN_EVIDENCE", "OUTDATED", "UNRESOLVED_CONTRADICTION")


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def check_auditor_excerpt(state, store: SourceStore, claim: Claim, agent: str, audited: dict, threshold: float) -> dict:
    """An auditor's VERIFIED counts only if its quoted excerpt is really in the source."""
    status = audited.get("status", "NOT_VERIFIED")
    src = state.sources.get(audited.get("source_id", ""))
    result = {"status_claimed": status, "status": status, "excerpt_check": "NOT_CHECKED"}
    if status in ("VERIFIED", "PARTIALLY_VERIFIED"):
        txt = store.text(src) if src else None
        if not audited.get("excerpt") or txt is None:
            result["excerpt_check"] = "SOURCE_UNAVAILABLE" if src else "UNKNOWN_SOURCE"
            result["status"] = "NOT_VERIFIED"
        else:
            check, score = match_quote(audited["excerpt"], txt, threshold)
            result["excerpt_check"], result["score"] = check, score
            if check == "NOT_FOUND":
                result["status"] = "NOT_VERIFIED"
                state.bump(agent, "verification_excerpt_not_found")
                key = f"auditor-excerpt:{agent}:{claim.claim_id}"
                if not any(i.key == key for i in state.issues):
                    state.add_issue(raised_by="system", stage="audit", category="factual", key=key,
                                severity="RED" if claim.importance == "CRITICAL" else "YELLOW",
                                claim_ids=[claim.claim_id],
                                description=f"{agent} marked {claim.claim_id} {status} but its quoted excerpt "
                                            f"is not in source {audited.get('source_id')} (possible fabricated verification).",
                                proposed_resolution="Re-verify with a different auditor and the primary source.")
    state.bump(agent, "audits")
    return result
