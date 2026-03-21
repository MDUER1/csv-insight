from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import duckdb

from src.models import (
    ColumnProfile,
    CsvIngestionResult,
    DatasetProfile,
    DatasetValidationResult,
    RunIssueTrendPoint,
    StoredAnalysisRun,
    StoredRunDetails,
    StoredValidationIssue,
)


DEFAULT_ANALYSIS_DB_PATH = Path("data/processed/analysis.duckdb")

RUN_COLUMN_NAMES = (
    "run_id",
    "source_name",
    "stored_path",
    "uploaded_at",
    "file_hash",
    "file_size_bytes",
    "row_count",
    "column_count",
    "total_null_count",
    "duplicate_row_count",
    "issue_count",
    "affected_row_count",
    "clean_row_count",
    "affected_column_count",
    "rule_count",
    "quality_level",
    "biggest_problem_labels",
    "validation_message",
)


class DuckDbAnalysisStore:
    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = (
            Path(database_path)
            if database_path is not None
            else DEFAULT_ANALYSIS_DB_PATH
        )

    def save_upload_run(
        self,
        ingestion_result: CsvIngestionResult,
        file_content: bytes,
        profile_result: DatasetProfile,
        validation_result: DatasetValidationResult,
        uploaded_at: datetime | None = None,
    ) -> str:
        run_id = uuid4().hex
        resolved_uploaded_at = _normalize_uploaded_at(uploaded_at)
        file_hash = hashlib.sha256(file_content).hexdigest()
        summary = validation_result.summary
        connection = self._connect()

        try:
            connection.execute("BEGIN TRANSACTION")
            connection.execute(
                """
                INSERT INTO upload_runs (
                    run_id,
                    source_name,
                    stored_path,
                    uploaded_at,
                    file_hash,
                    file_size_bytes,
                    row_count,
                    column_count,
                    total_null_count,
                    duplicate_row_count,
                    issue_count,
                    affected_row_count,
                    clean_row_count,
                    affected_column_count,
                    rule_count,
                    quality_level,
                    biggest_problem_labels,
                    validation_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_id,
                    ingestion_result.source_name,
                    str(ingestion_result.stored_path),
                    resolved_uploaded_at.isoformat(),
                    file_hash,
                    len(file_content),
                    profile_result.row_count,
                    profile_result.column_count,
                    profile_result.total_null_count,
                    profile_result.duplicate_row_count,
                    summary.issue_count,
                    summary.affected_row_count,
                    summary.clean_row_count,
                    summary.affected_column_count,
                    summary.rule_count,
                    summary.quality_level,
                    json.dumps(summary.biggest_problem_labels),
                    summary.message,
                ],
            )
            connection.execute(
                """
                INSERT INTO dataset_profiles (
                    run_id,
                    row_count,
                    column_count,
                    total_null_count,
                    duplicate_row_count
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    run_id,
                    profile_result.row_count,
                    profile_result.column_count,
                    profile_result.total_null_count,
                    profile_result.duplicate_row_count,
                ],
            )

            if profile_result.column_profiles:
                connection.executemany(
                    """
                    INSERT INTO column_profiles (
                        run_id,
                        column_name,
                        column_index,
                        data_type,
                        null_count,
                        non_null_count,
                        unique_count,
                        null_ratio,
                        uniqueness_ratio
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            run_id,
                            column_profile.column_name,
                            column_profile.column_index,
                            column_profile.data_type,
                            column_profile.null_count,
                            column_profile.non_null_count,
                            column_profile.unique_count,
                            column_profile.null_ratio,
                            column_profile.uniqueness_ratio,
                        )
                        for column_profile in profile_result.column_profiles
                    ],
                )

            if validation_result.issues:
                connection.executemany(
                    """
                    INSERT INTO validation_issues (
                        run_id,
                        issue_index,
                        rule_name,
                        severity,
                        column_name,
                        affected_row_count,
                        sample_rows,
                        description
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            run_id,
                            issue_index,
                            issue.rule_name,
                            issue.severity,
                            issue.column_name,
                            issue.affected_row_count,
                            json.dumps(issue.sample_row_numbers),
                            issue.description,
                        )
                        for issue_index, issue in enumerate(validation_result.issues)
                    ],
                )

            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

        return run_id

    def load_recent_runs(self, limit: int = 10) -> tuple[StoredAnalysisRun, ...]:
        connection = self._connect()
        try:
            rows = connection.execute(
                f"""
                SELECT {", ".join(RUN_COLUMN_NAMES)}
                FROM upload_runs
                ORDER BY uploaded_at DESC, run_id DESC
                LIMIT ?
                """,
                [limit],
            ).fetchall()
        finally:
            connection.close()

        return tuple(_build_stored_run(row) for row in rows)

    def load_latest_run(self) -> StoredRunDetails | None:
        recent_runs = self.load_recent_runs(limit=1)
        if not recent_runs:
            return None

        return self.load_run_details(recent_runs[0].run_id)

    def load_run_details(self, run_id: str) -> StoredRunDetails | None:
        connection = self._connect()
        try:
            run_row = connection.execute(
                f"""
                SELECT {", ".join(RUN_COLUMN_NAMES)}
                FROM upload_runs
                WHERE run_id = ?
                """,
                [run_id],
            ).fetchone()
            if run_row is None:
                return None

            profile_row = connection.execute(
                """
                SELECT row_count, column_count, total_null_count, duplicate_row_count
                FROM dataset_profiles
                WHERE run_id = ?
                """,
                [run_id],
            ).fetchone()
            column_rows = connection.execute(
                """
                SELECT
                    column_name,
                    column_index,
                    data_type,
                    null_count,
                    non_null_count,
                    unique_count,
                    null_ratio,
                    uniqueness_ratio
                FROM column_profiles
                WHERE run_id = ?
                ORDER BY column_index
                """,
                [run_id],
            ).fetchall()
            issue_rows = connection.execute(
                """
                SELECT
                    rule_name,
                    severity,
                    column_name,
                    affected_row_count,
                    sample_rows,
                    description
                FROM validation_issues
                WHERE run_id = ?
                ORDER BY issue_index
                """,
                [run_id],
            ).fetchall()
        finally:
            connection.close()

        if profile_row is None:
            return None

        column_profiles = tuple(
            ColumnProfile(
                column_name=str(column_name),
                column_index=int(column_index),
                data_type=str(data_type),
                null_count=int(null_count),
                non_null_count=int(non_null_count),
                unique_count=int(unique_count),
                null_ratio=float(null_ratio),
                uniqueness_ratio=float(uniqueness_ratio),
            )
            for (
                column_name,
                column_index,
                data_type,
                null_count,
                non_null_count,
                unique_count,
                null_ratio,
                uniqueness_ratio,
            ) in column_rows
        )
        profile = DatasetProfile(
            row_count=int(profile_row[0]),
            column_count=int(profile_row[1]),
            duplicate_row_count=int(profile_row[3]),
            null_counts={
                column_profile.column_name: column_profile.null_count
                for column_profile in column_profiles
            },
            column_profiles=column_profiles,
        )
        issues = tuple(
            StoredValidationIssue(
                run_id=run_id,
                rule_name=str(rule_name),
                severity=str(severity),
                column_name=str(column_name) if column_name is not None else None,
                affected_row_count=int(affected_row_count),
                sample_row_numbers=_deserialize_int_tuple(sample_rows),
                description=str(description),
            )
            for (
                rule_name,
                severity,
                column_name,
                affected_row_count,
                sample_rows,
                description,
            ) in issue_rows
        )
        return StoredRunDetails(
            run=_build_stored_run(run_row),
            profile=profile,
            issues=issues,
        )

    def load_issue_trends(self, limit: int = 10) -> tuple[RunIssueTrendPoint, ...]:
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT run_id, uploaded_at, source_name, issue_count, affected_row_count, quality_level
                FROM upload_runs
                ORDER BY uploaded_at DESC, run_id DESC
                LIMIT ?
                """,
                [limit],
            ).fetchall()
        finally:
            connection.close()

        return tuple(
            RunIssueTrendPoint(
                run_id=str(run_id),
                uploaded_at=datetime.fromisoformat(str(uploaded_at)),
                source_name=str(source_name),
                issue_count=int(issue_count),
                affected_row_count=int(affected_row_count),
                quality_level=str(quality_level),
            )
            for (
                run_id,
                uploaded_at,
                source_name,
                issue_count,
                affected_row_count,
                quality_level,
            ) in rows
        )

    def _connect(self) -> duckdb.DuckDBPyConnection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect(str(self.database_path))
        _ensure_schema(connection)
        return connection


def _ensure_schema(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS upload_runs (
            run_id VARCHAR PRIMARY KEY,
            source_name VARCHAR NOT NULL,
            stored_path VARCHAR NOT NULL,
            uploaded_at VARCHAR NOT NULL,
            file_hash VARCHAR NOT NULL,
            file_size_bytes BIGINT NOT NULL,
            row_count BIGINT NOT NULL,
            column_count BIGINT NOT NULL,
            total_null_count BIGINT NOT NULL,
            duplicate_row_count BIGINT NOT NULL,
            issue_count BIGINT NOT NULL,
            affected_row_count BIGINT NOT NULL,
            clean_row_count BIGINT NOT NULL,
            affected_column_count BIGINT NOT NULL,
            rule_count BIGINT NOT NULL,
            quality_level VARCHAR NOT NULL,
            biggest_problem_labels VARCHAR NOT NULL,
            validation_message VARCHAR NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset_profiles (
            run_id VARCHAR PRIMARY KEY,
            row_count BIGINT NOT NULL,
            column_count BIGINT NOT NULL,
            total_null_count BIGINT NOT NULL,
            duplicate_row_count BIGINT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS column_profiles (
            run_id VARCHAR NOT NULL,
            column_name VARCHAR NOT NULL,
            column_index INTEGER NOT NULL,
            data_type VARCHAR NOT NULL,
            null_count BIGINT NOT NULL,
            non_null_count BIGINT NOT NULL,
            unique_count BIGINT NOT NULL,
            null_ratio DOUBLE NOT NULL,
            uniqueness_ratio DOUBLE NOT NULL,
            PRIMARY KEY (run_id, column_name)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS validation_issues (
            run_id VARCHAR NOT NULL,
            issue_index INTEGER NOT NULL,
            rule_name VARCHAR NOT NULL,
            severity VARCHAR NOT NULL,
            column_name VARCHAR,
            affected_row_count BIGINT NOT NULL,
            sample_rows VARCHAR NOT NULL,
            description VARCHAR NOT NULL,
            PRIMARY KEY (run_id, issue_index)
        )
        """
    )


def _build_stored_run(row: tuple[object, ...]) -> StoredAnalysisRun:
    return StoredAnalysisRun(
        run_id=str(row[0]),
        source_name=str(row[1]),
        stored_path=Path(str(row[2])),
        uploaded_at=datetime.fromisoformat(str(row[3])),
        file_hash=str(row[4]),
        file_size_bytes=int(row[5]),
        row_count=int(row[6]),
        column_count=int(row[7]),
        total_null_count=int(row[8]),
        duplicate_row_count=int(row[9]),
        issue_count=int(row[10]),
        affected_row_count=int(row[11]),
        clean_row_count=int(row[12]),
        affected_column_count=int(row[13]),
        rule_count=int(row[14]),
        quality_level=str(row[15]),
        biggest_problem_labels=tuple(json.loads(str(row[16]))),
        validation_message=str(row[17]),
    )


def _deserialize_int_tuple(value: object) -> tuple[int, ...]:
    return tuple(int(item) for item in json.loads(str(value)))


def _normalize_uploaded_at(uploaded_at: datetime | None) -> datetime:
    if uploaded_at is None:
        return datetime.now(timezone.utc)
    if uploaded_at.tzinfo is None:
        return uploaded_at.replace(tzinfo=timezone.utc)
    return uploaded_at.astimezone(timezone.utc)
