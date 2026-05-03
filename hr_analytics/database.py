from __future__ import annotations

import json
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from .config import DATABASE_URL, DATA_DIR


TABLES = ("calls", "absence", "employees", "load_metadata")


def get_engine(database_url: str | None = None) -> Engine:
    DATA_DIR.mkdir(exist_ok=True)
    return create_engine(database_url or DATABASE_URL, future=True)


def initialise_database(engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS load_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
        )


def _json_default(value: Any) -> str:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


def save_metadata(metadata: dict[str, Any], engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    rows = [
        {"key": key, "value": json.dumps(value, default=_json_default)}
        for key, value in metadata.items()
    ]
    dataframe = pd.DataFrame(rows)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM load_metadata"))
    dataframe.to_sql("load_metadata", engine, if_exists="append", index=False)


def load_metadata(engine: Engine | None = None) -> dict[str, Any]:
    engine = engine or get_engine()
    if not inspect(engine).has_table("load_metadata"):
        return {}
    dataframe = pd.read_sql_query("SELECT key, value FROM load_metadata", engine)
    metadata: dict[str, Any] = {}
    for _, row in dataframe.iterrows():
        try:
            metadata[row["key"]] = json.loads(row["value"])
        except json.JSONDecodeError:
            metadata[row["key"]] = row["value"]
    return metadata


def save_calls_dataframe(calls: pd.DataFrame, engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    calls.to_sql("calls", engine, if_exists="replace", index=False)


def save_absence_dataframe(absence: pd.DataFrame, engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    absence.to_sql("absence", engine, if_exists="replace", index=False)


def save_employees_dataframe(employees: pd.DataFrame, engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    employees.to_sql("employees", engine, if_exists="replace", index=False)


def save_model_frames(
    calls: pd.DataFrame,
    absence: pd.DataFrame,
    employees: pd.DataFrame,
    metadata: dict[str, Any],
    engine: Engine | None = None,
) -> None:
    engine = engine or get_engine()
    initialise_database(engine)
    save_calls_dataframe(calls, engine)
    save_absence_dataframe(absence, engine)
    save_employees_dataframe(employees, engine)
    save_metadata(metadata, engine)


def _read_table(table_name: str, engine: Engine) -> pd.DataFrame:
    if not inspect(engine).has_table(table_name):
        return pd.DataFrame()
    return pd.read_sql_query(f"SELECT * FROM {table_name}", engine)


def _parse_datetime_columns(dataframe: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    dataframe = dataframe.copy()
    for column in columns:
        if column in dataframe.columns:
            dataframe[column] = pd.to_datetime(dataframe[column], errors="coerce")
    return dataframe


def _parse_bool_columns(dataframe: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    dataframe = dataframe.copy()
    truthy = {True, 1, "1", "true", "True", "TRUE", "yes", "Yes"}
    falsey = {False, 0, "0", "false", "False", "FALSE", "no", "No"}
    for column in columns:
        if column in dataframe.columns:
            dataframe[column] = dataframe[column].map(
                lambda value: True if value in truthy else False if value in falsey else pd.NA
            ).astype("boolean")
    return dataframe


def load_data_from_database(engine: Engine | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    engine = engine or get_engine()
    calls = _read_table("calls", engine)
    absence = _read_table("absence", engine)
    employees = _read_table("employees", engine)
    metadata = load_metadata(engine)

    calls = _parse_datetime_columns(
        calls,
        (
            "date_reported",
            "resolution_date",
            "last_queue_assigned_date",
            "last_response_date",
            "completion_date_and_time",
            "reported_month",
            "resolution_month",
        ),
    )
    calls = _parse_bool_columns(
        calls,
        (
            "first_response_compliant",
            "handler_missing",
            "category_missing",
            "resolution_date_invalid",
            "negative_resolution_duration",
        ),
    )
    absence = _parse_datetime_columns(absence, ("date",))
    return calls, absence, employees, metadata


def clear_database(engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    with engine.begin() as connection:
        for table in TABLES:
            connection.execute(text(f"DROP TABLE IF EXISTS {table}"))
    initialise_database(engine)

