#!/usr/bin/env python3
# Inkly Run Time - applies Inkly-specific configurations to GitHub Copilot CLI
# before executing it. This includes loading guardrails, flags, and other settings.
# Reads from ~/.inkly/config.toml for settings.
import sys
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # Python <=3.10
from pathlib import Path
import subprocess

config_path = Path.home() / ".inkly" / "config.toml"

try:
    with config_path.open("rb") as f:
        config = tomllib.load(f)
except Exception as e:
    print(f"Inkly config error: {e}", file=sys.stderr)
    sys.exit(1)

# Build copilot command
cmd = ["copilot"]

if len(sys.argv) > 1:
    # Non-interactive prompt mode
    cmd += ["-p"] + sys.argv[1:]
# else: interactive mode (no flags)

# Exec copilot directly
try:
    subprocess.execvp("copilot", cmd)
except FileNotFoundError:
    print("Inkly error: 'copilot' not found on PATH", file=sys.stderr)
    sys.exit(1)