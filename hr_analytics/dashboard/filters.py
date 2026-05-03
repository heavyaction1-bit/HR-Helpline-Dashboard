from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st


@dataclass
class DashboardFilters:
    start_date: date | None
    end_date: date | None
    employees: list[str]
    categories: list[str]
    channels: list[str]
    statuses: list[str]
    months: list[str]


def _name_options(calls: pd.DataFrame, absence: pd.DataFrame, employees: pd.DataFrame) -> list[str]:
    names: set[str] = set()
    for dataframe, columns in (
        (employees, ("employee_name",)),
        (calls, ("handler_name",)),
        (absence, ("employee_name", "matched_employee_name", "source_employee_name")),
    ):
        for column in columns:
            if column in dataframe:
                names.update(dataframe[column].dropna().astype(str).str.strip().loc[lambda series: series.ne("")])
    return sorted(names)


def _resolve_alias(name: Any, alias_map: dict[str, str]) -> str:
    current = "" if pd.isna(name) else str(name).strip()
    visited: set[str] = set()
    while current in alias_map and current not in visited:
        visited.add(current)
        current = alias_map[current]
    return current


def render_name_matching(calls: pd.DataFrame, absence: pd.DataFrame, employees: pd.DataFrame) -> dict[str, str]:
    if "name_aliases" not in st.session_state:
        st.session_state["name_aliases"] = {}

    alias_map = dict(st.session_state["name_aliases"])
    options = _name_options(calls, absence, employees)

    with st.sidebar.expander("Name matching", expanded=False):
        st.caption("Merge short names or alternate spellings into one staff record before team selection and reporting.")
        if not options:
            st.caption("Load data to enable name matching.")
            return alias_map

        canonical = st.selectbox("Main staff record", options, key="alias_canonical_name")
        alias_options = [name for name in options if name != canonical]
        selected_aliases = st.multiselect(
            "Names to merge into this record",
            alias_options,
            key="alias_names_to_merge",
            help="Example: choose the full staff name above, then select a short name such as Effie here.",
        )

        if st.button("Add name match", key="add_name_match"):
            for alias in selected_aliases:
                alias_map[alias] = canonical
            st.session_state["name_aliases"] = alias_map
            st.rerun()

        if alias_map:
            mapping_rows = [
                {"Alias / source name": alias, "Main staff record": target}
                for alias, target in sorted(alias_map.items())
            ]
            st.dataframe(pd.DataFrame(mapping_rows), width="stretch", hide_index=True)

            remove_choice = st.selectbox(
                "Remove a match",
                [""] + [f"{alias} -> {target}" for alias, target in sorted(alias_map.items())],
                key="remove_name_match_choice",
            )
            if st.button("Remove selected match", key="remove_name_match") and remove_choice:
                alias_to_remove = remove_choice.split(" -> ", 1)[0]
                alias_map.pop(alias_to_remove, None)
                st.session_state["name_aliases"] = alias_map
                st.rerun()

            if st.button("Clear all name matches", key="clear_name_matches"):
                st.session_state["name_aliases"] = {}
                st.rerun()
        else:
            st.caption("No name matches have been added yet.")

    return alias_map


def apply_name_aliases(
    calls: pd.DataFrame,
    absence: pd.DataFrame,
    employees: pd.DataFrame,
    alias_map: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not alias_map:
        return calls, absence, employees

    calls = calls.copy()
    absence = absence.copy()
    employees = employees.copy()

    if "handler_name" in calls:
        if "handler_name_original" not in calls:
            calls["handler_name_original"] = calls["handler_name"]
        calls["handler_name"] = calls["handler_name"].map(lambda name: _resolve_alias(name, alias_map))

    if not absence.empty:
        if "employee_name" in absence and "employee_name_original" not in absence:
            absence["employee_name_original"] = absence["employee_name"]
        if "matched_employee_name" in absence:
            if "matched_employee_name_original" not in absence:
                absence["matched_employee_name_original"] = absence["matched_employee_name"]
            absence["matched_employee_name"] = absence["matched_employee_name"].map(lambda name: _resolve_alias(name, alias_map))
        elif "employee_name" in absence:
            absence["employee_name"] = absence["employee_name"].map(lambda name: _resolve_alias(name, alias_map))

    if not employees.empty and "employee_name" in employees:
        employees["employee_name"] = employees["employee_name"].map(lambda name: _resolve_alias(name, alias_map))
        source_map = (
            employees.groupby("employee_name")["source"]
            .apply(lambda values: ", ".join(sorted({part.strip() for value in values.dropna().astype(str) for part in value.split(",") if part.strip()})))
            .reset_index()
        )
        source_map["employee_id"] = range(1, len(source_map) + 1)
        employees = source_map[["employee_id", "employee_name", "source"]]

    return calls, absence, employees


def suggested_team_members(calls: pd.DataFrame, employees: pd.DataFrame, team_size: int = 7) -> list[str]:
    employee_options = _sorted_options(employees.get("employee_name", pd.Series(dtype="string")))
    if calls.empty or "handler_name" not in calls:
        return employee_options[:team_size]

    counts = (
        calls["handler_name"]
        .dropna()
        .astype(str)
        .loc[lambda series: series.ne("Unassigned / Unknown")]
        .value_counts()
    )
    suggested = [name for name in counts.index.tolist() if name in employee_options][:team_size]
    if len(suggested) < team_size:
        suggested.extend([name for name in employee_options if name not in suggested][: team_size - len(suggested)])
    return suggested


def render_team_selection(calls: pd.DataFrame, employees: pd.DataFrame) -> list[str]:
    st.sidebar.subheader("Team selection")
    employee_options = _sorted_options(employees.get("employee_name", pd.Series(dtype="string")))
    default_team = suggested_team_members(calls, employees)
    selected_team = st.sidebar.multiselect(
        "Core HR Helpline team members",
        employee_options,
        default=default_team,
        key="core_team_members",
        help="Select the core team to include in the dashboard. Occasional handlers outside this list are excluded from charts and metrics.",
    )
    st.sidebar.caption(
        "Default suggestion uses the seven handlers with the highest case volume. Adjust this list to match the actual team."
    )
    if selected_team:
        st.sidebar.caption(f"Dashboard scoped to {len(selected_team)} selected team member(s).")
    else:
        st.sidebar.warning("Select at least one team member to populate the dashboard.")
    return selected_team


def apply_team_selection(
    calls: pd.DataFrame,
    absence: pd.DataFrame,
    employees: pd.DataFrame,
    selected_team: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not selected_team:
        return calls.iloc[0:0].copy(), absence.iloc[0:0].copy(), employees.iloc[0:0].copy()

    team_calls = calls.loc[calls["handler_name"].astype(str).isin(selected_team)].copy()
    team_employees = employees.loc[employees["employee_name"].astype(str).isin(selected_team)].copy()
    team_absence = absence.copy()
    if not team_absence.empty:
        absence_employee_col = "matched_employee_name" if "matched_employee_name" in team_absence else "employee_name"
        team_absence = team_absence.loc[team_absence[absence_employee_col].astype(str).isin(selected_team)].copy()
    return team_calls, team_absence, team_employees


def _sorted_options(series: pd.Series) -> list[str]:
    if series.empty:
        return []
    return sorted(series.dropna().astype(str).unique().tolist())


def render_sidebar_filters(calls: pd.DataFrame, employees: pd.DataFrame) -> DashboardFilters:
    st.sidebar.divider()
    st.sidebar.subheader("Dashboard filters")

    date_series = pd.to_datetime(calls.get("date_reported", pd.Series(dtype="datetime64[ns]")), errors="coerce").dropna()
    if date_series.empty:
        start_date = None
        end_date = None
        st.sidebar.caption("Upload data to enable filters.")
    else:
        min_date = date_series.min().date()
        max_date = date_series.max().date()
        selected_range = st.sidebar.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        if isinstance(selected_range, tuple) and len(selected_range) == 2:
            start_date, end_date = selected_range
        else:
            start_date = selected_range
            end_date = selected_range

    employee_options = _sorted_options(employees.get("employee_name", pd.Series(dtype="string")))
    selected_employees = st.sidebar.multiselect("Employee / handler", employee_options)

    category_options = _sorted_options(calls.get("category_name", pd.Series(dtype="string")))
    selected_categories = st.sidebar.multiselect("Category", category_options)

    channel_options = _sorted_options(calls.get("channel_type", pd.Series(dtype="string")))
    selected_channels = st.sidebar.multiselect("Channel", channel_options)

    status_options = _sorted_options(calls.get("status", pd.Series(dtype="string")))
    selected_statuses = st.sidebar.multiselect("Status", status_options)

    month_options = []
    if "reported_month" in calls:
        month_options = (
            pd.to_datetime(calls["reported_month"], errors="coerce")
            .dropna()
            .dt.strftime("%Y-%m")
            .sort_values()
            .unique()
            .tolist()
        )
    selected_months = st.sidebar.multiselect("Month / year", month_options)

    return DashboardFilters(
        start_date=start_date,
        end_date=end_date,
        employees=selected_employees,
        categories=selected_categories,
        channels=selected_channels,
        statuses=selected_statuses,
        months=selected_months,
    )


def apply_filters(
    calls: pd.DataFrame,
    absence: pd.DataFrame,
    filters: DashboardFilters,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    filtered_calls = calls.copy()
    filtered_absence = absence.copy()

    if filters.start_date and filters.end_date:
        start = pd.Timestamp(filters.start_date)
        end = pd.Timestamp(filters.end_date) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        filtered_calls = filtered_calls.loc[
            pd.to_datetime(filtered_calls["date_reported"], errors="coerce").between(start, end)
        ]
        if not filtered_absence.empty and "date" in filtered_absence:
            filtered_absence = filtered_absence.loc[
                pd.to_datetime(filtered_absence["date"], errors="coerce").between(start.normalize(), end.normalize())
            ]

    if filters.months and "reported_month" in filtered_calls:
        month_labels = pd.to_datetime(filtered_calls["reported_month"], errors="coerce").dt.strftime("%Y-%m")
        filtered_calls = filtered_calls.loc[month_labels.isin(filters.months)]

    if filters.employees:
        filtered_calls = filtered_calls.loc[filtered_calls["handler_name"].astype(str).isin(filters.employees)]
        if not filtered_absence.empty:
            absence_employee_col = "matched_employee_name" if "matched_employee_name" in filtered_absence else "employee_name"
            filtered_absence = filtered_absence.loc[filtered_absence[absence_employee_col].astype(str).isin(filters.employees)]

    if filters.categories:
        filtered_calls = filtered_calls.loc[filtered_calls["category_name"].astype(str).isin(filters.categories)]
    if filters.channels:
        filtered_calls = filtered_calls.loc[filtered_calls["channel_type"].astype(str).isin(filters.channels)]
    if filters.statuses:
        filtered_calls = filtered_calls.loc[filtered_calls["status"].astype(str).isin(filters.statuses)]

    return filtered_calls, filtered_absence
