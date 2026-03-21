from __future__ import annotations

import pandas as pd

from src.models import ValidationIssue, ValidationRuleConfig
from src.rules.checks.common import (
    build_issue,
    has_leading_or_trailing_whitespace,
    row_numbers_from_mask,
)


def check_leading_trailing_whitespace(
    dataframe: pd.DataFrame,
    rule_config: ValidationRuleConfig,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for column_name in dataframe.columns:
        series = dataframe[column_name]
        failing_row_numbers = row_numbers_from_mask(
            series.map(has_leading_or_trailing_whitespace)
        )
        if not failing_row_numbers:
            continue

        column_label = str(column_name)
        issues.append(
            build_issue(
                rule_name="Leading/trailing whitespace check",
                severity="warning",
                column_name=column_label,
                description=f"Column '{column_label}' contains values with leading or trailing whitespace.",
                failing_row_numbers=failing_row_numbers,
                rule_config=rule_config,
                summary_label="leading/trailing whitespace",
            )
        )

    return issues
