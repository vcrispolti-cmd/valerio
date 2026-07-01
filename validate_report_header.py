#!/usr/bin/env python
"""
Validate REPORT_HEADER accounting identity:

ECG Revenue Reported
= Level A Allocation
+ Level B Allocation
+ Statutory Transfers
"""

import argparse
import sys

import pandas as pd

VARS = [
    "ECG Revenue Reported (GHS)",
    "ECG Revenue Allocated to Level A (GHS)",
    "ECG Revenue Allocated to Level B (GHS)",
    "Statutory Transfers (GHS)",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="out/panel_long.csv")
    ap.add_argument("--tol", type=float, default=0.5)
    args = ap.parse_args()

    df = pd.read_csv(args.panel)
    df["report_month"] = pd.to_datetime(df["report_month"], errors="coerce")

    rh = df[(df.company == "__REPORT__") & (df.table_type == "REPORT_HEADER")]
    piv = rh.pivot_table(
        index="report_month",
        columns="variable",
        values="value",
        aggfunc="sum",
    )

    missing = set(VARS) - set(piv.columns)
    if missing:
        print("Missing variables:", missing, file=sys.stderr)
        sys.exit(2)

    resid = piv[VARS[0]] - piv[VARS[1]] - piv[VARS[2]] - piv[VARS[3]]
    bad = resid.abs() > args.tol

    for m, v in resid.items():
        print(f"{m:%Y-%m} residual: {v:,.2f}")

    if bad.any():
        print("\nIdentity FAILED for some months")
        sys.exit(1)

    print("\nIdentity holds for all months")
    sys.exit(0)


if __name__ == "__main__":
    main()
