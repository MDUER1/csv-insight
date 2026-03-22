# CSV Data Quality Platform

A local-first learning project that ingests CSV files, profiles their contents, detects data-quality issues, and reports the results through a Streamlit dashboard.

## Stack

- Python for the full MVP
- DuckDB for local analytical storage
- Pandas for profiling and rule evaluation
- Pydantic for typed domain models
- Streamlit for the dashboard
- Pytest for automated tests

## What Version 1 Does

- Upload a folder of CSV files through a local dashboard
- Store the raw file on disk and dataset metadata in DuckDB
- Profile each column
- Run built-in data-quality checks
- Show issues, sample failing rows, dataset previews, and column profiles
- Export issue reports as CSV or JSON

## Project Layout

```text
app/                  Streamlit UI
config/               Rule thresholds and defaults
data/                 Local database and uploaded files
docs/                 Notes and learning artifacts
sample_data/          Example CSVs for manual testing
src/                  Ingestion, storage, profiling, and rule engine code
tests/                Unit and integration tests
```

## Local Setup

The machine in this workspace currently has Python `3.14.0`. Streamlit's documentation has historically recommended Python `3.13` or lower, while newer package metadata may already allow `3.14`. The safest path is:

1. Install Python `3.13` if you want the documented compatibility path.
2. Create a virtual environment with the interpreter you want to use.
3. Install the project in editable mode.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

### Run the dashboard

```powershell
python -m streamlit run app/main.py
```

### Run the tests

```powershell
python -m pytest
```

## Learning Workflow

- Implement one thin vertical slice at a time.
- Ask the agent for tests before asking it for code.
- Keep decisions in [`docs/decision-log.md`](docs/decision-log.md).
- Ask the agent to explain generated code in beginner terms before moving on.

