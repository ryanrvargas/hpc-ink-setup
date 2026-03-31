from __future__ import annotations

import shutil
import subprocess

from inkly.plugins.common import format_plugin_output, validate_plugin_meta


# Metadata describing this plugin.
# This is used by plugin discovery, retrieval, and runtime selection.
PLUGIN_META = {
    "name": "node_info",
    "description": (
        "Lists cluster partitions and node resources such as CPUs, memory, and GPU availability "
        "using sinfo."
    ),
    "category": "node-info",
    "example_queries": [
        "What partitions are available?",
        "Which nodes have GPUs?",
        "What resources does this cluster have?",
        "How much memory do nodes provide?",
    ],
}

# Validate metadata at import time so invalid plugins fail early.
validate_plugin_meta(PLUGIN_META)


def _command_exists(cmd: str) -> bool:
    """
    Check whether a command is available on PATH.

    This is used before calling cluster tools so the plugin can return
    a clean fallback message instead of failing with a subprocess error.
    """
    return shutil.which(cmd) is not None


def _run_capture(cmd: list[str]) -> str | None:
    """
    Run a command and return stripped stdout.

    Returns:
        Command output if successful, otherwise None.

    This keeps subprocess error handling contained in one place so the
    rest of the plugin logic stays simple.
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


def _get_node_info_lines(limit: int = 8) -> list[str]:
    """
    Collect and format node / partition information from sinfo.

    The output is limited so plugin context stays readable and does not
    overwhelm the runtime prompt.

    Returns:
        A list of formatted lines describing partitions and resources.
        If data cannot be collected or parsed, a fallback message is returned.
    """
    # sinfo is required for live node and partition information.
    if not _command_exists("sinfo"):
        return ["Node information unavailable: sinfo not found."]

    # %P = partition, %D = nodes, %c = CPUs, %m = memory, %G = GRES / GPU info
    output = _run_capture(["sinfo", "-h", "-o", "%P|%D|%c|%m|%G"])
    if not output:
        return ["Node information unavailable: sinfo returned no data."]

    lines: list[str] = []

    # Only keep the first few rows so output stays short.
    for row in output.splitlines()[:limit]:
        parts = row.split("|")
        if len(parts) != 5:
            continue

        partition, nodes, cpus, memory, gres = (part.strip() for part in parts)

        # Clean up GRES / GPU info for partitions without GPUs.
        if not gres or gres == "(null)":
            gres = "This partition has no GPUs."

        lines.append(
            f"- {partition}: {nodes} nodes, {cpus} CPUs/node, {memory} MB/node, GPUs: {gres}"
        )

    # If nothing valid could be parsed, return a fallback message.
    if not lines:
        return ["Node information unavailable: could not parse sinfo output."]

    return lines


def run() -> str:
    """
    Entry point for the node-info plugin.

    This gathers current partition and node resource information, formats it,
    and returns it as a clean plugin output block.
    """
    body_lines: list[str] = []

    body_lines.append("Partitions and resources:")
    body_lines.extend(_get_node_info_lines())

    return format_plugin_output("Node / Partition Information", body_lines)