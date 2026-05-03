from __future__ import annotations

import plotly.express as px
import streamlit as st

from hr_analytics import metrics
from .components import apply_chart_layout, empty_state


def render(calls, absence, employees, filters):
    st.header("Absence and Leave")
    st.caption("Sickness, annual leave, estimated availability, and demand context.")

    if absence.empty:
        empty_state("No absence or leave records are available for the current filters.")
        return

    absence_summary = metrics.absence_metrics(absence)
    left, right = st.columns(2)
    with left:
        fig = px.bar(
            absence_summary.sort_values("sickness_days"),
            x="sickness_days",
            y="employee_name",
            orientation="h",
            title="Sickness days by employee",
        )
        st.plotly_chart(apply_chart_layout(fig, height=420), width="stretch")

        monthly_absence = metrics.absence_by_month(absence)
        fig = px.bar(
            monthly_absence,
            x="month",
            y="days",
            color="absence_type",
            title="Total unavailable days by month",
        )
        st.plotly_chart(apply_chart_layout(fig), width="stretch")

    with right:
        fig = px.bar(
            absence_summary.sort_values("annual_leave_days"),
            x="annual_leave_days",
            y="employee_name",
            orientation="h",
            title="Annual leave days by employee",
        )
        st.plotly_chart(apply_chart_layout(fig, height=420), width="stretch")

        availability = metrics.team_availability_by_month(absence, employees, filters.start_date, filters.end_date)
        fig = px.line(
            availability,
            x="month",
            y=["estimated_working_days", "available_staff_days"],
            markers=True,
            title="Team availability by month",
        )
        st.plotly_chart(apply_chart_layout(fig), width="stretch")

    availability = metrics.team_availability_by_month(absence, employees, filters.start_date, filters.end_date)
    received = metrics.cases_by_month(calls).rename(columns={"reported_month": "month", "cases": "cases_received"})
    demand_context = availability.merge(received, on="month", how="left").fillna({"cases_received": 0})
    fig = px.bar(
        demand_context,
        x="month",
        y="cases_received",
        title="Cases received vs available staff days by month",
    )
    fig.add_scatter(
        x=demand_context["month"],
        y=demand_context["available_staff_days"],
        mode="lines+markers",
        name="Available staff days",
        yaxis="y2",
    )
    fig.update_layout(
        yaxis_title="Cases received",
        yaxis2=dict(title="Available staff days", overlaying="y", side="right"),
    )
    st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")
