#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

# Paths
HOME = Path.home()
INKLY_HOME = HOME / ".inkly"
COPILOT_DIR = HOME / ".copilot"

CONTAINER_IMAGE = Path(__file__).parent / "inkly.sif"
CONTEXT_FILE = INKLY_HOME / "context.json"


def main():
    INKLY_HOME.mkdir(parents=True, exist_ok=True)
    # 1. Generate fresh context.json
    SCRIPT_DIR = Path(__file__).parent
    HOST_CONTEXT_SCRIPT = SCRIPT_DIR / "ink_host_context.py"
    # Generate fresh context on host and write to INKLY_HOME/context.json
    subprocess.run([sys.executable, str(HOST_CONTEXT_SCRIPT), str(INKLY_HOME)], check=True)

    # 2. Build apptainer command
    cmd = [
        "apptainer",
        "exec",
        "--cleanenv",
        "--nv",
        "--bind", f"{INKLY_HOME}:{INKLY_HOME}",  # Bind entire Inkly state dir for flexibility
        "--bind", f"{COPILOT_DIR}:{COPILOT_DIR}",  # Bind entire copilot auth dir for flexibility
        "--bind", f"{CONTEXT_FILE}:/context.json",
        str(CONTAINER_IMAGE),
        "ink",
        "--context", "/context.json",
        *sys.argv[1:],
    ]

    # 3. Run container
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
