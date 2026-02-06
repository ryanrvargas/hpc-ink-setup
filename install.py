#!/usr/bin/env python3

import os
import subprocess
import shutil
from pathlib import Path
import sys

from config import TomlParser

# Path and environment setup :)

HOME = Path.home()
# DEFAULT_INKLY_HOME is only used to bootstrap config.toml.
# After parsing, STATE_CFG.inkly_home is the single source of truth.
DEFAULT_INKLY_HOME = HOME / ".inkly"

NVM_DIR = HOME / ".nvm"  # User-space nvm install location
NPM_GLOBAL = HOME / ".npm-global"  # User-space npm prefix
USER_BIN = NPM_GLOBAL / "bin"  # User-visible commands (ink, inkly)

CONFIG_PATH = DEFAULT_INKLY_HOME / "config.toml"  # Default config path

NODE_CFG = None  # Node Config will be set later
INSTALL_CFG = None  # Install Config will be set later
STATE_CFG = None  # State Config will be set later


def verify_default_config():
    DEFAULT_INKLY_HOME.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        shutil.copy2(Path(__file__).parent / "config.toml", CONFIG_PATH)


def run(cmd, check=True, shell=False):
    # Execute a command and fail fast on errors
    print(f"->{cmd}")
    subprocess.run(cmd, check=check, shell=shell)


def command_exists(cmd):
    # Check if a command is available on PATH
    return shutil.which(cmd) is not None


# Verify and create necessary directories
def verify_dirs():
    if STATE_CFG is None:
        raise RuntimeError("STATE_CFG not initialized before verify_dirs()")

    STATE_CFG.inkly_home.mkdir(parents=True, exist_ok=True)
    STATE_CFG.bin_dir.mkdir(parents=True, exist_ok=True)
    STATE_CFG.copilot_config_dir.mkdir(parents=True, exist_ok=True)
    STATE_CFG.log_dir.mkdir(parents=True, exist_ok=True)
    USER_BIN.mkdir(parents=True, exist_ok=True)

    LIB_DIR = STATE_CFG.inkly_home / "lib"
    LIB_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copy2(
        Path(__file__).parent / "config.py",
        LIB_DIR / "config.py",
    )


def verify_nvm_and_node():
    # Node Config
    node_cfg = NODE_CFG
    if NODE_CFG is None:
        raise RuntimeError("NODE_CFG not initialized before verify_nvm_and_node()")

    # verify desired Node version is installed
    version = node_cfg.node_version

    if (NVM_DIR / "nvm.sh").exists():
        result = subprocess.run(
            f'''
            export NVM_DIR="{NVM_DIR}"
            . "{NVM_DIR}/nvm.sh"
            nvm ls {version} >/dev/null 2>&1
            ''',
            shell=True,
        )
        if result.returncode == 0:
            # Correct Node version already installed via NVM
            return

    # Node is missing or broken
    if not node_cfg.install_if_missing:
        raise RuntimeError("Node missing and auto-install disabled in config")

    # Install nvm if missing
    if not NVM_DIR.exists():
        if node_cfg.allow_curl and command_exists("curl"):
            run(
                f"curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v{node_cfg.nvm_version}/install.sh | bash",
                shell=True,
            )
        elif node_cfg.allow_wget and command_exists("wget"):
            run(
                f"wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v{node_cfg.nvm_version}/install.sh | bash",
                shell=True,
            )
        else:
            raise RuntimeError("No permitted download method for nvm")

    # Now NVM must exist
    if not (NVM_DIR / "nvm.sh").exists():
        raise RuntimeError("NVM install completed but nvm.sh is missing")

    # Install and use desired Node version
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


# Configure npm to use user-writable global prefix and update shell rc
# so future shells have correct PATH,


def configure_npm():
    cfg = INSTALL_CFG

    if not cfg.allow_modify_shell_rc:
        return

    shell_rc = Path(cfg.shell_rc).expanduser()
    # verify npm uses a user-writable prefix to avoid permission issues
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
    run_with_nvm("npm install -g @github/copilot")  # verify npm is up to date
    # How it looks in the subprocess output: npm install -g @github/copilot


def install_ink():
    # Copy ink into persistent Inkly bin
    ink_src = Path(__file__).parent / "ink"
    ink_dst = STATE_CFG.bin_dir / "ink"

    if not ink_src.exists():
        raise RuntimeError("ink launcher script missing from installer")

    # Create persistent Inkly bin dir and copy ink there,
    ink_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ink_src, ink_dst)
    ink_dst.chmod(0o755)

    # Create user-visible ink launcher, pointing to persistent Inkly bin,
    launcher = USER_BIN / "ink"
    launcher.parent.mkdir(parents=True, exist_ok=True)

    if launcher.exists() or launcher.is_symlink():
        launcher.unlink()

    launcher.symlink_to(ink_dst)


def verify():
    # Basic sanity checks after installation
    if (NVM_DIR / "nvm.sh").exists():
        run_with_nvm("node -v")
        run_with_nvm("npm -v")
        run_with_nvm("copilot --version", check=False)
    else:
        raise RuntimeError("Verification failed: NVM missing")


def main():
    global NODE_CFG, INSTALL_CFG, STATE_CFG
    # Entry point for installer
    print("Installing Inkly (Python installer)")

    verify_default_config()
    parser = TomlParser(CONFIG_PATH)
    cfg = parser.load()
    NODE_CFG = cfg.node
    INSTALL_CFG = cfg.install
    STATE_CFG = cfg.state
    # Verify Copilot always uses Ink state directory,
    os.environ["COPILOT_CONFIG_DIR"] = str(STATE_CFG.copilot_config_dir)
    verify_dirs()
    verify_nvm_and_node()
    configure_npm()
    install_copilot()
    install_ink()
    verify()

    print("\nInstallation complete.")
    print("Open a new shell or run: source ~/.bashrc")
    print("Then run: ink\nThen /login to authenticate Copilot.")
    # INFO Debug visibility (remove later or gate behind flag) ink --debug
    print(f"[ink] using config: {CONFIG_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
