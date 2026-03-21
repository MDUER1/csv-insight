from __future__ import annotations

from datetime import datetime, timezone

import duckdb
import pandas as pd

from src.profiling import build_dataset_profile
from src.rules import validate_dataset
from src.storage.analysis_repository import (
    get_latest_run,
    get_run,
    get_run_issues,
    initialize_analysis_storage,
    list_runs,
    save_analysis_run,
)


def test_initialize_analysis_storage_creates_required_tables(tmp_path) -> None:
    database_path = tmp_path / "processed" / "analysis.duckdb"

    resolved_database_path = initialize_analysis_storage(database_path)

    assert resolved_database_path == database_path.resolve()
    assert resolved_database_path.exists()

    connection = duckdb.connect(str(resolved_database_path))
    try:
        tables = {
            row[0]
            for row in connection.execute("SHOW TABLES").fetchall()
        }
    finally:
        connection.close()

    assert {"analysis_runs", "validation_issues"} <= tables


def test_save_analysis_run_persists_run_summary(tmp_path) -> None:
    database_path = tmp_path / "processed" / "analysis.duckdb"
    uploaded_at = datetime(2026, 3, 20, 8, 30, tzinfo=timezone.utc)
    profile_result, validation_result = build_sample_analysis_results()
    raw_file_path = tmp_path / "raw" / "people.csv"

    saved_run = save_analysis_run(
        file_name="people.csv",
        raw_file_path=raw_file_path,
        profile_result=profile_result,
        validation_result=validation_result,
        uploaded_at=uploaded_at,
        database_path=database_path,
    )
    loaded_run = get_run(saved_run.run_id, database_path=database_path)

    assert loaded_run is not None
    assert loaded_run.run_id == saved_run.run_id
    assert loaded_run.file_name == "people.csv"
    assert loaded_run.raw_file_path == raw_file_path.resolve()
    assert loaded_run.uploaded_at == uploaded_at
    assert loaded_run.row_count == 3
    assert loaded_run.column_count == 3
    assert loaded_run.total_null_count == 2
    assert loaded_run.total_issue_count == 6
    assert loaded_run.affected_row_count == 2


def test_get_latest_run_returns_most_recent_saved_run(tmp_path) -> None:
    database_path = tmp_path / "processed" / "analysis.duckdb"
    profile_result, validation_result = build_sample_analysis_results()

    save_analysis_run(
        file_name="older.csv",
        profile_result=profile_result,
        validation_result=validation_result,
        uploaded_at=datetime(2026, 3, 19, 8, 30, tzinfo=timezone.utc),
        database_path=database_path,
    )
    save_analysis_run(
        file_name="latest.csv",
        profile_result=profile_result,
        validation_result=validation_result,
        uploaded_at=datetime(2026, 3, 20, 8, 30, tzinfo=timezone.utc),
        database_path=database_path,
    )

    latest_run = get_latest_run(database_path=database_path)

    assert latest_run is not None
    assert latest_run.file_name == "latest.csv"


def test_list_runs_returns_saved_runs_in_reverse_chronological_order(tmp_path) -> None:
    database_path = tmp_path / "processed" / "analysis.duckdb"
    profile_result, validation_result = build_sample_analysis_results()

    first_run = save_analysis_run(
        file_name="first.csv",
        profile_result=profile_result,
        validation_result=validation_result,
        uploaded_at=datetime(2026, 3, 18, 8, 30, tzinfo=timezone.utc),
        database_path=database_path,
    )
    second_run = save_analysis_run(
        file_name="second.csv",
        profile_result=profile_result,
        validation_result=validation_result,
        uploaded_at=datetime(2026, 3, 20, 8, 30, tzinfo=timezone.utc),
        database_path=database_path,
    )

    runs = list_runs(database_path=database_path)

    assert [run.run_id for run in runs] == [second_run.run_id, first_run.run_id]
    assert [run.file_name for run in runs] == ["second.csv", "first.csv"]


def test_get_run_issues_round_trips_saved_validation_issues(tmp_path) -> None:
    database_path = tmp_path / "processed" / "analysis.duckdb"
    profile_result, validation_result = build_sample_analysis_results()

    saved_run = save_analysis_run(
        file_name="people.csv",
        profile_result=profile_result,
        validation_result=validation_result,
        uploaded_at=datetime(2026, 3, 20, 8, 30, tzinfo=timezone.utc),
        database_path=database_path,
    )

    issues = get_run_issues(saved_run.run_id, database_path=database_path)

    assert [issue.rule_name for issue in issues] == [
        "Null check",
        "Duplicate identifier check",
        "Duplicate row check",
    ]
    assert [issue.severity for issue in issues] == ["warning", "error", "error"]
    assert [issue.column_name for issue in issues] == ["name", "id", None]
    assert [issue.affected_row_count for issue in issues] == [2, 2, 2]
    assert [issue.failing_row_numbers for issue in issues] == [(2, 3), (2, 3), (2, 3)]
    assert [issue.sample_row_numbers for issue in issues] == [(2, 3), (2, 3), (2, 3)]


def build_sample_analysis_results():
    dataframe = pd.DataFrame(
        {
            "id": [1, 2, 2],
            "name": ["Ada", None, None],
            "city": ["London", "Paris", "Paris"],
        }
    )
    return build_dataset_profile(dataframe), validate_dataset(dataframe)
