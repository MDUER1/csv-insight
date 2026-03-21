from __future__ import annotations

import pandas as pd

from src.models import ValidationIssue, ValidationRuleConfig
from src.rules.checks.common import build_issue, row_numbers_from_mask


def check_duplicate_rows(
    dataframe: pd.DataFrame,
    rule_config: ValidationRuleConfig,
) -> list[ValidationIssue]:
    failing_row_numbers = row_numbers_from_mask(dataframe.duplicated(keep=False))
    if not failing_row_numbers:
        return []

    return [
        build_issue(
            rule_name="Duplicate row check",
            severity="error",
            column_name=None,
            description="Duplicate rows detected across the full record.",
            failing_row_numbers=failing_row_numbers,
            rule_config=rule_config,
            summary_label="duplicate rows",
        )
    ]
