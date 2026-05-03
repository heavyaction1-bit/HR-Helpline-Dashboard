from __future__ import annotations

import streamlit as st

from hr_analytics.config import APP_NAME, ORGANISATION_NAME
from hr_analytics.data_loader import load_raw_workbook
from hr_analytics.database import (
    clear_database,
    get_engine,
    initialise_database,
    load_data_from_database,
    save_model_frames,
)
from hr_analytics.dashboard import (
    absence_leave,
    chatgpt_insights,
    customer_query,
    data_quality,
    employee_performance,
    resource_impact,
    staff_reports,
    team_overview,
)
from hr_analytics.dashboard.components import configure_page_style
from hr_analytics.dashboard.filters import (
    apply_filters,
    apply_name_aliases,
    apply_team_selection,
    render_name_matching,
    render_sidebar_filters,
    render_team_selection,
)
from hr_analytics.sample_data import generate_sample_raw_workbook
from hr_analytics.security import get_current_user
from hr_analytics.transformations import transform_workbook


st.set_page_config(
    page_title=APP_NAME,
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)
configure_page_style()


def process_and_store(raw_sr_data, raw_sickness, raw_annual_leave, source_stats, label: str) -> None:
    with st.spinner(f"Cleaning and loading {label}..."):
        model = transform_workbook(raw_sr_data, raw_sickness, raw_annual_leave, source_stats)
        save_model_frames(model.calls, model.absence, model.employees, model.metadata)
    st.success(f"Loaded {len(model.calls):,} cases, {len(model.absence):,} absence/leave records, and {len(model.employees):,} employees.")


def sidebar_data_controls() -> None:
    st.sidebar.title("HR Helpline Analytics")
    st.sidebar.caption(f"{ORGANISATION_NAME} prototype")
    st.sidebar.markdown(
        "Local development only. Uploads are cleaned and stored in a local SQLite database."
    )

    uploaded_file = st.sidebar.file_uploader(
        "Upload Excel workbook",
        type=["xlsx", "xlsm"],
        help="Expected sheets: SR Data, Sickness, Annual leave",
    )
    if uploaded_file is not None and st.sidebar.button("Load uploaded workbook", type="primary"):
        try:
            loaded = load_raw_workbook(uploaded_file.getvalue())
            process_and_store(
                loaded.sr_data,
                loaded.sickness,
                loaded.annual_leave,
                loaded.stats,
                uploaded_file.name,
            )
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"Could not load workbook: {exc}")

    if st.sidebar.button("Load sample data"):
        sr_data, sickness, annual_leave = generate_sample_raw_workbook()
        source_stats = {
            "SR Data": {"rows_loaded": len(sr_data), "columns_loaded": len(sr_data.columns), "columns": list(sr_data.columns)},
            "Sickness": {"rows_loaded": len(sickness), "columns_loaded": len(sickness.columns), "columns": list(sickness.columns)},
            "Annual leave": {"rows_loaded": len(annual_leave), "columns_loaded": len(annual_leave.columns), "columns": list(annual_leave.columns)},
        }
        process_and_store(sr_data, sickness, annual_leave, source_stats, "sample data")
        st.rerun()

    if st.sidebar.button("Clear local database"):
        clear_database()
        st.sidebar.success("Local database cleared.")
        st.rerun()


def render_empty_state() -> None:
    st.title(APP_NAME)
    st.subheader(ORGANISATION_NAME)
    st.markdown(
        """
        <div class="prototype-note">
        Upload an Excel workbook with <strong>SR Data</strong>, <strong>Sickness</strong>, and
        <strong>Annual leave</strong> sheets, or load sample data from the sidebar to explore the dashboard.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.write(
        "This prototype keeps data local, uses SQLite for the first database layer, and has a placeholder user context so authentication and permissions can be added later."
    )


def main() -> None:
    initialise_database(get_engine())
    sidebar_data_controls()

    calls, absence, employees, metadata = load_data_from_database()
    current_user = get_current_user()

    if calls.empty:
        render_empty_state()
        return

    st.title(APP_NAME)
    st.caption(f"{ORGANISATION_NAME} | {current_user.display_name}")
    st.markdown(
        """
        <div class="prototype-note">
        Prototype only: do not use this as a live HR performance management system without authentication,
        role-based access, data protection review, and agreed interpretation guidance.
        </div>
        """,
        unsafe_allow_html=True,
    )

    alias_map = render_name_matching(calls, absence, employees)
    matched_calls, matched_absence, matched_employees = apply_name_aliases(calls, absence, employees, alias_map)

    selected_team = render_team_selection(matched_calls, matched_employees)
    team_calls, team_absence, team_employees = apply_team_selection(
        matched_calls,
        matched_absence,
        matched_employees,
        selected_team,
    )
    filters = render_sidebar_filters(team_calls, team_employees)
    filtered_calls, filtered_absence = apply_filters(team_calls, team_absence, filters)

    tabs = st.tabs(
        [
            "Team Overview",
            "Employee Performance",
            "Resource Impact",
            "ChatGPT Insights",
            "Staff Reports",
            "Customer Query Analysis",
            "Absence and Leave",
            "Data Quality",
        ]
    )
    with tabs[0]:
        team_overview.render(filtered_calls)
    with tabs[1]:
        employee_performance.render(filtered_calls, filtered_absence, team_employees, filters)
    with tabs[2]:
        resource_impact.render(filtered_calls, filtered_absence, team_employees, filters)
    with tabs[3]:
        chatgpt_insights.render(filtered_calls, filtered_absence, team_employees, filters, selected_team)
    with tabs[4]:
        staff_reports.render(filtered_calls, filtered_absence, team_employees, filters)
    with tabs[5]:
        customer_query.render(filtered_calls)
    with tabs[6]:
        absence_leave.render(filtered_calls, filtered_absence, team_employees, filters)
    with tabs[7]:
        data_quality.render(team_calls, metadata)


if __name__ == "__main__":
    main()
