from __future__ import annotations

import pandas as pd

from src.models import ValidationIssue, ValidationRuleConfig
from src.rules.checks.common import build_issue, row_numbers_from_mask


def check_null_values(
    dataframe: pd.DataFrame,
    rule_config: ValidationRuleConfig,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    null_mask = dataframe.isna()

    for column_name in dataframe.columns:
        failing_row_numbers = row_numbers_from_mask(null_mask[column_name])
        if not failing_row_numbers:
            continue

        column_label = str(column_name)
        issues.append(
            build_issue(
                rule_name="Null check",
                severity="warning",
                column_name=column_label,
                description=f"Column '{column_label}' contains null values.",
                failing_row_numbers=failing_row_numbers,
                rule_config=rule_config,
                summary_label="missing values",
            )
        )

    return issues
