"""Individual data-quality checks."""

from src.rules.checks.duplicate_key_columns import check_duplicate_key_columns
from src.rules.checks.duplicate_rows import check_duplicate_rows
from src.rules.checks.invalid_date_formats import check_invalid_date_formats
from src.rules.checks.invalid_email_formats import check_invalid_email_formats
from src.rules.checks.leading_trailing_whitespace import (
    check_leading_trailing_whitespace,
)
from src.rules.checks.nulls import check_null_values
from src.rules.checks.numeric_range_violations import check_numeric_range_violations
from src.rules.checks.whitespace_only_values import check_whitespace_only_values


RULE_CHECKS = (
    check_null_values,
    check_duplicate_key_columns,
    check_whitespace_only_values,
    check_leading_trailing_whitespace,
    check_invalid_email_formats,
    check_invalid_date_formats,
    check_numeric_range_violations,
    check_duplicate_rows,
)

__all__ = [
    "RULE_CHECKS",
    "check_duplicate_key_columns",
    "check_duplicate_rows",
    "check_invalid_date_formats",
    "check_invalid_email_formats",
    "check_leading_trailing_whitespace",
    "check_null_values",
    "check_numeric_range_violations",
    "check_whitespace_only_values",
]
