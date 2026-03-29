from __future__ import annotations

from pathlib import Path

from inkly.intelligence.analytics import load_cluster_intelligence_summary
from inkly.plugins.common import format_plugin_output, validate_plugin_meta


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

validate_plugin_meta(PLUGIN_META)


def _format_partition_section(partition_stats: dict) -> list[str]:
    if not partition_stats:
        return ["Partition success rates unavailable."]

    lines = ["Top partition success rates:"]
    for partition, stats in list(partition_stats.items())[:5]:
        successful_jobs = stats.get("successful_jobs", 0)
        total_jobs = stats.get("total_jobs", 0)
        success_rate = stats.get("success_rate")

        if success_rate is None:
            lines.append(f"- {partition}: success rate unavailable")
            continue

        lines.append(
            f"- {partition}: {successful_jobs}/{total_jobs} successful "
            f"({success_rate:.3f})"
        )

    return lines


def _format_memory_section(memory_stats: dict) -> list[str]:
    if not memory_stats:
        return ["Memory bucket failure rates unavailable."]

    lines = ["Memory bucket failure rates:"]
    for bucket, stats in list(memory_stats.items())[:5]:
        total_jobs = stats.get("total_jobs", 0)
        failure_rate = stats.get("failure_rate")

        if failure_rate is None:
            lines.append(f"- {bucket}: failure rate unavailable")
            continue

        lines.append(
            f"- {bucket}: {failure_rate:.3f} failure rate over {total_jobs} jobs"
        )

    return lines


def _format_failure_section(failure_stats: dict) -> list[str]:
    if not failure_stats:
        return ["Failure distribution unavailable."]

    lines = ["Most common failure types:"]
    for state, stats in list(failure_stats.items())[:5]:
        count = stats.get("count", 0)
        percentage = stats.get("percentage")

        if percentage is None:
            lines.append(f"- {state}: {count}")
            continue

        lines.append(f"- {state}: {count} ({percentage:.3f})")

    return lines


def run() -> str:
    db_path = Path.home() / ".inkly" / "jobs.db"

    if not db_path.exists():
        return format_plugin_output(
            "Job History Summary",
            ["Job-history database not found."],
        )

    try:
        summary = load_cluster_intelligence_summary(str(db_path))
    except Exception as exc:
        return format_plugin_output(
            "Job History Summary",
            [f"Unable to load job-history summary: {exc}"],
        )

    dataset_size = summary.get("dataset_size", 0)
    partition_stats = summary.get("partition_success", {})
    memory_stats = summary.get("memory_analysis", {})
    failure_stats = summary.get("failure_distribution", {})

    body_lines: list[str] = [f"Dataset size: {dataset_size} jobs", ""]

    body_lines.extend(_format_partition_section(partition_stats))
    body_lines.append("")

    body_lines.extend(_format_memory_section(memory_stats))
    body_lines.append("")

    body_lines.extend(_format_failure_section(failure_stats))

    return format_plugin_output("Job History Summary", body_lines)