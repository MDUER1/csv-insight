from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.models import NumericRangeConstraint, ValidationRuleConfig


DEFAULT_RULE_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default_rules.json"


def load_validation_rule_config(
    config_path: Path | str | None = None,
) -> ValidationRuleConfig:
    resolved_path = Path(config_path) if config_path is not None else DEFAULT_RULE_CONFIG_PATH
    return _load_validation_rule_config(resolved_path.resolve())


@lru_cache(maxsize=8)
def _load_validation_rule_config(config_path: Path) -> ValidationRuleConfig:
    with config_path.open(encoding="utf-8") as file:
        raw_config = json.load(file)

    required_keywords = _read_string_list(raw_config, "required_column_keywords")
    email_keywords = _read_string_list(raw_config, "email_column_keywords") or _filter_keywords(
        required_keywords,
        match_text="email",
    ) or ("email",)
    date_keywords = _read_string_list(raw_config, "date_column_keywords") or _filter_keywords(
        required_keywords,
        match_text="date",
    ) or ("date",)

    numeric_ranges = {
        str(column_keyword): NumericRangeConstraint(
            min_value=_read_optional_float(range_config, "min"),
            max_value=_read_optional_float(range_config, "max"),
        )
        for column_keyword, range_config in raw_config.get("numeric_ranges", {}).items()
    }

    return ValidationRuleConfig(
        sample_row_limit=int(raw_config.get("sample_row_limit", 5)),
        key_column_patterns=_read_string_list(raw_config, "key_column_patterns"),
        email_column_keywords=email_keywords,
        date_column_keywords=date_keywords,
        numeric_ranges=numeric_ranges,
    )


def _read_string_list(raw_config: dict[str, Any], key: str) -> tuple[str, ...]:
    values = raw_config.get(key, ())
    return tuple(str(value) for value in values)


def _filter_keywords(
    keywords: tuple[str, ...],
    match_text: str,
) -> tuple[str, ...]:
    normalized_match_text = match_text.casefold()
    return tuple(
        keyword
        for keyword in keywords
        if normalized_match_text in keyword.casefold()
    )


def _read_optional_float(raw_config: dict[str, Any], key: str) -> float | None:
    if key not in raw_config:
        return None
    return float(raw_config[key])
