#!/usr/bin/env python3
# Inkly Run Time - applies Inkly-specific configurations to GitHub Copilot CLI
# before executing it. This includes loading guardrails, flags, and other settings.
# Reads from ~/.inkly/config.toml for settings.
import sys
import tomllib
from pathlib import Path
import subprocess

config_path = Path.home() / ".inkly" / "config.toml"

try:
    with config_path.open("rb") as f:
        config = tomllib.load(f)
except Exception as e:
    print(f"Inkly config error: {e}", file=sys.stderr)
    sys.exit(1)

# apply guardrails, flags, etc. Later we can expand this to do more.
subprocess.execvp("copilot", "-p" + sys.argv[1:])
