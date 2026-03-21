from __future__ import annotations

import pandas as pd

from src.models import ValidationIssue, ValidationRuleConfig
from src.rules.checks.common import (
    build_issue,
    column_name_matches_keyword,
    row_numbers_from_mask,
)


def check_duplicate_key_columns(
    dataframe: pd.DataFrame,
    rule_config: ValidationRuleConfig,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for column_name in dataframe.columns:
        column_label = str(column_name)
        if not any(
            column_name_matches_keyword(column_label, pattern)
            for pattern in rule_config.key_column_patterns
        ):
            continue

        series = dataframe[column_name]
        duplicate_mask = pd.Series(False, index=series.index)
        non_null_mask = ~series.isna()
        if non_null_mask.any():
            duplicate_mask.loc[non_null_mask] = series.loc[non_null_mask].duplicated(keep=False)

        failing_row_numbers = row_numbers_from_mask(duplicate_mask)
        if not failing_row_numbers:
            continue

        issues.append(
            build_issue(
                rule_name="Duplicate identifier check",
                severity="error",
                column_name=column_label,
                description=f"Column '{column_label}' contains duplicate key values.",
                failing_row_numbers=failing_row_numbers,
                rule_config=rule_config,
                summary_label=_build_duplicate_key_summary_label(column_label),
            )
        )

    return issues


def _build_duplicate_key_summary_label(column_name: str) -> str:
    friendly_name = column_name.replace("_", " ")
    normalized_name = friendly_name.casefold()

    if normalized_name == "id":
        return "duplicate IDs"
    if normalized_name.endswith(" id"):
        return f"duplicate {friendly_name[:-3]} IDs"
    return f"duplicate values in {friendly_name}"
