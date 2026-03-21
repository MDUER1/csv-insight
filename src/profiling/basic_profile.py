from __future__ import annotations

import pandas as pd

from src.models import ColumnProfile, DatasetProfile


def build_dataset_profile(dataframe: pd.DataFrame) -> DatasetProfile:
    row_count = int(dataframe.shape[0])
    column_profiles: list[ColumnProfile] = []
    null_counts: dict[str, int] = {}

    for column_index, column_name in enumerate(dataframe.columns):
        series = dataframe.iloc[:, column_index]
        resolved_column_name = str(column_name)
        null_count = int(series.isna().sum())
        non_null_count = max(row_count - null_count, 0)
        unique_count = int(series.nunique(dropna=True))
        null_counts[resolved_column_name] = null_count
        column_profiles.append(
            ColumnProfile(
                column_name=resolved_column_name,
                column_index=column_index,
                data_type=str(series.dtype),
                null_count=null_count,
                non_null_count=non_null_count,
                unique_count=unique_count,
                null_ratio=(null_count / row_count) if row_count else 0.0,
                uniqueness_ratio=(
                    unique_count / non_null_count
                    if non_null_count
                    else 0.0
                ),
            )
        )

    return DatasetProfile(
        row_count=row_count,
        column_count=int(dataframe.shape[1]),
        duplicate_row_count=int(dataframe.duplicated(keep=False).sum()),
        null_counts=null_counts,
        column_profiles=tuple(column_profiles),
    )
