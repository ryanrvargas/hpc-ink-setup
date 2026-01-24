#!/usr/bin/env python3

import os
import subprocess
import shutil
from pathlib import Path

# Path and environment setup :)

HOME = Path.home()

INKLY_HOME = HOME / ".inkly"  # Persistent Inkly state directory
COPILOT_STATE = INKLY_HOME / "copilot"  # Copilot config + auth storage

NVM_DIR = HOME / ".nvm"  # User-space nvm install location
NPM_GLOBAL = HOME / ".npm-global"  # User-space npm prefix
BIN_DIR = NPM_GLOBAL / "bin"  # Location for ink / inkly wrappers

BASHRC = HOME / ".bashrc"  # Shell persistence target


def run(cmd, check=True, shell=False):
    # Execute a command and fail fast on errors
    print(f"->{cmd}")
    subprocess.run(cmd, check=check, shell=shell)


def command_exists(cmd):
    # Check if a command is available on PATH
    return shutil.which(cmd) is not None


def ensure_dirs():
    # Create all persistent directories required by Inkly
    COPILOT_STATE.mkdir(parents=True, exist_ok=True)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    (INKLY_HOME / "bin").mkdir(parents=True, exist_ok=True)


def ensure_nvm_and_node():
    # If Node already exists, do nothing
    # Check for node via nvm instead of Python PATH
    try:
        run_with_nvm("node -v")
        return
    except subprocess.CalledProcessError:
        pass

    # Node missing -> install via nvm
    print("Node not found. Installing via nvm.")

    if not NVM_DIR.exists():
        # Install nvm only if it is not already present
        if command_exists("curl"):
            run(
                "curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash",
                shell=True,
            )
        elif command_exists("wget"):
            run(
                "wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash",
                shell=True,
            )
        else:
            raise RuntimeError("curl or wget is required to install nvm")

    # Load nvm and install latest LTS Node
    run(
        f"""
        export NVM_DIR="{NVM_DIR}"
        . "{NVM_DIR}/nvm.sh"
        nvm install --lts
        nvm use --lts
        """,
        shell=True,
    )


# Persist nvm environment for future shells, this sure fix a lot of issues
def run_with_nvm(cmd, check=True):
    run(
        f"""
        export NVM_DIR="{NVM_DIR}"
        . "{NVM_DIR}/nvm.sh"
        {cmd}
        """,
        check=check,
        shell=True,
    )


def configure_npm():
    # Ensure npm uses a user-writable prefix to avoid permission issues
    npmrc = HOME / ".npmrc"

    if npmrc.exists():
        # Remove conflicting prefix/globalconfig entries
        lines = npmrc.read_text().splitlines()
        cleaned = [
            line for line in lines if not line.startswith(("prefix=", "globalconfig="))
        ]
        npmrc.write_text("\n".join(cleaned) + "\n")

    # Persist ~/.npm-global/bin into PATH for future shells
    if BASHRC.exists():
        bashrc_text = BASHRC.read_text()
        if str(BIN_DIR) in bashrc_text:
            return

    with BASHRC.open("a") as f:
        f.write('\nexport PATH="$HOME/.npm-global/bin:$PATH"\n')


def install_copilot():
    # Install GitHub Copilot CLI using nvm-loaded environment
    run_with_nvm("npm install -g @github/copilot")  # Ensure npm is up to date
    # How it looks in the subprocess output: npm install -g @github/copilot


# Going to remove this and make it into a Toml file later so users can configure it as they like
def write_inkly_wrapper():
    # Create the secure inkly wrapper that fronts Copilot
    wrapper = BIN_DIR / "inkly"

    wrapper.write_text(
        """#!/bin/bash
set -euo pipefail

# Force Copilot to run from the user npm prefix
COPILOT_BIN="$(command -v copilot)"

# Fail fast if Copilot is not available
if [ -z "$COPILOT_BIN" ] || [ ! -x "$COPILOT_BIN" ]; then
  echo "Error: copilot not found on PATH" >&2
  exit 1
fi

# Guardrails against destructive operations
deny_flags=(
  --disable-parallel-tools-execution
  --deny-tool 'shell(rm:*)'
  --deny-tool 'shell(sudo:*)'
  --deny-tool 'shell(chmod:*)'
  --deny-tool 'shell(chown:*)'
  --deny-tool 'shell(rmdir:*)'
  --deny-tool 'shell(unlink:*)'
  --deny-tool 'shell(cp:*)'
  --deny-tool 'shell(mv:*)'
)

clean_output() {
  sed -e '/^Total usage est:/,/^Usage by model:/d' \
      -e '/^Usage by model:/d' \
      -e '/^[[:space:]]*claude-.*Premium request)/d'
}

# Interactive mode (preserve TUI)
if [ "$#" -eq 0 ]; then
  exec "$COPILOT_BIN" "${deny_flags[@]}"
fi

case "$1" in
  -p)
    shift
    prompt="$*"
    ;;
  -*|help|--help|-h|login|logout|whoami|version|update|suggest|chat|terms)
    exec "$COPILOT_BIN" "$@" "${deny_flags[@]}" ;;
esac


prompt="$*"

# Block dangerous shell intent in prompt mode
if printf '%s' "$prompt" | grep -Eiq '\\b(rm|mv|unlink|dd|chmod|chown|rmdir|sudo)\\b|cp[[:space:]]+-r'; then
  echo "Operation blocked: destructive command detected."
  exit 1
fi

"$COPILOT_BIN" -p "$prompt" "${deny_flags[@]}" 2>&1 | clean_output
"""
    )

    wrapper.chmod(0o755)


def install_ink_launcher():
    # Copy ink.sh into persistent Inkly bin
    ink_src = Path(__file__).parent / "ink.sh"
    ink_dst = INKLY_HOME / "bin" / "ink.sh"

    shutil.copy2(ink_src, ink_dst)
    ink_dst.chmod(0o755)

    # Create lightweight launcher in npm-global/bin
    launcher = BIN_DIR / "ink"
    launcher.write_text('#!/bin/bash\nexec "$HOME/.inkly/bin/ink.sh" "$@"\n')
    launcher.chmod(0o755)


# Going to remove this and make it into a Toml file later so users can configure it as they like
def persist_env():
    # Going to keep this part
    # Avoid duplicating Inkly environment blocks
    if BASHRC.exists() and "Inkly persistent state" in BASHRC.read_text():
        return

    # This part can be removed
    # Persist Inkly and Copilot environment configuration
    with BASHRC.open("a") as f:
        f.write(
            """
# --- Inkly persistent state ---
export INKLY_HOME="$HOME/.inkly"
export COPILOT_CONFIG_DIR="$HOME/.inkly/copilot"

# --- Inkly/Copilot HPC-safe settings ---
export COPILOT_NO_COLOR=1
export COPILOT_THEME=plain
export NO_COLOR=1
export COPILOT_LOG_LEVEL=none
export COPILOT_DISABLE_USAGE_FOOTER=1
"""
        )


def verify():
    # Basic sanity checks after installation
    run_with_nvm("node -v")
    run_with_nvm("npm -v")
    run_with_nvm("copilot --version", check=False)


def main():
    # Entry point for installer
    print("Installing Inkly (Python installer)")

    # Ensure Copilot always uses Inkly state directory
    os.environ["COPILOT_CONFIG_DIR"] = str(COPILOT_STATE)

    ensure_dirs()
    ensure_nvm_and_node()
    configure_npm()
    install_copilot()
    write_inkly_wrapper()
    install_ink_launcher()
    persist_env()
    verify()

    print("\nInstallation complete.")
    print("Open a new shell or run: source ~/.bashrc")
    print("Then run: inkly\nThen /login to authenticate Copilot.")


if __name__ == "__main__":
    main()
