from __future__ import annotations

import pandas as pd

from src.models import ValidationIssue, ValidationRuleConfig
from src.rules.checks.common import (
    build_issue,
    describe_numeric_range,
    find_best_keyword_match,
    is_blank_string,
    row_numbers_from_mask,
    strip_string,
)


def check_numeric_range_violations(
    dataframe: pd.DataFrame,
    rule_config: ValidationRuleConfig,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for column_name in dataframe.columns:
        column_label = str(column_name)
        matched_range_name = find_best_keyword_match(
            column_label,
            rule_config.numeric_ranges.keys(),
        )
        if matched_range_name is None:
            continue

        constraint = rule_config.numeric_ranges[matched_range_name]
        series = dataframe[column_name]
        numeric_candidates = series.map(_normalize_numeric_candidate)
        numeric_values = pd.to_numeric(numeric_candidates, errors="coerce")
        comparable_mask = numeric_candidates.notna() & numeric_values.notna()
        if not comparable_mask.any():
            continue

        violation_mask = pd.Series(False, index=series.index)
        if constraint.min_value is not None:
            violation_mask |= comparable_mask & (numeric_values < constraint.min_value)
        if constraint.max_value is not None:
            violation_mask |= comparable_mask & (numeric_values > constraint.max_value)

        failing_row_numbers = row_numbers_from_mask(violation_mask)
        if not failing_row_numbers:
            continue

        issues.append(
            build_issue(
                rule_name="Numeric range check",
                severity="error",
                column_name=column_label,
                description=(
                    f"Column '{column_label}' contains values outside the allowed range "
                    f"{describe_numeric_range(constraint)}."
                ),
                failing_row_numbers=failing_row_numbers,
                rule_config=rule_config,
                summary_label="numeric range violations",
            )
        )

    return issues


def _normalize_numeric_candidate(value: object) -> object:
    if pd.isna(value) or is_blank_string(value):
        return None
    return strip_string(value)
