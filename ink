#!/usr/bin/env python3
"""
Ink: Cluster-aware Inkly runtime + launcher
- ink (cluster context + prompt injection)
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

# Bootstrap-only location used to find config.toml
# All real paths come from StateConfig after parsing
DEFAULT_INKLY_HOME = Path.home() / ".inkly"
CONFIG_PATH = DEFAULT_INKLY_HOME / "config.toml"
LIB_DIR = DEFAULT_INKLY_HOME / "lib"

# Ensure lib directory is on sys.path
if LIB_DIR.exists():
    sys.path.insert(0, str(LIB_DIR))
else:
    raise SystemExit(
        f"Ink not initialized correctly. Missing {LIB_DIR}.\n"
        "Please re-run install.py."
    )

# Internal imports, config.py lives in LIB_DIR
from config import TomlParser

__version__ = "0.1.0"
SESSION_ID = uuid.uuid4().hex # unique session identifier, for logging each run

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # Python <=3.10 in most cases this is used on HPC

# Utilities
def parse_args() -> argparse.Namespace:
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

    runtime = parser.add_argument_group("runtime options")
    runtime.add_argument(
        "prompt",
        nargs=argparse.REMAINDER,
        help="Prompt to send to Copilot (to start interactive mode type ink without arguments)",
    )

    meta = parser.add_argument_group("meta")
    meta.add_argument(
        "--version",
        action="version",
        version=f"ink {__version__}"
    )

    return parser.parse_args()

# Compute path, parse config file, and everything downstream trust state and config
def load_config_and_state() -> tuple[object, dict, object]:
    parser = TomlParser(CONFIG_PATH) # creating object of TomlParser class, 
    cfg = parser.load() # turn static policy into runtime reality
    #cfg.raw_policy = policy, based off of users wants, answers questions like "is prompt filtering enabled"
    #cfg.state = runtime-resolved paths etc, like where do logs go, where is coplit stored

    return cfg, cfg.raw_config, cfg.state # config: what is allowed , state: where those things live

def get_or_create_logging_salt(state) -> bytes:
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
    username = os.environ.get("USER", "unknown")
    salt = get_or_create_logging_salt(state)

    digest = hashlib.sha256(
        salt + username.encode("utf-8")
    ).hexdigest()

    return digest[:16]

def get_event_log_path(logging_cfg, state) -> Path:
    base = state.log_dir

    if logging_cfg.per_user_logs:
        user_hash = get_user_hash(state)
        return base / "users" / user_hash / "events.jsonl"

    return base / "events.jsonl"

# Error handling
def die(msg: str, code: int = 1, *, logging_cfg=None, state=None, event_type: str = "error"):
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

def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None

# Run a command and capture stdout, return None or stdout string
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
    
# Policy level semantics restrictions on what users are allowed to ask
def enforce_prompt_filter(user_prompt: str, config: dict, *, state, logging_cfg):
    # Prompt filtering
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
    net = config.get("network", {})
    if not net.get("require_internet", True):
        os.environ["NO_NETWORK"] = "1"

# # Logging functions, including turn history
# def append_turn(config: dict, state, user: str, assistant: str):
#     # Append a turn to the turn history log, enforcing max_turns
#     logging_cfg = config.get("logging", {})
#     if not logging_cfg.get("enabled", False):
#         return

#     max_turns = logging_cfg.get("max_turns")

#     # Ensure log directory exists
#     log_dir = state.log_dir
#     log_dir.mkdir(parents=True, exist_ok=True)

#     log_path = log_dir / "turns.jsonl"

#     turn = {
#         "id": datetime.now(timezone.utc).isoformat(),
#         "user": user,
#         "assistant": assistant,
#         "cwd": os.getcwd(),
#         "hostname": os.uname().nodename,
#     }

#     # append
#     with log_path.open("a") as f:
#         f.write(json.dumps(turn) + "\n")

#     # truncate
#     if isinstance(max_turns, int) and max_turns > 0:
#         lines = log_path.read_text().splitlines()
#         if len(lines) > max_turns:
#             log_path.write_text("\n".join(lines[-max_turns:]) + "\n")

def log_event(event_type: str, payload: dict, logging_cfg, state):
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
    return getattr(logging_cfg, "log_raw_prompts", False)

def rotate_logs_if_needed(log_path: Path, logging_cfg):
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
    try:
        os.chmod(path, 0o700)
    except PermissionError:
        pass

def ensure_secure_file(path: Path):
    try:
        os.chmod(path, 0o600)
    except PermissionError:
        pass

# def load_turn_history(config: dict, state) -> List[dict]:
#     logging_cfg = config.get("logging", {})
#     if not logging_cfg.get("enabled", False):
#         return []

#     log_path = state.log_dir / "turns.jsonl"
#     if not log_path.exists():
#         return []

#     turns = []
#     for line in log_path.read_text().splitlines():
#         try:
#             turns.append(json.loads(line))
#         except json.JSONDecodeError:
#             continue
#     return turns

def debug_dump_prompt(prompt: str, config: dict):
    wrapper = config.get("wrapper", {})
    if not wrapper.get("debug_prompt", False):
        return

    print("\n===== INK DEBUG PROMPT BEGIN =====", file=sys.stderr)
    print(prompt, file=sys.stderr)
    print("===== INK DEBUG PROMPT END =====\n", file=sys.stderr)

def build_session_context(state) -> dict:
    return {
        "session_id": SESSION_ID,
        "user_id": get_user_hash(state),
        "host": os.uname().nodename,
        "pid": os.getpid(),
    }

def main() -> int:
    args = parse_args()
    user_prompt = ""

    try:
        cfg, config, state = load_config_and_state()
        os.environ.setdefault(
            "COPILOT_CONFIG_DIR",
            str(state.copilot_config_dir)
        )
    except Exception as e:
        die(
            f"Inkly config error: {e}"
        )
    
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
        # turns = load_turn_history(config, state)

        # history_block = ""
        # if turns:
        #     history_block = "Conversation history:\n"
        #     for t in turns:
        #         history_block += f"USER: {t['user']}\n"
        #         history_block += f"ASSISTANT: {t['assistant']}\n\n"

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
        # Interactive mode: attach to real TTY
        return subprocess.call(cmd)
    

if __name__ == "__main__":
    sys.exit(main())