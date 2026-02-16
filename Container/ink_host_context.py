"""
Ink Host Context Gatherer (importable)

This module gathers sanitized HPC environment context
on the host side before container execution.

Design Goals
------------
- Safe to import (no side effects)
- No filesystem assumptions at import time
- Suppress noisy subprocess errors
- Mirror ink_core coding conventions
- Produce structured JSON (not formatted text)
"""

import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime, timezone
import json


# System Utilities (mirrors ink_core style)
def command_exists(cmd: str) -> bool:
    """Return True if a command exists in PATH."""
    return shutil.which(cmd) is not None


def run_capture(cmd: list[str]) -> Optional[str]:
    """
    Execute a command and capture stdout only.

    Errors are intentionally suppressed.
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
    except subprocess.CalledProcessError:
        return None


# Context Gathering
def gather_host_context() -> Dict:
    """
    Gather sanitized HPC environment context.

    This function must:
    - Avoid leaking usernames
    - Avoid leaking full paths
    - Avoid environment dumps
    - Limit output size
    """

    context: Dict = {
        "schema_version": 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "host": {},
        "slurm": {"present": False},
        "gpu": {"present": False},
    }

    # Hostname
    if command_exists("hostname"):
        hostname = run_capture(["hostname"])
        if hostname:
            context["host"]["hostname"] = hostname

    # OS release (safe fields only)
    os_release = Path("/etc/os-release")
    if os_release.exists():
        try:
            with os_release.open() as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        os_name = line.split("=", 1)[1].strip().strip('"')
                        context["host"]["os"] = os_name
                        break
        except OSError:
            pass

    # SLURM summary (avoid squeue due to usernames)
    if command_exists("sinfo"):
        sinfo = run_capture(["sinfo", "-h", "-o", "%P %D %C"])
        if sinfo:
            context["slurm"] = {
                "present": True,
                "summary": sinfo.splitlines()[:5],
            }

    # Detect slurm config presence only (no full file read)
    if Path("/etc/slurm/slurm.conf").exists():
        context.setdefault("slurm", {})["config_present"] = True

    # GPU summary
    if command_exists("nvidia-smi"):
        gpu = run_capture(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader",
            ]
        )
        if gpu:
            context["gpu"] = {
                "present": True,
                "summary": gpu.splitlines()[:4],
            }

    return context


# Context Serialization
def write_host_context(state_dir: Path) -> Path:
    """
    Serialize host context to JSON file.

    This function performs filesystem writes and must
    only be called by the host wrapper (not at import time).
    """
    state_dir.mkdir(parents=True, exist_ok=True)

    context = gather_host_context()
    output_path = state_dir / "context.json"

    output_path.write_text(json.dumps(context, indent=2))

    return output_path
