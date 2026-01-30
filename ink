#!/usr/bin/env python3
"""
Ink: Cluster-aware Inkly runtime + launcher

Combines:
- ink (cluster context + prompt injection)
- inkly-runtime.py (config, guardrails, Copilot exec)
"""

import re
import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List
import json
from datetime import datetime, timezone
import argparse


try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # Python <=3.10

# Utilities
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ink",
        description="Ink: Cluster-aware Inkly runtime + launcher"
    )

    parser.add_argument(
        "prompt",
        nargs=argparse.REMAINDER,
        help="Prompt to send to Copilot"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="ink 0.1.0"
    )

    return parser.parse_args()

def die(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    raise SystemExit(code)

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

def enforce_prompt_filter(user_prompt: str, config: dict):
    pf = config.get("prompt_filter", {})
    if not pf.get("enabled", False):
        return  # filtering disabled, allow everything

    text = user_prompt
    if pf.get("case_insensitive", False):
        text = text.lower()

    # Keyword blocking
    for kw in pf.get("blocked_keywords", []):
        check_kw = kw.lower() if pf.get("case_insensitive", False) else kw
        if re.search(rf"\b{re.escape(check_kw)}\b", text):
            die(f"Blocked by policy: keyword '{kw}'")

    # Regex blocking
    for pattern in pf.get("blocked_regex", []):
        flags = re.IGNORECASE if pf.get("case_insensitive", False) else 0
        if re.search(pattern, user_prompt, flags):
            die(f"Blocked by policy: pattern '{pattern}'")

def enforce_deny_shell_commands(user_prompt: str, config: dict):
    guardrails = config.get("copilot", {}).get("guardrails", {})
    rules = guardrails.get("deny_shell_commands", [])

    if not rules:
        return  # nothing to enforce

    text = user_prompt.strip()

    for rule in rules:
        # Format: "rm:*", "sudo:*"
        cmd = rule.split(":", 1)[0]

        # Very intentional: shell-like word boundary
        if re.search(rf"\b{re.escape(cmd)}\b", text):
            die(f"Blocked by policy: shell command '{cmd}'")

def enforce_wrapper_policy(config: dict):
    wrapper = config.get("wrapper", {})

    if wrapper.get("require_login", False):
        if not os.environ.get("COPILOT_AUTHENTICATED"):
            die("Copilot login required by policy")

    if wrapper.get("fail_on_missing_copilot", True):
        if not shutil.which("copilot"):
            die("Copilot CLI not found (required by policy)")

def enforce_network_policy(config: dict):
    net = config.get("network", {})
    if not net.get("require_internet", True):
        os.environ["NO_NETWORK"] = "1"

def append_turn(config: dict, user: str, assistant: str):
    logging_cfg = config.get("logging", {})
    if not logging_cfg.get("enabled", False):
        return

    max_turns = logging_cfg.get("max_turns")

    state = config.get("state", {})
    log_dir_value = state.get("log_dir")
    if not log_dir_value:
        return

    log_dir = Path(os.path.expanduser(log_dir_value))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / "turns.jsonl"

    turn = {
        "id": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "assistant": assistant,
        "cwd": os.getcwd(),
        "hostname": os.uname().nodename,
    }

    # append
    with log_path.open("a") as f:
        f.write(json.dumps(turn) + "\n")

    # truncate
    if isinstance(max_turns, int) and max_turns > 0:
        lines = log_path.read_text().splitlines()
        if len(lines) > max_turns:
            log_path.write_text("\n".join(lines[-max_turns:]) + "\n")

def load_turn_history(config: dict) -> List[dict]:
    logging_cfg = config.get("logging", {})
    if not logging_cfg.get("enabled", False):
        return []

    state = config.get("state", {})
    log_dir_value = state.get("log_dir")
    if not log_dir_value:
        return []

    log_path = Path(os.path.expanduser(log_dir_value)) / "turns.jsonl"
    if not log_path.exists():
        return []

    turns = []
    for line in log_path.read_text().splitlines():
        try:
            turns.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return turns


def debug_dump_prompt(prompt: str, config: dict):
    wrapper = config.get("wrapper", {})
    if not wrapper.get("debug_prompt", False):
        return

    print("\n===== INK DEBUG PROMPT BEGIN =====", file=sys.stderr)
    print(prompt, file=sys.stderr)
    print("===== INK DEBUG PROMPT END =====\n", file=sys.stderr)


def main() -> int:
    args = parse_args()
    user_prompt = ""

    try:
        with CONFIG_PATH.open("rb") as f:
            config = tomllib.load(f)
    except Exception as e:
        die(f"Inkly config error: {e}")

    # Pre-flight runtime checks
    enforce_wrapper_policy(config)
    enforce_network_policy(config)

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

    if args.prompt:
        user_prompt = " ".join(args.prompt)

        # HARD enforcement gates (order does not matter, but must be before Copilot)
        enforce_prompt_filter(user_prompt, config)
        enforce_deny_shell_commands(user_prompt, config)

        context_block = "\n".join(ctx)
        turns = load_turn_history(config)

        history_block = ""
        if turns:
            history_block = "Conversation history:\n"
            for t in turns:
                history_block += f"USER: {t['user']}\n"
                history_block += f"ASSISTANT: {t['assistant']}\n\n"

        full_prompt = (
            "Using the following HPC environment context:\n"
            f"{context_block}\n\n"
            f"{history_block}"
            f"Now: {user_prompt}"
        )

        debug_dump_prompt(full_prompt, config)
        cmd += ["-p", full_prompt]
    # else: interactive mode (no flags)

    # Exec Copilot (final)
    try:
        result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
        )

        assistant_output = result.stdout.strip()
    
        if user_prompt:
            append_turn(config, user_prompt, assistant_output)

        print(assistant_output)
        return result.returncode
    except FileNotFoundError:
        die("Inkly error: 'copilot' not found on PATH")
    

if __name__ == "__main__":
    sys.exit(main())