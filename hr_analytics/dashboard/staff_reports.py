from __future__ import annotations

import html
import re

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import streamlit as st

from hr_analytics import metrics
from .components import apply_chart_layout, empty_state, format_number, format_percent, kpi_grid


REPORT_NOTE = (
    "These reports are intended for transparent workload conversations. They should be read with context: "
    "case complexity, allocation method, working pattern, absence, leave, vacancies, training, and non-case work "
    "all affect the numbers."
)


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "staff_member"


def _date_bounds(calls: pd.DataFrame, absence: pd.DataFrame, filters) -> tuple[object, object]:
    if filters.start_date and filters.end_date:
        return filters.start_date, filters.end_date

    dates = []
    if not calls.empty and "date_reported" in calls:
        dates.extend(pd.to_datetime(calls["date_reported"], errors="coerce").dropna().tolist())
    if not absence.empty and "date" in absence:
        dates.extend(pd.to_datetime(absence["date"], errors="coerce").dropna().tolist())
    if not dates:
        return None, None
    return min(dates), max(dates)


def _employee_options(employees: pd.DataFrame, filters) -> list[str]:
    all_names = employees.get("employee_name", pd.Series(dtype="string")).dropna().astype(str).tolist()
    if getattr(filters, "employees", None):
        return [name for name in all_names if name in filters.employees]
    return all_names


def _staff_absence(absence: pd.DataFrame, employee_name: str) -> pd.DataFrame:
    if absence.empty:
        return absence.copy()
    employee_column = "matched_employee_name" if "matched_employee_name" in absence else "employee_name"
    return absence.loc[absence[employee_column].astype(str).eq(employee_name)].copy()


def _staff_monthly(employee_calls: pd.DataFrame, employee_absence: pd.DataFrame) -> pd.DataFrame:
    if employee_calls.empty:
        monthly = pd.DataFrame(columns=["month", "cases_received", "cases_closed", "average_resolution_days", "average_interactions", "first_response_compliance_rate"])
    else:
        source = employee_calls.dropna(subset=["reported_month"]).copy()
        source["is_closed"] = source["status"].map(metrics.is_closed_status)
        monthly = (
            source.groupby("reported_month")
            .agg(
                cases_received=("sr_number", "count"),
                cases_closed=("is_closed", "sum"),
                average_resolution_days=("resolution_days", "mean"),
                average_interactions=("number_of_interactions", "mean"),
                first_response_compliance_rate=("first_response_compliant", "mean"),
            )
            .reset_index()
            .rename(columns={"reported_month": "month"})
        )

    if employee_absence.empty:
        monthly["sickness_days"] = 0.0
        monthly["annual_leave_days"] = 0.0
        return monthly.sort_values("month") if "month" in monthly else monthly

    absence_month = metrics.absence_by_month(employee_absence)
    absence_pivot = (
        absence_month.pivot_table(index="month", columns="absence_type", values="days", aggfunc="sum", fill_value=0)
        .reset_index()
        .rename(columns={"Sickness": "sickness_days", "Annual Leave": "annual_leave_days"})
    )
    for column in ("sickness_days", "annual_leave_days"):
        if column not in absence_pivot:
            absence_pivot[column] = 0.0

    if monthly.empty:
        monthly = absence_pivot[["month", "sickness_days", "annual_leave_days"]].copy()
        for column in ("cases_received", "cases_closed", "average_resolution_days", "average_interactions", "first_response_compliance_rate"):
            monthly[column] = 0 if column in ("cases_received", "cases_closed") else pd.NA
    else:
        monthly = monthly.merge(absence_pivot[["month", "sickness_days", "annual_leave_days"]], on="month", how="outer")
    monthly[["cases_received", "cases_closed", "sickness_days", "annual_leave_days"]] = monthly[
        ["cases_received", "cases_closed", "sickness_days", "annual_leave_days"]
    ].fillna(0)
    return monthly.sort_values("month")


def _report_row(employee_table: pd.DataFrame, employee_name: str) -> pd.Series:
    row = employee_table.loc[employee_table["employee_name"].astype(str).eq(employee_name)]
    if row.empty:
        return pd.Series(dtype="object")
    return row.iloc[0]


def _summary_csv(employee_table: pd.DataFrame) -> bytes:
    export = employee_table.rename(
        columns={
            "employee_name": "Employee",
            "cases_handled": "Cases handled",
            "cases_closed_resolved": "Cases closed/resolved",
            "open_cases_assigned": "Open cases assigned",
            "first_response_compliance_rate": "First response compliance rate",
            "average_resolution_days": "Average resolution days",
            "median_resolution_days": "Median resolution days",
            "average_interactions_per_case": "Average interactions per case",
            "sickness_days": "Sickness days",
            "annual_leave_days": "Annual leave days",
            "total_unavailable_days": "Total unavailable days",
            "estimated_available_working_days": "Estimated available working days",
            "cases_per_available_working_day": "Cases per available working day",
        }
    )
    return export.to_csv(index=False).encode("utf-8")


def _staff_html_report(
    employee_name: str,
    row: pd.Series,
    monthly: pd.DataFrame,
    category_mix: pd.DataFrame,
    channel_mix: pd.DataFrame,
    start_date: object,
    end_date: object,
) -> bytes:
    period = f"{pd.to_datetime(start_date).date()} to {pd.to_datetime(end_date).date()}"
    monthly_table = monthly.copy()
    if not monthly_table.empty and "month" in monthly_table:
        monthly_table["month"] = pd.to_datetime(monthly_table["month"], errors="coerce").dt.strftime("%Y-%m")

    sections = [
        ("Monthly detail", monthly_table),
        ("Category mix", category_mix),
        ("Channel mix", channel_mix),
    ]
    section_html = []
    for title, dataframe in sections:
        if dataframe.empty:
            section_html.append(f"<h2>{html.escape(title)}</h2><p>No data available.</p>")
        else:
            section_html.append(f"<h2>{html.escape(title)}</h2>{dataframe.to_html(index=False, border=0, escape=True)}")

    def metric(label: str, value: object) -> str:
        return f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>"

    html_doc = f"""
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>HR Helpline staff report - {html.escape(employee_name)}</title>
      <style>
        body {{ font-family: Arial, sans-serif; color: #172033; margin: 32px; line-height: 1.45; }}
        h1 {{ color: #005EB8; margin-bottom: 0; }}
        h2 {{ margin-top: 28px; color: #172033; }}
        .note {{ background: #eef4fb; border-left: 4px solid #005EB8; padding: 12px 14px; border-radius: 6px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
        th, td {{ border: 1px solid #d9dee7; padding: 8px; text-align: left; }}
        th {{ background: #f3f5f8; }}
      </style>
    </head>
    <body>
      <h1>HR Helpline staff report</h1>
      <p><strong>Staff member:</strong> {html.escape(employee_name)}<br>
      <strong>Period:</strong> {html.escape(period)}</p>
      <p class="note">{html.escape(REPORT_NOTE)}</p>
      <h2>Summary</h2>
      <table>
        {metric("Cases handled", format_number(row.get("cases_handled")))}
        {metric("Cases closed/resolved", format_number(row.get("cases_closed_resolved")))}
        {metric("Open cases assigned", format_number(row.get("open_cases_assigned")))}
        {metric("First response compliance", format_percent(row.get("first_response_compliance_rate") if pd.notna(row.get("first_response_compliance_rate")) else None))}
        {metric("Average resolution days", format_number(row.get("average_resolution_days"), 1))}
        {metric("Median resolution days", format_number(row.get("median_resolution_days"), 1))}
        {metric("Average interactions per case", format_number(row.get("average_interactions_per_case"), 1))}
        {metric("Sickness days", format_number(row.get("sickness_days"), 1))}
        {metric("Annual leave days", format_number(row.get("annual_leave_days"), 1))}
        {metric("Estimated available working days", format_number(row.get("estimated_available_working_days"), 1))}
        {metric("Cases per available working day", format_number(row.get("cases_per_available_working_day"), 2))}
      </table>
      {"".join(section_html)}
    </body>
    </html>
    """
    return html_doc.encode("utf-8")


def _kpi_items(row: pd.Series) -> list[tuple[str, object, str | None]]:
    return [
        ("Cases handled", format_number(row.get("cases_handled")), None),
        ("Closed / resolved", format_number(row.get("cases_closed_resolved")), None),
        ("Open assigned", format_number(row.get("open_cases_assigned")), None),
        (
            "First response compliance",
            format_percent(row.get("first_response_compliance_rate") if pd.notna(row.get("first_response_compliance_rate")) else None),
            None,
        ),
        ("Avg resolution days", format_number(row.get("average_resolution_days"), 1), None),
        ("Median resolution days", format_number(row.get("median_resolution_days"), 1), None),
        ("Avg interactions / case", format_number(row.get("average_interactions_per_case"), 1), None),
        ("Sickness days", format_number(row.get("sickness_days"), 1), None),
        ("Annual leave days", format_number(row.get("annual_leave_days"), 1), None),
        ("Available working days", format_number(row.get("estimated_available_working_days"), 1), "Estimated Monday to Friday minus sickness and annual leave"),
        ("Cases / available day", format_number(row.get("cases_per_available_working_day"), 2), None),
    ]


def render(calls: pd.DataFrame, absence: pd.DataFrame, employees: pd.DataFrame, filters) -> None:
    st.header("Staff Reports")
    st.caption("Preview and export individual performance reports for selected core team members.")
    st.info(REPORT_NOTE)

    start_date, end_date = _date_bounds(calls, absence, filters)
    employee_names = _employee_options(employees, filters)
    if start_date is None or end_date is None or not employee_names:
        empty_state("Select team members and a date range to create staff reports.")
        return

    report_employees = employees.loc[employees["employee_name"].astype(str).isin(employee_names)].copy()
    employee_table = metrics.employee_metrics(calls, absence, report_employees, start_date, end_date)
    if employee_table.empty:
        empty_state("No staff report data is available for the current filters.")
        return

    st.download_button(
        "Download all selected staff summaries (CSV)",
        data=_summary_csv(employee_table),
        file_name="hr_helpline_staff_summary.csv",
        mime="text/csv",
    )

    selected_employee = st.selectbox("Select staff member", employee_table["employee_name"].tolist())
    row = _report_row(employee_table, selected_employee)
    employee_calls = calls.loc[calls["handler_name"].astype(str).eq(selected_employee)].copy()
    employee_absence = _staff_absence(absence, selected_employee)
    monthly = _staff_monthly(employee_calls, employee_absence)

    kpi_grid(_kpi_items(row), columns=4)

    category_mix = metrics.cases_by_category(employee_calls, top_n=12)
    channel_mix = metrics.cases_by_channel(employee_calls)

    html_report = _staff_html_report(
        selected_employee,
        row,
        monthly,
        category_mix,
        channel_mix,
        start_date,
        end_date,
    )
    st.download_button(
        "Download selected staff report (HTML)",
        data=html_report,
        file_name=f"hr_helpline_staff_report_{_slug(selected_employee)}.html",
        mime="text/html",
    )

    st.divider()
    left, right = st.columns(2)
    with left:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        if not monthly.empty:
            fig.add_trace(
                go.Bar(x=monthly["month"], y=monthly["cases_received"], name="Cases received", marker_color="#005EB8"),
                secondary_y=False,
            )
            fig.add_trace(
                go.Scatter(
                    x=monthly["month"],
                    y=monthly["average_resolution_days"],
                    name="Avg resolution days",
                    mode="lines+markers",
                    line=dict(color="#B3842F"),
                ),
                secondary_y=True,
            )
        fig.update_layout(title=f"Monthly cases and resolution time for {selected_employee}")
        fig.update_yaxes(title_text="Cases", secondary_y=False)
        fig.update_yaxes(title_text="Avg resolution days", secondary_y=True)
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

        if category_mix.empty:
            st.info("No category data for this staff member.")
        else:
            fig = px.bar(
                category_mix.sort_values("cases"),
                x="cases",
                y="category_name",
                orientation="h",
                title="Category mix",
            )
            st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

    with right:
        absence_month = monthly.melt(
            id_vars=["month"],
            value_vars=[column for column in ("sickness_days", "annual_leave_days") if column in monthly],
            var_name="absence_type",
            value_name="days",
        )
        absence_month["absence_type"] = absence_month["absence_type"].map(
            {"sickness_days": "Sickness", "annual_leave_days": "Annual Leave"}
        )
        fig = px.bar(absence_month, x="month", y="days", color="absence_type", title="Leave and sickness by month")
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

        if channel_mix.empty:
            st.info("No channel data for this staff member.")
        else:
            fig = px.bar(channel_mix, x="channel_type", y="cases", title="Channel mix")
            st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

    st.subheader("Monthly report detail")
    display_monthly = monthly.copy()
    if not display_monthly.empty:
        display_monthly["month"] = pd.to_datetime(display_monthly["month"], errors="coerce").dt.strftime("%Y-%m")
    st.dataframe(display_monthly, width="stretch", hide_index=True)
