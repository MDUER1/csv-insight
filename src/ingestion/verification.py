from __future__ import annotations

from src.ingestion.csv_reader import InvalidCsvFileError, read_csv_bytes
from src.models import CsvIngestionResult, CsvIngestionVerification


def verify_ingestion_result(
    ingestion_result: CsvIngestionResult,
    file_content: bytes,
) -> CsvIngestionVerification:
    if not ingestion_result.stored_path.exists():
        return CsvIngestionVerification(
            is_valid=False,
            message="Upload failed verification because the stored raw copy was not found.",
        )

    if ingestion_result.stored_path.read_bytes() != file_content:
        return CsvIngestionVerification(
            is_valid=False,
            message="Upload failed verification because the stored raw copy does not match the uploaded file.",
        )

    try:
        reparsed_dataframe = read_csv_bytes(file_content)
    except InvalidCsvFileError as exc:
        return CsvIngestionVerification(
            is_valid=False,
            message=f"Upload failed verification because the stored file could not be reparsed: {exc}",
        )

    if not ingestion_result.dataframe.equals(reparsed_dataframe):
        return CsvIngestionVerification(
            is_valid=False,
            message="Upload failed verification because the parsed data could not be reproduced from the uploaded file.",
        )

    return CsvIngestionVerification(
        is_valid=True,
        message="Upload, storage, and parsing checks passed.",
    )
