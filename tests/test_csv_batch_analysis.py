from __future__ import annotations

from src.models import CsvUpload
from src.storage import DuckDbAnalysisStore
from src.workflows import analyze_csv_uploads, build_upload_batch_key


def test_build_upload_batch_key_is_order_independent() -> None:
    first_uploads = (
        CsvUpload(file_name="nested/orders.csv", file_content=b"id,total\n1,10\n"),
        CsvUpload(file_name="customers.csv", file_content=b"id,name\n1,Ada\n"),
    )
    second_uploads = tuple(reversed(first_uploads))

    assert build_upload_batch_key(first_uploads) == build_upload_batch_key(second_uploads)


def test_analyze_csv_uploads_processes_each_valid_file_and_tracks_rejections(
    tmp_path,
) -> None:
    analysis_store = DuckDbAnalysisStore(
        database_path=tmp_path / "processed" / "analysis.duckdb"
    )
    uploads = (
        CsvUpload(
            file_name="folder/clean_people.csv",
            file_content=b"id,name\n1,Ada\n2,Grace\n",
        ),
        CsvUpload(
            file_name="folder/broken_people.csv",
            file_content=b'id,name\n1,"Ada\n',
        ),
    )

    result = analyze_csv_uploads(uploads=uploads, analysis_store=analysis_store)

    assert result.total_file_count == 2
    assert result.successful_file_count == 1
    assert result.failed_file_count == 1
    assert result.total_row_count == 2
    assert result.persisted_run_count == 1

    successful_analysis = result.successful_analyses[0]
    assert successful_analysis.file_name == "folder/clean_people.csv"
    assert successful_analysis.profile_result.row_count == 2
    assert successful_analysis.run_id is not None
    assert successful_analysis.persistence_error is None

    failed_analysis = result.failed_analyses[0]
    assert failed_analysis.file_name == "folder/broken_people.csv"
    assert "parsed as CSV" in failed_analysis.error_message

    recent_runs = analysis_store.load_recent_runs(limit=5)

    assert len(recent_runs) == 1
    assert recent_runs[0].source_name == "folder/clean_people.csv"


def test_analyze_csv_uploads_keeps_results_when_duckdb_persistence_fails() -> None:
    class FailingAnalysisStore:
        def save_upload_run(self, **_: object) -> str:
            raise OSError("disk full")

    result = analyze_csv_uploads(
        uploads=(
            CsvUpload(
                file_name="people.csv",
                file_content=b"id,name\n1,Ada\n",
            ),
        ),
        analysis_store=FailingAnalysisStore(),
    )

    assert result.successful_file_count == 1
    assert result.persisted_run_count == 0
    assert result.failed_file_count == 0
    assert result.successful_analyses[0].run_id is None
    assert result.successful_analyses[0].persistence_error == "DuckDB persistence failed: disk full"
