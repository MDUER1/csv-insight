from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


DEFAULT_RAW_DATA_DIR = Path("data/raw")


def store_raw_csv(
    file_name: str,
    file_content: bytes,
    raw_data_dir: Path | str | None = None,
) -> Path:
    destination_dir = Path(raw_data_dir) if raw_data_dir is not None else DEFAULT_RAW_DATA_DIR
    destination_dir.mkdir(parents=True, exist_ok=True)

    destination_path = destination_dir / build_raw_file_name(file_name)
    destination_path.write_bytes(file_content)
    return destination_path.resolve()


def build_raw_file_name(file_name: str) -> str:
    clean_name = Path(file_name).name
    sanitized_stem = _sanitize_name(Path(clean_name).stem) or "upload"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    unique_suffix = uuid4().hex[:8]
    return f"{sanitized_stem}_{timestamp}_{unique_suffix}.csv"


def _sanitize_name(file_stem: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", file_stem.strip())
    return normalized.strip("._-")
