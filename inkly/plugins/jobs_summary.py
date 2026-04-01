from __future__ import annotations

from pathlib import Path

from inkly.intelligence.analytics import load_cluster_intelligence_summary
from inkly.plugins.common import format_plugin_output, validate_plugin_meta


# Metadata describing this plugin.
# This is used by plugin discovery, retrieval, and runtime selection.
PLUGIN_META = {
    "name": "jobs_summary",
    "description": (
        "Summarizes historical Slurm job outcomes and resource trends from the Inkly "
        "SQLite database, including partition success rates, memory failure rates, and "
        "common failure types."
    ),
    "category": "job-history",
    "example_queries": [
        "Why are jobs failing on this cluster?",
        "What partitions have the best success rate?",
        "Do high-memory jobs fail more often?",
        "What are the most common job failures?",
    ],
}

# Validate metadata at import time so invalid plugins fail early.
validate_plugin_meta(PLUGIN_META)


def _format_partition_section(partition_stats: dict) -> list[str]:
    """
    Format partition-level success statistics into display lines.

    This keeps the output concise and only shows the first few partition entries.
    If no partition data is available, a fallback message is returned.
    """
    if not partition_stats:
        return ["Partition success rates unavailable."]

    lines = ["Top partition success rates:"]
    for partition, stats in list(partition_stats.items())[:5]:
        successful_jobs = stats.get("successful_jobs", 0)
        total_jobs = stats.get("total_jobs", 0)
        success_rate = stats.get("success_rate")

        # If success rate is missing, keep the output readable instead of failing.
        if success_rate is None:
            lines.append(f"- {partition}: success rate unavailable")
            continue

        lines.append(
            f"- {partition}: {successful_jobs}/{total_jobs} successful "
            f"({success_rate:.3f})"
        )

    return lines


def _format_memory_section(memory_stats: dict) -> list[str]:
    """
    Format memory-bucket failure statistics into display lines.

    This keeps the output short and focused on the first few memory buckets.
    If no memory data is available, a fallback message is returned.
    """
    if not memory_stats:
        return ["Memory bucket failure rates unavailable."]

    lines = ["Memory bucket failure rates:"]
    for bucket, stats in list(memory_stats.items())[:5]:
        total_jobs = stats.get("total_jobs", 0)
        failure_rate = stats.get("failure_rate")

        # If failure rate is missing, show a fallback line instead of formatting None.
        if failure_rate is None:
            lines.append(f"- {bucket}: failure rate unavailable")
            continue

        lines.append(
            f"- {bucket}: {failure_rate:.3f} failure rate over {total_jobs} jobs"
        )

    return lines


def _normalize_failure_state(state: str) -> str:
    """
    Normalize raw Slurm failure-state strings into cleaner display labels.

    This is used to collapse variants of the same failure type into one label.

    Examples:
    - 'CANCELLED by 583311' -> 'CANCELLED'
    - 'FAILED' -> 'FAILED'
    - 'OUT_OF_MEMORY' -> 'OUT_OF_MEMORY'
    """
    cleaned = (state or "").strip()

    # Slurm cancellation messages may include extra detail after the base state.
    # This normalizes those variants into one display category.
    if cleaned.startswith("CANCELLED"):
        return "CANCELLED"

    return cleaned


def _format_failure_section(failure_stats: dict) -> list[str]:
    """
    Format failure-state distribution into display lines.

    Raw failure states may contain multiple variants for the same state,
    so values are normalized and merged before sorting.
    """
    if not failure_stats:
        return ["Failure-state distribution unavailable."]

    # This stores merged totals after raw states are normalized.
    normalized_totals: dict[str, dict[str, float]] = {}

    for raw_state, stats in failure_stats.items():
        normalized_state = _normalize_failure_state(raw_state)

        # Initialize the merged bucket if it does not exist yet.
        if normalized_state not in normalized_totals:
            normalized_totals[normalized_state] = {
                "count": 0,
                "percentage": 0.0,
            }

        # Merge counts and percentages across normalized states.
        normalized_totals[normalized_state]["count"] += stats.get("count", 0)
        normalized_totals[normalized_state]["percentage"] += stats.get(
            "percentage", 0.0
        )

    # Sort by count descending so the most common failure states appear first.
    sorted_states = sorted(
        normalized_totals.items(),
        key=lambda item: item[1]["count"],
        reverse=True,
    )

    lines = ["Most common failure states:"]
    for state, stats in sorted_states[:5]:
        count = stats.get("count", 0)
        percentage = stats.get("percentage", 0.0)
        lines.append(f"- {state}: {count} ({percentage:.3f})")

    return lines


def run() -> str:
    """
    Entry point for the job-history summary plugin.

    This loads precomputed cluster intelligence from the local SQLite database,
    formats the main summary sections, and returns the result as a clean text block.

    Behavior:
    - If the database does not exist, return a fallback message
    - If loading fails, return an error message in plugin-output format
    - Otherwise, format dataset size, partition stats, memory stats, and failure stats
    """
    # Job-history summaries are loaded from the local Inkly database.
    db_path = Path.home() / ".inkly" / "jobs.db"

    # If the database is missing, return a safe fallback response.
    if not db_path.exists():
        return format_plugin_output(
            "Job History Summary",
            ["Job-history database not found."],
        )

    try:
        # Load precomputed intelligence summary tables.
        summary = load_cluster_intelligence_summary(str(db_path))
    except Exception as exc:
        # Keep plugin failures contained so the runtime can continue.
        return format_plugin_output(
            "Job History Summary",
            [f"Unable to load job-history summary: {exc}"],
        )

    # Pull the main sections out of the summary payload.
    dataset_size = summary.get("dataset_size", 0)
    partition_stats = summary.get("partition_success", {})
    memory_stats = summary.get("memory_analysis", {})
    failure_stats = summary.get("failure_distribution", {})

    # Build the response in sections.
    body_lines: list[str] = [f"Dataset size: {dataset_size} jobs", ""]

    body_lines.extend(_format_partition_section(partition_stats))
    body_lines.append("")

    body_lines.extend(_format_memory_section(memory_stats))
    body_lines.append("")

    body_lines.extend(_format_failure_section(failure_stats))

    # Return a final formatted plugin-output block.
    return format_plugin_output("Job History Summary", body_lines)
