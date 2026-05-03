from __future__ import annotations

from dataclasses import dataclass
import re

import pandas as pd

from .config import (
    EXPECTED_SR_COLUMNS,
    UNKNOWN_CATEGORY,
    UNKNOWN_HANDLER,
    UNKNOWN_TEXT,
)


COLUMN_ALIASES = {
    "handler_first_name": "handler_first_name",
    "handler_last_name": "handler_last_name",
    "sr_resolution_date": "resolution_date",
    "resolution_date": "resolution_date",
    "average_time_to_resolve_days": "average_time_to_resolve",
    "average_time_to_resolve": "average_time_to_resolve",
    "no_of_interactions_to_resolve_an_sr": "number_of_interactions",
    "number_of_interactions": "number_of_interactions",
    "no_of_first_response_compliant_srs": "first_response_compliant",
    "first_response_compliant": "first_response_compliant",
    "sr_title": "sr_title",
}

DATE_COLUMNS = (
    "date_reported",
    "resolution_date",
    "last_queue_assigned_date",
    "last_response_date",
    "completion_date_and_time",
)


@dataclass
class ModelFrames:
    calls: pd.DataFrame
    absence: pd.DataFrame
    employees: pd.DataFrame
    metadata: dict[str, object]


def snake_case(value: object) -> str:
    text = str(value).strip()
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_").lower()
    return text


def standardise_column_names(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe = dataframe.copy()
    seen: dict[str, int] = {}
    clean_names: list[str] = []
    for index, column in enumerate(dataframe.columns):
        clean = COLUMN_ALIASES.get(snake_case(column), snake_case(column))
        if not clean:
            clean = f"column_{index + 1}"
        count = seen.get(clean, 0)
        seen[clean] = count + 1
        clean_names.append(clean if count == 0 else f"{clean}_{count + 1}")
    dataframe.columns = clean_names
    return dataframe


def _clean_text_series(series: pd.Series, fallback: str | None = None) -> pd.Series:
    cleaned = series.astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    cleaned = cleaned.mask(cleaned.str.lower().isin({"", "nan", "none", "<na>"}))
    if fallback is not None:
        cleaned = cleaned.fillna(fallback)
    return cleaned


def coerce_excel_date(series: pd.Series) -> pd.Series:
    if series.empty:
        return pd.to_datetime(series, errors="coerce")

    parsed = pd.to_datetime(series, errors="coerce")
    numeric = pd.to_numeric(series, errors="coerce")
    plausible_excel_serial = numeric.where(numeric.between(20_000, 80_000))
    parsed_serial = pd.to_datetime(
        plausible_excel_serial,
        unit="D",
        origin="1899-12-30",
        errors="coerce",
    )
    return parsed.fillna(parsed_serial)


def coerce_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    cleaned = (
        series.astype("string")
        .str.replace(",", "", regex=False)
        .str.replace(r"[^0-9.\-]", "", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def coerce_boolean(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    result = pd.Series(pd.NA, index=series.index, dtype="boolean")
    result = result.mask(numeric == 0, False)
    result = result.mask(numeric > 0, True)

    text = series.astype("string").str.strip().str.lower()
    true_values = {"true", "yes", "y", "1", "compliant", "met", "pass", "passed"}
    false_values = {"false", "no", "n", "0", "non-compliant", "not compliant", "failed"}
    result = result.mask(text.isin(true_values), True)
    result = result.mask(text.isin(false_values), False)
    return result


def _ensure_expected_columns(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    dataframe = dataframe.copy()
    missing = [
        original_name
        for canonical_name, original_name in EXPECTED_SR_COLUMNS.items()
        if canonical_name not in dataframe.columns
    ]
    for canonical_name in EXPECTED_SR_COLUMNS:
        if canonical_name not in dataframe.columns:
            dataframe[canonical_name] = pd.NA
    return dataframe, missing


def clean_sr_data(raw_sr_data: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    calls = standardise_column_names(raw_sr_data)
    calls, missing_expected = _ensure_expected_columns(calls)

    for column in DATE_COLUMNS:
        if column in calls.columns:
            calls[f"{column}_raw"] = calls[column]
            calls[column] = coerce_excel_date(calls[column])

    for column in ("average_time_to_resolve", "number_of_interactions"):
        calls[f"{column}_raw"] = calls[column]
        calls[column] = coerce_numeric(calls[column])

    calls["first_response_compliant_raw"] = calls["first_response_compliant"]
    calls["first_response_compliant"] = coerce_boolean(calls["first_response_compliant"])
    calls["first_response_compliant_label"] = (
        calls["first_response_compliant"].map({True: "Yes", False: "No"}).fillna("Unknown")
    )

    first = _clean_text_series(calls["handler_first_name"])
    last = _clean_text_series(calls["handler_last_name"])
    handler_name = (first.fillna("") + " " + last.fillna("")).str.strip()
    handler_name = handler_name.str.replace(r"\s+", " ", regex=True)
    calls["handler_missing"] = handler_name.isna() | handler_name.eq("")
    calls["handler_name"] = handler_name.mask(calls["handler_missing"], UNKNOWN_HANDLER)

    calls["category_missing"] = calls["category_name"].isna() | _clean_text_series(calls["category_name"]).isna()
    calls["category_name"] = _clean_text_series(calls["category_name"], UNKNOWN_CATEGORY)
    calls["channel_type"] = _clean_text_series(calls["channel_type"], UNKNOWN_TEXT)
    calls["status"] = _clean_text_series(calls["status"], UNKNOWN_TEXT)
    calls["sr_number"] = _clean_text_series(calls["sr_number"])

    calls["reported_month"] = calls["date_reported"].dt.to_period("M").dt.to_timestamp()
    calls["resolution_month"] = calls["resolution_date"].dt.to_period("M").dt.to_timestamp()

    has_reported_and_resolution = calls["date_reported"].notna() & calls["resolution_date"].notna()
    calls["resolution_days"] = pd.NA
    calls.loc[has_reported_and_resolution, "resolution_days"] = (
        calls.loc[has_reported_and_resolution, "resolution_date"].dt.normalize()
        - calls.loc[has_reported_and_resolution, "date_reported"].dt.normalize()
    ).dt.days
    calls["resolution_days"] = pd.to_numeric(calls["resolution_days"], errors="coerce")

    resolution_raw_present = (
        calls["resolution_date_raw"].notna()
        & calls["resolution_date_raw"].astype("string").str.strip().ne("")
    )
    calls["resolution_date_invalid"] = resolution_raw_present & calls["resolution_date"].isna()
    calls["negative_resolution_duration"] = calls["resolution_days"] < 0

    return calls, missing_expected


def _find_date_column(dataframe: pd.DataFrame) -> object:
    for column in dataframe.columns:
        if "date" in str(column).strip().lower():
            return column
    return dataframe.columns[0]


def _normalise_employee_name(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return None
    return text


def clean_absence_sheet(raw_absence: pd.DataFrame, absence_type: str) -> pd.DataFrame:
    if raw_absence.empty:
        return pd.DataFrame(columns=["date", "employee_name", "absence_type", "value"])

    source = raw_absence.copy()
    date_column = _find_date_column(source)
    source[date_column] = coerce_excel_date(source[date_column]).dt.normalize()
    employee_columns = [
        column
        for column in source.columns
        if column != date_column and not str(column).strip().lower().startswith("unnamed")
    ]

    long = source.melt(
        id_vars=[date_column],
        value_vars=employee_columns,
        var_name="employee_name",
        value_name="raw_value",
    )
    long = long.rename(columns={date_column: "date"})
    long["employee_name"] = long["employee_name"].map(_normalise_employee_name)
    long["raw_text"] = long["raw_value"].astype("string").str.strip()
    numeric_value = pd.to_numeric(long["raw_value"], errors="coerce")

    has_marker = long["raw_value"].notna() & long["raw_text"].ne("") & long["raw_text"].str.lower().ne("nan")
    has_marker = has_marker & ~(numeric_value.fillna(1).eq(0))
    long = long.loc[has_marker & long["date"].notna() & long["employee_name"].notna()].copy()
    long["absence_type"] = absence_type
    long["value"] = numeric_value.loc[long.index].where(numeric_value.loc[long.index] > 0, 1.0)
    return long[["date", "employee_name", "absence_type", "value"]]


def _normalise_for_match(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _handler_name_resolver(calls: pd.DataFrame):
    handler_names = sorted(
        name
        for name in calls.get("handler_name", pd.Series(dtype="string")).dropna().unique()
        if str(name) != UNKNOWN_HANDLER
    )
    exact = {_normalise_for_match(name): name for name in handler_names}

    first_name_map: dict[str, str | None] = {}
    for handler in handler_names:
        first_token = _normalise_for_match(handler).split(" ")[0]
        if first_token not in first_name_map:
            first_name_map[first_token] = handler
        else:
            first_name_map[first_token] = None

    def resolve(name: object) -> str:
        normalised = _normalise_for_match(name)
        if normalised in exact:
            return exact[normalised]
        first_match = first_name_map.get(normalised)
        return first_match or str(name)

    return resolve


def align_absence_to_handlers(absence: pd.DataFrame, calls: pd.DataFrame) -> pd.DataFrame:
    if absence.empty:
        absence = absence.copy()
        absence["matched_employee_name"] = pd.Series(dtype="string")
        return absence

    aligned = absence.copy()
    resolve = _handler_name_resolver(calls)
    aligned["source_employee_name"] = aligned["employee_name"]
    aligned["matched_employee_name"] = aligned["employee_name"].map(resolve)
    return aligned


def absence_header_employee_names(raw_absence: pd.DataFrame) -> list[str]:
    if raw_absence.empty:
        return []
    date_column = _find_date_column(raw_absence)
    names = []
    for column in raw_absence.columns:
        if column == date_column or str(column).strip().lower().startswith("unnamed"):
            continue
        name = _normalise_employee_name(column)
        if name:
            names.append(name)
    return names


def build_employee_dimension(
    calls: pd.DataFrame,
    absence: pd.DataFrame,
    extra_absence_names: list[str] | None = None,
) -> pd.DataFrame:
    call_names = set(calls.get("handler_name", pd.Series(dtype="string")).dropna().astype(str))
    absence_names = set(
        absence.get("matched_employee_name", absence.get("employee_name", pd.Series(dtype="string")))
        .dropna()
        .astype(str)
    )
    absence_names.update(extra_absence_names or [])
    all_names = sorted(name for name in call_names | absence_names if name.strip())
    rows = []
    for index, name in enumerate(all_names, start=1):
        sources = []
        if name in call_names:
            sources.append("Calls")
        if name in absence_names:
            sources.append("Absence")
        rows.append(
            {
                "employee_id": index,
                "employee_name": name,
                "source": ", ".join(sources),
            }
        )
    return pd.DataFrame(rows)


def transform_workbook(
    raw_sr_data: pd.DataFrame,
    raw_sickness: pd.DataFrame,
    raw_annual_leave: pd.DataFrame,
    source_stats: dict[str, object] | None = None,
) -> ModelFrames:
    calls, missing_expected = clean_sr_data(raw_sr_data)
    sickness = clean_absence_sheet(raw_sickness, "Sickness")
    annual_leave = clean_absence_sheet(raw_annual_leave, "Annual Leave")
    absence = pd.concat([sickness, annual_leave], ignore_index=True)
    absence = align_absence_to_handlers(absence, calls)
    resolve = _handler_name_resolver(calls)
    absence_sheet_names = [
        resolve(name)
        for name in absence_header_employee_names(raw_sickness) + absence_header_employee_names(raw_annual_leave)
    ]
    employees = build_employee_dimension(calls, absence, absence_sheet_names)

    metadata = {
        "missing_expected_columns": missing_expected,
        "source_stats": source_stats or {},
        "calls_rows_cleaned": int(calls.shape[0]),
        "absence_rows_cleaned": int(absence.shape[0]),
        "employees_count": int(employees.shape[0]),
    }
    return ModelFrames(calls=calls, absence=absence, employees=employees, metadata=metadata)
