from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    issue_count: int
    affected_row_count: int
    clean_row_count: int
    affected_column_count: int
    rule_count: int
    quality_level: str
    biggest_problem_labels: tuple[str, ...]
    message: str


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    rule_name: str
    severity: str
    column_name: str | None
    description: str
    affected_row_count: int
    failing_row_numbers: tuple[int, ...]
    summary_label: str | None = None
    sample_row_limit: int = 5

    @property
    def sample_row_numbers(self) -> tuple[int, ...]:
        return self.failing_row_numbers[: self.sample_row_limit]


@dataclass(frozen=True, slots=True)
class DatasetValidationResult:
    summary: ValidationSummary
    issues: tuple[ValidationIssue, ...]


@dataclass(frozen=True, slots=True)
class NumericRangeConstraint:
    min_value: float | None = None
    max_value: float | None = None


@dataclass(frozen=True, slots=True)
class ValidationRuleConfig:
    sample_row_limit: int = 5
    key_column_patterns: tuple[str, ...] = ()
    email_column_keywords: tuple[str, ...] = ("email",)
    date_column_keywords: tuple[str, ...] = ("date",)
    numeric_ranges: Mapping[str, NumericRangeConstraint] = field(default_factory=dict)
