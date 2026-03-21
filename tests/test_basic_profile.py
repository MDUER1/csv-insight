from __future__ import annotations

import pandas as pd
import pytest

from src.profiling import build_dataset_profile


def test_build_dataset_profile_returns_core_dataset_metrics() -> None:
    dataframe = pd.DataFrame(
        {
            "id": [1, None, 3],
            "name": ["Ada", None, "Grace"],
            "city": ["London", "Paris", "Berlin"],
        }
    )

    result = build_dataset_profile(dataframe)

    assert result.row_count == 3
    assert result.column_count == 3
    assert result.duplicate_row_count == 0
    assert result.null_counts == {"id": 1, "name": 1, "city": 0}
    assert result.total_null_count == 2
    assert [column.column_name for column in result.column_profiles] == [
        "id",
        "name",
        "city",
    ]
    assert [column.data_type for column in result.column_profiles] == [
        "float64",
        "object",
        "object",
    ]
    assert [column.unique_count for column in result.column_profiles] == [2, 2, 3]
    assert result.column_profiles[0].null_ratio == pytest.approx(1 / 3)
    assert result.column_profiles[1].uniqueness_ratio == pytest.approx(1.0)
