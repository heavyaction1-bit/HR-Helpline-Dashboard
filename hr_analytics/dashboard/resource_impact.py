from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from hr_analytics import metrics
from .components import apply_chart_layout, empty_state, format_number, format_percent, kpi_grid


INTERPRETATION_NOTE = (
    "This view shows operational association, not proof of cause. Annual leave, sickness, case mix, "
    "allocation rules, part-time patterns, vacancies, training, and non-call work can all affect handling outcomes."
)


def _employee_scope(employees: pd.DataFrame, filters) -> pd.DataFrame:
    if getattr(filters, "employees", None):
        return employees.loc[employees["employee_name"].astype(str).isin(filters.employees)].copy()
    return employees.copy()


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


def _resource_summary(impact: pd.DataFrame, calls: pd.DataFrame) -> list[tuple[str, object, str | None]]:
    total_working = impact["estimated_working_days"].sum()
    total_unavailable = impact["unavailable_days"].sum()
    total_available = impact["available_staff_days"].sum()
    absence_rate = total_unavailable / total_working if total_working else None
    cases_per_available_day = calls.shape[0] / total_available if total_available else 0

    return [
        ("Cases received", format_number(calls.shape[0]), None),
        ("Available staff days", format_number(total_available, 1), "Estimated Monday to Friday capacity after leave/sickness"),
        ("Unavailable days", format_number(total_unavailable, 1), "Sickness plus annual leave in the selected period"),
        ("Unavailable rate", format_percent(absence_rate), "Unavailable days as a share of estimated staff working days"),
        ("Cases / available day", format_number(cases_per_available_day, 2), "Demand adjusted for estimated resource availability"),
        ("Avg resolution days", format_number(metrics.average_resolution_days(calls), 1), None),
        ("Avg interactions / case", format_number(metrics.average_interactions(calls), 1), None),
        ("First response compliance", format_percent(metrics.first_response_compliance_rate(calls)), None),
    ]


def _format_impact_table(impact: pd.DataFrame) -> pd.DataFrame:
    table = impact.copy()
    table["month"] = pd.to_datetime(table["month"], errors="coerce").dt.strftime("%Y-%m")
    percent_columns = ["availability_rate", "absence_rate", "first_response_compliance_rate"]
    one_decimal_columns = [
        "estimated_working_days",
        "sickness_days",
        "annual_leave_days",
        "unavailable_days",
        "available_staff_days",
        "average_resolution_days",
        "median_resolution_days",
        "average_interactions",
    ]
    two_decimal_columns = ["cases_per_available_staff_day", "closed_per_available_staff_day", "pressure_index"]

    for column in percent_columns:
        if column in table:
            table[column] = table[column].map(lambda value: "N/A" if pd.isna(value) else f"{value:.1%}")
    for column in one_decimal_columns:
        if column in table:
            table[column] = table[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.1f}")
    for column in two_decimal_columns:
        if column in table:
            table[column] = table[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.2f}")

    display_columns = [
        "month",
        "employee_count",
        "cases_received",
        "cases_closed",
        "open_cases_reported",
        "sickness_days",
        "annual_leave_days",
        "unavailable_days",
        "available_staff_days",
        "absence_rate",
        "cases_per_available_staff_day",
        "average_resolution_days",
        "median_resolution_days",
        "average_interactions",
        "first_response_compliance_rate",
        "pressure_index",
    ]
    return table[[column for column in display_columns if column in table]].rename(
        columns={
            "month": "Month",
            "employee_count": "Employees in resource model",
            "cases_received": "Cases received",
            "cases_closed": "Cases closed",
            "open_cases_reported": "Open cases reported",
            "sickness_days": "Sickness days",
            "annual_leave_days": "Annual leave days",
            "unavailable_days": "Unavailable days",
            "available_staff_days": "Available staff days",
            "absence_rate": "Unavailable rate",
            "cases_per_available_staff_day": "Cases / available day",
            "average_resolution_days": "Avg resolution days",
            "median_resolution_days": "Median resolution days",
            "average_interactions": "Avg interactions",
            "first_response_compliance_rate": "First response compliance",
            "pressure_index": "Pressure index",
        }
    )


def render(calls: pd.DataFrame, absence: pd.DataFrame, employees: pd.DataFrame, filters) -> None:
    st.header("Resource Impact")
    st.caption("How annual leave and sickness relate to available resource, case demand, and handling outcomes.")
    st.info(INTERPRETATION_NOTE)

    start_date, end_date = _date_bounds(calls, absence, filters)
    if start_date is None or end_date is None:
        empty_state()
        return

    scoped_employees = _employee_scope(employees, filters)
    impact = metrics.monthly_resource_impact(calls, absence, scoped_employees, start_date, end_date)
    if impact.empty:
        empty_state()
        return

    if not getattr(filters, "employees", None):
        st.caption(
            "Resource model uses all employees found in call-handler and absence data. Use the Employee / handler filter to focus on a current resource pool."
        )

    kpi_grid(_resource_summary(impact, calls), columns=4)
    st.divider()

    left, right = st.columns(2)
    with left:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=impact["month"],
                y=impact["available_staff_days"],
                name="Available staff days",
                marker_color="#005EB8",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=impact["month"],
                y=impact["cases_received"],
                name="Cases received",
                mode="lines+markers",
                line=dict(color="#72246C"),
            ),
            secondary_y=True,
        )
        fig.update_layout(title="Available staff days vs cases received")
        fig.update_yaxes(title_text="Available staff days", secondary_y=False)
        fig.update_yaxes(title_text="Cases received", secondary_y=True)
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

        absence_mix = impact.melt(
            id_vars=["month"],
            value_vars=["sickness_days", "annual_leave_days"],
            var_name="absence_type",
            value_name="days",
        )
        absence_mix["absence_type"] = absence_mix["absence_type"].map(
            {"sickness_days": "Sickness", "annual_leave_days": "Annual Leave"}
        )
        fig = px.bar(
            absence_mix,
            x="month",
            y="days",
            color="absence_type",
            title="Unavailable days by type",
        )
        st.plotly_chart(apply_chart_layout(fig), width="stretch")

    with right:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(
                x=impact["month"],
                y=impact["cases_per_available_staff_day"],
                name="Cases / available day",
                mode="lines+markers",
                line=dict(color="#005EB8"),
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=impact["month"],
                y=impact["average_resolution_days"],
                name="Avg resolution days",
                mode="lines+markers",
                line=dict(color="#B3842F"),
            ),
            secondary_y=True,
        )
        fig.update_layout(title="Resource pressure and resolution time")
        fig.update_yaxes(title_text="Cases / available staff day", secondary_y=False)
        fig.update_yaxes(title_text="Avg resolution days", secondary_y=True)
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

        fig = px.scatter(
            impact,
            x="absence_rate",
            y="cases_per_available_staff_day",
            size="cases_received",
            hover_data={
                "month": "|%Y-%m",
                "cases_received": True,
                "available_staff_days": ":.1f",
                "average_resolution_days": ":.1f",
                "absence_rate": ":.1%",
            },
            title="Unavailable rate vs demand per available day",
        )
        fig.update_xaxes(tickformat=".0%", title="Unavailable rate")
        fig.update_yaxes(title="Cases / available staff day")
        st.plotly_chart(apply_chart_layout(fig), width="stretch")

    st.subheader("Highest resource pressure months")
    pressure = impact.sort_values("cases_per_available_staff_day", ascending=False).head(6)
    st.dataframe(_format_impact_table(pressure), width="stretch", hide_index=True)

    st.subheader("Monthly resource impact detail")
    st.dataframe(_format_impact_table(impact), width="stretch", hide_index=True)
