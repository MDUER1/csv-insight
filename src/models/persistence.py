from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.models.profiling import DatasetProfile
from src.models.validation import ValidationSummary


@dataclass(frozen=True, slots=True)
class StoredAnalysisRun:
    run_id: str
    source_name: str
    stored_path: Path
    uploaded_at: datetime
    file_hash: str
    file_size_bytes: int
    row_count: int
    column_count: int
    total_null_count: int
    duplicate_row_count: int
    issue_count: int
    affected_row_count: int
    clean_row_count: int
    affected_column_count: int
    rule_count: int
    quality_level: str
    biggest_problem_labels: tuple[str, ...]
    validation_message: str

    @property
    def validation_summary(self) -> ValidationSummary:
        return ValidationSummary(
            issue_count=self.issue_count,
            affected_row_count=self.affected_row_count,
            clean_row_count=self.clean_row_count,
            affected_column_count=self.affected_column_count,
            rule_count=self.rule_count,
            quality_level=self.quality_level,
            biggest_problem_labels=self.biggest_problem_labels,
            message=self.validation_message,
        )


@dataclass(frozen=True, slots=True)
class StoredValidationIssue:
    run_id: str
    rule_name: str
    severity: str
    column_name: str | None
    affected_row_count: int
    sample_row_numbers: tuple[int, ...]
    description: str


@dataclass(frozen=True, slots=True)
class StoredRunDetails:
    run: StoredAnalysisRun
    profile: DatasetProfile
    issues: tuple[StoredValidationIssue, ...]


@dataclass(frozen=True, slots=True)
class RunIssueTrendPoint:
    run_id: str
    uploaded_at: datetime
    source_name: str
    issue_count: int
    affected_row_count: int
    quality_level: str
