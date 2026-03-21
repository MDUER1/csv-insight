from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PersistedAnalysisRun:
    run_id: str
    file_name: str
    uploaded_at: datetime
    row_count: int
    column_count: int
    total_null_count: int
    total_issue_count: int
    affected_row_count: int
    raw_file_path: Path | None = None
