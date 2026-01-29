#!/usr/bin/env python3
"""
Ink: Cluster-aware Inkly runtime + launcher

Combines:
- ink (cluster context + prompt injection)
- inkly-runtime.py (config, guardrails, Copilot exec)
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List


try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # Python <=3.10

# Utilities
def die(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    sys.exit(code)

def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def run_capture(cmd: List[str]) -> Optional[str]:
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

# Load Inkly config
INKLY_HOME = Path.home() / ".inkly"
CONFIG_PATH = INKLY_HOME / "config.toml"
NPM_BIN = Path.home() / ".npm-global" / "bin"

try:
    with CONFIG_PATH.open("rb") as f:
        config = tomllib.load(f)
except Exception as e:
    die(f"Inkly config error: {e}")

# Ensure Copilot is discoverable
os.environ["PATH"] = f"{NPM_BIN}:{os.environ.get('PATH', '')}"

# Gather HPC context
ctx: List[str] = []

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

if command_exists("nvidia-smi"):
    if run_capture(["nvidia-smi", "-L"]) is not None:
        gpu = run_capture([
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader",
        ])
        if gpu:
            ctx.append(f"GPU: {gpu.splitlines()[0]}")

# Build Copilot command
cmd = ["copilot"]

if len(sys.argv) > 1:
    user_prompt = " ".join(sys.argv[1:])

    context_block = "\n".join(ctx)

    full_prompt = (
        "Using the following HPC environment context:\n"
        f"{context_block}\n\n"
        f"Now: {user_prompt}"
    )

    cmd += ["-p", full_prompt]
# else: interactive mode (no flags)

# Exec Copilot (final)
try:
    os.execvp("copilot", cmd)
except FileNotFoundError:
    die("Inkly error: 'copilot' not found on PATH")
