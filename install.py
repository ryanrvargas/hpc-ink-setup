#!/usr/bin/env python3

import os
import subprocess
import shutil
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # Python <=3.10


# Path and environment setup :)

HOME = Path.home()

INKLY_HOME = HOME / ".inkly"  # Persistent Inkly state directory
COPILOT_STATE = INKLY_HOME / "copilot"  # Copilot config + auth storage

NVM_DIR = HOME / ".nvm"  # User-space nvm install location
NPM_GLOBAL = HOME / ".npm-global"  # User-space npm prefix
USER_BIN = NPM_GLOBAL / "bin"  # User-visible commands (ink, inkly)

CONFIG_PATH = INKLY_HOME / "config.toml"

def ensure_default_config():
    INKLY_HOME.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        shutil.copy2(
            Path(__file__).parent / "config.toml",
            CONFIG_PATH
        )

def load_config():
    if not CONFIG_PATH.exists():
        raise RuntimeError("Inkly config.toml not found at ~/.inkly/config.toml")

    with CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)

def run(cmd, check=True, shell=False):
    # Execute a command and fail fast on errors
    print(f"->{cmd}")
    subprocess.run(cmd, check=check, shell=shell)


def command_exists(cmd):
    # Check if a command is available on PATH
    return shutil.which(cmd) is not None


def ensure_dirs():
    state = CONFIG["state"]

    inkly_home = Path(os.path.expanduser(state["inkly_home"]))
    inkly_bin = Path(os.path.expanduser(state["bin_dir"]))
    copilot_dir = Path(os.path.expanduser(state["copilot_config_dir"]))
    log_dir = Path(os.path.expanduser(state["log_dir"]))

    inkly_home.mkdir(parents=True, exist_ok=True)
    inkly_bin.mkdir(parents=True, exist_ok=True)
    copilot_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    USER_BIN.mkdir(parents=True, exist_ok=True)




def ensure_nvm_and_node():
    node_cfg = CONFIG["node"]
    
    # First, check if node exists at all (system, module, or user path)
    if command_exists("node"):
        try:
            subprocess.run(
                ["node", "-e", "require('child_process')"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except subprocess.CalledProcessError:
            pass

    if not node_cfg.get("install_if_missing", True):
        raise RuntimeError("Node missing and auto-install disabled in config")

    if not NVM_DIR.exists():
        if node_cfg.get("allow_curl", True) and command_exists("curl"):
            run(
                f"curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v{node_cfg['nvm_version']}/install.sh | bash",
                shell=True,
            )
        elif node_cfg.get("allow_wget", True) and command_exists("wget"):
            run(
                f"wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v{node_cfg['nvm_version']}/install.sh | bash",
                shell=True,
            )
        else:
            raise RuntimeError("No permitted download method for nvm")
            
    # Now NVM must exist
    if not (NVM_DIR / "nvm.sh").exists():
        raise RuntimeError("NVM install completed but nvm.sh is missing")
    
    if node_cfg["node_version"] in ("lts", "stable", "latest"):
        raise RuntimeError(
            "Alias-based Node versions (lts/stable/latest) are not supported on HPC. "
            "Use an explicit Node version in config.toml."
        )

    version = node_cfg["node_version"]

    run(
    f"""
    export NVM_DIR="{NVM_DIR}"
    . "{NVM_DIR}/nvm.sh"

    if ! nvm ls {version} >/dev/null 2>&1; then
        nvm install {version}
    fi

    nvm use {version}
    """,
    shell=True,
    )

# Persist nvm environment for future shells, this sure fix a lot of issues
def run_with_nvm(cmd, check=True):
    if not (NVM_DIR / "nvm.sh").exists():
        raise RuntimeError("nvm.sh not found in NVM_DIR")
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
    install_cfg = CONFIG["install"]

    if not install_cfg.get("allow_modify_shell_rc", True):
        return

    shell_rc = Path(os.path.expanduser(install_cfg["shell_rc"]))

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
    if shell_rc.exists():
        rc_text = shell_rc.read_text()
        if str(USER_BIN) in rc_text:
            return

    with shell_rc.open("a") as f:
        f.write('\nexport PATH="$HOME/.npm-global/bin:$PATH"\n')


def install_copilot():
    # Install GitHub Copilot CLI using nvm-loaded environment
    if not (NVM_DIR / "nvm.sh").exists():
        raise RuntimeError(
            "Inkly requires an NVM-managed Node runtime to install Copilot. "
            "Disable system Node or allow NVM install."
        )
    run_with_nvm("npm install -g @github/copilot")  # Ensure npm is up to date
    # How it looks in the subprocess output: npm install -g @github/copilot


# Going to remove this and make it into a Toml file later so users can configure it as they like
def write_inkly_wrapper():
    wrapper = USER_BIN / "inkly"

    wrapper.write_text(
        """#!/bin/bash
set -euo pipefail

CONFIG="$HOME/.inkly/config.toml"

if [ ! -f "$CONFIG" ]; then
  echo "Inkly config.toml not found" >&2
  exit 1
fi

COPILOT_BIN="$(command -v copilot)"

if [ -z "$COPILOT_BIN" ]; then
  echo "copilot not found on PATH" >&2
  exit 1
fi

exec "$COPILOT_BIN" -p "$@"
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
    launcher = USER_BIN / "ink"
    launcher.write_text('#!/bin/bash\nexec "$HOME/.inkly/bin/ink.sh" "$@"\n')
    launcher.chmod(0o755)

def verify():
    # Basic sanity checks after installation
    if (NVM_DIR / "nvm.sh").exists():
        run_with_nvm("node -v")
        run_with_nvm("npm -v")
        run_with_nvm("copilot --version", check=False)
    else:
        run(["node", "-v"])
        run(["npm", "-v"])
        run(["copilot", "--version"], check=False)


def main():
    global CONFIG

    # Entry point for installer
    print("Installing Inkly (Python installer)")

    # Ensure Copilot always uses Inkly state directory
    os.environ["COPILOT_CONFIG_DIR"] = str(COPILOT_STATE)

    ensure_default_config()
    CONFIG = load_config()
    ensure_dirs()
    ensure_nvm_and_node()
    configure_npm()
    install_copilot()
    write_inkly_wrapper()
    install_ink_launcher()
    verify()

    print("\nInstallation complete.")
    print("Open a new shell or run: source ~/.bashrc")
    print("Then run: inkly\nThen /login to authenticate Copilot.")


if __name__ == "__main__":
    main()
