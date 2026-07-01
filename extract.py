# extract.py
import os
import re
import logging
from dataclasses import dataclass
from typing import List, Optional, Any, Dict

import pdfplumber

logger = logging.getLogger(__name__)

AMT = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"

# =============================================================================
# Data container
# =============================================================================

@dataclass
class ExtractedTable:
    file_name: str
    report_month: Optional[str]  # YYYY-MM
    page: int
    header: List[str]
    rows: List[List[Any]]

# =============================================================================
# Helpers
# =============================================================================

def infer_month(fname: str) -> Optional[str]:
    # Anchored to start of filename so "report_202501.pdf" does not match.
    m = re.match(r"^(\d{4})(\d{2})", fname)
    if not m:
        return None
    yyyy, mm = int(m.group(1)), int(m.group(2))
    if 1 <= mm <= 12:
        return f"{yyyy:04d}-{mm:02d}"
    return None


def _clean(x: Any) -> str:
    return re.sub(r"\s+", " ", ("" if x is None else str(x))).strip()


def _to_float(val: Any) -> float:
    try:
        return float(_clean(val).replace(",", ""))
    except Exception:
        return float("nan")

# =============================================================================
# REPORT_HEADER extraction
# =============================================================================

def extract_intro_metrics(pdf_path: str) -> Dict[str, Any]:
    fname = os.path.basename(pdf_path)
    report_month = infer_month(fname)

    metrics = {
        "report_month": report_month,
        "file_name": fname,
        "ecg_revenue_reported": None,
        "ecg_revenue_allocated_level_a": None,
        "ecg_revenue_allocated_level_b": None,
        "remaining_allocated_to_level_b": None,
    }

    re_ecg = re.compile(
        rf"total\s+ECG\s+revenue(?:s)?\s+reported.*?GHS\s+({AMT})",
        re.I | re.S,
    )

    re_level_a_new = re.compile(
        rf"total\s+amount\s+of\s+GHS\s+({AMT}).*?"
        rf"(?:IPP|Independent\s+Power\s+Producer|Level\s*A)",
        re.I | re.S,
    )

    re_level_a_old = re.compile(
        rf"total\s+amount\s+of\s+GHS\s+({AMT}).*?"
        rf"(?:representing|represents).*?payment\s+due",
        re.I | re.S,
    )

    re_level_b_explicit = re.compile(
        rf"remaining(?:\s+amount\s+of)?\s+GHS\s+({AMT}).*?"
        rf"(?:allocated|was\s+then\s+allocated).*?"
        rf"(?:SOEs?|State\s+Owned\s+Enterprises)",
        re.I | re.S,
    )

    re_level_b_narrative = re.compile(
        rf"remaining\s+amount\s+of\s+GHS\s+({AMT})",
        re.I | re.S,
    )

    re_level_b_bare = re.compile(
        rf"remaining\s+GHS\s+({AMT})",
        re.I | re.S,
    )

    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for p in pdf.pages[:2]:
                text += "\n" + (p.extract_text() or "")
            text = _clean(text)

        m = re_ecg.search(text)
        if m:
            metrics["ecg_revenue_reported"] = m.group(1)

        for pat in (re_level_a_new, re_level_a_old):
            m = pat.search(text)
            if m:
                metrics["ecg_revenue_allocated_level_a"] = m.group(1)
                break

        for pat in (re_level_b_explicit, re_level_b_narrative, re_level_b_bare):
            m = pat.search(text)
            if m:
                metrics["ecg_revenue_allocated_level_b"] = m.group(1)
                metrics["remaining_allocated_to_level_b"] = m.group(1)
                break

        ecg_v = _to_float(metrics["ecg_revenue_reported"])
        a_v = _to_float(metrics["ecg_revenue_allocated_level_a"])

        # FIX: only attempt rescaling when the ratio is plausibly a missing digit
        # (≤1000×). Multiply *after* the guard so we never overshoot and then
        # silently accept a wrong value.
        if ecg_v > 0 and a_v > 0 and ecg_v < a_v and (a_v / ecg_v) <= 1000:
            rescaled = ecg_v
            for _ in range(3):
                rescaled *= 10
                if rescaled >= a_v:
                    metrics["ecg_revenue_reported"] = f"{rescaled:,.2f}"
                    logger.warning(
                        "%s: ECG revenue corrected due to malformed formatting "
                        "(rescaled to %s).",
                        fname, metrics["ecg_revenue_reported"],
                    )
                    break
            else:
                logger.warning(
                    "%s: ECG revenue (%s) < Level A (%s) but rescaling did not "
                    "converge; leaving value unchanged.",
                    fname, metrics["ecg_revenue_reported"], a_v,
                )

        if metrics["ecg_revenue_allocated_level_a"] is None:
            logger.warning("%s: Level A allocation not found.", fname)

        if metrics["ecg_revenue_allocated_level_b"] is None:
            logger.warning("%s: Level B allocation not found.", fname)

    except Exception as e:
        logger.warning("%s: intro metric extraction failed (%s)", fname, e)

    return metrics

# =============================================================================
# Table detection helpers
# =============================================================================

def looks_like_company_table(header: List[str]) -> bool:
    h = " ".join(c.lower() for c in header if c)
    return ("company" in h) or ("name of" in h) or ("producer" in h)


def looks_like_fx_summary_table(header: List[str]) -> bool:
    h = " ".join(c.lower() for c in header if c)
    return (
        "beneficiary" in h
        and "period" in h
        and "amount" in h
        and "usd" in h
    )

# =============================================================================
# Table extraction
# =============================================================================

def extract_tables(pdf_path: str) -> List[ExtractedTable]:
    """
    Raises on PDF open/parse failure so the caller can track which files failed.
    Previously this silently returned [] and swallowed the error.
    """
    fname = os.path.basename(pdf_path)
    month = infer_month(fname)
    out: List[ExtractedTable] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []

            for t in tables:
                if not t or len(t) < 2:
                    continue

                header = [_clean(x) for x in t[0]]
                if sum(1 for c in header if c) < 2:
                    continue

                if not (
                    looks_like_company_table(header)
                    or looks_like_fx_summary_table(header)
                ):
                    continue

                hlen = len(header)
                rows = []
                for r in t[1:]:
                    rr = list(r) if r else []
                    rr = rr[:hlen] + [None] * (hlen - len(rr))
                    rows.append(rr)

                out.append(
                    ExtractedTable(
                        file_name=fname,
                        report_month=month,
                        page=page_no,
                        header=header,
                        rows=rows,
                    )
                )

    return out
