from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

import pandas as pd

from src.models import (
    DatasetValidationResult,
    ValidationIssue,
    ValidationRuleConfig,
    ValidationSummary,
)
from src.rules.checks import RULE_CHECKS
from src.rules.config import load_validation_rule_config


ISSUE_TABLE_COLUMNS = [
    "rule",
    "severity",
    "column",
    "affected_rows",
    "sample_rows",
    "description",
]
FAILING_ROWS_TABLE_BASE_COLUMNS = ["row_number", "issues"]


def validate_dataset(
    dataframe: pd.DataFrame,
    rule_config: ValidationRuleConfig | None = None,
) -> DatasetValidationResult:
    resolved_rule_config = rule_config or load_validation_rule_config()
    issues: list[ValidationIssue] = []

    for rule_check in RULE_CHECKS:
        issues.extend(rule_check(dataframe, resolved_rule_config))

    summary = _build_validation_summary(dataframe, issues)
    return DatasetValidationResult(summary=summary, issues=tuple(issues))


def build_issue_table(validation_result: DatasetValidationResult) -> pd.DataFrame:
    return build_issue_records_table(validation_result.issues)


def build_issue_records_table(
    issues: Sequence[ValidationIssue],
) -> pd.DataFrame:
    if not issues:
        return pd.DataFrame(columns=ISSUE_TABLE_COLUMNS)

    return pd.DataFrame(
        [
            {
                "rule": issue.rule_name,
                "severity": issue.severity.title(),
                "column": issue.column_name or "Dataset",
                "affected_rows": issue.affected_row_count,
                "sample_rows": ", ".join(
                    str(row_number)
                    for row_number in issue.sample_row_numbers
                ),
                "description": issue.description,
            }
            for issue in issues
        ],
        columns=ISSUE_TABLE_COLUMNS,
    )


def build_sample_failing_rows_table(
    dataframe: pd.DataFrame,
    validation_result: DatasetValidationResult,
    row_limit: int = 10,
) -> pd.DataFrame:
    issues_by_row = _map_issue_labels_by_row(validation_result.issues)
    if not issues_by_row:
        return pd.DataFrame(columns=FAILING_ROWS_TABLE_BASE_COLUMNS + list(dataframe.columns))

    row_numbers = sorted(issues_by_row)[:row_limit]
    sampled_rows = dataframe.iloc[[row_number - 1 for row_number in row_numbers]].copy()
    sampled_rows.insert(0, "issues", ["; ".join(issues_by_row[row_number]) for row_number in row_numbers])
    sampled_rows.insert(0, "row_number", row_numbers)
    return sampled_rows.reset_index(drop=True)


def _build_validation_summary(
    dataframe: pd.DataFrame,
    issues: list[ValidationIssue],
) -> ValidationSummary:
    issue_count = sum(issue.affected_row_count for issue in issues)
    affected_row_numbers = {
        row_number
        for issue in issues
        for row_number in issue.failing_row_numbers
    }
    affected_column_names = {
        issue.column_name
        for issue in issues
        if issue.column_name is not None
    }
    biggest_problem_labels = _build_biggest_problem_labels(issues)
    quality_level = _classify_quality_level(issue_count=issue_count, issues=issues)

    return ValidationSummary(
        issue_count=issue_count,
        affected_row_count=len(affected_row_numbers),
        clean_row_count=max(int(dataframe.shape[0]) - len(affected_row_numbers), 0),
        affected_column_count=len(affected_column_names),
        rule_count=len(issues),
        quality_level=quality_level,
        biggest_problem_labels=biggest_problem_labels,
        message=_build_validation_message(
            issue_count=issue_count,
            affected_column_count=len(affected_column_names),
            quality_level=quality_level,
            biggest_problem_labels=biggest_problem_labels,
        ),
    )


def _map_issue_labels_by_row(
    issues: tuple[ValidationIssue, ...],
) -> dict[int, list[str]]:
    issues_by_row: dict[int, list[str]] = defaultdict(list)

    for issue in issues:
        label = issue.rule_name
        if issue.column_name is not None:
            label = f"{label} ({issue.column_name})"

        for row_number in issue.failing_row_numbers:
            issues_by_row[row_number].append(label)

    for labels in issues_by_row.values():
        labels.sort()

    return dict(issues_by_row)


def _build_biggest_problem_labels(
    issues: list[ValidationIssue],
    label_limit: int = 2,
) -> tuple[str, ...]:
    issue_totals: dict[str, int] = defaultdict(int)

    for issue in issues:
        label = issue.summary_label or issue.rule_name.casefold()
        issue_totals[label] += issue.affected_row_count

    ranked_labels = sorted(
        issue_totals.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return tuple(label for label, _ in ranked_labels[:label_limit])


def _build_validation_message(
    issue_count: int,
    affected_column_count: int,
    quality_level: str,
    biggest_problem_labels: tuple[str, ...],
) -> str:
    if issue_count == 0:
        return "High quality: no validation issues detected."

    issue_word = "issue" if issue_count == 1 else "issues"
    problem_phrase = _join_labels(biggest_problem_labels) or "validation issues"
    problem_word = "problem" if len(biggest_problem_labels) == 1 else "problems"
    scope_message = _build_scope_message(affected_column_count)
    return (
        f"{quality_level} quality: {issue_count} {issue_word} {scope_message}, with "
        f"{problem_phrase} as the biggest {problem_word}."
    )


def _classify_quality_level(
    issue_count: int,
    issues: list[ValidationIssue],
) -> str:
    if issue_count == 0:
        return "High"

    has_error = any(issue.severity == "error" for issue in issues)
    if issue_count <= 5 and not has_error:
        return "High"
    if issue_count <= 20:
        return "Medium"
    return "Low"


def _join_labels(labels: tuple[str, ...]) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"


def _build_scope_message(affected_column_count: int) -> str:
    if affected_column_count == 0:
        return "across the dataset"

    column_word = "column" if affected_column_count == 1 else "columns"
    return f"across {affected_column_count} {column_word}"
