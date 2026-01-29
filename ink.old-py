#!/usr/bin/env python3
"""
Ink: HPC-aware assistant built on Inkly (Copilot CLI)
Usage:
    ink "Make me a Slurm sbatch for 2 GPU nodes for 24h"
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Utility functions
def die(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    sys.exit(code)

# Check if a command exists in PATH
def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None

# Run a command and capture its output
def run_capture(cmd: list[str]) -> str | None:
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

def main():
    home = Path.home()
    inkly_bin = home / ".npm-global" / "bin" / "inkly"

    # Detect Inkly binary
    if not inkly_bin.is_file() or not os.access(inkly_bin, os.X_OK):
        die("Inkly binary not found - run install.sh first.")

    ctx: list[str] = []

    # Gather HPC environment info
    if command_exists("hostname"):
        hostname = run_capture(["hostname"])
        if hostname:
            ctx.append(f"Hostname: {hostname}")

    os_release = Path("/etc/os-release")
    if os_release.exists():
        try:
            with os_release.open() as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        os_name = line.split("=", 1)[1].strip().strip('"')
                        ctx.append(f"OS: {os_name}")
                        break
        except OSError:
            pass

    if command_exists("sinfo"):
        sinfo = run_capture(["sinfo", "-h", "-o", "%P %D %C"])
        if sinfo:
            ctx.append("SLURM Queues (top):")
            for line in sinfo.splitlines()[:3]:
                ctx.append(f"  {line}")

    if Path("/etc/slurm/slurm.conf").exists():
        ctx.append("SLURM Config Path: /etc/slurm/slurm.conf")

    # Avoid unnecessary overhead
    if command_exists("nvidia-smi"):
        if run_capture(["nvidia-smi", "-L"]) is not None:
            gpu = run_capture([
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader",
            ])
            if gpu:
                ctx.append(f"GPU: {gpu.splitlines()[0]}")

    # Args handling
    if len(sys.argv) == 1:
        # Interactive mode
        os.execv(str(inkly_bin), [str(inkly_bin)])

    # Compose prompt
    context_block = "\n".join(ctx)
    user_prompt = " ".join(sys.argv[1:])

    prompt = (
        "Using the following HPC environment context:\n"
        f"{context_block}\n\n"
        f"Now: {user_prompt}"
    )

    # Replace process
    os.execv(str(inkly_bin), [str(inkly_bin), prompt])


if __name__ == "__main__":
    main()
