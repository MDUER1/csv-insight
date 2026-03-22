from __future__ import annotations

import hashlib
from collections.abc import Sequence

import duckdb

from src.ingestion import InvalidCsvFileError, ingest_csv_file, verify_ingestion_result
from src.models import (
    CsvUpload,
    CsvUploadBatchAnalysis,
    FailedCsvUploadAnalysis,
    SuccessfulCsvUploadAnalysis,
)
from src.profiling import build_dataset_profile
from src.rules import validate_dataset
from src.storage import DuckDbAnalysisStore


def analyze_csv_uploads(
    uploads: Sequence[CsvUpload],
    analysis_store: DuckDbAnalysisStore,
) -> CsvUploadBatchAnalysis:
    successful_analyses: list[SuccessfulCsvUploadAnalysis] = []
    failed_analyses: list[FailedCsvUploadAnalysis] = []

    for upload in sorted(uploads, key=_build_upload_sort_key):
        try:
            ingestion_result = ingest_csv_file(
                file_name=upload.file_name,
                file_content=upload.file_content,
            )
        except InvalidCsvFileError as exc:
            failed_analyses.append(
                FailedCsvUploadAnalysis(
                    file_name=upload.file_name,
                    file_content=upload.file_content,
                    error_message=str(exc),
                )
            )
            continue

        profile_result = build_dataset_profile(ingestion_result.dataframe)
        verification_result = verify_ingestion_result(
            ingestion_result=ingestion_result,
            file_content=upload.file_content,
        )
        validation_result = validate_dataset(ingestion_result.dataframe)
        run_id: str | None = None
        persistence_error: str | None = None

        try:
            run_id = analysis_store.save_upload_run(
                ingestion_result=ingestion_result,
                file_content=upload.file_content,
                profile_result=profile_result,
                validation_result=validation_result,
            )
        except (duckdb.Error, OSError) as exc:
            persistence_error = f"DuckDB persistence failed: {exc}"

        successful_analyses.append(
            SuccessfulCsvUploadAnalysis(
                file_name=upload.file_name,
                file_content=upload.file_content,
                ingestion_result=ingestion_result,
                profile_result=profile_result,
                verification_result=verification_result,
                validation_result=validation_result,
                run_id=run_id,
                persistence_error=persistence_error,
            )
        )

    return CsvUploadBatchAnalysis(
        successful_analyses=tuple(successful_analyses),
        failed_analyses=tuple(failed_analyses),
    )


def build_upload_batch_key(uploads: Sequence[CsvUpload]) -> str:
    upload_signatures = sorted(_build_upload_signature(upload) for upload in uploads)
    return hashlib.sha256("||".join(upload_signatures).encode("utf-8")).hexdigest()


def _build_upload_signature(upload: CsvUpload) -> str:
    normalized_file_name = upload.file_name.replace("\\", "/")
    file_hash = hashlib.sha256(upload.file_content).hexdigest()
    return f"{normalized_file_name}:{file_hash}"


def _build_upload_sort_key(upload: CsvUpload) -> tuple[str, str]:
    normalized_file_name = upload.file_name.replace("\\", "/").casefold()
    return normalized_file_name, _build_upload_signature(upload)
