import hashlib
from datetime import datetime, timezone

import duckdb
import pandas as pd
import streamlit as st

from src.ingestion import (
    InvalidCsvFileError,
    ingest_csv_file,
    verify_ingestion_result,
)
from src.models import StoredAnalysisRun, StoredRunDetails, StoredValidationIssue
from src.profiling import build_dataset_profile
from src.rules import (
    build_issue_table,
    build_sample_failing_rows_table,
    validate_dataset,
)
from src.storage import DuckDbAnalysisStore


PREVIEW_ROW_LIMIT = 10
FAILING_ROW_LIMIT = 10
HISTORY_LIMIT = 10
ANALYSIS_STORE = DuckDbAnalysisStore()


def apply_page_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --page-bg: #f4f6f2;
            --page-bg-secondary: #edf2ec;
            --surface: #ffffff;
            --surface-soft: #f8fbf8;
            --border: #d5dfd7;
            --text-strong: #152321;
            --text-muted: #5d6c69;
            --accent: #2f6f5e;
            --accent-soft: #e6f0eb;
            --shadow: 0 14px 32px rgba(21, 35, 33, 0.06);
        }
        .stApp {
            background: linear-gradient(
                180deg,
                var(--page-bg) 0%,
                var(--page-bg-secondary) 100%
            );
            color: var(--text-strong);
        }
        .block-container {
            max-width: 1100px;
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        .hero-card {
            padding: 1.5rem 1.75rem;
            border: 1px solid var(--border);
            border-radius: 22px;
            background: linear-gradient(135deg, var(--surface) 0%, var(--surface-soft) 100%);
            box-shadow: var(--shadow);
            margin-bottom: 1.25rem;
            position: relative;
            overflow: hidden;
        }
        .hero-card::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 6px;
            background: linear-gradient(180deg, var(--accent) 0%, #86ab9d 100%);
        }
        .hero-eyebrow {
            margin: 0 0 0.35rem 0;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.74rem;
            font-weight: 700;
            color: var(--accent);
        }
        .hero-title {
            font-size: 2.1rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            color: var(--text-strong);
            margin: 0;
        }
        .hero-copy {
            color: var(--text-muted);
            margin: 0.5rem 0 0 0;
            font-size: 1rem;
            max-width: 50rem;
        }
        .section-heading {
            margin: 0.5rem 0 1rem 0;
        }
        .section-title {
            margin: 0;
            font-size: 1.2rem;
            font-weight: 700;
            color: var(--text-strong);
        }
        .section-copy {
            margin: 0.3rem 0 0 0;
            color: var(--text-muted);
            font-size: 0.95rem;
        }
        [data-testid="stFileUploader"] {
            padding: 1rem;
            border-radius: 18px;
            background: var(--surface);
            border: 1px dashed #9ab4a7;
            box-shadow: var(--shadow);
        }
        [data-testid="stMetric"] {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 0.7rem;
            box-shadow: none;
        }
        [data-testid="stMetricLabel"] {
            color: var(--text-muted);
        }
        [data-testid="stMetricValue"] {
            color: var(--accent);
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            background: var(--surface);
        }
        div[data-baseweb="select"] > div {
            border-radius: 14px;
            border-color: var(--border);
            background: var(--surface);
        }
        button[data-baseweb="tab"] {
            background: var(--accent-soft);
            border-radius: 999px;
            border: 1px solid transparent;
            color: var(--text-muted);
            padding: 0.45rem 1rem;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background: var(--surface);
            border-color: var(--border);
            color: var(--accent);
            box-shadow: 0 6px 18px rgba(21, 35, 33, 0.06);
        }
        [data-testid="stAlert"] {
            border-radius: 16px;
            border: 1px solid rgba(154, 180, 167, 0.45);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <div class="hero-card">
            <p class="hero-eyebrow">Data Quality Dashboard</p>
            <p class="hero-title">Simple CSV quality overview</p>
            <p class="hero-copy">
                Upload a CSV, review the key quality signals first, and switch to saved runs
                when you want to compare earlier analyses. The layout keeps the current upload
                and the historical view visually separate.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_heading(title: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="section-heading">
            <p class="section-title">{title}</p>
            <p class="section-copy">{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_file_hash(file_content: bytes) -> str:
    return hashlib.sha256(file_content).hexdigest()


def build_upload_key(file_name: str, file_content: bytes) -> str:
    return f"{file_name}:{build_file_hash(file_content)}"


def clear_upload_state() -> None:
    for key in (
        "ingested_upload_key",
        "ingestion_result",
        "profile_result",
        "verification_result",
        "validation_result",
        "current_run_id",
        "persistence_error",
    ):
        st.session_state.pop(key, None)


def get_upload_results(
    uploaded_file,
    analysis_store: DuckDbAnalysisStore,
) -> tuple[bytes, object, object, object, object, str | None, str | None]:
    file_content = uploaded_file.getvalue()
    upload_key = build_upload_key(uploaded_file.name, file_content)

    if st.session_state.get("ingested_upload_key") != upload_key:
        ingestion_result = ingest_csv_file(
            file_name=uploaded_file.name,
            file_content=file_content,
        )
        profile_result = build_dataset_profile(ingestion_result.dataframe)
        verification_result = verify_ingestion_result(
            ingestion_result=ingestion_result,
            file_content=file_content,
        )
        validation_result = validate_dataset(ingestion_result.dataframe)
        current_run_id: str | None = None
        persistence_error: str | None = None

        try:
            current_run_id = analysis_store.save_upload_run(
                ingestion_result=ingestion_result,
                file_content=file_content,
                profile_result=profile_result,
                validation_result=validation_result,
            )
        except (duckdb.Error, OSError) as exc:
            persistence_error = f"DuckDB persistence failed: {exc}"

        st.session_state["ingestion_result"] = ingestion_result
        st.session_state["profile_result"] = profile_result
        st.session_state["verification_result"] = verification_result
        st.session_state["validation_result"] = validation_result
        st.session_state["current_run_id"] = current_run_id
        st.session_state["persistence_error"] = persistence_error
        st.session_state["ingested_upload_key"] = upload_key

    return (
        file_content,
        st.session_state["ingestion_result"],
        st.session_state["profile_result"],
        st.session_state["verification_result"],
        st.session_state["validation_result"],
        st.session_state.get("current_run_id"),
        st.session_state.get("persistence_error"),
    )


def render_summary(
    profile_result,
    validation_result,
    file_name: str,
    file_content: bytes,
    run_id: str | None,
) -> None:
    metrics = st.columns(6)
    metrics[0].metric("File", file_name)
    metrics[1].metric("Rows", profile_result.row_count)
    metrics[2].metric("Columns", profile_result.column_count)
    metrics[3].metric("Null values", profile_result.total_null_count)
    metrics[4].metric("Issues", validation_result.summary.issue_count)
    metrics[5].metric("Rows with issues", validation_result.summary.affected_row_count)
    caption = f"File size: {len(file_content):,} bytes"
    if run_id is not None:
        caption = f"{caption} | Saved run ID: {run_id[:12]}"
    st.caption(caption)


def render_validation_summary_message(summary) -> None:
    if summary.quality_level == "High":
        st.success(summary.message)
    elif summary.quality_level == "Medium":
        st.warning(summary.message)
    else:
        st.error(summary.message)


def render_null_counts(profile_result) -> None:
    st.subheader("Null counts")
    st.dataframe(
        [
            {"column": column_name, "null_count": null_count}
            for column_name, null_count in profile_result.null_counts.items()
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_column_profile_table(profile_result, title: str) -> None:
    st.subheader(title)
    st.dataframe(
        [
            {
                "column": column_profile.column_name,
                "data_type": column_profile.data_type,
                "null_count": column_profile.null_count,
                "non_null_count": column_profile.non_null_count,
                "unique_count": column_profile.unique_count,
                "null_ratio": f"{column_profile.null_ratio:.1%}",
                "uniqueness_ratio": f"{column_profile.uniqueness_ratio:.1%}",
            }
            for column_profile in profile_result.column_profiles
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_issue_table(validation_result) -> None:
    st.subheader("Issue table")
    issue_table = build_issue_table(validation_result)
    if issue_table.empty:
        st.success("No quality issues were detected by the current built-in checks.")
        return

    st.dataframe(issue_table, use_container_width=True, hide_index=True)


def render_saved_issue_table(issues: tuple[StoredValidationIssue, ...]) -> None:
    st.subheader("Stored validation issues")
    if not issues:
        st.success("No stored validation issues were found for this run.")
        return

    st.dataframe(
        [
            {
                "rule": issue.rule_name,
                "severity": issue.severity.title(),
                "column": issue.column_name or "Dataset",
                "affected_rows": issue.affected_row_count,
                "sample_rows": ", ".join(
                    str(row_number)
                    for row_number in issue.sample_row_numbers
                ),
                "description": issue.description,
            }
            for issue in issues
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_sample_failing_rows(ingestion_result, validation_result) -> None:
    st.subheader("Sample failing rows")
    failing_rows = build_sample_failing_rows_table(
        dataframe=ingestion_result.dataframe,
        validation_result=validation_result,
        row_limit=FAILING_ROW_LIMIT,
    )
    if failing_rows.empty:
        st.info("There are no failing rows to sample.")
        return

    st.caption(f"Showing up to {FAILING_ROW_LIMIT} rows that triggered one or more checks.")
    st.dataframe(failing_rows, use_container_width=True, hide_index=True)


def render_preview(ingestion_result) -> None:
    st.subheader("File preview")
    st.caption(f"Showing the first {PREVIEW_ROW_LIMIT} rows from the parsed dataset.")
    st.dataframe(
        ingestion_result.dataframe.head(PREVIEW_ROW_LIMIT),
        use_container_width=True,
        hide_index=True,
    )


def format_uploaded_at(uploaded_at: datetime) -> str:
    return uploaded_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def format_run_label(run: StoredAnalysisRun) -> str:
    return (
        f"{format_uploaded_at(run.uploaded_at)} | {run.source_name} | "
        f"{run.issue_count} issues | {run.quality_level}"
    )


def render_recent_runs_table(runs: tuple[StoredAnalysisRun, ...]) -> None:
    st.subheader("Recent uploads")
    st.dataframe(
        [
            {
                "uploaded_at": format_uploaded_at(run.uploaded_at),
                "file_name": run.source_name,
                "rows": run.row_count,
                "columns": run.column_count,
                "null_values": run.total_null_count,
                "duplicate_rows": run.duplicate_row_count,
                "issues": run.issue_count,
                "rows_with_issues": run.affected_row_count,
                "quality": run.quality_level,
            }
            for run in runs
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_issue_trends(trend_points) -> None:
    if len(trend_points) < 2:
        return

    st.subheader("Issue trends")
    trend_frame = pd.DataFrame(
        [
            {
                "uploaded_at": point.uploaded_at,
                "issue_count": point.issue_count,
                "affected_rows": point.affected_row_count,
            }
            for point in reversed(trend_points)
        ]
    ).set_index("uploaded_at")
    st.line_chart(trend_frame)


def render_saved_run_details(details: StoredRunDetails) -> None:
    st.subheader("Saved run details")
    st.markdown(f"**{details.run.source_name}**")
    st.caption(
        f"Uploaded {format_uploaded_at(details.run.uploaded_at)} | "
        f"Raw copy `{details.run.stored_path}` | "
        f"SHA-256 `{details.run.file_hash[:16]}...`"
    )
    metrics = st.columns(6)
    metrics[0].metric("Rows", details.run.row_count)
    metrics[1].metric("Columns", details.run.column_count)
    metrics[2].metric("Null values", details.run.total_null_count)
    metrics[3].metric("Duplicate rows", details.run.duplicate_row_count)
    metrics[4].metric("Issues", details.run.issue_count)
    metrics[5].metric("Rows with issues", details.run.affected_row_count)
    render_validation_summary_message(details.run.validation_summary)
    render_column_profile_table(details.profile, title="Stored column profile")
    render_saved_issue_table(details.issues)


def render_saved_runs_dashboard(
    analysis_store: DuckDbAnalysisStore,
    default_run_id: str | None = None,
) -> None:
    recent_runs = analysis_store.load_recent_runs(limit=HISTORY_LIMIT)
    if not recent_runs:
        st.info("No saved runs are available yet. Upload a CSV file to create the first persisted run.")
        return

    render_recent_runs_table(recent_runs)
    render_issue_trends(analysis_store.load_issue_trends(limit=HISTORY_LIMIT))

    run_options = {run.run_id: run for run in recent_runs}
    selected_run_id = default_run_id or st.session_state.get("selected_saved_run_id")
    if selected_run_id not in run_options:
        selected_run_id = recent_runs[0].run_id

    option_ids = list(run_options)
    if (
        st.session_state.get("selected_saved_run_id") not in run_options
        or default_run_id is not None
    ):
        st.session_state["selected_saved_run_id"] = selected_run_id
    selected_run_id = st.selectbox(
        "Inspect a saved run",
        options=option_ids,
        index=option_ids.index(selected_run_id),
        format_func=lambda run_id: format_run_label(run_options[run_id]),
        key="selected_saved_run_id",
    )

    selected_details = analysis_store.load_run_details(selected_run_id)
    if selected_details is None:
        st.warning("The selected run could not be loaded from DuckDB.")
        return

    render_saved_run_details(selected_details)


st.set_page_config(page_title="CSV Data Quality Platform", layout="wide")
apply_page_styles()
render_header()

current_upload_tab, saved_history_tab = st.tabs(["Current upload", "Saved history"])

with current_upload_tab:
    render_section_heading(
        title="Upload and inspect",
        description="Focus on the latest CSV first, then use the detail tabs to review issues, raw rows, and column-level metrics.",
    )
    uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])

    if uploaded_file is None:
        clear_upload_state()
        st.info("Upload a CSV file to preview the dataset and run the built-in validation checks.")
    else:
        try:
            (
                file_content,
                ingestion_result,
                profile_result,
                verification_result,
                validation_result,
                current_run_id,
                persistence_error,
            ) = get_upload_results(uploaded_file, ANALYSIS_STORE)
        except InvalidCsvFileError as exc:
            clear_upload_state()
            st.error(f"Validation error: {exc}")
        else:
            render_summary(
                profile_result=profile_result,
                validation_result=validation_result,
                file_name=uploaded_file.name,
                file_content=file_content,
                run_id=current_run_id,
            )
            render_validation_summary_message(validation_result.summary)
            if verification_result.is_valid:
                st.success(
                    f"{verification_result.message} Raw copy stored at `{ingestion_result.stored_path}`."
                )
            else:
                st.error(verification_result.message)
            if persistence_error is not None:
                st.warning(persistence_error)
            elif current_run_id is not None:
                st.caption("Analysis saved to DuckDB and added to the saved run history.")

            issues_tab, dataset_tab, columns_tab = st.tabs(
                ["Quality issues", "Dataset view", "Column profile"]
            )
            with issues_tab:
                render_issue_table(validation_result)
                render_sample_failing_rows(ingestion_result, validation_result)
            with dataset_tab:
                render_preview(ingestion_result)
                render_null_counts(profile_result)
            with columns_tab:
                render_column_profile_table(profile_result, title="Column profile")

with saved_history_tab:
    render_section_heading(
        title="Saved analysis history",
        description="Reopen recent runs, compare trend lines, and inspect the persisted column and issue summaries.",
    )
    render_saved_runs_dashboard(
        analysis_store=ANALYSIS_STORE,
        default_run_id=st.session_state.get("current_run_id"),
    )
