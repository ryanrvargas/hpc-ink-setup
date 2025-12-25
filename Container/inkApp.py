#!/usr/bin/env python3

import os
import sys
import subprocess
from pathlib import Path
import stat

# User-local paths for Inkly runtime and persistent state
HOME = Path.home()
INKLY_DIR = HOME / ".inkly"
COPILOT_STATE = INKLY_DIR / "copilot"
IMAGE = INKLY_DIR / "inkly1.sif"

# Create persistent Copilot token directory (host-side)
COPILOT_STATE.mkdir(parents=True, exist_ok=True)

# Restrict token access to the owning user only
os.chmod(COPILOT_STATE, stat.S_IRWXU)

# Fail early if the container image is missing
if not IMAGE.exists():
    print(f"Inkly container not found at: {IMAGE}", file=sys.stderr)
    print("Place inkly1.sif in ~/.inkly/", file=sys.stderr)
    sys.exit(1)

# Apptainer execution with full isolation and minimal persistence
cmd = [
    "apptainer", "exec",
    "--containall",
    "--cleanenv",
    "--no-home",
    "--writable-tmpfs",
    f"--bind={COPILOT_STATE}:/opt/inkhome/.config/.copilot",
    str(IMAGE),
    "ink",
]

# Pass user prompt directly to the ink entrypoint
cmd.extend(sys.argv[1:])

# Replace the current process with Apptainer
try:
    subprocess.execvp(cmd[0], cmd)
except FileNotFoundError:
    print("Apptainer not found in PATH.", file=sys.stderr)
    sys.exit(1)
