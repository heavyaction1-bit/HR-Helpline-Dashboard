from __future__ import annotations

import plotly.express as px
import streamlit as st

from hr_analytics import metrics
from .components import apply_chart_layout, empty_state


def render(calls):
    st.header("Customer Query Analysis")
    st.caption("Demand themes, channel patterns, and categories that tend to need more time or interaction.")

    if calls.empty:
        empty_state()
        return

    left, right = st.columns(2)
    with left:
        top_categories = metrics.cases_by_category(calls, top_n=15).sort_values("cases")
        fig = px.bar(top_categories, x="cases", y="category_name", orientation="h", title="Top categories")
        st.plotly_chart(apply_chart_layout(fig, height=480), width="stretch")

        category_metrics = metrics.category_resolution_metrics(calls)
        longest = category_metrics.dropna(subset=["average_resolution_days"]).sort_values("average_resolution_days").tail(12)
        fig = px.bar(
            longest,
            x="average_resolution_days",
            y="category_name",
            orientation="h",
            title="Categories with longest average resolution time",
        )
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

        category_channel = (
            calls.groupby(["category_name", "channel_type"])
            .size()
            .reset_index(name="cases")
        )
        top_for_stack = top_categories.sort_values("cases", ascending=False).head(10)["category_name"]
        category_channel = category_channel.loc[category_channel["category_name"].isin(top_for_stack)]
        fig = px.bar(
            category_channel,
            x="category_name",
            y="cases",
            color="channel_type",
            title="Category by channel",
        )
        fig.update_xaxes(tickangle=-35)
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

    with right:
        trend = metrics.category_trend_by_month(calls, top_n=8)
        fig = px.line(
            trend,
            x="reported_month",
            y="cases",
            color="category_name",
            markers=True,
            title="Category trend by month",
        )
        st.plotly_chart(apply_chart_layout(fig, height=480), width="stretch")

        category_metrics = metrics.category_resolution_metrics(calls)
        interactions = category_metrics.dropna(subset=["average_interactions"]).sort_values("average_interactions").tail(12)
        fig = px.bar(
            interactions,
            x="average_interactions",
            y="category_name",
            orientation="h",
            title="Categories with highest average interactions",
        )
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

        category_status = calls.groupby(["category_name", "status"]).size().reset_index(name="cases")
        top_for_stack = metrics.cases_by_category(calls, top_n=10)["category_name"]
        category_status = category_status.loc[category_status["category_name"].isin(top_for_stack)]
        fig = px.bar(
            category_status,
            x="category_name",
            y="cases",
            color="status",
            title="Status by category",
        )
        fig.update_xaxes(tickangle=-35)
        st.plotly_chart(apply_chart_layout(fig, height=430), width="stretch")

    keywords = metrics.keyword_analysis(calls)
    st.subheader("Search / keyword analysis")
    if keywords.empty:
        st.info("No SR title or description text columns were found for keyword analysis.")
    else:
        fig = px.bar(
            keywords.sort_values("count"),
            x="count",
            y="keyword",
            orientation="h",
            title="Most common keywords in SR title/description fields",
        )
        st.plotly_chart(apply_chart_layout(fig, height=520), width="stretch")
