from __future__ import annotations

import shutil
import subprocess

from inkly.plugins.common import format_plugin_output, validate_plugin_meta


PLUGIN_META = {
    "name": "queue_status",
    "description": (
        "Summarizes the current Slurm queue using squeue and sinfo, including "
        "running jobs, pending jobs, and partition load."
    ),
    "category": "queue-status",
    "example_queries": [
        "How busy is the cluster right now?",
        "Are there many pending jobs?",
        "What does the current queue look like?",
        "Is the gpu partition busy?",
    ],
}

validate_plugin_meta(PLUGIN_META)


def _command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _run_capture(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _count_jobs_by_state(state: str) -> int | None:
    if not _command_exists("squeue"):
        return None

    output = _run_capture(["squeue", "-h", "-t", state])
    if output is None:
        return None

    lines = [line for line in output.splitlines() if line.strip()]
    return len(lines)


def _get_partition_lines(limit: int = 5) -> list[str]:
    if not _command_exists("sinfo"):
        return ["Partition summary unavailable: sinfo not found."]

    output = _run_capture(["sinfo", "-h", "-o", "%P|%D|%C"])
    if not output:
        return ["Partition summary unavailable: sinfo returned no data."]

    lines: list[str] = []
    for row in output.splitlines()[:limit]:
        parts = row.split("|")
        if len(parts) != 3:
            continue

        partition, nodes, cpu_summary = (part.strip() for part in parts)
        lines.append(
            f"- {partition}: {nodes} nodes, CPU summary {cpu_summary}"
        )

    if not lines:
        return ["Partition summary unavailable: could not parse sinfo output."]

    return lines


def run() -> str:
    body_lines: list[str] = []

    running_jobs = _count_jobs_by_state("RUNNING")
    pending_jobs = _count_jobs_by_state("PENDING")

    if running_jobs is None or pending_jobs is None:
        body_lines.append("Queue counts unavailable: squeue not found or failed.")
    else:
        body_lines.append(f"Running jobs: {running_jobs}")
        body_lines.append(f"Pending jobs: {pending_jobs}")

    body_lines.append("Partitions:")
    body_lines.extend(_get_partition_lines())

    return format_plugin_output("Queue Status", body_lines)