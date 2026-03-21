from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from src.ingestion import ingest_csv_file
from src.profiling import build_dataset_profile
from src.rules import validate_dataset
from src.storage import DuckDbAnalysisStore


def test_duckdb_analysis_store_persists_runs_profiles_and_issues(tmp_path) -> None:
    store = DuckDbAnalysisStore(
        database_path=tmp_path / "processed" / "analysis.duckdb"
    )
    raw_data_dir = tmp_path / "raw"

    first_file_content = b"id,name,city\n1,Ada,London\n2,,Paris\n2,,Paris\n"
    first_ingestion_result = ingest_csv_file(
        file_name="dirty_people.csv",
        file_content=first_file_content,
        raw_data_dir=raw_data_dir,
    )
    first_profile_result = build_dataset_profile(first_ingestion_result.dataframe)
    first_validation_result = validate_dataset(first_ingestion_result.dataframe)
    first_run_id = store.save_upload_run(
        ingestion_result=first_ingestion_result,
        file_content=first_file_content,
        profile_result=first_profile_result,
        validation_result=first_validation_result,
        uploaded_at=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
    )

    second_file_content = b"id,name,city\n1,Ada,London\n2,Grace,Paris\n"
    second_ingestion_result = ingest_csv_file(
        file_name="clean_people.csv",
        file_content=second_file_content,
        raw_data_dir=raw_data_dir,
    )
    second_profile_result = build_dataset_profile(second_ingestion_result.dataframe)
    second_validation_result = validate_dataset(second_ingestion_result.dataframe)
    second_run_id = store.save_upload_run(
        ingestion_result=second_ingestion_result,
        file_content=second_file_content,
        profile_result=second_profile_result,
        validation_result=second_validation_result,
        uploaded_at=datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc),
    )

    recent_runs = store.load_recent_runs(limit=2)

    assert [run.run_id for run in recent_runs] == [second_run_id, first_run_id]
    assert recent_runs[1].source_name == "dirty_people.csv"
    assert recent_runs[1].stored_path == first_ingestion_result.stored_path
    assert recent_runs[1].file_hash == hashlib.sha256(first_file_content).hexdigest()
    assert recent_runs[1].row_count == 3
    assert recent_runs[1].column_count == 3
    assert recent_runs[1].total_null_count == 2
    assert recent_runs[1].duplicate_row_count == 2
    assert recent_runs[1].issue_count == first_validation_result.summary.issue_count
    assert recent_runs[1].quality_level == first_validation_result.summary.quality_level
    assert (
        recent_runs[1].validation_summary.message
        == first_validation_result.summary.message
    )

    latest_run = store.load_latest_run()

    assert latest_run is not None
    assert latest_run.run.run_id == second_run_id
    assert latest_run.run.source_name == "clean_people.csv"

    first_run_details = store.load_run_details(first_run_id)

    assert first_run_details is not None
    assert first_run_details.run.run_id == first_run_id
    assert first_run_details.profile.row_count == first_profile_result.row_count
    assert (
        first_run_details.profile.duplicate_row_count
        == first_profile_result.duplicate_row_count
    )
    assert [column.column_name for column in first_run_details.profile.column_profiles] == [
        "id",
        "name",
        "city",
    ]
    assert first_run_details.profile.column_profiles[1].null_count == 2
    assert [issue.rule_name for issue in first_run_details.issues] == [
        issue.rule_name for issue in first_validation_result.issues
    ]
    assert first_run_details.issues[0].sample_row_numbers == (
        first_validation_result.issues[0].sample_row_numbers
    )

    trend_points = store.load_issue_trends(limit=2)

    assert [(point.run_id, point.issue_count) for point in trend_points] == [
        (second_run_id, second_validation_result.summary.issue_count),
        (first_run_id, first_validation_result.summary.issue_count),
    ]
