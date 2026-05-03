from __future__ import annotations

import re

import pandas as pd

from .config import CLOSED_STATUS_KEYWORDS, UNKNOWN_CATEGORY, UNKNOWN_HANDLER


def is_closed_status(status: object) -> bool:
    text = "" if pd.isna(status) else str(status).strip().lower()
    return any(keyword in text for keyword in CLOSED_STATUS_KEYWORDS)


def add_status_flags(calls: pd.DataFrame) -> pd.DataFrame:
    calls = calls.copy()
    calls["is_closed"] = calls["status"].map(is_closed_status)
    return calls


def total_cases(calls: pd.DataFrame) -> int:
    return int(len(calls))


def closed_cases(calls: pd.DataFrame) -> int:
    if calls.empty:
        return 0
    return int(calls["status"].map(is_closed_status).sum())


def open_cases(calls: pd.DataFrame) -> int:
    return total_cases(calls) - closed_cases(calls)


def first_response_compliance_rate(calls: pd.DataFrame) -> float | None:
    if calls.empty or "first_response_compliant" not in calls:
        return None
    values = calls["first_response_compliant"].dropna()
    if values.empty:
        return None
    return float(values.astype(bool).mean())


def average_resolution_days(calls: pd.DataFrame) -> float | None:
    values = pd.to_numeric(calls.get("resolution_days", pd.Series(dtype="float")), errors="coerce")
    values = values.dropna()
    if values.empty:
        return None
    return float(values.mean())


def median_resolution_days(calls: pd.DataFrame) -> float | None:
    values = pd.to_numeric(calls.get("resolution_days", pd.Series(dtype="float")), errors="coerce")
    values = values.dropna()
    if values.empty:
        return None
    return float(values.median())


def average_interactions(calls: pd.DataFrame) -> float | None:
    values = pd.to_numeric(calls.get("number_of_interactions", pd.Series(dtype="float")), errors="coerce")
    values = values.dropna()
    if values.empty:
        return None
    return float(values.mean())


def cases_by_month(calls: pd.DataFrame) -> pd.DataFrame:
    if calls.empty or "reported_month" not in calls:
        return pd.DataFrame(columns=["reported_month", "cases"])
    grouped = calls.dropna(subset=["reported_month"]).groupby("reported_month").size().reset_index(name="cases")
    return grouped.sort_values("reported_month")


def cases_closed_by_month(calls: pd.DataFrame) -> pd.DataFrame:
    if calls.empty or "resolution_month" not in calls:
        return pd.DataFrame(columns=["resolution_month", "cases"])
    closed = calls.loc[calls["status"].map(is_closed_status)]
    grouped = closed.dropna(subset=["resolution_month"]).groupby("resolution_month").size().reset_index(name="cases")
    return grouped.sort_values("resolution_month")


def cases_by_category(calls: pd.DataFrame, top_n: int | None = None) -> pd.DataFrame:
    if calls.empty or "category_name" not in calls:
        return pd.DataFrame(columns=["category_name", "cases"])
    grouped = calls.groupby("category_name", dropna=False).size().reset_index(name="cases")
    grouped = grouped.sort_values("cases", ascending=False)
    return grouped.head(top_n) if top_n else grouped


def cases_by_channel(calls: pd.DataFrame) -> pd.DataFrame:
    if calls.empty or "channel_type" not in calls:
        return pd.DataFrame(columns=["channel_type", "cases"])
    return calls.groupby("channel_type", dropna=False).size().reset_index(name="cases").sort_values("cases", ascending=False)


def working_days_between(start_date: object, end_date: object) -> int:
    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end) or start > end:
        return 0
    return int(len(pd.bdate_range(start.normalize(), end.normalize())))


def absence_metrics(absence: pd.DataFrame) -> pd.DataFrame:
    if absence.empty:
        return pd.DataFrame(columns=["employee_name", "sickness_days", "annual_leave_days", "total_unavailable_days"])

    employee_column = "matched_employee_name" if "matched_employee_name" in absence else "employee_name"
    pivot = (
        absence.pivot_table(
            index=employee_column,
            columns="absence_type",
            values="value",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .rename(columns={employee_column: "employee_name"})
    )
    for column in ("Sickness", "Annual Leave"):
        if column not in pivot:
            pivot[column] = 0.0
    pivot = pivot.rename(columns={"Sickness": "sickness_days", "Annual Leave": "annual_leave_days"})
    pivot["total_unavailable_days"] = pivot["sickness_days"] + pivot["annual_leave_days"]
    return pivot[["employee_name", "sickness_days", "annual_leave_days", "total_unavailable_days"]]


def employee_metrics(
    calls: pd.DataFrame,
    absence: pd.DataFrame,
    employees: pd.DataFrame,
    start_date: object,
    end_date: object,
) -> pd.DataFrame:
    working_days = working_days_between(start_date, end_date)
    employee_names = employees.get("employee_name", pd.Series(dtype="string")).dropna().astype(str).tolist()

    call_rows = []
    for employee in employee_names:
        employee_calls = calls.loc[calls.get("handler_name", pd.Series(dtype="string")).astype(str).eq(employee)]
        compliance = first_response_compliance_rate(employee_calls)
        call_rows.append(
            {
                "employee_name": employee,
                "cases_handled": total_cases(employee_calls),
                "cases_closed_resolved": closed_cases(employee_calls),
                "open_cases_assigned": open_cases(employee_calls),
                "first_response_compliance_rate": compliance,
                "average_resolution_days": average_resolution_days(employee_calls),
                "median_resolution_days": median_resolution_days(employee_calls),
                "average_interactions_per_case": average_interactions(employee_calls),
            }
        )

    metrics = pd.DataFrame(call_rows)
    absence_summary = absence_metrics(absence)
    metrics = metrics.merge(absence_summary, on="employee_name", how="left")
    for column in ("sickness_days", "annual_leave_days", "total_unavailable_days"):
        metrics[column] = metrics[column].fillna(0.0)
    metrics["estimated_working_days"] = working_days
    metrics["estimated_available_working_days"] = (
        metrics["estimated_working_days"] - metrics["total_unavailable_days"]
    ).clip(lower=0)
    metrics["cases_per_available_working_day"] = metrics.apply(
        lambda row: row["cases_handled"] / row["estimated_available_working_days"]
        if row["estimated_available_working_days"] > 0
        else 0.0,
        axis=1,
    )
    return metrics.sort_values(["cases_handled", "employee_name"], ascending=[False, True])


def cases_per_available_day(
    cases_handled: int | float,
    available_working_days: int | float,
) -> float:
    if not available_working_days or available_working_days <= 0:
        return 0.0
    return float(cases_handled) / float(available_working_days)


def cases_received_this_month(calls: pd.DataFrame) -> int:
    if calls.empty or calls["date_reported"].dropna().empty:
        return 0
    reference_month = calls["date_reported"].dropna().max().to_period("M").to_timestamp()
    return int(calls["reported_month"].eq(reference_month).sum())


def cases_closed_this_month(calls: pd.DataFrame) -> int:
    if calls.empty or calls["resolution_date"].dropna().empty:
        return 0
    reference_month = calls["resolution_date"].dropna().max().to_period("M").to_timestamp()
    closed = calls.loc[calls["status"].map(is_closed_status)]
    return int(closed["resolution_month"].eq(reference_month).sum())


def monthly_resolution_average(calls: pd.DataFrame) -> pd.DataFrame:
    if calls.empty:
        return pd.DataFrame(columns=["reported_month", "average_resolution_days"])
    values = calls.dropna(subset=["reported_month", "resolution_days"])
    return (
        values.groupby("reported_month")["resolution_days"]
        .mean()
        .reset_index(name="average_resolution_days")
        .sort_values("reported_month")
    )


def monthly_compliance_trend(calls: pd.DataFrame) -> pd.DataFrame:
    if calls.empty:
        return pd.DataFrame(columns=["reported_month", "first_response_compliance_rate"])
    values = calls.dropna(subset=["reported_month", "first_response_compliant"])
    if values.empty:
        return pd.DataFrame(columns=["reported_month", "first_response_compliance_rate"])
    return (
        values.groupby("reported_month")["first_response_compliant"]
        .mean()
        .reset_index(name="first_response_compliance_rate")
        .sort_values("reported_month")
    )


def category_resolution_metrics(calls: pd.DataFrame) -> pd.DataFrame:
    values = calls.dropna(subset=["category_name"]).copy()
    if values.empty:
        return pd.DataFrame(columns=["category_name", "average_resolution_days", "average_interactions", "cases"])
    grouped = (
        values.groupby("category_name")
        .agg(
            average_resolution_days=("resolution_days", "mean"),
            average_interactions=("number_of_interactions", "mean"),
            cases=("sr_number", "count"),
        )
        .reset_index()
    )
    return grouped


def category_trend_by_month(calls: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    top_categories = cases_by_category(calls, top_n=top_n)["category_name"].tolist()
    values = calls.loc[calls["category_name"].isin(top_categories)].dropna(subset=["reported_month"])
    if values.empty:
        return pd.DataFrame(columns=["reported_month", "category_name", "cases"])
    return (
        values.groupby(["reported_month", "category_name"])
        .size()
        .reset_index(name="cases")
        .sort_values("reported_month")
    )


def keyword_analysis(calls: pd.DataFrame, max_words: int = 30) -> pd.DataFrame:
    text_columns = [column for column in ("sr_title", "description", "sr_description") if column in calls.columns]
    if not text_columns:
        return pd.DataFrame(columns=["keyword", "count"])

    stopwords = {
        "a", "an", "and", "are", "as", "at", "be", "by", "can", "for", "from", "fw", "hi",
        "in", "is", "it", "of", "on", "or", "re", "the", "to", "with", "you", "your", "please",
        "query", "request", "sr", "hr",
    }
    combined = calls[text_columns].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    words: dict[str, int] = {}
    for text in combined:
        for word in re.findall(r"[a-zA-Z][a-zA-Z']{2,}", text):
            if word not in stopwords and not word.startswith("sr_"):
                words[word] = words.get(word, 0) + 1
    return (
        pd.DataFrame([{"keyword": word, "count": count} for word, count in words.items()])
        .sort_values("count", ascending=False)
        .head(max_words)
        if words
        else pd.DataFrame(columns=["keyword", "count"])
    )


def absence_by_month(absence: pd.DataFrame) -> pd.DataFrame:
    if absence.empty:
        return pd.DataFrame(columns=["month", "absence_type", "days"])
    values = absence.copy()
    values["month"] = pd.to_datetime(values["date"]).dt.to_period("M").dt.to_timestamp()
    return (
        values.groupby(["month", "absence_type"])["value"]
        .sum()
        .reset_index(name="days")
        .sort_values("month")
    )


def team_availability_by_month(absence: pd.DataFrame, employees: pd.DataFrame, start_date: object, end_date: object) -> pd.DataFrame:
    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        return pd.DataFrame(columns=["month", "estimated_working_days", "unavailable_days", "available_staff_days"])

    months = pd.period_range(start=start, end=end, freq="M")
    employee_count = max(int(len(employees)), 1)
    absence_month = absence_by_month(absence).groupby("month")["days"].sum() if not absence.empty else pd.Series(dtype="float")

    rows = []
    for period in months:
        month_start = period.to_timestamp()
        month_end = period.to_timestamp(how="end").normalize()
        range_start = max(start.normalize(), month_start)
        range_end = min(end.normalize(), month_end)
        period_working_days = working_days_between(range_start, range_end)
        working_days = period_working_days * employee_count
        unavailable = float(absence_month.get(month_start, 0.0))
        rows.append(
            {
                "month": month_start,
                "employee_count": employee_count,
                "period_working_days": period_working_days,
                "estimated_working_days": working_days,
                "unavailable_days": unavailable,
                "available_staff_days": max(working_days - unavailable, 0),
            }
        )
    return pd.DataFrame(rows)


def monthly_resource_impact(
    calls: pd.DataFrame,
    absence: pd.DataFrame,
    employees: pd.DataFrame,
    start_date: object,
    end_date: object,
) -> pd.DataFrame:
    availability = team_availability_by_month(absence, employees, start_date, end_date)
    if availability.empty:
        return pd.DataFrame(
            columns=[
                "month",
                "employee_count",
                "estimated_working_days",
                "sickness_days",
                "annual_leave_days",
                "unavailable_days",
                "available_staff_days",
                "availability_rate",
                "absence_rate",
                "cases_received",
                "cases_closed",
                "open_cases_reported",
                "average_resolution_days",
                "median_resolution_days",
                "average_interactions",
                "first_response_compliance_rate",
                "cases_per_available_staff_day",
                "closed_per_available_staff_day",
                "pressure_index",
            ]
        )

    impact = availability.copy()
    absence_month = absence_by_month(absence) if not absence.empty else pd.DataFrame(columns=["month", "absence_type", "days"])
    if absence_month.empty:
        impact["sickness_days"] = 0.0
        impact["annual_leave_days"] = 0.0
    else:
        absence_pivot = (
            absence_month.pivot_table(index="month", columns="absence_type", values="days", aggfunc="sum", fill_value=0)
            .reset_index()
            .rename(columns={"Sickness": "sickness_days", "Annual Leave": "annual_leave_days"})
        )
        for column in ("sickness_days", "annual_leave_days"):
            if column not in absence_pivot:
                absence_pivot[column] = 0.0
        impact = impact.merge(absence_pivot[["month", "sickness_days", "annual_leave_days"]], on="month", how="left")
        impact[["sickness_days", "annual_leave_days"]] = impact[["sickness_days", "annual_leave_days"]].fillna(0.0)

    received = cases_by_month(calls).rename(columns={"reported_month": "month", "cases": "cases_received"})
    closed = cases_closed_by_month(calls).rename(columns={"resolution_month": "month", "cases": "cases_closed"})
    resolution_average = monthly_resolution_average(calls).rename(columns={"reported_month": "month"})
    compliance = monthly_compliance_trend(calls).rename(columns={"reported_month": "month"})

    if calls.empty:
        monthly_detail = pd.DataFrame(columns=["month", "open_cases_reported", "median_resolution_days", "average_interactions"])
    else:
        detail_source = calls.dropna(subset=["reported_month"]).copy()
        detail_source["open_case_flag"] = ~detail_source["status"].map(is_closed_status)
        monthly_detail = (
            detail_source.groupby("reported_month")
            .agg(
                open_cases_reported=("open_case_flag", "sum"),
                median_resolution_days=("resolution_days", "median"),
                average_interactions=("number_of_interactions", "mean"),
            )
            .reset_index()
            .rename(columns={"reported_month": "month"})
        )

    for dataframe in (received, closed, resolution_average, compliance, monthly_detail):
        impact = impact.merge(dataframe, on="month", how="left")

    count_columns = ("cases_received", "cases_closed", "open_cases_reported")
    for column in count_columns:
        if column in impact:
            impact[column] = impact[column].fillna(0).astype(int)

    numeric_fill_zero = ("sickness_days", "annual_leave_days", "unavailable_days", "available_staff_days")
    for column in numeric_fill_zero:
        if column in impact:
            impact[column] = pd.to_numeric(impact[column], errors="coerce").fillna(0.0)

    estimated = pd.to_numeric(impact["estimated_working_days"], errors="coerce")
    available = pd.to_numeric(impact["available_staff_days"], errors="coerce")
    impact["availability_rate"] = (available / estimated).where(estimated > 0)
    impact["absence_rate"] = (impact["unavailable_days"] / estimated).where(estimated > 0)
    impact["cases_per_available_staff_day"] = (impact["cases_received"] / available).where(available > 0, 0.0)
    impact["closed_per_available_staff_day"] = (impact["cases_closed"] / available).where(available > 0, 0.0)

    baseline = impact.loc[impact["available_staff_days"] > 0, "cases_per_available_staff_day"].mean()
    impact["pressure_index"] = (
        impact["cases_per_available_staff_day"] / baseline
        if pd.notna(baseline) and baseline > 0
        else 0.0
    )
    return impact.sort_values("month")


def data_quality_checks(calls: pd.DataFrame, metadata: dict[str, object] | None = None) -> dict[str, object]:
    metadata = metadata or {}
    duplicate_sr_numbers = (
        int(calls["sr_number"].duplicated(keep=False).sum())
        if "sr_number" in calls and calls["sr_number"].notna().any()
        else 0
    )
    date_reported = pd.to_datetime(calls.get("date_reported", pd.Series(dtype="datetime64[ns]")), errors="coerce")
    return {
        "missing_reported_date": int(date_reported.isna().sum()),
        "missing_handler": int(calls.get("handler_missing", pd.Series(dtype="bool")).fillna(False).sum()),
        "missing_category": int(calls.get("category_missing", pd.Series(dtype="bool")).fillna(False).sum()),
        "invalid_resolution_date": int(calls.get("resolution_date_invalid", pd.Series(dtype="bool")).fillna(False).sum()),
        "negative_resolution_duration": int(calls.get("negative_resolution_duration", pd.Series(dtype="bool")).fillna(False).sum()),
        "duplicate_sr_numbers": duplicate_sr_numbers,
        "expected_columns_missing": metadata.get("missing_expected_columns", []),
        "date_min": date_reported.min(),
        "date_max": date_reported.max(),
        "source_stats": metadata.get("source_stats", {}),
    }
