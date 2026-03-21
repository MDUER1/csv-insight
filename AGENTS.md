# CSV Data Quality & Insights Platform – Agent Instructions

## Project goal
Build a modular data quality platform where users can upload CSV files, automatically profile and validate the data, and visualize quality issues in a Streamlit dashboard.

## Architecture principles
- Keep `app/main.py` thin. It should only contain Streamlit UI and orchestration.
- All business logic must live in `src/`.
- Each module must have a clear responsibility.
- Prefer small reusable functions over large scripts.

## Module responsibilities

### app/
Contains Streamlit UI and orchestration only.

main.py responsibilities:
- File upload
- Calling ingestion logic
- Calling profiling logic
- Calling validation rules
- Displaying results

Do NOT:
- Put heavy data processing here
- Put database logic here
- Put validation rules here

### src/ingestion/
Responsible for reading data.

Examples:
- CSV parsing
- Encoding detection
- Initial dataframe creation
- Temporary file handling

### src/profiling/
Responsible for computing dataset metrics.

Examples:
- Row count
- Column count
- Null counts
- Duplicate rows
- Column uniqueness
- Data type detection

### src/rules/
Responsible for validation logic.

Examples:
- Null checks
- Duplicate checks
- Format validation
- Whitespace detection
- Email/date validation

Rules should:
- Return structured issue objects
- Not print output
- Be testable

### src/storage/
Responsible for persistence.

Examples:
- DuckDB connections
- Writing profiling results
- Writing validation results
- Loading previous runs

Do NOT mix business logic and storage.

### src/models/
Data structures only.

Examples:
- ProfileResult
- ValidationIssue
- ColumnMetrics

Prefer dataclasses or pydantic models.

## Data flow rules

Follow this pipeline:

Upload → Ingestion → Profiling → Validation → Storage → Dashboard

Temporary processing:
.tmp/

Permanent storage:
data/raw/
data/processed/

Never store temp files in data/.

## Testing rules

Every non-trivial logic function should have at least one test.

Tests belong in:
tests/

Test examples:
- CSV reading works
- Null detection works
- Duplicate detection works
- Profiling metrics correct

Run tests with:

pytest

New logic should ideally include tests.

## Coding guidelines

Prefer:
- Clear function names
- Small functions
- Pure functions where possible
- Type hints when useful

Avoid:
- Large monolithic scripts
- Business logic inside UI code
- Global mutable state

## Imports

Use absolute imports:

GOOD:
from src.ingestion.csv_reader import read_csv

BAD:
from ..ingestion import csv_reader

## Streamlit rules

Streamlit should:
- Display results
- Trigger logic

Streamlit should NOT:
- Perform heavy data transformations
- Store business logic

## First feature priority

Initial working feature should:

1 Upload CSV
2 Read dataframe
3 Compute:
   - row count
   - column count
   - null counts
4 Display results in Streamlit

Keep implementation simple first.
Refactor after working.

## General agent behavior

When adding features:
1 Keep structure modular
2 Add logic in src/
3 Wire in main.py
4 Add minimal tests
5 Keep code readable

Prefer correctness and clarity over clever solutions.