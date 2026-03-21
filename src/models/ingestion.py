from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True, slots=True)
class CsvIngestionResult:
    source_name: str
    stored_path: Path
    dataframe: pd.DataFrame


@dataclass(frozen=True, slots=True)
class CsvIngestionVerification:
    is_valid: bool
    message: str
