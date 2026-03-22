from __future__ import annotations

from dataclasses import dataclass

from src.models.ingestion import CsvIngestionResult, CsvIngestionVerification
from src.models.profiling import DatasetProfile
from src.models.validation import DatasetValidationResult


@dataclass(frozen=True, slots=True)
class CsvUpload:
    file_name: str
    file_content: bytes


@dataclass(frozen=True, slots=True)
class SuccessfulCsvUploadAnalysis:
    file_name: str
    file_content: bytes
    ingestion_result: CsvIngestionResult
    profile_result: DatasetProfile
    verification_result: CsvIngestionVerification
    validation_result: DatasetValidationResult
    run_id: str | None
    persistence_error: str | None


@dataclass(frozen=True, slots=True)
class FailedCsvUploadAnalysis:
    file_name: str
    file_content: bytes
    error_message: str


@dataclass(frozen=True, slots=True)
class CsvUploadBatchAnalysis:
    successful_analyses: tuple[SuccessfulCsvUploadAnalysis, ...]
    failed_analyses: tuple[FailedCsvUploadAnalysis, ...]

    @property
    def total_file_count(self) -> int:
        return self.successful_file_count + self.failed_file_count

    @property
    def successful_file_count(self) -> int:
        return len(self.successful_analyses)

    @property
    def failed_file_count(self) -> int:
        return len(self.failed_analyses)

    @property
    def total_size_bytes(self) -> int:
        return sum(
            len(analysis.file_content)
            for analysis in self.successful_analyses
        ) + sum(len(analysis.file_content) for analysis in self.failed_analyses)

    @property
    def total_row_count(self) -> int:
        return sum(
            analysis.profile_result.row_count
            for analysis in self.successful_analyses
        )

    @property
    def total_issue_count(self) -> int:
        return sum(
            analysis.validation_result.summary.issue_count
            for analysis in self.successful_analyses
        )

    @property
    def files_with_issues_count(self) -> int:
        return sum(
            analysis.validation_result.summary.issue_count > 0
            for analysis in self.successful_analyses
        )

    @property
    def persisted_run_count(self) -> int:
        return sum(
            analysis.run_id is not None
            for analysis in self.successful_analyses
        )
