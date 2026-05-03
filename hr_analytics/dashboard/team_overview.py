from __future__ import annotations

import plotly.express as px
import streamlit as st

from hr_analytics import metrics
from .components import apply_chart_layout, empty_state, format_number, format_percent, kpi_grid


def render(calls):
    st.header("Team Overview")
    st.caption("Whole-team demand, resolution flow, channel mix, and first response compliance.")

    if calls.empty:
        empty_state()
        return

    kpi_grid(
        [
            ("Total cases", format_number(metrics.total_cases(calls)), None),
            ("Open cases", format_number(metrics.open_cases(calls)), None),
            ("Closed / resolved", format_number(metrics.closed_cases(calls)), None),
            ("First response compliance", format_percent(metrics.first_response_compliance_rate(calls)), None),
            ("Avg resolution days", format_number(metrics.average_resolution_days(calls), 1), None),
            ("Median resolution days", format_number(metrics.median_resolution_days(calls), 1), None),
            ("Avg interactions / case", format_number(metrics.average_interactions(calls), 1), None),
            ("Cases received this month", format_number(metrics.cases_received_this_month(calls)), "Latest month in filtered data"),
            ("Cases closed this month", format_number(metrics.cases_closed_this_month(calls)), "Latest month in filtered data"),
        ],
        columns=3,
    )

    st.divider()
    left, right = st.columns(2)
    with left:
        monthly = metrics.cases_by_month(calls)
        fig = px.line(monthly, x="reported_month", y="cases", markers=True, title="Cases received by month")
        st.plotly_chart(apply_chart_layout(fig), width="stretch")

        status_counts = calls.groupby("status").size().reset_index(name="cases").sort_values("cases", ascending=False)
        fig = px.bar(status_counts, x="status", y="cases", title="Cases by status")
        st.plotly_chart(apply_chart_layout(fig), width="stretch")

        resolution = metrics.monthly_resolution_average(calls)
        fig = px.line(
            resolution,
            x="reported_month",
            y="average_resolution_days",
            markers=True,
            title="Average resolution days by month",
        )
        st.plotly_chart(apply_chart_layout(fig), width="stretch")

    with right:
        channel = metrics.cases_by_channel(calls)
        fig = px.bar(channel, x="channel_type", y="cases", title="Cases by channel")
        st.plotly_chart(apply_chart_layout(fig), width="stretch")

        top_categories = metrics.cases_by_category(calls, top_n=10).sort_values("cases")
        fig = px.bar(
            top_categories,
            x="cases",
            y="category_name",
            orientation="h",
            title="Top 10 categories",
        )
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

        compliance = metrics.monthly_compliance_trend(calls)
        fig = px.line(
            compliance,
            x="reported_month",
            y="first_response_compliance_rate",
            markers=True,
            title="First response compliance trend by month",
        )
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(apply_chart_layout(fig), width="stretch")
