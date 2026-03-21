from __future__ import annotations

import pandas as pd

from src.models import NumericRangeConstraint, ValidationRuleConfig
from src.rules import validate_dataset


def build_test_rule_config() -> ValidationRuleConfig:
    return ValidationRuleConfig(
        sample_row_limit=5,
        key_column_patterns=("customer_id",),
        email_column_keywords=("email",),
        date_column_keywords=("date",),
        numeric_ranges={
            "age": NumericRangeConstraint(min_value=0, max_value=120),
        },
    )


def test_validate_dataset_runs_all_requested_rule_checks() -> None:
    dataframe = pd.DataFrame(
        {
            "customer_id": [101, 101, 102, 103, 103],
            "name": ["Ada", None, "   ", " Grace ", " Grace "],
            "email": [
                "ada@example.com",
                "invalid-email",
                "grace@example.com",
                "linus@example.com",
                "linus@example.com",
            ],
            "order_date": [
                "2024-01-01",
                "not-a-date",
                "2024-05-01",
                "2024-06-01",
                "2024-06-01",
            ],
            "age": [34, 40, 150, -1, -1],
            "city": ["London", "Paris", "Berlin", "Rome", "Rome"],
        }
    )

    result = validate_dataset(dataframe, rule_config=build_test_rule_config())

    assert [issue.rule_name for issue in result.issues] == [
        "Null check",
        "Duplicate identifier check",
        "Whitespace-only value check",
        "Leading/trailing whitespace check",
        "Email format check",
        "Date format check",
        "Numeric range check",
        "Duplicate row check",
    ]
    assert result.summary.issue_count == 15
    assert result.summary.affected_row_count == 5
    assert result.summary.clean_row_count == 0
    assert result.summary.affected_column_count == 5
    assert result.summary.rule_count == 8
    assert result.summary.quality_level == "Medium"
    assert result.summary.biggest_problem_labels == (
        "duplicate customer IDs",
        "numeric range violations",
    )
    assert (
        result.summary.message
        == "Medium quality: 15 issues across 5 columns, with duplicate customer IDs and numeric range violations as the biggest problems."
    )


def test_validate_dataset_reports_high_quality_when_no_rules_fail() -> None:
    dataframe = pd.DataFrame(
        {
            "customer_id": [1, 2],
            "name": ["Ada", "Grace"],
            "email": ["ada@example.com", "grace@example.com"],
            "order_date": ["2024-01-01", "2024-01-02"],
            "age": [30, 40],
        }
    )

    result = validate_dataset(dataframe, rule_config=build_test_rule_config())

    assert result.issues == ()
    assert result.summary.issue_count == 0
    assert result.summary.affected_row_count == 0
    assert result.summary.clean_row_count == 2
    assert result.summary.affected_column_count == 0
    assert result.summary.rule_count == 0
    assert result.summary.quality_level == "High"
    assert result.summary.biggest_problem_labels == ()
    assert result.summary.message == "High quality: no validation issues detected."
