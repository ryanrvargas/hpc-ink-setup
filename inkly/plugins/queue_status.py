from __future__ import annotations

import shutil
import subprocess

from inkly.plugins.common import format_plugin_output, validate_plugin_meta


# Metadata describing this plugin.
# This is used by plugin discovery, retrieval, and runtime selection.
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

# Validate metadata at import time so invalid plugins fail early.
validate_plugin_meta(PLUGIN_META)


def _command_exists(cmd: str) -> bool:
    """
    Check whether a command is available on PATH.

    This is used before calling Slurm tools so the plugin can return
    a clean fallback message instead of failing with a subprocess error.
    """
    return shutil.which(cmd) is not None


def _run_capture(cmd: list[str]) -> str | None:
    """
    Run a command and return stripped stdout.

    Returns:
        Command output if successful, otherwise None.

    This keeps subprocess error handling in one place so the rest of the
    plugin logic stays simple.
    """
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
    """
    Count jobs in a given Slurm state using squeue.

    Args:
        state: Slurm job state to query, such as RUNNING or PENDING.

    Returns:
        Number of jobs in that state, or None if squeue is unavailable or fails.
    """
    # squeue is required for live queue counts.
    if not _command_exists("squeue"):
        return None

    output = _run_capture(["squeue", "-h", "-t", state])
    if output is None:
        return None

    # Count non-empty output lines, where each line represents one job.
    lines = [line for line in output.splitlines() if line.strip()]
    return len(lines)


def _get_partition_lines(limit: int = 5) -> list[str]:
    """
    Collect and format partition summary lines from sinfo.

    The output is limited so plugin context stays readable and does not
    overwhelm the runtime prompt.

    Returns:
        A list of formatted partition summary lines.
        If data cannot be collected or parsed, a fallback message is returned.
    """
    # sinfo is required for live partition information.
    if not _command_exists("sinfo"):
        return ["Partition summary unavailable: sinfo not found."]

    # %P = partition, %D = node count, %C = CPU allocation summary
    output = _run_capture(["sinfo", "-h", "-o", "%P|%D|%C"])
    if not output:
        return ["Partition summary unavailable: sinfo returned no data."]

    lines: list[str] = []
    for row in output.splitlines()[:limit]:
        parts = row.split("|")
        if len(parts) != 3:
            continue

        partition, nodes, cpu_summary = (part.strip() for part in parts)
        lines.append(f"- {partition}: {nodes} nodes, CPU summary {cpu_summary}")

    # If nothing valid could be parsed, return a fallback message.
    if not lines:
        return ["Partition summary unavailable: could not parse sinfo output."]

    return lines


def run() -> str:
    """
    Entry point for the queue-status plugin.

    This gathers current queue counts and partition summary information,
    then formats everything into a clean plugin output block.
    """
    body_lines: list[str] = []

    running_jobs = _count_jobs_by_state("RUNNING")
    pending_jobs = _count_jobs_by_state("PENDING")

    # If queue counts cannot be collected, return a clean fallback line.
    if running_jobs is None or pending_jobs is None:
        body_lines.append("Queue counts unavailable: squeue not found or failed.")
    else:
        body_lines.append(f"Running jobs: {running_jobs}")
        body_lines.append(f"Pending jobs: {pending_jobs}")

    body_lines.append("Partitions:")
    body_lines.extend(_get_partition_lines())

    return format_plugin_output("Queue Status", body_lines)