"""
Ink Core Runtime (importable)

This module contains the full runtime logic for Inkly.

Architectural Separation
------------------------
Inkly is intentionally split into two layers:

1) `ink` (CLI entrypoint)
   - Executable script
   - Extremely thin wrapper
   - Only calls `main()`

2) `ink_core` (this file)
   - Fully importable
   - Contains policy enforcement
   - Contains logging
   - Contains runtime orchestration

Import-Time vs Runtime Behavior
-------------------------------
This module must be safe to import in development and test environments.

That means:
- No filesystem assumptions at import time
- No required ~/.inkly installation at import time
- No SystemExit during import

All environment enforcement must happen inside `main()`.

Dev Mode vs Installed Mode
---------------------------
Inkly supports two execution contexts:

Dev/Test Mode:
- config.py is available in the repository root.
- ~/.inkly/lib may not exist.
- Unit tests import this module directly.

Installed Mode:
- config.py is copied to ~/.inkly/lib
- Runtime path is injected via bootstrap logic.
- CLI execution enforces installation guarantees.

This file must support both modes cleanly.
"""

import os
import textwrap
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List
import json
from datetime import datetime, timezone
import time
import argparse
import uuid
import hashlib
from inkly.config import TomlParser
from inkly.policy import (
    PolicyViolation,
    enforce_prompt_filter,
    enforce_deny_shell_commands,
    enforce_wrapper_policy,
    enforce_network_policy,
)
from inkly.intelligence.prompt_builder import maybe_inject_intelligence
from inkly.db import DEFAULT_DB_PATH
from inkly.jobs import refresh_jobs


## -----------------------------------------------------------------------------
# Bootstrap Path Configuration
# -----------------------------------------------------------------------------
# These paths represent the *installed* Inkly layout under ~/.inkly.
#
# In installed mode:
#   ~/.inkly/lib contains the runtime copy of config.py and other modules.
#
# In dev/test mode:
#   config.py is available in the repository root and no installation is required.
#
# The bootstrap guard determines which environment we are running in.
# -----------------------------------------------------------------------------

DEFAULT_INKLY_HOME = Path.home() / ".inkly"

CONFIG_PATH = DEFAULT_INKLY_HOME / "config.toml"
LIB_DIR = DEFAULT_INKLY_HOME / "lib"


# Bootstrap Import Guard
#
# Inkly must be fully installed before runtime execution.
# If the internal library directory is missing, fail fast
# to avoid undefined behavior or partial execution.
def ensure_bootstrap_import():
    """
    Ensure Inkly runtime dependencies are importable.

    This function resolves the dual-environment problem:

    1) Dev/Test Mode
       - `config.py` exists in repo root
       - No installation required
       - Do nothing

    2) Installed Mode
       - Runtime files live in ~/.inkly/lib
       - Must inject that directory into sys.path

    This function MUST only be called inside `main()`.
    It must never execute at module import time.
    """
    # If repo-root config.py is importable, we are in dev/test mode.
    try:
        import inkly.config as config  # noqa: F401

        return
    except Exception:
        pass

    # Otherwise fall back to installed layout under ~/.inkly/lib
    if LIB_DIR.exists():
        sys.path.insert(0, str(LIB_DIR))
        return

    raise SystemExit(
        f"Ink not initialized correctly. Missing {LIB_DIR}.\nPlease re-run install.py."
    )


__version__ = "0.1.0"
# Unique identifier for this Inkly execution.
# Used to correlate all log events generated during this run.
SESSION_ID = uuid.uuid4().hex  # unique session identifier, for logging each run


# Argument Parsing
def parse_args() -> argparse.Namespace:
    argv = sys.argv[1:]

    # Handle top-level flags that should work in either mode
    if "--version" in argv:
        parser = argparse.ArgumentParser(prog="ink")
        parser.add_argument("--version", action="version", version=f"ink {__version__}")
        parser.parse_args(["--version"])

    context_value = None
    cleaned_argv = []
    i = 0

    while i < len(argv):
        if argv[i] == "--context":
            if i + 1 >= len(argv):
                raise SystemExit("ink: error: --context requires a value")
            context_value = argv[i + 1]
            i += 2
        else:
            cleaned_argv.append(argv[i])
            i += 1

    # Structured command mode
    if cleaned_argv and cleaned_argv[0] == "jobs":
        parser = argparse.ArgumentParser(
            prog="ink",
            description=(
                "Ink is a cluster-aware AI assistant wrapper using GitHub Copilot CLI.\n"
                "It injects live HPC context into prompts and supports job intelligence tools."
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        parser.add_argument("--version", action="version", version=f"ink {__version__}")
        parser.add_argument(
            "--context", type=str, default=context_value, help=argparse.SUPPRESS
        )

        subparsers = parser.add_subparsers(dest="command", required=True)

        jobs_parser = subparsers.add_parser(
            "jobs", help="Structured job intelligence tools"
        )
        jobs_subparsers = jobs_parser.add_subparsers(dest="jobs_command", required=True)

        refresh_parser = jobs_subparsers.add_parser(
            "refresh",
            help="Refresh historical Slurm jobs from sacct into SQLite",
        )
        refresh_parser.add_argument(
            "--window-days",
            type=int,
            default=None,
            help="Override configured intelligence.window_days for this refresh",
        )

        jobs_subparsers.add_parser(
            "stats",
            help="Reserved for future job intelligence summary commands",
        )

        return parser.parse_args(argv)

    # Prompt mode
    return argparse.Namespace(
        command=None,
        jobs_command=None,
        window_days=None,
        context=context_value,
        prompt=cleaned_argv,
    )


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
    parser = TomlParser(CONFIG_PATH)  # creating object of TomlParser class,
    cfg = parser.load()  # turn static policy into runtime reality

    return (
        cfg,
        cfg.raw_config,
        cfg.state,
    )  # config: what is allowed , state: where those things live


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

    digest = hashlib.sha256(salt + username.encode("utf-8")).hexdigest()

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
def die(
    msg: str,
    code: int = 1,
    *,
    logging_cfg=None,
    state=None,
    event_type: str = "error",
    resolved_hostname: Optional[str] = None,
):
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
            resolved_hostname=resolved_hostname,
        )

    raise SystemExit(code)


# System Utilities
def command_exists(cmd: str) -> bool:
    """Return True if a command exists in PATH."""
    return shutil.which(cmd) is not None


def load_external_context(path: Path) -> Optional[dict]:
    """
    Load structured HPC context from JSON file.

    Used when Inkly is executed inside a container and
    host context has already been gathered.
    """
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(
            f"[ink] Failed to load external context from {path}: {e}", file=sys.stderr
        )
        return None


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


# Logging
def log_event(
    event_type: str,
    payload: dict,
    logging_cfg,
    state,
    *,
    resolved_hostname: Optional[str] = None,
):
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
        "session": build_session_context(state, resolved_hostname=resolved_hostname),
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
        dst = Path(str(log_path) + f".{i + 1}")
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


def build_session_context(state, resolved_hostname: Optional[str] = None) -> dict:
    """
    Build a minimal session context for structured logging.

    Includes a stable user hash, host name, PID, and session id.
    """
    host_value = resolved_hostname or os.uname().nodename

    return {
        "session_id": SESSION_ID,
        "user_id": get_user_hash(state),
        "host": host_value,
        "pid": os.getpid(),
    }


def gather_inline_context() -> List[str]:
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
            gpu = run_capture(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader",
                ]
            )
            if gpu:
                ctx.append(f"GPU: {gpu.splitlines()[0]}")

    return ctx


def build_context_block_from_json(data: dict) -> str:
    """
    Convert structured JSON context into formatted prompt block.
    """
    lines: List[str] = []

    host = data.get("host", {})
    if host.get("hostname"):
        lines.append(f"Hostname: {host['hostname']}")
    if host.get("os"):
        lines.append(f"OS: {host['os']}")

    slurm = data.get("slurm", {})
    if slurm.get("present"):
        lines.append("SLURM Queues (top):")
        for line in slurm.get("summary", [])[:3]:
            lines.append(f"  {line}")

    gpu = data.get("gpu", {})
    if gpu.get("present"):
        for line in gpu.get("summary", [])[:1]:
            lines.append(f"GPU: {line}")

    return "\n".join(lines)


def resolve_context_block(args) -> str:
    if getattr(args, "context", None):
        external = load_external_context(Path(args.context))
        if external:
            return build_context_block_from_json(external)

    inline_ctx = gather_inline_context()
    return "\n".join(inline_ctx)


def print_refresh_summary(summary) -> None:
    print("Inkly Job Intelligence Refresh")
    print()
    print(f"Jobs scanned:  {summary.jobs_scanned:,}")
    print(f"Jobs inserted: {summary.jobs_inserted:,}")
    print(f"Existing jobs upserted:  {summary.jobs_updated:,}")
    if summary.jobs_removed:
        print(f"Jobs removed:  {summary.jobs_removed:,}")
    print(f"Window:        {summary.window_days} days")
    print()
    print("Database updated successfully.")


def main() -> int:
    """
    Inkly entrypoint.

    Loads config, enforces policy, gathers HPC context, and either
    runs Copilot once (prompt mode) or launches interactive mode.
    """
    ensure_bootstrap_import()  # ensure that we can import from the internal library, fail fast if not

    # Parse CLI arguments early to decide prompt vs. interactive mode
    args = parse_args()
    user_prompt = ""

    resolved_hostname = None

    if getattr(args, "context", None):
        external = load_external_context(Path(args.context))
        if external:
            resolved_hostname = external.get("host", {}).get("hostname")

    try:
        # Load validated policy/config and state paths
        cfg, config, state = load_config_and_state()

    except Exception as e:
        # Fail fast with a structured error if config cannot be loaded
        print(f"Inkly config error: {e}", file=sys.stderr)
        raise SystemExit(1)

    # Start session logging (includes session id + environment context)
    log_event(
        event_type="session_start",
        payload={
            "ink_version": __version__,
            "logging_enabled": True,
        },
        logging_cfg=cfg.logging,
        state=state,
        resolved_hostname=resolved_hostname,
    )
    # PRIVACY NOTICE — raw prompt logging opt-in
    if cfg.logging.log_raw_prompts:
        log_event(
            event_type="privacy_notice",
            payload={
                "raw_prompt_logging": True,
                "message": "Raw user prompts are being logged in plaintext.",
            },
            logging_cfg=cfg.logging,
            state=state,
            resolved_hostname=resolved_hostname,
        )

    if args.command == "jobs":
        if args.jobs_command == "refresh":
            window_days = (
                args.window_days
                if args.window_days is not None
                else cfg.intelligence.window_days
            )

            try:
                summary = refresh_jobs(window_days=window_days)
            except Exception as e:
                print(f"Inkly job refresh failed: {e}", file=sys.stderr)
                return 1

            print_refresh_summary(summary)
            return 0

        if args.jobs_command == "stats":
            print("ink jobs stats is not implemented yet.", file=sys.stderr)
            return 1

    # Pre-flight runtime checks
    enforce_wrapper_policy(config, state=state, logging_cfg=cfg.logging)
    enforce_network_policy(config)

    if args.prompt:
        user_prompt = " ".join(args.prompt)

        # HARD enforcement gates (order does not matter, but must be before Copilot)
        try:
            enforce_prompt_filter(
                user_prompt, config, state=state, logging_cfg=cfg.logging
            )
            enforce_deny_shell_commands(
                user_prompt, config, state=state, logging_cfg=cfg.logging
            )
        except PolicyViolation as e:
            die(
                str(e),
                logging_cfg=cfg.logging,
                state=state,
                resolved_hostname=resolved_hostname,
            )

    # Build Copilot command
    cmd = ["copilot"]
    # Safe to log now — prompt passed all guardrails
    if args.prompt:
        # Determine context source
        context_block = resolve_context_block(args)

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
            resolved_hostname=resolved_hostname,
        )

        BASE_PROMPT = textwrap.dedent("""
            You are Inkly, an HPC assistant.

            STRICT RULES:
            - TEXT ONLY.
            - No file creation.
            - No path suggestions.
            - Output must contain:
            1) Complete code block
            2) Short numbered instructions
            """)

        full_prompt = (
            BASE_PROMPT + "\n\n"
            "Respond in the following exact format:\n\n"
            "=== CODE START ===\n"
            "<complete code here>\n"
            "=== CODE END ===\n\n"
            "=== INSTRUCTIONS ===\n"
            "1. Step one\n"
            "2. Step two\n"
            "3. Step three\n"
            "And so on... if needed\n"
            "=== END ===\n\n"
            "Cluster Context:\n"
            f"{context_block}\n\n"
            f"Task:\n{user_prompt}\n"
        )

        if cfg.intelligence.enabled and cfg.intelligence.auto_refresh:
            try:
                refresh_jobs(window_days=cfg.intelligence.window_days)
            except Exception as e:
                print(f"[ink] Intelligence auto-refresh failed: {e}", file=sys.stderr)

        enrich_start = time.perf_counter()

        intelligence_result = maybe_inject_intelligence(
            full_prompt,
            cfg,
            str(DEFAULT_DB_PATH),
        )

        enrich_ms = (time.perf_counter() - enrich_start) * 1000
        print(f"[ink][perf] prompt_enrichment: {enrich_ms:.2f} ms", file=sys.stderr)

        full_prompt = intelligence_result.prompt

        if intelligence_result.message:
            print(f"[ink] {intelligence_result.message}", file=sys.stderr)
            log_event(
                event_type="intelligence_guard",
                payload={
                    "dataset_size": intelligence_result.dataset_size,
                    "min_jobs_required": cfg.intelligence.min_jobs_required,
                    "message": intelligence_result.message,
                },
                logging_cfg=cfg.logging,
                state=state,
                resolved_hostname=resolved_hostname,
            )

        if intelligence_result.injected:
            payload = {
                "dataset_size": intelligence_result.dataset_size,
                "prompt_enrichment_ms": round(enrich_ms, 2),
            }

            if intelligence_result.timings:
                payload.update(intelligence_result.timings)

            log_event(
                event_type="intelligence_performance",
                payload=payload,
                logging_cfg=cfg.logging,
                state=state,
                resolved_hostname=resolved_hostname,
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
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
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
            resolved_hostname=resolved_hostname,
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
            resolved_hostname=resolved_hostname,
        )

        print(assistant_output)
        return result.returncode

    else:
        # In interactive mode, launch Copilot CLI directly
        return subprocess.call(cmd)
