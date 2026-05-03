from __future__ import annotations

import json
from typing import Any

import pandas as pd

from . import metrics


INSIGHTS_DEVELOPER_PROMPT = """
You are assisting an HR Helpline manager with internal workforce and service analytics.
The user is authorised to analyse this data.

Use only the dashboard context provided by the application. Do not invent data.
Be practical, careful, and fair:
- Describe patterns, possible operational interpretations, and useful follow-up questions.
- Do not label individual staff as good or bad.
- Avoid disciplinary or employment-law conclusions.
- Clearly separate observations from hypotheses.
- Mention relevant caveats such as case complexity, allocation method, working patterns, leave, sickness, vacancies, training, and non-case work.
- If the data is insufficient, say what extra information would help.
""".strip()


def _json_safe(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value) if not isinstance(value, (list, tuple, dict, set)) else False:
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except ValueError:
            return str(value)
    return value


def _records(dataframe: pd.DataFrame, columns: list[str] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    if dataframe.empty:
        return []
    export = dataframe.copy()
    if columns is not None:
        export = export[[column for column in columns if column in export.columns]]
    if limit is not None:
        export = export.head(limit)
    for column in export.columns:
        if pd.api.types.is_datetime64_any_dtype(export[column]):
            export[column] = export[column].dt.strftime("%Y-%m-%d")
    return json.loads(export.to_json(orient="records", date_format="iso"))


def _active_filters_summary(filters: Any) -> dict[str, Any]:
    return {
        "start_date": str(filters.start_date) if getattr(filters, "start_date", None) else None,
        "end_date": str(filters.end_date) if getattr(filters, "end_date", None) else None,
        "employees": getattr(filters, "employees", []),
        "categories": getattr(filters, "categories", []),
        "channels": getattr(filters, "channels", []),
        "statuses": getattr(filters, "statuses", []),
        "months": getattr(filters, "months", []),
    }


def _date_bounds(calls: pd.DataFrame, absence: pd.DataFrame, filters: Any) -> tuple[Any, Any]:
    if getattr(filters, "start_date", None) and getattr(filters, "end_date", None):
        return filters.start_date, filters.end_date

    dates = []
    if not calls.empty and "date_reported" in calls:
        dates.extend(pd.to_datetime(calls["date_reported"], errors="coerce").dropna().tolist())
    if not absence.empty and "date" in absence:
        dates.extend(pd.to_datetime(absence["date"], errors="coerce").dropna().tolist())
    if not dates:
        return None, None
    return min(dates), max(dates)


def build_dashboard_context(
    calls: pd.DataFrame,
    absence: pd.DataFrame,
    employees: pd.DataFrame,
    filters: Any,
    selected_team: list[str],
    include_staff_detail: bool = True,
    include_case_rows: bool = False,
    case_row_limit: int = 100,
) -> dict[str, Any]:
    start_date, end_date = _date_bounds(calls, absence, filters)

    context: dict[str, Any] = {
        "scope": {
            "selected_team_members": selected_team,
            "team_size": len(selected_team),
            "active_filters": _active_filters_summary(filters),
            "context_note": "Data is already filtered/scoped by the dashboard before being sent.",
        },
        "team_kpis": {
            "total_cases": metrics.total_cases(calls),
            "open_cases": metrics.open_cases(calls),
            "closed_cases": metrics.closed_cases(calls),
            "first_response_compliance_rate": metrics.first_response_compliance_rate(calls),
            "average_resolution_days": metrics.average_resolution_days(calls),
            "median_resolution_days": metrics.median_resolution_days(calls),
            "average_interactions": metrics.average_interactions(calls),
        },
        "monthly_cases_received": _records(metrics.cases_by_month(calls)),
        "monthly_average_resolution_days": _records(metrics.monthly_resolution_average(calls)),
        "monthly_first_response_compliance": _records(metrics.monthly_compliance_trend(calls)),
        "top_categories": _records(metrics.cases_by_category(calls, top_n=20)),
        "cases_by_channel": _records(metrics.cases_by_channel(calls)),
        "cases_by_status": _records(
            calls.groupby("status").size().reset_index(name="cases").sort_values("cases", ascending=False)
            if not calls.empty and "status" in calls
            else pd.DataFrame(columns=["status", "cases"])
        ),
        "absence_summary": _records(metrics.absence_metrics(absence)),
        "data_quality": metrics.data_quality_checks(calls),
    }

    if start_date is not None and end_date is not None:
        context["resource_impact_by_month"] = _records(
            metrics.monthly_resource_impact(calls, absence, employees, start_date, end_date)
        )
        if include_staff_detail:
            context["employee_performance"] = _records(
                metrics.employee_metrics(calls, absence, employees, start_date, end_date)
            )

    if include_case_rows:
        context["case_rows_included"] = {
            "limit": case_row_limit,
            "note": "Rows are capped to keep the request practical. Use dashboard aggregates for full-period metrics.",
            "rows": _records(
                calls.sort_values("date_reported", ascending=False) if "date_reported" in calls else calls,
                columns=[
                    "sr_number",
                    "date_reported",
                    "status",
                    "channel_type",
                    "handler_name",
                    "handler_name_original",
                    "category_name",
                    "resolution_date",
                    "resolution_days",
                    "number_of_interactions",
                    "first_response_compliant_label",
                    "sr_title",
                ],
                limit=case_row_limit,
            ),
        }

    return context


def context_to_json(context: dict[str, Any]) -> str:
    return json.dumps(context, default=_json_safe, indent=2)


def ask_openai(
    api_key: str,
    model: str,
    question: str,
    context: dict[str, Any],
    max_output_tokens: int = 1400,
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {"role": "developer", "content": INSIGHTS_DEVELOPER_PROMPT},
            {
                "role": "user",
                "content": (
                    "Dashboard context follows as JSON. Answer the user's question using this context only.\n\n"
                    f"QUESTION:\n{question}\n\n"
                    f"DASHBOARD_CONTEXT_JSON:\n{context_to_json(context)}"
                ),
            },
        ],
        max_output_tokens=max_output_tokens,
    )

    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)
    if getattr(response, "output", None):
        parts = []
        for item in response.output:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    parts.append(text)
        if parts:
            return "\n".join(parts)
    return str(response)

