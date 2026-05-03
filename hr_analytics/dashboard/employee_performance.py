from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from hr_analytics import metrics
from .components import apply_chart_layout, empty_state


FAIRNESS_TEXT = (
    "Raw case volume should not be used on its own to compare colleagues. Absence, annual leave, "
    "working pattern, case complexity, allocation method, and non-case duties all affect output. "
    "Use this page as context for workload discussion and service planning, not as a standalone judgement."
)


def _format_table(dataframe: pd.DataFrame) -> pd.DataFrame:
    formatted = dataframe.copy()
    if "first_response_compliance_rate" in formatted:
        formatted["first_response_compliance_rate"] = formatted["first_response_compliance_rate"].map(
            lambda value: "N/A" if pd.isna(value) else f"{value:.1%}"
        )
    numeric_columns = [
        "average_resolution_days",
        "median_resolution_days",
        "average_interactions_per_case",
        "sickness_days",
        "annual_leave_days",
        "total_unavailable_days",
        "estimated_available_working_days",
        "cases_per_available_working_day",
    ]
    for column in numeric_columns:
        if column in formatted:
            formatted[column] = formatted[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.1f}")
    return formatted.rename(
        columns={
            "employee_name": "Employee",
            "cases_handled": "Cases handled",
            "cases_closed_resolved": "Cases closed/resolved",
            "open_cases_assigned": "Open cases assigned",
            "first_response_compliance_rate": "First response compliance",
            "average_resolution_days": "Avg resolution days",
            "median_resolution_days": "Median resolution days",
            "average_interactions_per_case": "Avg interactions / case",
            "sickness_days": "Sickness days",
            "annual_leave_days": "Annual leave days",
            "total_unavailable_days": "Total unavailable days",
            "estimated_available_working_days": "Estimated available working days",
            "cases_per_available_working_day": "Cases / available working day",
        }
    )


def render(calls, absence, employees, filters):
    st.header("Employee Performance")
    st.info(FAIRNESS_TEXT)

    if calls.empty and absence.empty:
        empty_state()
        return

    employee_table = metrics.employee_metrics(
        calls,
        absence,
        employees,
        filters.start_date or calls["date_reported"].min(),
        filters.end_date or calls["date_reported"].max(),
    )
    st.dataframe(_format_table(employee_table), width="stretch", hide_index=True)

    st.divider()
    left, right = st.columns(2)
    with left:
        chart_data = employee_table.sort_values("cases_handled", ascending=True)
        fig = px.bar(chart_data, x="cases_handled", y="employee_name", orientation="h", title="Cases handled by employee")
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

        fig = px.bar(
            employee_table.sort_values("first_response_compliance_rate", ascending=True),
            x="first_response_compliance_rate",
            y="employee_name",
            orientation="h",
            title="First response compliance by employee",
        )
        fig.update_xaxes(tickformat=".0%")
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

    with right:
        fig = px.bar(
            employee_table.sort_values("cases_per_available_working_day", ascending=True),
            x="cases_per_available_working_day",
            y="employee_name",
            orientation="h",
            title="Cases per available working day",
        )
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

        absence_long = employee_table.melt(
            id_vars=["employee_name"],
            value_vars=["sickness_days", "annual_leave_days"],
            var_name="absence_type",
            value_name="days",
        )
        absence_long["absence_type"] = absence_long["absence_type"].map(
            {"sickness_days": "Sickness", "annual_leave_days": "Annual Leave"}
        )
        fig = px.bar(
            absence_long,
            x="days",
            y="employee_name",
            color="absence_type",
            orientation="h",
            title="Absence days by employee",
        )
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

    selected_employee = st.selectbox(
        "Category mix by selected employee",
        options=employee_table["employee_name"].tolist(),
        index=0 if not employee_table.empty else None,
    )
    if selected_employee:
        employee_calls = calls.loc[calls["handler_name"].eq(selected_employee)]
        category_mix = metrics.cases_by_category(employee_calls, top_n=12).sort_values("cases")
        if category_mix.empty:
            empty_state("No category data is available for the selected employee.")
        else:
            fig = px.bar(
                category_mix,
                x="cases",
                y="category_name",
                orientation="h",
                title=f"Category mix for {selected_employee}",
            )
            st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")
