#!/usr/bin/env python3
"""
Ink: Cluster-aware Inkly runtime + launcher
- ink (cluster context + prompt injection)

This module is the primary runtime entrypoint for Inkly.
It coordinates configuration loading, policy enforcement,
HPC context discovery, Copilot invocation, and structured logging.

This file enforces policy.
It does not define policy.
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
import uuid
import hashlib

# Bootstrap Paths
#
# These paths are used ONLY during startup to locate Inkly’s
# configuration and internal libraries.
#
# After config parsing, all authoritative paths must come
# from StateConfig to avoid accidental filesystem misuse.
DEFAULT_INKLY_HOME = Path.home() / ".inkly"
CONFIG_PATH = DEFAULT_INKLY_HOME / "config.toml"
LIB_DIR = DEFAULT_INKLY_HOME / "lib"

# Bootstrap Import Guard
#
# Inkly must be fully installed before runtime execution.
# If the internal library directory is missing, fail fast
# to avoid undefined behavior or partial execution.
if LIB_DIR.exists():
    sys.path.insert(0, str(LIB_DIR))
else:
    raise SystemExit(
        f"Ink not initialized correctly. Missing {LIB_DIR}.\n"
        "Please re-run install.py."
    )

# Internal Imports
#
# config.py lives inside Inkly’s private runtime library.
# It is responsible for parsing TOML policy and producing
# validated runtime configuration objects.
from config import TomlParser

__version__ = "0.1.0"
# Unique identifier for this Inkly execution.
# Used to correlate all log events generated during this run.
SESSION_ID = uuid.uuid4().hex # unique session identifier, for logging each run

# TOML Compatibility
#
# Python version on HPC systems varies widely.
# Prefer stdlib tomllib when available, otherwise fall back.
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # Python <=3.10 in most cases this is used on HPC

# Argument Parsing
def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for Inkly.

    Inkly supports two execution modes:
    - Prompt mode: a prompt is provided and executed once
    - Interactive mode: Copilot CLI is launched directly

    Returns:
        argparse.Namespace: Parsed runtime arguments.
    """
    parser = argparse.ArgumentParser(
        prog="ink",
        usage="ink \"[prompt]\"",
        description=(
            "Ink is a cluster-aware AI assistant wrapper using GitHub Copilot CLI.\n"
            "It injects live HPC context (Slurm, GPUs, OS, queues) into prompts\n"
            "and enforces safety guardrails before execution."
        ),
        epilog=(
            "Examples:\n"
            "  ink \"Generate a Slurm sbatch for 2 GPUs for 24 hours\"\n"
            "  ink \"Why did my job get stuck in PD state?\"\n"
            "  ink            # start interactive Copilot session\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Runtime prompt handling
    runtime = parser.add_argument_group("runtime options")
    runtime.add_argument(
        "prompt",
        nargs=argparse.REMAINDER,
        help="Prompt to send to Copilot (to start interactive mode type ink without arguments)",
    )

    # Metadata / informational flags
    meta = parser.add_argument_group("meta")
    meta.add_argument(
        "--version",
        action="version",
        version=f"ink {__version__}"
    )

    return parser.parse_args()

# Configuration & State Loading
def load_config_and_state() -> tuple[object, dict, object]:
    """
    Load and validate Inkly configuration.

    This function performs the transition from static policy
    (config.toml) to runtime-enforced objects.

    Downstream code must trust:
    - cfg: what is allowed
    - state: where things live
    - raw_config: original policy (inspection only)

    Returns:
        tuple: (InklyConfig, raw_config dict, StateConfig)
    """
    parser = TomlParser(CONFIG_PATH) # creating object of TomlParser class, 
    cfg = parser.load() # turn static policy into runtime reality

    return cfg, cfg.raw_config, cfg.state # config: what is allowed , state: where those things live

# Logging Identity & Privacy
def get_or_create_logging_salt(state) -> bytes:
    """
    Retrieve or generate a persistent logging salt.

    The salt enables stable, anonymized per-user hashing
    without storing usernames in logs.
    """
    salt_path = state.inkly_home / "logging_salt"

    if salt_path.exists():
        return salt_path.read_bytes()

    salt = os.urandom(32)
    state.inkly_home.mkdir(parents=True, exist_ok=True)
    salt_path.write_bytes(salt)

    try:
        os.chmod(salt_path, 0o600)
    except PermissionError:
        pass

    return salt

def get_user_hash(state) -> str:
    """
    Return a stable, anonymized user identifier.

    This hash is consistent per user but not reversible.
    """
    username = os.environ.get("USER", "unknown")
    salt = get_or_create_logging_salt(state)

    digest = hashlib.sha256(
        salt + username.encode("utf-8")
    ).hexdigest()

    return digest[:16]

def get_event_log_path(logging_cfg, state) -> Path:
    """
    Determine the correct event log path based on policy.

    Supports per-user isolation or global aggregation.
    """
    base = state.log_dir

    if logging_cfg.per_user_logs:
        user_hash = get_user_hash(state)
        return base / "users" / user_hash / "events.jsonl"

    return base / "events.jsonl"

# Fatal Error Handling
def die(msg: str, code: int = 1, *, logging_cfg=None, state=None, event_type: str = "error"):
    """
    Terminate execution with optional structured logging.

    All unrecoverable errors should funnel through this
    function to ensure consistent logging behavior.
    """
    print(msg, file=sys.stderr)

    if logging_cfg and state:
        log_event(
            event_type=event_type,
            payload={
                "message": msg,
                "fatal": True,
            },
            logging_cfg=logging_cfg,
            state=state,
        )

    raise SystemExit(code)

# System Utilities
def command_exists(cmd: str) -> bool:
    """Return True if a command exists in PATH."""
    return shutil.which(cmd) is not None

# Run a command and capture stdout, return None or stdout string
def run_capture(cmd: List[str]) -> Optional[str]:
    """
    Execute a command and capture stdout only.

    Used for environment probing. Errors are intentionally
    suppressed to avoid noisy output.
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

# Policy Enforcement    
# Policy level semantics restrictions on what users are allowed to ask
def enforce_prompt_filter(user_prompt: str, config: dict, *, state, logging_cfg):
    """
    Enforce prompt-level intent restrictions.

    Blocks disallowed keywords or patterns before any
    tool-level execution occurs.
    """
    pf = config.get("prompt_filter", {}) # 
    if not pf.get("enabled", False):
        return  # filtering disabled, allow everything

    text = user_prompt
    if pf.get("case_insensitive", False):
        text = text.lower()

    # Keyword blocking
    for kw in pf.get("blocked_keywords", []): # return list of keywords
        check_kw = kw.lower() if pf.get("case_insensitive", False) else kw
        # .escape turns userspecified keyword into literal match. \b is word boundary, so the key word is a standalone word
        if re.search(rf"\b{re.escape(check_kw)}\b", text):
            # If any blocked keyword is found, die with policy block message
            die(
                "Blocked by policy",
                logging_cfg=logging_cfg,
                state=state,
            )

    # Regex blocking
    for pattern in pf.get("blocked_regex", []):
        flags = re.IGNORECASE if pf.get("case_insensitive", False) else 0
        if re.search(pattern, user_prompt, flags):
            die(
                "Blocked by policy",
                logging_cfg=logging_cfg,
                state=state,
            )

def enforce_deny_shell_commands(user_prompt: str, config: dict, *, state, logging_cfg): # * forces callers to pass state as keyword argument
    """
    Enforce hard denial of dangerous shell commands.

    This layer prevents filesystem destruction or
    privilege escalation regardless of intent.
    """
    guardrails = config.get("copilot", {}).get("guardrails", {}) # get copilot/guardrails section of config into a dict
    rules = guardrails.get("deny_shell_commands", []) # find deny_shell_commands keyword, return list of rules, emypty list if missing

    if not rules:
        return  # nothing to enforce, exit function

    text = user_prompt.strip()

    for rule in rules:
        # Format: "rm:*", "sudo:*"
        cmd = rule.split(":", 1)[0] # everything before the first colon is kept

        # Very intentional: shell-like word boundary
        if re.search(rf"\b{re.escape(cmd)}\b", text):
            die(
                f"Blocked by policy: shell command '{cmd}'",
                logging_cfg=logging_cfg,
                state=state,
            )

def enforce_wrapper_policy(config: dict, *, state, logging_cfg):
    """
    Enforce wrapper-level runtime requirements.

    Validates authentication and required tooling
    before invoking Copilot.
    """
    wrapper = config.get("wrapper", {})

    if wrapper.get("require_login", False):
        if not os.environ.get("COPILOT_AUTHENTICATED"):
            die(
                "Copilot login required by policy",
                logging_cfg=logging_cfg,
                state=state,
            )

    if wrapper.get("fail_on_missing_copilot", True):
        if not shutil.which("copilot"):
            die(
                "Copilot CLI not found (required by policy)",
                logging_cfg=logging_cfg,
                state=state,
            )

def enforce_network_policy(config: dict):
    """
    Apply network access constraints.

    Signals downstream tools when outbound
    network access is prohibited.
    """
    net = config.get("network", {})
    if not net.get("require_internet", True):
        os.environ["NO_NETWORK"] = "1"

# Logging
def log_event(event_type: str, payload: dict, logging_cfg, state):
    """
    Append a structured event to the Inkly event log.

    Events are append-only, schema-versioned,
    and suitable for audit or research analysis.
    """
    if not logging_cfg.enabled:
        return
    if event_type == "user_prompt" and not logging_cfg.log_user_prompts:
        return

    if event_type == "ai_response" and not logging_cfg.log_ai_responses:
        return

    if event_type == "job_outcome" and not logging_cfg.log_job_outcomes:
        return
    
    log_path = get_event_log_path(logging_cfg, state)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if logging_cfg.per_user_logs:
        ensure_secure_dir(state.log_dir / "users")
        ensure_secure_dir(log_path.parent)
    else:
        ensure_secure_dir(log_path.parent)

    rotate_logs_if_needed(log_path, logging_cfg)
    
    event = {
        "schema_version": logging_cfg.schema_version,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session": build_session_context(state),
        "payload": payload,
    }

    with log_path.open("a") as f:
        f.write(json.dumps(event) + "\n")

    ensure_secure_file(log_path)

def should_log_raw_prompts(logging_cfg) -> bool:
    """Return True if raw prompt logging is enabled by policy."""
    return getattr(logging_cfg, "log_raw_prompts", False)

def rotate_logs_if_needed(log_path: Path, logging_cfg):
    """
    Rotate log files when size limits are exceeded.

    Oldest logs are discarded first to bound disk usage.
    """
    if not log_path.exists():
        return
    if log_path.stat().st_size <= logging_cfg.max_bytes:
        return

    # Remove the oldest rotated file
    oldest = Path(str(log_path) + f".{logging_cfg.max_log_files}")
    if oldest.exists():
        oldest.unlink()

    # Shift existing rotated logs
    for i in range(logging_cfg.max_log_files - 1, 0, -1):
        src = Path(str(log_path) + f".{i}")
        dst = Path(str(log_path) + f".{i+1}")
        if src.exists():
            src.rename(dst)

    # Rotate current log
    rotated = Path(str(log_path) + ".1")
    log_path.rename(rotated)

def ensure_secure_dir(path: Path):
    """
    Set directory permissions to be accessible only by the owner.

    This helps protect sensitive log data from unauthorized access.
    """
    try:
        os.chmod(path, 0o700)
    except PermissionError:
        pass

def ensure_secure_file(path: Path):
    """
    Set file permissions to be accessible only by the owner.

    This helps protect sensitive log data from unauthorized access.
    """
    try:
        os.chmod(path, 0o600)
    except PermissionError:
        pass

def debug_dump_prompt(prompt: str, config: dict):
    """
    Emit the full prompt to stderr when debug mode is enabled.

    This is controlled by `wrapper.debug_prompt` in the config and
    is intended for local inspection only.
    """
    wrapper = config.get("wrapper", {})
    if not wrapper.get("debug_prompt", False):
        return

    print("\n===== INK DEBUG PROMPT BEGIN =====", file=sys.stderr)
    print(prompt, file=sys.stderr)
    print("===== INK DEBUG PROMPT END =====\n", file=sys.stderr)

def build_session_context(state) -> dict:
    """
    Build a minimal session context for structured logging.

    Includes a stable user hash, host name, PID, and session id.
    """
    return {
        "session_id": SESSION_ID,
        "user_id": get_user_hash(state),
        "host": os.uname().nodename,
        "pid": os.getpid(),
    }

def main() -> int:
    """
    Inkly entrypoint.

    Loads config, enforces policy, gathers HPC context, and either
    runs Copilot once (prompt mode) or launches interactive mode.
    """
    # Parse CLI arguments early to decide prompt vs. interactive mode
    args = parse_args()
    user_prompt = ""

    try:
        # Load validated policy/config and state paths
        cfg, config, state = load_config_and_state()
        # Ensure Copilot uses Inkly-managed config dir
        os.environ.setdefault(
            "COPILOT_CONFIG_DIR",
            str(state.copilot_config_dir)
        )
    except Exception as e:
        # Fail fast with a structured error if config cannot be loaded
        die(
            f"Inkly config error: {e}"
        )
    # Start session logging (includes session id + environment context)
    log_event(
        event_type="session_start",
        payload={
            "ink_version": __version__,
            "logging_enabled": True,
        },
        logging_cfg=cfg.logging,
        state=state,
    )
    # PRIVACY NOTICE — raw prompt logging opt-in
    if cfg.logging.log_raw_prompts:
        log_event(
            event_type="privacy_notice",
            payload={
                "raw_prompt_logging": True,
                "message": "Raw user prompts are being logged in plaintext."
            },
            logging_cfg=cfg.logging,
            state=state,
        )

    # Pre-flight runtime checks
    enforce_wrapper_policy(config, state=state, logging_cfg=cfg.logging)
    enforce_network_policy(config)

    # Gather HPC context
    ctx: List[str] = []

    if command_exists("hostname"):
        hostname = run_capture(["hostname"])
        if hostname:
            # Record hostname for cluster context
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
        enforce_prompt_filter(user_prompt, config, state=state, logging_cfg=cfg.logging)
        enforce_deny_shell_commands(user_prompt, config, state=state, logging_cfg=cfg.logging)

        # Safe to log now — prompt passed all guardrails
        payload = {
            "length": len(user_prompt),
            "prompt_hash": hashlib.sha256(user_prompt.encode("utf-8")).hexdigest(),
        }

        if should_log_raw_prompts(cfg.logging):
            payload["prompt"] = user_prompt

        log_event(
            event_type="user_prompt",
            payload=payload,
            logging_cfg=cfg.logging,
            state=state,
        )
        context_block = "\n".join(ctx)

        full_prompt = (
            "Using the following HPC environment context:\n"
            f"{context_block}\n\n"
            f"Now: {user_prompt}"
        )

        debug_dump_prompt(full_prompt, config)
        cmd += ["-p", full_prompt]
    # else: interactive mode (no flags)

    # Exec Copilot (final)
    if user_prompt:
        # In prompt mode, build a single-shot invocation
        # (actual execution logic follows below)
        t0 = datetime.now(timezone.utc)

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        t1 = datetime.now(timezone.utc)
        duration_ms = int((t1 - t0).total_seconds() * 1000)

        assistant_output = result.stdout.strip()

        log_event(
            event_type="ai_response",
            payload={
                "response_length": len(assistant_output),
            },
            logging_cfg=cfg.logging,
            state=state,
        )

        log_event(
            event_type="copilot_exit",
            payload={
                "returncode": result.returncode,
                "stdout_len": len(result.stdout or ""),
                "stderr_len": len(result.stderr or ""),
                "duration_ms": duration_ms,
            },
            logging_cfg=cfg.logging,
            state=state,
        )

        print(assistant_output)
        return result.returncode

    else:
        # In interactive mode, launch Copilot CLI directly
        return subprocess.call(cmd)
    

if __name__ == "__main__":
    sys.exit(main())