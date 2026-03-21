from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd

from src.models import NumericRangeConstraint, ValidationIssue, ValidationRuleConfig


EMAIL_PATTERN = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
_CAMEL_BOUNDARY_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_BOUNDARY_2 = re.compile(r"([a-z0-9])([A-Z])")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def build_issue(
    *,
    rule_name: str,
    severity: str,
    column_name: str | None,
    description: str,
    failing_row_numbers: tuple[int, ...],
    rule_config: ValidationRuleConfig,
    summary_label: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        rule_name=rule_name,
        severity=severity,
        column_name=column_name,
        description=description,
        affected_row_count=len(failing_row_numbers),
        failing_row_numbers=failing_row_numbers,
        summary_label=summary_label or rule_name,
        sample_row_limit=rule_config.sample_row_limit,
    )


def row_numbers_from_mask(mask: pd.Series) -> tuple[int, ...]:
    return tuple(
        row_number
        for row_number, has_issue in enumerate(mask.fillna(False).astype(bool).tolist(), start=1)
        if has_issue
    )


def is_blank_string(value: object) -> bool:
    return isinstance(value, str) and value.strip() == ""


def is_whitespace_only_string(value: object) -> bool:
    return isinstance(value, str) and value != "" and value.strip() == ""


def has_leading_or_trailing_whitespace(value: object) -> bool:
    return isinstance(value, str) and value.strip() != "" and value != value.strip()


def strip_string(value: object) -> object:
    if isinstance(value, str):
        return value.strip()
    return value


def find_best_keyword_match(
    column_name: str,
    keywords: Iterable[str],
) -> str | None:
    matches = [
        keyword
        for keyword in keywords
        if column_name_matches_keyword(column_name, keyword)
    ]
    if not matches:
        return None

    return max(matches, key=lambda keyword: len(normalize_name(keyword)))


def column_name_matches_keyword(column_name: str, keyword: str) -> bool:
    normalized_column_name = normalize_name(column_name)
    normalized_keyword = normalize_name(keyword)
    if not normalized_column_name or not normalized_keyword:
        return False

    if normalized_column_name == normalized_keyword:
        return True

    column_tokens = normalized_column_name.split("_")
    keyword_tokens = normalized_keyword.split("_")
    if len(keyword_tokens) == 1:
        return keyword_tokens[0] in column_tokens

    token_window_size = len(keyword_tokens)
    return any(
        column_tokens[start_index : start_index + token_window_size] == keyword_tokens
        for start_index in range(len(column_tokens) - token_window_size + 1)
    )


def normalize_name(value: str) -> str:
    normalized = _CAMEL_BOUNDARY_1.sub(r"\1_\2", str(value).strip())
    normalized = _CAMEL_BOUNDARY_2.sub(r"\1_\2", normalized)
    normalized = _NON_ALPHANUMERIC.sub("_", normalized.casefold())
    return normalized.strip("_")


def describe_numeric_range(constraint: NumericRangeConstraint) -> str:
    if constraint.min_value is not None and constraint.max_value is not None:
        return f"{constraint.min_value:g} to {constraint.max_value:g}"
    if constraint.min_value is not None:
        return f"at least {constraint.min_value:g}"
    if constraint.max_value is not None:
        return f"at most {constraint.max_value:g}"
    return "a configured range"
