from __future__ import annotations

import pandas as pd

from src.models import ValidationIssue, ValidationRuleConfig
from src.rules.checks.common import (
    build_issue,
    is_whitespace_only_string,
    row_numbers_from_mask,
)


def check_whitespace_only_values(
    dataframe: pd.DataFrame,
    rule_config: ValidationRuleConfig,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for column_name in dataframe.columns:
        series = dataframe[column_name]
        failing_row_numbers = row_numbers_from_mask(series.map(is_whitespace_only_string))
        if not failing_row_numbers:
            continue

        column_label = str(column_name)
        issues.append(
            build_issue(
                rule_name="Whitespace-only value check",
                severity="warning",
                column_name=column_label,
                description=f"Column '{column_label}' contains whitespace-only string values.",
                failing_row_numbers=failing_row_numbers,
                rule_config=rule_config,
                summary_label="whitespace-only values",
            )
        )

    return issues
