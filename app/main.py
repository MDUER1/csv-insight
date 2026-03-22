from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from src.models import (
    CsvUpload,
    CsvUploadBatchAnalysis,
    FailedCsvUploadAnalysis,
    StoredAnalysisRun,
    StoredRunDetails,
    StoredValidationIssue,
    SuccessfulCsvUploadAnalysis,
)
from src.rules import (
    build_issue_table,
    build_sample_failing_rows_table,
)
from src.storage import DuckDbAnalysisStore
from src.workflows import analyze_csv_uploads, build_upload_batch_key


PREVIEW_ROW_LIMIT = 10
FAILING_ROW_LIMIT = 10
HISTORY_LIMIT = 10
ANALYSIS_STORE = DuckDbAnalysisStore()


def apply_page_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(14, 165, 233, 0.10), transparent 28%),
                linear-gradient(180deg, #f8fafc 0%, #eef4f7 100%);
        }
        .block-container {
            max-width: 1100px;
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        .hero-card {
            padding: 1.5rem 1.75rem;
            border: 1px solid rgba(148, 163, 184, 0.25);
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.9);
            box-shadow: 0 20px 45px rgba(15, 23, 42, 0.07);
            margin-bottom: 1.25rem;
        }
        .hero-title {
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            color: #0f172a;
            margin: 0;
        }
        .hero-copy {
            color: #475569;
            margin: 0.5rem 0 0 0;
            font-size: 1rem;
        }
        [data-testid="stFileUploader"] {
            padding: 1rem;
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid rgba(148, 163, 184, 0.25);
        }
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 16px;
            padding: 0.6rem;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.05);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        """
        <div class="hero-card">
            <p class="hero-title">CSV Folder Upload</p>
            <p class="hero-copy">
                Upload a folder of CSV files, inspect each dataset profile, review detected
                quality issues, and keep every processed file in DuckDB so recent uploads and
                saved profiles are available across sessions.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def clear_upload_state() -> None:
    for key in (
        "ingested_upload_key",
        "upload_batch_analysis",
        "selected_uploaded_file_index",
    ):
        st.session_state.pop(key, None)


def get_upload_results(
    uploaded_files,
    analysis_store: DuckDbAnalysisStore,
) -> CsvUploadBatchAnalysis:
    uploads = tuple(
        CsvUpload(
            file_name=uploaded_file.name,
            file_content=uploaded_file.getvalue(),
        )
        for uploaded_file in uploaded_files
    )
    upload_key = build_upload_batch_key(uploads)

    if st.session_state.get("ingested_upload_key") != upload_key:
        st.session_state["upload_batch_analysis"] = analyze_csv_uploads(
            uploads=uploads,
            analysis_store=analysis_store,
        )
        st.session_state["ingested_upload_key"] = upload_key
        st.session_state["selected_uploaded_file_index"] = 0

    return st.session_state["upload_batch_analysis"]


def render_batch_summary(batch_analysis: CsvUploadBatchAnalysis) -> None:
    metrics = st.columns(6)
    metrics[0].metric("CSV files", batch_analysis.total_file_count)
    metrics[1].metric("Valid", batch_analysis.successful_file_count)
    metrics[2].metric("Rejected", batch_analysis.failed_file_count)
    metrics[3].metric("Rows", batch_analysis.total_row_count)
    metrics[4].metric("Issues", batch_analysis.total_issue_count)
    metrics[5].metric("Files with issues", batch_analysis.files_with_issues_count)

    caption = f"Total uploaded size: {batch_analysis.total_size_bytes:,} bytes"
    if batch_analysis.persisted_run_count:
        caption = f"{caption} | Saved runs: {batch_analysis.persisted_run_count}"
    st.caption(caption)


def render_rejected_uploads(
    failed_analyses: tuple[FailedCsvUploadAnalysis, ...],
) -> None:
    if not failed_analyses:
        return

    st.subheader("Rejected files")
    st.dataframe(
        [
            {
                "file_name": analysis.file_name,
                "error": analysis.error_message,
            }
            for analysis in failed_analyses
        ],
        use_container_width=True,
        hide_index=True,
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
    st.header("Saved analysis history")
    recent_runs = analysis_store.load_recent_runs(limit=HISTORY_LIMIT)
    if not recent_runs:
        st.info(
            "No saved runs are available yet. Upload a folder of CSV files to create "
            "the first persisted run."
        )
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


def format_uploaded_file_label(
    upload_analysis: SuccessfulCsvUploadAnalysis,
) -> str:
    summary = upload_analysis.validation_result.summary
    return (
        f"{upload_analysis.file_name} | "
        f"{upload_analysis.profile_result.row_count} rows | "
        f"{summary.issue_count} issues | "
        f"{summary.quality_level}"
    )


def select_uploaded_file(
    successful_analyses: tuple[SuccessfulCsvUploadAnalysis, ...],
) -> SuccessfulCsvUploadAnalysis:
    st.subheader("Processed files")
    option_indices = list(range(len(successful_analyses)))
    selected_index = st.session_state.get("selected_uploaded_file_index", 0)
    if selected_index not in option_indices:
        st.session_state["selected_uploaded_file_index"] = 0
        selected_index = 0

    selected_index = st.selectbox(
        "Inspect a processed file",
        options=option_indices,
        index=option_indices.index(selected_index),
        format_func=lambda index: format_uploaded_file_label(successful_analyses[index]),
        key="selected_uploaded_file_index",
    )
    return successful_analyses[selected_index]


st.set_page_config(page_title="CSV Data Quality Platform", layout="wide")
apply_page_styles()
render_header()

uploaded_files = st.file_uploader(
    "Upload a folder of CSV files",
    type=["csv"],
    accept_multiple_files="directory",
)
selected_run_id: str | None = None

if not uploaded_files:
    clear_upload_state()
    st.info(
        "Upload a folder of CSV files to preview datasets and run the built-in validation checks."
    )
else:
    batch_analysis = get_upload_results(uploaded_files, ANALYSIS_STORE)
    render_batch_summary(batch_analysis)
    render_rejected_uploads(batch_analysis.failed_analyses)

    if not batch_analysis.successful_analyses:
        st.error("No valid CSV files were processed from the uploaded folder.")
    else:
        selected_analysis = select_uploaded_file(batch_analysis.successful_analyses)
        selected_run_id = selected_analysis.run_id
        st.divider()
        render_summary(
            profile_result=selected_analysis.profile_result,
            validation_result=selected_analysis.validation_result,
            file_name=selected_analysis.file_name,
            file_content=selected_analysis.file_content,
            run_id=selected_analysis.run_id,
        )
        render_validation_summary_message(selected_analysis.validation_result.summary)
        if selected_analysis.verification_result.is_valid:
            st.success(
                f"{selected_analysis.verification_result.message} Raw copy stored at "
                f"`{selected_analysis.ingestion_result.stored_path}`."
            )
        else:
            st.error(selected_analysis.verification_result.message)
        if selected_analysis.persistence_error is not None:
            st.warning(selected_analysis.persistence_error)
        elif selected_analysis.run_id is not None:
            st.caption("Analysis saved to DuckDB and added to the saved run history.")
        render_issue_table(selected_analysis.validation_result)
        render_sample_failing_rows(
            selected_analysis.ingestion_result,
            selected_analysis.validation_result,
        )
        render_preview(selected_analysis.ingestion_result)
        render_null_counts(selected_analysis.profile_result)
        render_column_profile_table(
            selected_analysis.profile_result,
            title="Column profile",
        )

st.divider()
render_saved_runs_dashboard(
    analysis_store=ANALYSIS_STORE,
    default_run_id=selected_run_id,
)
