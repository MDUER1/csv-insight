from __future__ import annotations

import pandas as pd

from src.models import ValidationIssue, ValidationRuleConfig
from src.rules.checks.common import (
    EMAIL_PATTERN,
    build_issue,
    find_best_keyword_match,
    is_blank_string,
    row_numbers_from_mask,
    strip_string,
)


def check_invalid_email_formats(
    dataframe: pd.DataFrame,
    rule_config: ValidationRuleConfig,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for column_name in dataframe.columns:
        column_label = str(column_name)
        if find_best_keyword_match(column_label, rule_config.email_column_keywords) is None:
            continue

        series = dataframe[column_name]
        failing_row_numbers = row_numbers_from_mask(series.map(_is_invalid_email_value))
        if not failing_row_numbers:
            continue

        issues.append(
            build_issue(
                rule_name="Email format check",
                severity="error",
                column_name=column_label,
                description=f"Column '{column_label}' contains invalid email addresses.",
                failing_row_numbers=failing_row_numbers,
                rule_config=rule_config,
                summary_label="invalid email formats",
            )
        )

    return issues


def _is_invalid_email_value(value: object) -> bool:
    if pd.isna(value) or is_blank_string(value):
        return False
    if not isinstance(value, str):
        return True

    normalized_value = strip_string(value)
    return not bool(EMAIL_PATTERN.fullmatch(str(normalized_value)))
