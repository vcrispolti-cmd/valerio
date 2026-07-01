# main.py
import os
import logging
from pathlib import Path

import pandas as pd

from logging_config import setup_logging
from extract import extract_tables, extract_intro_metrics
from transform import build_panel_long, compute_shortfalls_from_panel
from analyze import summarize_shortfalls, summarize_shortfalls_by_company_type


def find_pdfs(path: str):
    """Return sorted list of PDF paths in the given directory."""
    return sorted(str(p) for p in Path(path).glob("*.pdf"))


def main():
    project_root = os.path.dirname(os.path.abspath(__file__))
    pdf_dir = os.path.join(project_root, "CWM_reports")
    out_dir = os.path.join(project_root, "out")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    setup_logging(os.path.join(out_dir, "pipeline.log"))
    log = logging.getLogger("main")

    pdfs = find_pdfs(pdf_dir)
    if not pdfs:
        log.error("No PDFs found in %s", pdf_dir)
        return

    log.info("Found %d CWM reports", len(pdfs))

    # ------------------------------------------------------------------
    # Extract — track failures explicitly instead of silently dropping them
    # ------------------------------------------------------------------
    header_rows = []
    all_tables = []
    failed_pdfs = []

    for pdf in pdfs:
        fname = os.path.basename(pdf)
        log.info("Processing %s", fname)
        header_rows.append(extract_intro_metrics(pdf))
        try:
            all_tables.extend(extract_tables(pdf))
        except Exception as exc:
            log.error("Table extraction failed for %s: %s", fname, exc, exc_info=True)
            failed_pdfs.append(fname)

    if failed_pdfs:
        log.warning(
            "%d PDF(s) failed table extraction and were skipped: %s",
            len(failed_pdfs), ", ".join(failed_pdfs),
        )

    header_df = pd.DataFrame(header_rows)

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------
    panel_long, fx_summary, fx_monthly = build_panel_long(all_tables, header_df)

    if panel_long.empty:
        raise RuntimeError("panel_long is empty after processing")

    # ------------------------------------------------------------------
    # README sheet content
    # ------------------------------------------------------------------
    readme_df = pd.DataFrame({
        "Sheet name": [
            "CWM_panel",
            "FX_financing_summary",
            "FX_financing_monthly",
        ],
        "Description": [
            "Canonical monthly Cash Waterfall Mechanism (CWM) panel at company level. "
            "Includes T1–T4 tables, REPORT_HEADER rows, statutory transfers, and derived "
            "USD→GHS conversions where applicable.",

            "USD financing totals reported in CWM PDFs over multi-month periods "
            "(e.g. January–May 2025, June–September 2025), aggregated by beneficiary category "
            "(IPPs, Liquid Fuels, Gas Suppliers, etc.). Values are as reported in the PDFs.",

            "Monthly normalized equivalents of FX_financing_summary. "
            "Each multi-month total is evenly split across the months in the reported period. "
            "All rows in this sheet are derived (is_derived = True).",
        ],
        "Frequency": [
            "Monthly",
            "Multi-month (as reported)",
            "Monthly (derived)",
        ],
        "Unit of observation": [
            "Company",
            "Beneficiary category",
            "Beneficiary category",
        ],
        "Currency": [
            "GHS, USD, percentages",
            "USD",
            "USD",
        ],
        "Important notes": [
            "This is the primary dataset for CWM analysis and time-series work.",
            "These totals should NOT be interpreted as monthly payments and are not part of the CWM allocation cascade.",
            "Monthly values are mechanical allocations for time-series convenience only and do not represent actual payments.",
        ],
    })

    # ------------------------------------------------------------------
    # Save Excel
    # ------------------------------------------------------------------
    excel_path = os.path.join(out_dir, "panel_long.xlsx")
    with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
        readme_df.to_excel(writer, sheet_name="README", index=False)
        panel_long.to_excel(writer, sheet_name="CWM_panel", index=False)
        if not fx_summary.empty:
            fx_summary.to_excel(writer, sheet_name="FX_financing_summary", index=False)
        if not fx_monthly.empty:
            fx_monthly.to_excel(writer, sheet_name="FX_financing_monthly", index=False)

    log.info("Saved panel_long.xlsx with README and FX sheets")

    # ------------------------------------------------------------------
    # Save CSVs
    # ------------------------------------------------------------------
    panel_long.to_csv(os.path.join(out_dir, "panel_long.csv"), index=False)
    fx_summary.to_csv(os.path.join(out_dir, "fx_financing_summary.csv"), index=False)
    fx_monthly.to_csv(os.path.join(out_dir, "fx_financing_summary_monthly.csv"), index=False)

    # ------------------------------------------------------------------
    # Shortfalls
    # ------------------------------------------------------------------
    shortfalls = compute_shortfalls_from_panel(panel_long)
    shortfalls.to_csv(os.path.join(out_dir, "shortfalls_company_month.csv"), index=False)

    by_company, by_month = summarize_shortfalls(shortfalls)
    by_company.to_csv(os.path.join(out_dir, "shortfalls_by_company.csv"), index=False)
    by_month.to_csv(os.path.join(out_dir, "shortfalls_by_month.csv"), index=False)

    by_company_type = summarize_shortfalls_by_company_type(shortfalls)
    by_company_type.to_csv(os.path.join(out_dir, "shortfalls_by_company_type.csv"), index=False)

    log.info("Pipeline completed successfully.")


if __name__ == "__main__":
    main()
