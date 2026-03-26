from __future__ import annotations

from pathlib import Path

from inkly.intelligence.analytics import load_cluster_intelligence_summary

PLUGIN_META = {
    "name": "jobs_summary",
    "description": "Summarizes historical Slurm job outcomes and resource trends from the Inkly SQLite database.",
    "category": "job-history",
    "example_queries": [
        "Why are jobs failing on this cluster?",
        "What partitions have the best success rate?",
        "Do high-memory jobs fail more often?",
    ],
}


def run() -> str:
    db_path = Path.home() / ".inkly" / "jobs.db"

    if not db_path.exists():
        return "Job-history database not found."

    summary = load_cluster_intelligence_summary(str(db_path))
    dataset_size = summary.get("dataset_size", 0)

    lines = [f"Dataset size: {dataset_size} jobs"]

    partition_stats = summary.get("partition_success", {})
    if partition_stats:
        lines.append("Partition success rates:")
        for partition, stats in partition_stats.items():
            lines.append(
                f"- {partition}: {stats['successful_jobs']}/{stats['total_jobs']} "
                f"successful ({stats['success_rate']:.3f})"
            )

    memory_stats = summary.get("memory_analysis", {})
    if memory_stats:
        lines.append("Memory bucket failure rates:")
        for bucket, stats in memory_stats.items():
            lines.append(
                f"- {bucket}: {stats['failure_rate']:.3f} failure rate "
                f"over {stats['total_jobs']} jobs"
            )

    failure_stats = summary.get("failure_distribution", {})
    if failure_stats:
        lines.append("Failure distribution:")
        for state, stats in failure_stats.items():
            lines.append(
                f"- {state}: {stats['count']} ({stats['percentage']:.3f})"
            )

    return "\n".join(lines)