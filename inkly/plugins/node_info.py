from __future__ import annotations

import shutil
import subprocess

from inkly.plugins.common import format_plugin_output, validate_plugin_meta


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


def _get_node_info_lines(limit: int = 8) -> list[str]:
    if not _command_exists("sinfo"):
        return ["Node information unavailable: sinfo not found."]

    output = _run_capture(["sinfo", "-h", "-o", "%P|%D|%c|%m|%G"])
    if not output:
        return ["Node information unavailable: sinfo returned no data."]

    lines: list[str] = []

    for row in output.splitlines()[:limit]:
        parts = row.split("|")
        if len(parts) != 5:
            continue

        partition, nodes, cpus, memory, gres = (part.strip() for part in parts)

        # Clean up GRES (GPU info)
        if not gres or gres == "(null)":
            gres = "This partition has no GPUs."

        lines.append(
            f"- {partition}: {nodes} nodes, {cpus} CPUs/node, {memory} MB/node, GPUs: {gres}"
        )

    if not lines:
        return ["Node information unavailable: could not parse sinfo output."]

    return lines


def run() -> str:
    body_lines: list[str] = []

    body_lines.append("Partitions and resources:")
    body_lines.extend(_get_node_info_lines())

    return format_plugin_output("Node / Partition Information", body_lines)
