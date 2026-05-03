from __future__ import annotations

import pandas as pd
import streamlit as st

from hr_analytics import metrics
from .components import format_number, kpi_grid


def _problem_rows(calls: pd.DataFrame, mask: pd.Series, columns: list[str]) -> pd.DataFrame:
    available_columns = [column for column in columns if column in calls.columns]
    return calls.loc[mask, available_columns].head(50)


def render(calls, metadata):
    st.header("Data Quality")
    st.caption("Checks to help spot loading issues, missing fields, duplicates, and date problems.")

    checks = metrics.data_quality_checks(calls, metadata)
    date_min = checks["date_min"]
    date_max = checks["date_max"]
    date_range = "N/A"
    if pd.notna(date_min) and pd.notna(date_max):
        date_range = f"{date_min.date()} to {date_max.date()}"

    kpi_grid(
        [
            ("Missing reported date", format_number(checks["missing_reported_date"]), None),
            ("Missing handler", format_number(checks["missing_handler"]), None),
            ("Missing category", format_number(checks["missing_category"]), None),
            ("Invalid resolution date", format_number(checks["invalid_resolution_date"]), None),
            ("Negative resolution duration", format_number(checks["negative_resolution_duration"]), None),
            ("Duplicate SR numbers", format_number(checks["duplicate_sr_numbers"]), None),
            ("Date range", date_range, None),
        ],
        columns=3,
    )

    st.subheader("Expected columns")
    missing_columns = checks.get("expected_columns_missing", [])
    if missing_columns:
        st.warning("Expected columns not found: " + ", ".join(missing_columns))
    else:
        st.success("All expected SR Data columns were found or mapped.")

    st.subheader("Rows loaded from workbook")
    source_stats = checks.get("source_stats", {})
    if source_stats:
        stats_rows = []
        for sheet_name, stats in source_stats.items():
            stats_rows.append(
                {
                    "Sheet": sheet_name,
                    "Rows loaded": stats.get("rows_loaded", 0),
                    "Columns loaded": stats.get("columns_loaded", 0),
                }
            )
        st.dataframe(pd.DataFrame(stats_rows), width="stretch", hide_index=True)
    else:
        st.info("No workbook load metadata is available in the database.")

    st.subheader("Problem row samples")
    columns = ["sr_number", "date_reported", "handler_name", "status", "category_name", "resolution_date", "resolution_days"]
    expanders = {
        "Rows with missing reported date": calls["date_reported"].isna() if "date_reported" in calls else pd.Series(dtype="bool"),
        "Rows with missing handler": calls.get("handler_missing", pd.Series(False, index=calls.index)).fillna(False).astype(bool),
        "Rows with missing category": calls.get("category_missing", pd.Series(False, index=calls.index)).fillna(False).astype(bool),
        "Rows with invalid resolution date": calls.get("resolution_date_invalid", pd.Series(False, index=calls.index)).fillna(False).astype(bool),
        "Rows with negative resolution duration": calls.get("negative_resolution_duration", pd.Series(False, index=calls.index)).fillna(False).astype(bool),
        "Duplicate SR numbers": calls["sr_number"].duplicated(keep=False) if "sr_number" in calls else pd.Series(dtype="bool"),
    }
    for title, mask in expanders.items():
        with st.expander(title):
            sample = _problem_rows(calls, mask, columns)
            if sample.empty:
                st.write("No rows found.")
            else:
                st.dataframe(sample, width="stretch", hide_index=True)
