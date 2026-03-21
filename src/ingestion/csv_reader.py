from __future__ import annotations

import csv
from io import BytesIO
from pathlib import Path

import pandas as pd

from src.models import CsvIngestionResult
from src.storage import store_raw_csv


SUPPORTED_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252")


class InvalidCsvFileError(ValueError):
    """Raised when an uploaded file is not an acceptable CSV."""


def ingest_csv_file(
    file_name: str,
    file_content: bytes,
    raw_data_dir: Path | str | None = None,
) -> CsvIngestionResult:
    validate_csv_upload(file_name=file_name, file_content=file_content)
    dataframe = read_csv_bytes(file_content)
    stored_path = store_raw_csv(
        file_name=file_name,
        file_content=file_content,
        raw_data_dir=raw_data_dir,
    )
    return CsvIngestionResult(
        source_name=file_name,
        stored_path=stored_path,
        dataframe=dataframe,
    )


def validate_csv_upload(file_name: str, file_content: bytes) -> None:
    if not is_csv_file(file_name):
        raise InvalidCsvFileError("Uploaded file must use the .csv extension.")

    if not file_content:
        raise InvalidCsvFileError("Uploaded CSV file is empty.")


def is_csv_file(file_name: str) -> bool:
    return bool(file_name) and Path(file_name).suffix.casefold() == ".csv"


def read_csv_bytes(file_content: bytes) -> pd.DataFrame:
    last_encoding_error: UnicodeDecodeError | None = None

    for encoding in SUPPORTED_ENCODINGS:
        try:
            delimiter = detect_csv_delimiter(file_content=file_content, encoding=encoding)
            return pd.read_csv(
                BytesIO(file_content),
                encoding=encoding,
                sep=delimiter,
            )
        except UnicodeDecodeError as exc:
            last_encoding_error = exc
        except pd.errors.EmptyDataError as exc:
            raise InvalidCsvFileError("Uploaded CSV file is empty.") from exc
        except pd.errors.ParserError as exc:
            raise InvalidCsvFileError("Uploaded file could not be parsed as CSV.") from exc

    raise InvalidCsvFileError(
        "Uploaded CSV file uses an unsupported text encoding."
    ) from last_encoding_error


def detect_csv_delimiter(file_content: bytes, encoding: str) -> str:
    sample = file_content[:4096].decode(encoding)

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return ","

    return dialect.delimiter
