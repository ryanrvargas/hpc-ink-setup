#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

# Paths
HOME = Path.home()
INKLY_HOME = HOME / ".inkly"
COPILOT_AUTH = HOME / ".copilot"
CONTAINER_IMAGE = Path(__file__).parent / "inkly.sif"
CONTEXT_FILE = INKLY_HOME / "context.json"

def main():
    # 1. Generate fresh context.json
    subprocess.run(
        ["python3", "ink_host_context.py", str(CONTEXT_FILE)],
        check=True
    )

    # 2. Build apptainer command
    cmd = [
        "apptainer", "exec",
        "--bind", f"{INKLY_HOME}:{INKLY_HOME}",
        "--bind", f"{COPILOT_AUTH}:{COPILOT_AUTH}",
        "--bind", f"{CONTEXT_FILE}:{CONTEXT_FILE}",
        str(CONTAINER_IMAGE),
        "ink",
        "--context", str(CONTEXT_FILE),
        *sys.argv[1:]
    ]

    # 3. Run container
    return subprocess.call(cmd)

if __name__ == "__main__":
    sys.exit(main())
