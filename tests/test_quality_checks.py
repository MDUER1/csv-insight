from __future__ import annotations

import pandas as pd

from src.rules import build_issue_table, build_sample_failing_rows_table, validate_dataset


def test_validate_dataset_returns_issue_summary_and_tables() -> None:
    dataframe = pd.DataFrame(
        {
            "id": [1, 2, 2],
            "name": ["Ada", None, None],
            "city": ["London", "Paris", "Paris"],
        }
    )

    result = validate_dataset(dataframe)

    assert result.summary.issue_count == 6
    assert result.summary.affected_row_count == 2
    assert result.summary.clean_row_count == 1
    assert result.summary.affected_column_count == 2
    assert result.summary.rule_count == 3
    assert result.summary.quality_level == "Medium"
    assert result.summary.biggest_problem_labels == (
        "duplicate IDs",
        "duplicate rows",
    )
    assert (
        result.summary.message
        == "Medium quality: 6 issues across 2 columns, with duplicate IDs and duplicate rows as the biggest problems."
    )
    assert [issue.rule_name for issue in result.issues] == [
        "Null check",
        "Duplicate identifier check",
        "Duplicate row check",
    ]
    assert result.issues[0].column_name == "name"
    assert result.issues[0].failing_row_numbers == (2, 3)
    assert result.issues[1].column_name == "id"
    assert result.issues[1].failing_row_numbers == (2, 3)
    assert result.issues[2].failing_row_numbers == (2, 3)

    issue_table = build_issue_table(result)

    assert issue_table.to_dict(orient="records") == [
        {
            "rule": "Null check",
            "severity": "Warning",
            "column": "name",
            "affected_rows": 2,
            "sample_rows": "2, 3",
            "description": "Column 'name' contains null values.",
        },
        {
            "rule": "Duplicate identifier check",
            "severity": "Error",
            "column": "id",
            "affected_rows": 2,
            "sample_rows": "2, 3",
            "description": "Column 'id' contains duplicate key values.",
        },
        {
            "rule": "Duplicate row check",
            "severity": "Error",
            "column": "Dataset",
            "affected_rows": 2,
            "sample_rows": "2, 3",
            "description": "Duplicate rows detected across the full record.",
        },
    ]

    failing_rows = build_sample_failing_rows_table(dataframe, result)

    assert failing_rows["row_number"].tolist() == [2, 3]
    assert failing_rows["issues"].tolist() == [
        "Duplicate identifier check (id); Duplicate row check; Null check (name)",
        "Duplicate identifier check (id); Duplicate row check; Null check (name)",
    ]


def test_validate_dataset_returns_empty_tables_for_clean_data() -> None:
    dataframe = pd.DataFrame(
        {
            "id": [1, 2],
            "name": ["Ada", "Grace"],
        }
    )

    result = validate_dataset(dataframe)

    assert result.summary.issue_count == 0
    assert result.summary.affected_row_count == 0
    assert result.summary.clean_row_count == 2
    assert result.summary.affected_column_count == 0
    assert result.summary.rule_count == 0
    assert result.summary.quality_level == "High"
    assert result.summary.biggest_problem_labels == ()
    assert result.summary.message == "High quality: no validation issues detected."
    assert result.issues == ()
    assert build_issue_table(result).empty is True
    assert build_sample_failing_rows_table(dataframe, result).empty is True
