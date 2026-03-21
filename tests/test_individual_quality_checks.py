from __future__ import annotations

import pandas as pd

from src.models import NumericRangeConstraint, ValidationRuleConfig
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


def build_test_rule_config() -> ValidationRuleConfig:
    return ValidationRuleConfig(
        sample_row_limit=3,
        key_column_patterns=("order_id",),
        email_column_keywords=("email",),
        date_column_keywords=("date",),
        numeric_ranges={
            "age": NumericRangeConstraint(min_value=0, max_value=120),
        },
    )


def test_check_null_values_returns_column_issue() -> None:
    dataframe = pd.DataFrame({"name": ["Ada", None, None]})

    issues = check_null_values(dataframe, build_test_rule_config())

    assert len(issues) == 1
    assert issues[0].rule_name == "Null check"
    assert issues[0].severity == "warning"
    assert issues[0].column_name == "name"
    assert issues[0].failing_row_numbers == (2, 3)


def test_check_duplicate_rows_returns_dataset_issue() -> None:
    dataframe = pd.DataFrame({"id": [1, 1], "name": ["Ada", "Ada"]})

    issues = check_duplicate_rows(dataframe, build_test_rule_config())

    assert len(issues) == 1
    assert issues[0].rule_name == "Duplicate row check"
    assert issues[0].column_name is None
    assert issues[0].failing_row_numbers == (1, 2)


def test_check_duplicate_key_columns_uses_configured_key_patterns() -> None:
    dataframe = pd.DataFrame({"order_id": [1001, 1001, None, 1002]})

    issues = check_duplicate_key_columns(dataframe, build_test_rule_config())

    assert len(issues) == 1
    assert issues[0].rule_name == "Duplicate identifier check"
    assert issues[0].column_name == "order_id"
    assert issues[0].failing_row_numbers == (1, 2)


def test_check_whitespace_only_values_detects_space_only_strings() -> None:
    dataframe = pd.DataFrame({"name": ["Ada", "   ", "\t"]})

    issues = check_whitespace_only_values(dataframe, build_test_rule_config())

    assert len(issues) == 1
    assert issues[0].rule_name == "Whitespace-only value check"
    assert issues[0].column_name == "name"
    assert issues[0].failing_row_numbers == (2, 3)


def test_check_leading_trailing_whitespace_ignores_whitespace_only_strings() -> None:
    dataframe = pd.DataFrame({"name": [" Ada", "Grace ", "   ", "Linus"]})

    issues = check_leading_trailing_whitespace(dataframe, build_test_rule_config())

    assert len(issues) == 1
    assert issues[0].rule_name == "Leading/trailing whitespace check"
    assert issues[0].column_name == "name"
    assert issues[0].failing_row_numbers == (1, 2)


def test_check_invalid_email_formats_uses_trimmed_email_values() -> None:
    dataframe = pd.DataFrame(
        {"contact_email": [" ada@example.com ", "invalid-email", None, "   "]}
    )

    issues = check_invalid_email_formats(dataframe, build_test_rule_config())

    assert len(issues) == 1
    assert issues[0].rule_name == "Email format check"
    assert issues[0].column_name == "contact_email"
    assert issues[0].failing_row_numbers == (2,)


def test_check_invalid_date_formats_allows_parseable_trimmed_dates() -> None:
    dataframe = pd.DataFrame(
        {"ship_date": ["2024-01-01", " not-a-date ", " 2024/02/03 ", None]}
    )

    issues = check_invalid_date_formats(dataframe, build_test_rule_config())

    assert len(issues) == 1
    assert issues[0].rule_name == "Date format check"
    assert issues[0].column_name == "ship_date"
    assert issues[0].failing_row_numbers == (2,)


def test_check_numeric_range_violations_uses_matching_column_names() -> None:
    dataframe = pd.DataFrame({"customer_age": [-1, 35, 121, None]})

    issues = check_numeric_range_violations(dataframe, build_test_rule_config())

    assert len(issues) == 1
    assert issues[0].rule_name == "Numeric range check"
    assert issues[0].column_name == "customer_age"
    assert issues[0].failing_row_numbers == (1, 3)
    assert issues[0].sample_row_numbers == (1, 3)
