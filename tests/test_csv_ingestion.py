from __future__ import annotations

import pytest

from src.ingestion import InvalidCsvFileError, ingest_csv_file, verify_ingestion_result


def test_ingest_csv_file_reads_dataframe_and_stores_raw_copy(tmp_path) -> None:
    raw_data_dir = tmp_path / "raw"
    file_content = b"id,name\n1,Ada\n2,Grace\n"

    result = ingest_csv_file(
        file_name="people.csv",
        file_content=file_content,
        raw_data_dir=raw_data_dir,
    )

    assert result.source_name == "people.csv"
    assert result.stored_path.parent == raw_data_dir.resolve()
    assert result.stored_path.suffix == ".csv"
    assert result.stored_path.read_bytes() == file_content
    assert result.dataframe.to_dict(orient="records") == [
        {"id": 1, "name": "Ada"},
        {"id": 2, "name": "Grace"},
    ]


def test_ingest_csv_file_parses_semicolon_delimited_csv(tmp_path) -> None:
    result = ingest_csv_file(
        file_name="people.csv",
        file_content=b"id;name\n1;Ada\n2;Grace\n",
        raw_data_dir=tmp_path / "raw",
    )

    assert result.dataframe.to_dict(orient="records") == [
        {"id": 1, "name": "Ada"},
        {"id": 2, "name": "Grace"},
    ]


def test_ingest_csv_file_rejects_non_csv_extension(tmp_path) -> None:
    with pytest.raises(InvalidCsvFileError, match=r"\.csv extension"):
        ingest_csv_file(
            file_name="people.txt",
            file_content=b"id,name\n1,Ada\n",
            raw_data_dir=tmp_path / "raw",
        )


def test_ingest_csv_file_rejects_invalid_csv_content(tmp_path) -> None:
    raw_data_dir = tmp_path / "raw"

    with pytest.raises(InvalidCsvFileError, match="parsed as CSV"):
        ingest_csv_file(
            file_name="broken.csv",
            file_content=b'id,name\n1,"Ada\n',
            raw_data_dir=raw_data_dir,
        )

    assert not raw_data_dir.exists()


def test_verify_ingestion_result_confirms_upload_storage_and_parsing(tmp_path) -> None:
    file_content = b"id,name\n1,Ada\n2,Grace\n"
    result = ingest_csv_file(
        file_name="people.csv",
        file_content=file_content,
        raw_data_dir=tmp_path / "raw",
    )

    verification = verify_ingestion_result(result, file_content)

    assert verification.is_valid is True
    assert verification.message == "Upload, storage, and parsing checks passed."


def test_verify_ingestion_result_reports_when_stored_copy_is_changed(tmp_path) -> None:
    file_content = b"id,name\n1,Ada\n2,Grace\n"
    result = ingest_csv_file(
        file_name="people.csv",
        file_content=file_content,
        raw_data_dir=tmp_path / "raw",
    )
    result.stored_path.write_bytes(b"id,name\n1,Ada\n2,Changed\n")

    verification = verify_ingestion_result(result, file_content)

    assert verification.is_valid is False
    assert "stored raw copy does not match" in verification.message
