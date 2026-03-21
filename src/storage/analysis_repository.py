from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import duckdb

from src.models.profiling import DatasetProfile
from src.models.storage import PersistedAnalysisRun
from src.models.validation import DatasetValidationResult, ValidationIssue


DEFAULT_PROCESSED_DATA_DIR = Path("data/processed")
DEFAULT_DATABASE_PATH = DEFAULT_PROCESSED_DATA_DIR / "analysis.duckdb"

RUN_SELECT_COLUMNS = """
    run_id,
    file_name,
    raw_file_path,
    uploaded_at,
    row_count,
    column_count,
    total_null_count,
    total_issue_count,
    affected_row_count
"""


def initialize_analysis_storage(
    database_path: Path | str | None = None,
) -> Path:
    resolved_database_path = _resolve_database_path(database_path)
    with _connect(resolved_database_path) as connection:
        _ensure_schema(connection)
    return resolved_database_path


def save_analysis_run(
    file_name: str,
    profile_result: DatasetProfile,
    validation_result: DatasetValidationResult,
    raw_file_path: Path | str | None = None,
    uploaded_at: datetime | None = None,
    database_path: Path | str | None = None,
) -> PersistedAnalysisRun:
    resolved_database_path = initialize_analysis_storage(database_path)
    normalized_uploaded_at = _normalize_uploaded_at(uploaded_at)
    persisted_run = PersistedAnalysisRun(
        run_id=uuid4().hex,
        file_name=file_name,
        uploaded_at=normalized_uploaded_at,
        row_count=profile_result.row_count,
        column_count=profile_result.column_count,
        total_null_count=profile_result.total_null_count,
        total_issue_count=validation_result.summary.issue_count,
        affected_row_count=validation_result.summary.affected_row_count,
        raw_file_path=Path(raw_file_path).resolve() if raw_file_path is not None else None,
    )
    issue_rows = [
        (
            persisted_run.run_id,
            index,
            issue.rule_name,
            issue.severity,
            issue.column_name,
            issue.description,
            issue.affected_row_count,
            json.dumps(list(issue.failing_row_numbers)),
            issue.summary_label,
            issue.sample_row_limit,
        )
        for index, issue in enumerate(validation_result.issues)
    ]

    with _connect(resolved_database_path) as connection:
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute(
                """
                INSERT INTO analysis_runs (
                    run_id,
                    file_name,
                    raw_file_path,
                    uploaded_at,
                    row_count,
                    column_count,
                    total_null_count,
                    total_issue_count,
                    affected_row_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    persisted_run.run_id,
                    persisted_run.file_name,
                    str(persisted_run.raw_file_path) if persisted_run.raw_file_path is not None else None,
                    persisted_run.uploaded_at.replace(tzinfo=None),
                    persisted_run.row_count,
                    persisted_run.column_count,
                    persisted_run.total_null_count,
                    persisted_run.total_issue_count,
                    persisted_run.affected_row_count,
                ],
            )
            if issue_rows:
                connection.executemany(
                    """
                    INSERT INTO validation_issues (
                        run_id,
                        issue_position,
                        rule_name,
                        severity,
                        column_name,
                        description,
                        affected_row_count,
                        failing_row_numbers,
                        summary_label,
                        sample_row_limit
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    issue_rows,
                )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    return persisted_run


def get_latest_run(
    database_path: Path | str | None = None,
) -> PersistedAnalysisRun | None:
    resolved_database_path = initialize_analysis_storage(database_path)
    with _connect(resolved_database_path) as connection:
        row = connection.execute(
            f"""
            SELECT {RUN_SELECT_COLUMNS}
            FROM analysis_runs
            ORDER BY uploaded_at DESC, run_id DESC
            LIMIT 1
            """
        ).fetchone()
    return _build_persisted_run(row) if row is not None else None


def get_run(
    run_id: str,
    database_path: Path | str | None = None,
) -> PersistedAnalysisRun | None:
    resolved_database_path = initialize_analysis_storage(database_path)
    with _connect(resolved_database_path) as connection:
        row = connection.execute(
            f"""
            SELECT {RUN_SELECT_COLUMNS}
            FROM analysis_runs
            WHERE run_id = ?
            """,
            [run_id],
        ).fetchone()
    return _build_persisted_run(row) if row is not None else None


def list_runs(
    database_path: Path | str | None = None,
) -> tuple[PersistedAnalysisRun, ...]:
    resolved_database_path = initialize_analysis_storage(database_path)
    with _connect(resolved_database_path) as connection:
        rows = connection.execute(
            f"""
            SELECT {RUN_SELECT_COLUMNS}
            FROM analysis_runs
            ORDER BY uploaded_at DESC, run_id DESC
            """
        ).fetchall()
    return tuple(_build_persisted_run(row) for row in rows)


def get_run_issues(
    run_id: str,
    database_path: Path | str | None = None,
) -> tuple[ValidationIssue, ...]:
    resolved_database_path = initialize_analysis_storage(database_path)
    with _connect(resolved_database_path) as connection:
        rows = connection.execute(
            """
            SELECT
                rule_name,
                severity,
                column_name,
                description,
                affected_row_count,
                failing_row_numbers,
                summary_label,
                sample_row_limit
            FROM validation_issues
            WHERE run_id = ?
            ORDER BY issue_position ASC
            """,
            [run_id],
        ).fetchall()
    return tuple(_build_validation_issue(row) for row in rows)


@contextmanager
def _connect(database_path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect(str(database_path))
    try:
        _ensure_schema(connection)
        yield connection
    finally:
        connection.close()


def _resolve_database_path(database_path: Path | str | None) -> Path:
    resolved_database_path = Path(database_path) if database_path is not None else DEFAULT_DATABASE_PATH
    resolved_database_path.parent.mkdir(parents=True, exist_ok=True)
    return resolved_database_path.resolve()


def _ensure_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_runs (
            run_id VARCHAR PRIMARY KEY,
            file_name VARCHAR NOT NULL,
            raw_file_path VARCHAR,
            uploaded_at TIMESTAMP NOT NULL,
            row_count INTEGER NOT NULL,
            column_count INTEGER NOT NULL,
            total_null_count INTEGER NOT NULL,
            total_issue_count INTEGER NOT NULL,
            affected_row_count INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS validation_issues (
            run_id VARCHAR NOT NULL,
            issue_position INTEGER NOT NULL,
            rule_name VARCHAR NOT NULL,
            severity VARCHAR NOT NULL,
            column_name VARCHAR,
            description VARCHAR NOT NULL,
            affected_row_count INTEGER NOT NULL,
            failing_row_numbers VARCHAR NOT NULL,
            summary_label VARCHAR,
            sample_row_limit INTEGER NOT NULL,
            PRIMARY KEY (run_id, issue_position)
        )
        """
    )


def _normalize_uploaded_at(uploaded_at: datetime | None) -> datetime:
    if uploaded_at is None:
        return datetime.now(timezone.utc)
    if uploaded_at.tzinfo is None:
        return uploaded_at.replace(tzinfo=timezone.utc)
    return uploaded_at.astimezone(timezone.utc)


def _build_persisted_run(row: tuple[object, ...]) -> PersistedAnalysisRun:
    uploaded_at = row[3]
    if not isinstance(uploaded_at, datetime):
        raise TypeError("Expected uploaded_at to be a datetime.")
    normalized_uploaded_at = (
        uploaded_at.replace(tzinfo=timezone.utc)
        if uploaded_at.tzinfo is None
        else uploaded_at.astimezone(timezone.utc)
    )
    raw_file_path = Path(row[2]) if row[2] is not None else None
    return PersistedAnalysisRun(
        run_id=str(row[0]),
        file_name=str(row[1]),
        raw_file_path=raw_file_path,
        uploaded_at=normalized_uploaded_at,
        row_count=int(row[4]),
        column_count=int(row[5]),
        total_null_count=int(row[6]),
        total_issue_count=int(row[7]),
        affected_row_count=int(row[8]),
    )


def _build_validation_issue(row: tuple[object, ...]) -> ValidationIssue:
    failing_row_numbers = tuple(int(value) for value in json.loads(str(row[5])))
    return ValidationIssue(
        rule_name=str(row[0]),
        severity=str(row[1]),
        column_name=str(row[2]) if row[2] is not None else None,
        description=str(row[3]),
        affected_row_count=int(row[4]),
        failing_row_numbers=failing_row_numbers,
        summary_label=str(row[6]) if row[6] is not None else None,
        sample_row_limit=int(row[7]),
    )
