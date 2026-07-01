# transform.py
import logging
import os
import re
from functools import lru_cache
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd

from extract import ExtractedTable

logger = logging.getLogger(__name__)

# =============================================================================
# 1) Robust parsing helpers
# =============================================================================

PLACEHOLDERS = {
    "", "-", "–", "—", "n/a", "na", "none",
    "no data", "no data submitted", "no data submit-ted"
}

def clean(x: Any) -> str:
    return "" if x is None else re.sub(r"\s+", " ", str(x)).strip()

def safe_float(x: Any) -> float:
    """
    Robust numeric parser:
    - returns NaN for placeholders and dash-only cells
    - strips commas/currency symbols
    """
    s = clean(x).lower()
    if not s or s in PLACEHOLDERS:
        return np.nan
    if re.fullmatch(r"[-–—]+", s):
        return np.nan
    s2 = re.sub(r"[^\d\.\-]", "", s.replace(",", ""))
    if not s2 or s2 in {"-", ".", "-.", ".-"}:
        return np.nan
    try:
        return float(s2)
    except ValueError:
        return np.nan

def norm_col(c: Any) -> str:
    return re.sub(r"\s+", " ", str(c)).strip().lower()

# =============================================================================
# 2) Company name harmonization
# =============================================================================

def normalize_company(raw):
    """Canonicalize entity names; return None for totals/aggregates."""
    if raw is None:
        return None

    s = re.sub(r"\s+", " ", str(raw)).strip()
    s_low = s.lower()

    if re.fullmatch(r"(total|grand total)", s_low):
        return None

    # IPPs
    if "aksa" in s_low:
        return "Aksa"
    if "amandi" in s_low or "twin city" in s_low:
        return "Amandi"
    if "asogli" in s_low or "sunon" in s_low:
        return "Sunon Asogli"
    if "cenpower" in s_low:
        return "Cenpower"
    if "karpower" in s_low or "karpowership" in s_low:
        return "Karpower"
    if "meinergy" in s_low:
        return "Meinergy"
    if "early power" in s_low:
        return "Early Power"
    if "cenit" in s_low:
        return "Cenit"
    if "bxc" in s_low:
        return "BXC Solar"
    if "safisana" in s_low:
        return "Safisana"
    if "ameri" in s_low:
        return "AMERI"
    if "tico" in s_low:
        return "TICO"
    if "genser" in s_low:
        return "Genser"
    if re.fullmatch(r"cie", s_low) or "cie" in s_low:
        return "CIE"
    if "pds" in s_low:
        return "PDS"

    # SOEs / utilities
    if s_low == "ecg" or "electricity company of ghana" in s_low:
        return "ECG"
    if s_low.startswith("vra") and ("ngas" in s_low or "wapco" in s_low):
        return "VRA (NGAS + WAPCo)"
    if s_low.startswith("vra"):
        return "VRA"
    if "gridco" in s_low:
        return "GRIDCo"
    if s_low.startswith("bui"):
        return "Bui"
    if "nedco" in s_low:
        return "NEDCo"
    if "purc" in s_low:
        return "PURC"
    if "gog" in s_low or "government of ghana" in s_low:
        return "GoG"
    if "bost" in s_low:
        return "BOST"
    if "tor" in s_low:
        return "TOR"

    # Gas entities
    if "gnpc" in s_low:
        return "GNPC"
    if "gngc" in s_low or "ghana gas" in s_low:
        return "GNGC"

    # Fuel/gas suppliers
    if "wapco" in s_low:
        return "WAPCo"
    if "n-gas" in s_low or "n gas" in s_low or "nigeria gas" in s_low:
        return "N-Gas"
    if "sahara" in s_low:
        return "Sahara"
    if re.fullmatch(r"bp", s_low) or s_low.startswith("bp "):
        return "BP"
    if "tullow" in s_low:
        return "Tullow"
    if "octp" in s_low:
        return "OCTP"

    # Fuel lines
    if "fuel purchases" in s_low or "fuel purchase" in s_low:
        return "Fuel Purchases"
    if "fuel levy" in s_low:
        return "Fuel Levy"
    if "fuel account" in s_low:
        return "Fuel Account"

    # Regulatory levy variants
    if "regulatory levy" in s_low:
        if "gas" in s_low:
            return "Regulatory Levy – Gas"
        if "power" in s_low:
            return "Regulatory Levy – Power"
        return "Regulatory Levy"

    return s

# =============================================================================
# 3) Company type classification
# =============================================================================

SOE_SET = {
    "ECG", "VRA", "BOST", "GNGC", "GNPC", "TOR", "Bui", "GRIDCo", "NEDCo", "PURC", "GoG"
}
IPP_SET = {
    "Cenpower", "Karpower", "Aksa", "Meinergy", "Early Power", "Amandi", "TICO",
    "BXC Solar", "Genser", "PDS", "AMERI", "Cenit", "Sunon Asogli", "Safisana", "CIE"
}
FUEL_SET = {"Sahara", "N-Gas", "BP", "Tullow", "OCTP", "WAPCo"}

def classify_company_type(harmonized_company: str) -> str:
    if not harmonized_company or harmonized_company == "__REPORT__":
        return "Other"
    if harmonized_company in SOE_SET:
        return "SOE"
    if harmonized_company in IPP_SET:
        return "IPP"
    if harmonized_company in FUEL_SET:
        return "Fuel Supplier"
    return "Other"

# =============================================================================
# 4) Header harmonization schema
# =============================================================================

T1_RULES = [
    (r"^company$", "Company"),
    (r"cwm\s+percentage.*", "CWM Percentage (%)"),
    (r"expected\s+payment.*\(ghs\)", "Expected payment to level A (GHS)"),
    (r"expected\s+payment\s+cmw.*", "Expected payment to level A (GHS)"),
    (r"expected\s+payment\s+by\s+cwm.*", "Expected payment to level A (GHS)"),
]

T2_RULES = [
    (r"^company$", "Company"),
    (r"(cwm|ecg)\s+payment.*\(ghs\)", "ECG Payment (GHS)"),
    (r"mof\s+top\s*up.*\(ghs\)", "MoF Top-Up (GHS)"),
]

T3_RULES = [
    (r"item\s+no.*", None),
    (r"(name of independent power producer|name of ipp|ipp name|name of beneficiary|company)", "Company"),
    (r"cwm\s+percentage.*", "CWM Percentage (%)"),
    (r"(amount\s+paid.*usd|expected\s+amount\s+to\s+be\s+paid.*usd|expected\s+amount\s+to\s+be\s+paid\s*\(usd\))",
     "Expected payment to level A (USD)"),
    (r"(ghs\s+equivalent.*|amount\s+paid.*\(ghs\)|amount\s+paid\s+ghs|expected\s+payment\s+by\s+ecg.*\(ghs\)|expected\s+amount\s+to\s+be\s+paid.*\(ghs\))",
     "Expected payment to level A (GHS)"),
    (r"(actual\s+amount\s+paid.*\(ghs\)|actual\s+payment.*\(ghs\))",
     "Actual payment to level A (GHS)"),
]

T4_RULES = [
    (r"^company$", "Company"),
    (r"cwm\s+percentage.*", "CWM Percentage (%)"),
    (r"expected\s+payment.*\(ghs\)", "Expected payment to level B (GHS)"),
    (r"actual\s+payment.*\(ghs\)", "Actual payment to level B (GHS)"),
    (r"(cwm\s+variance|variance).*\(ghs\)", "Variance (GHS)"),
]

def apply_header_rules(df: pd.DataFrame, rules):
    rename, drop = {}, []
    for col in df.columns:
        c = norm_col(col)
        for pat, std in rules:
            if re.search(pat, c):
                if std is None:
                    drop.append(col)
                else:
                    rename[col] = std
                break
    return df.drop(columns=drop, errors="ignore").rename(columns=rename)

# =============================================================================
# 5) Table classification
# =============================================================================

def classify_table(cols):
    h = " | ".join(norm_col(c) for c in cols)

    if ("beneficiary" in h) and ("period" in h) and ("usd" in h) and ("amount" in h):
        return "FX_FINANCING_SUMMARY"

    if ("mof top" in h) and (("cwm payment" in h) or ("ecg payment" in h)):
        return "T2_MOF_TOPUP"
    if (("amount paid" in h) or ("amount to be paid" in h)) and ("usd" in h or "ghs equivalent" in h or "actual amount paid" in h):
        return "T3_LEVEL_A_PAYMENTS"
    if ("expected" in h and "actual" in h and "payment" in h and "ghs" in h):
        return "T4_LEVEL_B_SUMMARY"
    if ("cwm percentage" in h and "expected" in h and "ghs" in h and "actual" not in h):
        return "T1_ALLOCATION_REVENUE"
    return "OTHER"

# =============================================================================
# 6) Wide -> long
# =============================================================================

def wide_to_long(df_std: pd.DataFrame, report_month: str, file_name: str, table_type: str) -> pd.DataFrame:
    if "Company" not in df_std.columns:
        return pd.DataFrame()

    rows = []
    for _, r in df_std.iterrows():
        company = normalize_company(r.get("Company"))
        if not company:
            continue

        company_type = classify_company_type(company)

        for col in df_std.columns:
            if col == "Company":
                continue

            if "(USD)" in col:
                curr = "USD"
            elif "(GHS)" in col:
                curr = "GHS"
            elif "(%)" in col:
                curr = "PCT"
            else:
                curr = ""

            v = safe_float(r.get(col))
            if pd.isna(v):
                continue

            rows.append({
                "report_month": pd.to_datetime(report_month, format="%Y-%m", errors="coerce"),
                "company": company,
                "company_type": company_type,
                "table_type": table_type,
                "variable": col,
                "currency": curr,
                "value": v,
                "source_file": file_name,
                "is_derived": False,
            })

    return pd.DataFrame(rows)

# =============================================================================
# 7) REPORT_HEADER -> long
# =============================================================================

def _make_header_row(report_month, fname, var, val, derived=False):
    """Return a single panel row dict, or None if val is not numeric."""
    v = safe_float(val)
    if pd.isna(v):
        return None
    return {
        "report_month": pd.to_datetime(report_month, format="%Y-%m", errors="coerce"),
        "company": "__REPORT__",
        "company_type": "Other",
        "table_type": "REPORT_HEADER",
        "variable": var,
        "currency": "GHS",
        "value": v,
        "source_file": fname,
        "is_derived": bool(derived),
    }

def header_metrics_to_long(header_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in header_df.iterrows():
        rm = r.get("report_month")
        fname = r.get("file_name")

        ecg = r.get("ecg_revenue_reported")
        lvl_a = r.get("ecg_revenue_allocated_level_a")
        lvl_b = r.get("ecg_revenue_allocated_level_b")
        if lvl_b is None:
            lvl_b = r.get("remaining_allocated_to_level_b")

        for var, val in [
            ("ECG Revenue Reported (GHS)", ecg),
            ("ECG Revenue Allocated to Level B (GHS)", lvl_b),
        ]:
            row = _make_header_row(rm, fname, var, val, derived=False)
            if row:
                rows.append(row)

        if lvl_a is not None:
            row = _make_header_row(rm, fname, "ECG Revenue Allocated to Level A (GHS)", lvl_a, derived=False)
            if row:
                rows.append(row)

    return pd.DataFrame(rows)

# =============================================================================
# 7.5) BoG monthly FX loader
# =============================================================================

MONTH_NAME_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

def _project_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return here if here else os.getcwd()

def _candidate_fx_paths(root: str) -> List[str]:
    cand = [
        os.path.join(root, "data", "bog_monthly_fx.csv"),
        os.path.join(root, "data", "bog_exchange_rate_monthly.csv"),
        os.path.join(root, "bog_monthly_fx.csv"),
        os.path.join(root, "bog_exchange_rate_monthly.csv"),
        os.path.join(root, "out", "bog_monthly_fx.csv"),
    ]
    scan_dirs = [os.path.join(root, "data"), root, os.path.join(root, "out")]
    for d in scan_dirs:
        if os.path.isdir(d):
            for fn in os.listdir(d):
                low = fn.lower()
                if low.endswith(".csv") and ("bog" in low) and ("fx" in low or "exchange" in low):
                    cand.append(os.path.join(d, fn))
    seen, out = set(), []
    for p in cand:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out

def _parse_month_token(x: Any) -> Optional[pd.Timestamp]:
    if x is None:
        return None
    if isinstance(x, pd.Timestamp):
        return x.to_period("M").to_timestamp()
    s = clean(x)
    if not s:
        return None
    s_low = s.lower().replace(" ", "")

    m = re.match(r"^(\d{4})[m\-\/](\d{1,2})$", s_low)
    if m:
        y = int(m.group(1))
        mo = int(m.group(2))
        if 1 <= mo <= 12:
            return pd.Timestamp(year=y, month=mo, day=1)

    dt = pd.to_datetime(s, errors="coerce")
    if pd.notna(dt):
        return dt.to_period("M").to_timestamp()

    m2 = re.match(r"^([a-z]+)\s+(\d{4})$", clean(x).lower())
    if m2 and m2.group(1) in MONTH_NAME_MAP:
        mo = MONTH_NAME_MAP[m2.group(1)]
        y = int(m2.group(2))
        return pd.Timestamp(year=y, month=mo, day=1)

    return None

def _try_long_format(df: pd.DataFrame) -> Optional[pd.Series]:
    cols = {c.lower(): c for c in df.columns}
    date_col = None
    for key in ["month", "period", "date", "time", "report_month"]:
        if key in cols:
            date_col = cols[key]
            break
    if date_col is None:
        for c in df.columns:
            if "month" in c.lower() or "period" in c.lower():
                date_col = c
                break
    if date_col is None:
        return None

    val_col = None
    for key in ["rate", "value", "mid", "fx", "ghs_per_usd", "ghs/usd"]:
        if key in cols:
            val_col = cols[key]
            break
    if val_col is None:
        num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if len(num_cols) == 1:
            val_col = num_cols[0]
    if val_col is None:
        return None

    tmp = df[[date_col, val_col]].copy()
    tmp["month_ts"] = tmp[date_col].apply(_parse_month_token)
    tmp["rate"] = tmp[val_col].apply(safe_float)
    tmp = tmp.dropna(subset=["month_ts", "rate"])
    if tmp.empty:
        return None
    return tmp.groupby("month_ts")["rate"].mean().sort_index()

def _try_wide_format(df: pd.DataFrame) -> Optional[pd.Series]:
    year_col = None
    for c in df.columns:
        if c.lower() == "year" or c.lower().startswith("year"):
            year_col = c
            break
    if year_col is None:
        return None

    month_cols = [c for c in df.columns if c.lower().strip()[:3] in MONTH_NAME_MAP]
    if not month_cols:
        return None

    out = {}
    for _, r in df.iterrows():
        y = safe_float(r.get(year_col))
        if pd.isna(y):
            continue
        y = int(y)
        for mc in month_cols:
            mo = MONTH_NAME_MAP[mc.lower().strip()[:3]]
            v = safe_float(r.get(mc))
            if pd.notna(v):
                out[pd.Timestamp(year=y, month=mo, day=1)] = float(v)

    if not out:
        return None
    return pd.Series(out).sort_index()

@lru_cache(maxsize=8)
def load_bog_monthly_fx(start_ym: str, end_ym: str, root_dir: Optional[str] = None) -> Tuple[pd.Series, str]:
    root = root_dir or _project_root()
    candidates = _candidate_fx_paths(root)

    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue

        s = _try_long_format(df)
        if s is None:
            s = _try_wide_format(df)

        if s is None or s.empty:
            continue

        start = pd.to_datetime(start_ym, format="%Y-%m").to_period("M").to_timestamp()
        end = pd.to_datetime(end_ym, format="%Y-%m").to_period("M").to_timestamp()
        s = s[(s.index >= start) & (s.index <= end)].sort_index()

        if not s.empty:
            # Return a copy so callers cannot mutate the cached Series.
            return s.copy(), f"BoG monthly FX CSV: {os.path.basename(path)}"

    return pd.Series(dtype=float), "BoG monthly FX CSV: NOT FOUND"

# =============================================================================
# 7.6) FX financing summary tables + normalization
# =============================================================================

def _fx_rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for c in df.columns:
        cl = norm_col(c)
        if "beneficiary" in cl:
            rename[c] = "Beneficiary"
        elif "period" in cl:
            rename[c] = "Period"
        elif "amount" in cl and "usd" in cl:
            rename[c] = "Amount (USD)"
    return df.rename(columns=rename)

def _parse_fx_period(text: str) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp], Optional[int]]:
    """
    Parses 'January to May 2025', 'June – September 2025', etc.
    Returns (start_ts, end_ts, n_months).

    FIX: replace en-dash and plain hyphen with ' to ' BEFORE lowercasing so
    that embedded date strings (e.g. '2025-06') do not get mangled — the
    subsequent regex anchors on word boundaries and a trailing 4-digit year,
    so stray replacements are harmless.
    """
    if not text:
        return None, None, None

    t = clean(text)
    t = t.replace("–", " to ").replace("-", " to ")
    t = re.sub(r"\s+", " ", t).strip().lower()

    m = re.match(r"^([a-z]+)\s+to\s+([a-z]+)\s+(\d{4})$", t)
    if not m:
        return None, None, None

    m1, m2, y = m.group(1), m.group(2), int(m.group(3))
    m1_key = m1 if m1 in MONTH_NAME_MAP else m1[:3]
    m2_key = m2 if m2 in MONTH_NAME_MAP else m2[:3]
    if m1_key not in MONTH_NAME_MAP or m2_key not in MONTH_NAME_MAP:
        return None, None, None

    start = pd.Timestamp(y, MONTH_NAME_MAP[m1_key], 1)
    end = pd.Timestamp(y, MONTH_NAME_MAP[m2_key], 1) + pd.offsets.MonthEnd(1)
    n_months = len(pd.period_range(start.to_period("M"), end.to_period("M"), freq="M"))
    return start, end, n_months

def fx_summary_to_frames(df_raw: pd.DataFrame, t: ExtractedTable) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Returns:
      fx_summary_rows: one row per category total over the period
      fx_monthly_rows: monthly normalized equal split across months
    """
    df = _fx_rename_columns(df_raw.copy())

    period_text = None
    if "Period" in df.columns:
        for val in df["Period"].tolist():
            v = clean(val)
            if v and (("to" in v.lower()) or ("–" in v) or ("-" in v)):
                period_text = v
                break

    p_start, p_end, n_months = _parse_fx_period(period_text) if period_text else (None, None, None)

    if p_start is not None and p_end is not None and n_months is not None and n_months > 1:
        logger.warning(
            "%s: multi-month FX table detected (%s → %s, %d months).",
            t.file_name,
            p_start.strftime("%Y-%m"),
            p_end.strftime("%Y-%m"),
            n_months,
        )
    else:
        logger.warning(
            "%s: FX financing table detected but period could not be parsed (period_text=%r).",
            t.file_name,
            period_text,
        )

    fx_rows: List[Dict[str, Any]] = []
    fx_monthly: List[Dict[str, Any]] = []

    for _, r in df.iterrows():
        ben = clean(r.get("Beneficiary"))
        if not ben:
            continue
        if ben.lower() in {"total", "grand total"}:
            continue

        amt = safe_float(r.get("Amount (USD)"))
        if pd.isna(amt):
            continue

        fx_rows.append({
            "table_type": "FX_FINANCING_SUMMARY",
            "beneficiary_category": ben,
            "period_text": period_text,
            "period_start": p_start,
            "period_end": p_end,
            "n_months": n_months,
            "currency": "USD",
            "value": float(amt),
            "source_file": t.file_name,
            "page": getattr(t, "page", None),
            "report_month_source": t.report_month,
            "is_derived": False,
        })

        if p_start is not None and p_end is not None and n_months:
            per_m = float(amt) / float(n_months)
            for m_ts in pd.period_range(p_start.to_period("M"), p_end.to_period("M"), freq="M").to_timestamp():
                fx_monthly.append({
                    "table_type": "FX_FINANCING_SUMMARY_MONTHLY",
                    "report_month": m_ts,
                    "beneficiary_category": ben,
                    "currency": "USD",
                    "value": per_m,
                    "allocation_method": "equal_split_across_months",
                    "period_start": p_start,
                    "period_end": p_end,
                    "source_file": t.file_name,
                    "page": getattr(t, "page", None),
                    "report_month_source": t.report_month,
                    "is_derived": True,
                })

    return fx_rows, fx_monthly

# =============================================================================
# 8) Panel construction helpers (split out of build_panel_long)
# =============================================================================

def _process_tables(tables: list) -> Tuple[List[pd.DataFrame], List[Dict], List[Dict]]:
    """Classify and convert each ExtractedTable; return frames + FX row lists."""
    frames: List[pd.DataFrame] = []
    fx_summary_rows: List[Dict[str, Any]] = []
    fx_monthly_rows: List[Dict[str, Any]] = []

    for t in tables:
        df = pd.DataFrame(t.rows, columns=t.header)
        kind = classify_table(df.columns.tolist())

        if kind == "FX_FINANCING_SUMMARY":
            r1, r2 = fx_summary_to_frames(df, t)
            fx_summary_rows.extend(r1)
            fx_monthly_rows.extend(r2)
            continue

        if kind == "T1_ALLOCATION_REVENUE":
            df_std = apply_header_rules(df, T1_RULES)
            frames.append(wide_to_long(df_std, t.report_month, t.file_name, "T1_ALLOCATION_REVENUE"))

        elif kind == "T2_MOF_TOPUP":
            df_std = apply_header_rules(df, T2_RULES)
            frames.append(wide_to_long(df_std, t.report_month, t.file_name, "T2_MOF_TOPUP"))

        elif kind == "T3_LEVEL_A_PAYMENTS":
            df_std = apply_header_rules(df, T3_RULES)
            frames.append(wide_to_long(df_std, t.report_month, t.file_name, "T3_LEVEL_A_PAYMENTS"))

        elif kind == "T4_LEVEL_B_SUMMARY":
            df_std = apply_header_rules(df, T4_RULES)
            if (
                "Variance (GHS)" not in df_std.columns
                and "Expected payment to level B (GHS)" in df_std.columns
                and "Actual payment to level B (GHS)" in df_std.columns
            ):
                exp = pd.to_numeric(
                    df_std["Expected payment to level B (GHS)"].astype(str).str.replace(",", ""),
                    errors="coerce",
                )
                act = pd.to_numeric(
                    df_std["Actual payment to level B (GHS)"].astype(str).str.replace(",", ""),
                    errors="coerce",
                )
                df_std["Variance (GHS)"] = act - exp
            frames.append(wide_to_long(df_std, t.report_month, t.file_name, "T4_LEVEL_B_SUMMARY"))

    return frames, fx_summary_rows, fx_monthly_rows


def _impute_ghs_from_usd(panel: pd.DataFrame, fx_series: pd.Series, fx_label: str) -> List[Dict]:
    """
    For T3 rows that have USD but no GHS value, derive GHS using BoG FX rates
    first, then fall back to within-month implied FX median.
    """
    usd_var = "Expected payment to level A (USD)"
    ghs_var = "Expected payment to level A (GHS)"

    t3 = panel[panel["table_type"] == "T3_LEVEL_A_PAYMENTS"].copy()
    piv = t3.pivot_table(
        index=["report_month", "company"], columns="variable", values="value", aggfunc="sum"
    )

    derived_rows: List[Dict] = []

    if piv.empty or usd_var not in piv.columns:
        return derived_rows

    ghs_existing = piv[ghs_var] if ghs_var in piv.columns else pd.Series(index=piv.index, dtype=float)
    need = ghs_existing.isna() & piv[usd_var].notna()

    # Pass 1: BoG CSV rates
    if need.any() and not fx_series.empty:
        for (m, comp), usd_val in piv.loc[need, usd_var].items():
            m0 = pd.to_datetime(m).to_period("M").to_timestamp()
            rate = fx_series.get(m0)
            if rate is None or pd.isna(rate):
                continue
            derived_rows.append({
                "report_month": m,
                "company": comp,
                "company_type": classify_company_type(comp),
                "table_type": "T3_LEVEL_A_PAYMENTS",
                "variable": ghs_var,
                "currency": "GHS",
                "value": float(usd_val) * float(rate),
                "source_file": fx_label,
                "is_derived": True,
            })

    # Pass 2: within-month implied FX median (for rows not covered by Pass 1)
    if ghs_var in piv.columns:
        with_pairs = piv[piv[usd_var].notna() & piv[ghs_var].notna()].copy()
        if not with_pairs.empty:
            with_pairs["implied_fx"] = with_pairs[ghs_var] / with_pairs[usd_var]
            month_implied = with_pairs.groupby(level=0)["implied_fx"].median()

            filled_keys = {(r["report_month"], r["company"]) for r in derived_rows}
            # FIX: build need_keys only from piv where ghs_var IS in columns
            # (the outer `if ghs_var in piv.columns` already guarantees this,
            # so the dead `ghs_var not in piv.columns` branch is removed).
            need_keys = [
                k for k in piv.index
                if pd.notna(piv.at[k, usd_var]) and pd.isna(piv.at[k, ghs_var])
            ]
            for (m, comp) in need_keys:
                if (m, comp) in filled_keys:
                    continue
                rate = month_implied.get(m)
                if rate is None or pd.isna(rate):
                    continue
                usd_val = piv.at[(m, comp), usd_var]
                derived_rows.append({
                    "report_month": m,
                    "company": comp,
                    "company_type": classify_company_type(comp),
                    "table_type": "T3_LEVEL_A_PAYMENTS",
                    "variable": ghs_var,
                    "currency": "GHS",
                    "value": float(usd_val) * float(rate),
                    "source_file": "Imputed using within-month implied FX (median)",
                    "is_derived": True,
                })

    return derived_rows


def _derive_level_a_header(panel: pd.DataFrame, ghs_var: str, level_a_var: str) -> List[Dict]:
    """Backfill REPORT_HEADER Level A from T3 totals when missing."""
    t3_totals = panel[
        (panel["table_type"] == "T3_LEVEL_A_PAYMENTS") & (panel["variable"] == ghs_var)
    ].groupby("report_month", as_index=True)["value"].sum()

    existing_level_a = panel[
        (panel["company"] == "__REPORT__")
        & (panel["table_type"] == "REPORT_HEADER")
        & (panel["variable"] == level_a_var)
    ].groupby("report_month", as_index=True)["value"].sum()

    new_rows = []
    for m in t3_totals.index:
        if m in existing_level_a.index:
            continue
        val = t3_totals.loc[m]
        if pd.notna(val) and val > 0:
            new_rows.append({
                "report_month": m,
                "company": "__REPORT__",
                "company_type": "Other",
                "table_type": "REPORT_HEADER",
                "variable": level_a_var,
                "currency": "GHS",
                "value": float(val),
                "source_file": "",
                "is_derived": True,
            })
            logger.warning(
                "Derived REPORT_HEADER Level A for %s from T3 totals: %0.2f",
                m.strftime("%Y-%m"), val,
            )
    return new_rows


def _compute_statutory_transfers(panel: pd.DataFrame, level_a_var: str) -> List[Dict]:
    """Recompute Statutory Transfers = ECG Revenue - Level A - Level B."""
    statutory_var = "Statutory Transfers (GHS)"
    ecg_var = "ECG Revenue Reported (GHS)"
    level_b_var = "ECG Revenue Allocated to Level B (GHS)"

    rh = panel[(panel["company"] == "__REPORT__") & (panel["table_type"] == "REPORT_HEADER")]
    ecg_s = rh[rh["variable"] == ecg_var].groupby("report_month")["value"].sum()
    a_s = rh[rh["variable"] == level_a_var].groupby("report_month")["value"].sum()
    b_s = rh[rh["variable"] == level_b_var].groupby("report_month")["value"].sum()

    stat_rows = []
    for m in ecg_s.index:
        if m not in a_s.index or m not in b_s.index:
            continue
        stat = ecg_s.loc[m] - a_s.loc[m] - b_s.loc[m]
        if pd.notna(stat):
            stat_rows.append({
                "report_month": m,
                "company": "__REPORT__",
                "company_type": "Other",
                "table_type": "REPORT_HEADER",
                "variable": statutory_var,
                "currency": "GHS",
                "value": float(stat),
                "source_file": "",
                "is_derived": True,
            })
    return stat_rows


def _compute_implied_fx_rows(panel: pd.DataFrame, usd_var: str, ghs_var: str) -> pd.DataFrame:
    """Derive implied GHS/USD rate per company-month from T3 pairs."""
    t3_pairs = panel[
        (panel["table_type"] == "T3_LEVEL_A_PAYMENTS")
        & (panel["variable"].isin([usd_var, ghs_var]))
    ].copy()

    if t3_pairs.empty:
        return pd.DataFrame()

    piv_fx = t3_pairs.pivot_table(
        index=["report_month", "company"], columns="variable", values="value", aggfunc="sum"
    )
    if usd_var not in piv_fx.columns or ghs_var not in piv_fx.columns:
        return pd.DataFrame()

    fx = (piv_fx[ghs_var] / piv_fx[usd_var]).replace([np.inf, -np.inf], np.nan).dropna()
    if fx.empty:
        return pd.DataFrame()

    # FIX: name the Series before reset_index to avoid positional iloc assignment.
    fx.name = "value"
    fx_rows = fx.reset_index()
    fx_rows["company_type"] = fx_rows["company"].apply(classify_company_type)
    fx_rows["table_type"] = "IMPLIED_FX"
    fx_rows["variable"] = "Implied FX Rate (GHS/USD)"
    fx_rows["currency"] = "GHS/USD"
    fx_rows["source_file"] = ""
    fx_rows["is_derived"] = True
    return fx_rows[["report_month", "company", "company_type", "table_type",
                     "variable", "currency", "value", "source_file", "is_derived"]]

# =============================================================================
# 9) MAIN: build_panel_long
# =============================================================================

PANEL_COLUMNS = [
    "report_month", "company", "company_type", "table_type",
    "variable", "currency", "value", "source_file", "is_derived",
]

def build_panel_long(
    tables: list, header_df: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    frames, fx_summary_rows, fx_monthly_rows = _process_tables(tables)

    panel = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=PANEL_COLUMNS)
    panel = pd.concat([panel, header_metrics_to_long(header_df)], ignore_index=True)

    if "is_derived" not in panel.columns:
        panel["is_derived"] = False
    panel["is_derived"] = panel["is_derived"].fillna(False).astype(bool)

    usd_var = "Expected payment to level A (USD)"
    ghs_var = "Expected payment to level A (GHS)"
    level_a_var = "ECG Revenue Allocated to Level A (GHS)"
    statutory_var = "Statutory Transfers (GHS)"

    # Load BoG FX series
    fx_series = pd.Series(dtype=float)
    fx_label = "BoG monthly FX CSV: NOT LOADED"
    min_m = panel["report_month"].min()
    max_m = panel["report_month"].max()
    if pd.notna(min_m) and pd.notna(max_m):
        fx_series, fx_label = load_bog_monthly_fx(
            pd.to_datetime(min_m).strftime("%Y-%m"),
            pd.to_datetime(max_m).strftime("%Y-%m"),
            root_dir=_project_root(),
        )
        if fx_series.empty:
            logger.warning("%s. USD->GHS imputation will fall back to within-month implied FX.", fx_label)
        else:
            logger.info("Loaded FX series (%d months) from %s", len(fx_series), fx_label)

    # Impute missing GHS values
    derived_rows = _impute_ghs_from_usd(panel, fx_series, fx_label)
    if derived_rows:
        panel = pd.concat([panel, pd.DataFrame(derived_rows)], ignore_index=True)
        logger.warning("Filled %d missing T3 '%s' values.", len(derived_rows), ghs_var)

    # Backfill REPORT_HEADER Level A
    new_level_a = _derive_level_a_header(panel, ghs_var, level_a_var)
    if new_level_a:
        panel = pd.concat([panel, pd.DataFrame(new_level_a)], ignore_index=True)

    # Recompute Statutory Transfers (drop any stale rows first)
    panel = panel[~(
        (panel["company"] == "__REPORT__")
        & (panel["table_type"] == "REPORT_HEADER")
        & (panel["variable"] == statutory_var)
    )].copy()
    stat_rows = _compute_statutory_transfers(panel, level_a_var)
    if stat_rows:
        panel = pd.concat([panel, pd.DataFrame(stat_rows)], ignore_index=True)

    # Implied FX rows
    implied_fx = _compute_implied_fx_rows(panel, usd_var, ghs_var)
    if not implied_fx.empty:
        panel = pd.concat([panel, implied_fx], ignore_index=True)

    panel["is_derived"] = panel["is_derived"].fillna(False).astype(bool)
    panel = panel.sort_values(["report_month", "company", "table_type", "variable"]).reset_index(drop=True)

    return panel, pd.DataFrame(fx_summary_rows), pd.DataFrame(fx_monthly_rows)

# =============================================================================
# 10) Shortfalls
# =============================================================================

def compute_shortfalls_from_panel(panel_long: pd.DataFrame) -> pd.DataFrame:
    df = panel_long.copy()
    df = df[df["company"] != "__REPORT__"]

    exp_var = "Expected payment to level B (GHS)"
    act_var = "Actual payment to level B (GHS)"

    exp = (
        df[(df.table_type == "T4_LEVEL_B_SUMMARY") & (df.variable == exp_var)]
        .groupby(["report_month", "company"], as_index=False)["value"]
        .sum()
        .rename(columns={"value": "expected_ghs"})
    )

    act = (
        df[(df.table_type == "T4_LEVEL_B_SUMMARY") & (df.variable == act_var)]
        .groupby(["report_month", "company"], as_index=False)["value"]
        .sum()
        .rename(columns={"value": "actual_ghs"})
    )

    mof = (
        df[(df.table_type == "T2_MOF_TOPUP") & (df.variable == "MoF Top-Up (GHS)")]
        .groupby(["report_month", "company"], as_index=False)["value"]
        .sum()
        .rename(columns={"value": "mof_topup_ghs"})
    )

    out = (
        exp.merge(act, on=["report_month", "company"], how="outer")
           .merge(mof, on=["report_month", "company"], how="outer")
    )

    out["expected_ghs"] = out["expected_ghs"].fillna(0.0)
    out["actual_ghs"] = out["actual_ghs"].fillna(0.0)
    out["mof_topup_ghs"] = out["mof_topup_ghs"].fillna(0.0)

    out["shortfall_ecg_only_ghs"] = out["expected_ghs"] - out["actual_ghs"]
    out["shortfall_after_mof_ghs"] = out["expected_ghs"] - (out["actual_ghs"] + out["mof_topup_ghs"])

    out["company_type"] = out["company"].apply(classify_company_type)
    return out.sort_values(["report_month", "company"]).reset_index(drop=True)
