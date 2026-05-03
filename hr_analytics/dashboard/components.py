from __future__ import annotations

import html

import plotly.express as px
import streamlit as st


COLOR_SEQUENCE = ["#005EB8", "#72246C", "#00857A", "#4B5563", "#B3842F", "#7A869A", "#2F5D62"]


def configure_page_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.6rem;
            padding-bottom: 2rem;
        }
        .prototype-note {
            background: #eef4fb;
            border-left: 4px solid #005EB8;
            padding: 0.8rem 1rem;
            border-radius: 6px;
            color: #172033;
        }
        .kpi-card {
            background: #ffffff;
            border: 1px solid #d9dee7;
            border-radius: 8px;
            padding: 0.9rem 1rem;
            min-height: 104px;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
        }
        .kpi-label {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0;
            color: #526071;
            margin-bottom: 0.35rem;
        }
        .kpi-value {
            font-size: 1.75rem;
            line-height: 1.15;
            font-weight: 700;
            color: #172033;
        }
        .kpi-help {
            font-size: 0.8rem;
            color: #667085;
            margin-top: 0.25rem;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #d9dee7;
            border-radius: 8px;
            padding: 0.75rem 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def plotly_template():
    template = px.defaults.template or "plotly_white"
    px.defaults.color_discrete_sequence = COLOR_SEQUENCE
    return template


def apply_chart_layout(fig, height: int = 360):
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=20, r=20, t=48, b=24),
        legend_title_text="",
        font=dict(color="#172033"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def format_number(value: object, decimals: int = 0) -> str:
    if value is None:
        return "N/A"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if decimals == 0:
        return f"{number:,.0f}"
    return f"{number:,.{decimals}f}"


def format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1%}"


def kpi_card(label: str, value: object, help_text: str | None = None) -> None:
    safe_label = html.escape(label)
    safe_value = html.escape(str(value))
    help_html = f'<div class="kpi-help">{html.escape(help_text)}</div>' if help_text else ""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{safe_label}</div>
            <div class="kpi-value">{safe_value}</div>
            {help_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_grid(items: list[tuple[str, object, str | None]], columns: int = 4) -> None:
    for start in range(0, len(items), columns):
        cols = st.columns(columns)
        for col, item in zip(cols, items[start : start + columns]):
            with col:
                kpi_card(*item)


def empty_state(message: str = "No data is available for the current filters.") -> None:
    st.info(message)

