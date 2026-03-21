from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    column_name: str
    column_index: int
    data_type: str
    null_count: int
    non_null_count: int
    unique_count: int
    null_ratio: float
    uniqueness_ratio: float


@dataclass(frozen=True, slots=True)
class DatasetProfile:
    row_count: int
    column_count: int
    duplicate_row_count: int
    null_counts: dict[str, int]
    column_profiles: tuple[ColumnProfile, ...]

    @property
    def total_null_count(self) -> int:
        return sum(self.null_counts.values())
