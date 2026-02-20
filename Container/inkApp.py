#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path
import shutil


HOME = Path.home()
INKLY_HOME = HOME / ".inkly"
COPILOT_DIR = HOME / ".copilot"
CONTAINER_IMAGE = Path(__file__).parent / "inkly.sif"

def main() -> int:
    runtime = shutil.which("apptainer") or shutil.which("singularity")
    if not runtime:
        print("Error: neither apptainer nor singularity found on PATH.", file=sys.stderr)
        return 1

    if not CONTAINER_IMAGE.exists():
        print(f"Error: container image not found: {CONTAINER_IMAGE}", file=sys.stderr)
        return 1

    script_dir = Path(__file__).parent
    host_context_script = script_dir / "ink_host_context.py"
    if not host_context_script.exists():
        print(f"Error: missing host context script: {host_context_script}", file=sys.stderr)
        return 1

    # Pre-flight: state layout
    INKLY_HOME.mkdir(parents=True, exist_ok=True)
    (INKLY_HOME / "logs").mkdir(parents=True, exist_ok=True)

    cfg_path = INKLY_HOME / "config.toml"
    if not cfg_path.exists():
        print(f"Error: missing config: {cfg_path}", file=sys.stderr)
        return 1

    # Generate fresh context.json
    subprocess.run([sys.executable, str(host_context_script), str(INKLY_HOME)], check=True)
    context_file = INKLY_HOME / "context.json"

    enable_nv = shutil.which("nvidia-smi") is not None

    # Build container command
    cmd = [
        runtime,
        "exec",
        "--cleanenv",
        "--contain",
        "--no-home",
    ]

    if enable_nv:
        cmd.append("--nv")

    cmd += [
        "--bind", f"{cfg_path}:{cfg_path}",
        "--bind", f"{INKLY_HOME / 'logs'}:{INKLY_HOME / 'logs'}",
        "--bind", f"{COPILOT_DIR}:{COPILOT_DIR}",
        "--bind", f"{context_file}:/context.json",
        str(CONTAINER_IMAGE),
        "ink",
        "--context", "/context.json",
        *sys.argv[1:],
    ]

    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())