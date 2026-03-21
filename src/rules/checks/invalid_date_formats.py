from __future__ import annotations

import pandas as pd

from src.models import ValidationIssue, ValidationRuleConfig
from src.rules.checks.common import (
    build_issue,
    find_best_keyword_match,
    is_blank_string,
    row_numbers_from_mask,
    strip_string,
)


def check_invalid_date_formats(
    dataframe: pd.DataFrame,
    rule_config: ValidationRuleConfig,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for column_name in dataframe.columns:
        column_label = str(column_name)
        if find_best_keyword_match(column_label, rule_config.date_column_keywords) is None:
            continue

        series = dataframe[column_name]
        candidate_mask = series.map(_is_populated_date_candidate)
        if not candidate_mask.any():
            continue

        normalized_values = series.loc[candidate_mask].map(strip_string)
        parsed_values = _parse_dates(normalized_values)
        invalid_mask = pd.Series(False, index=series.index)
        invalid_mask.loc[candidate_mask] = parsed_values.isna()
        failing_row_numbers = row_numbers_from_mask(invalid_mask)
        if not failing_row_numbers:
            continue

        issues.append(
            build_issue(
                rule_name="Date format check",
                severity="error",
                column_name=column_label,
                description=f"Column '{column_label}' contains invalid date values.",
                failing_row_numbers=failing_row_numbers,
                rule_config=rule_config,
                summary_label="invalid date formats",
            )
        )

    return issues


def _is_populated_date_candidate(value: object) -> bool:
    return not pd.isna(value) and not is_blank_string(value)


def _parse_dates(series: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    except (TypeError, ValueError):
        return pd.to_datetime(series, errors="coerce")
