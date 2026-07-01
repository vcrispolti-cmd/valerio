# analyze.py

import pandas as pd
import numpy as np


REQUIRED_COLS = [
    "report_month",
    "company",
    "company_type",
    "expected_ghs",
    "actual_ghs",
    "mof_topup_ghs",
    "shortfall_ecg_only_ghs",
    "shortfall_after_mof_ghs",
]


def _ensure_columns(df: pd.DataFrame, cols, fill_value=0.0) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            out[c] = fill_value
    return out


def summarize_shortfalls(shortfalls: pd.DataFrame):
    """Returns (by_company, by_month)."""
    if shortfalls is None or shortfalls.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = shortfalls.copy()

    if "report_month" in df.columns:
        df["report_month"] = pd.to_datetime(df["report_month"], errors="coerce")

    if "company" in df.columns:
        df = df[df["company"].astype(str) != "__REPORT__"]

    df = _ensure_columns(df, REQUIRED_COLS)

    numeric_cols = [
        "expected_ghs",
        "actual_ghs",
        "mof_topup_ghs",
        "shortfall_ecg_only_ghs",
        "shortfall_after_mof_ghs",
    ]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    by_company = (
        df.groupby("company", as_index=False)
          .agg(
              company_type=("company_type", "first"),
              total_expected_ghs=("expected_ghs", "sum"),
              total_actual_ghs=("actual_ghs", "sum"),
              total_mof_topup_ghs=("mof_topup_ghs", "sum"),
              total_shortfall_ecg_only_ghs=("shortfall_ecg_only_ghs", "sum"),
              total_shortfall_after_mof_ghs=("shortfall_after_mof_ghs", "sum"),
              months_reported=("report_month", "nunique"),
          )
          .sort_values("total_shortfall_ecg_only_ghs", ascending=False)
    )

    by_month = (
        df.groupby("report_month", as_index=False)
          .agg(
              total_expected_ghs=("expected_ghs", "sum"),
              total_actual_ghs=("actual_ghs", "sum"),
              total_mof_topup_ghs=("mof_topup_ghs", "sum"),
              total_shortfall_ecg_only_ghs=("shortfall_ecg_only_ghs", "sum"),
              total_shortfall_after_mof_ghs=("shortfall_after_mof_ghs", "sum"),
          )
          .sort_values("report_month")
    )

    return by_company, by_month


def summarize_shortfalls_by_company_type(shortfalls: pd.DataFrame):
    """SOE / IPP / Fuel Supplier aggregation."""
    if shortfalls is None or shortfalls.empty:
        return pd.DataFrame()

    df = shortfalls.copy()
    df = _ensure_columns(df, REQUIRED_COLS)

    for c in [
        "expected_ghs",
        "actual_ghs",
        "mof_topup_ghs",
        "shortfall_ecg_only_ghs",
        "shortfall_after_mof_ghs",
    ]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    return (
        df.groupby("company_type", as_index=False)
          .agg(
              total_expected_ghs=("expected_ghs", "sum"),
              total_actual_ghs=("actual_ghs", "sum"),
              total_mof_topup_ghs=("mof_topup_ghs", "sum"),
              total_shortfall_ecg_only_ghs=("shortfall_ecg_only_ghs", "sum"),
              total_shortfall_after_mof_ghs=("shortfall_after_mof_ghs", "sum"),
              companies=("company", "nunique"),
          )
          .sort_values("total_shortfall_ecg_only_ghs", ascending=False)
    )


def top_company_month_shortfalls(shortfalls: pd.DataFrame, n=10, after_mof=False):
    if shortfalls is None or shortfalls.empty:
        return pd.DataFrame()

    df = shortfalls.copy()
    df = _ensure_columns(df, REQUIRED_COLS)

    key = "shortfall_after_mof_ghs" if after_mof else "shortfall_ecg_only_ghs"
    for c in ["expected_ghs", "actual_ghs", "mof_topup_ghs", key]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    return (
        df.sort_values(key, ascending=False)
          .head(n)
          [["report_month", "company", "company_type",
            "expected_ghs", "actual_ghs", "mof_topup_ghs", key]]
    )
