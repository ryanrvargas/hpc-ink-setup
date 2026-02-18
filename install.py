#!/usr/bin/env python3

import subprocess
import shutil
from pathlib import Path
import sys

from inkly.config import TomlParser

# Bootstrap Paths & Environment
#
# These paths are used to bootstrap Inkly during installation.
# After config parsing, STATE_CFG is the single source of truth
# for all runtime and persistent paths.

HOME = Path.home()

# DEFAULT_INKLY_HOME is only used to locate config.toml initially.
# Once parsed, STATE_CFG.inkly_home must be used instead.
DEFAULT_INKLY_HOME = HOME / ".inkly"

# User-space NVM installation directory
NVM_DIR = HOME / ".nvm"

# User-space npm global prefix to avoid system-wide installs
NPM_GLOBAL = HOME / ".npm-global"

# Directory where user-visible commands (ink, copilot) will live
USER_BIN = NPM_GLOBAL / "bin"

# Default location of Inkly configuration file
CONFIG_PATH = DEFAULT_INKLY_HOME / "config.toml"

# Global config objects populated after parsing config.toml
NODE_CFG = None  # NodeConfig (Node / NVM policy)
INSTALL_CFG = None  # InstallConfig (installation behavior)
STATE_CFG = None  # StateConfig (persistent paths)


# Default Configuration Bootstrap
def verify_default_config():
    """
    Ensure a default config.toml exists.

    If the user has not created a config yet, copy the
    template config.toml from the installer directory
    into ~/.inkly/config.toml.
    """
    DEFAULT_INKLY_HOME.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        shutil.copy2(Path(__file__).parent / "config.toml", CONFIG_PATH)


# Command Execution Helpers
def run(cmd, check=True, shell=False):
    """
    Execute a command and optionally fail fast.

    This is used for installer operations where failure
    should abort installation immediately.
    """
    print(f"->{cmd}")
    subprocess.run(cmd, check=check, shell=shell)


def command_exists(cmd):
    """
    Return True if a command is available on PATH.
    """
    return shutil.which(cmd) is not None


# Directory Verification & Setup
def verify_dirs():
    """
    Create all required Inkly directories.

    This includes persistent state, binaries, logs,
    Copilot config storage, and Inkly's private lib directory.
    """
    if STATE_CFG is None:
        raise RuntimeError("STATE_CFG not initialized before verify_dirs()")

    STATE_CFG.inkly_home.mkdir(parents=True, exist_ok=True)
    STATE_CFG.bin_dir.mkdir(parents=True, exist_ok=True)
    STATE_CFG.log_dir.mkdir(parents=True, exist_ok=True)
    USER_BIN.mkdir(parents=True, exist_ok=True)

    # Internal library directory for Inkly runtime code
    LIB_DIR = STATE_CFG.inkly_home / "lib"
    LIB_DIR.mkdir(parents=True, exist_ok=True)

    # Copy entire inkly runtime package into private lib directory
    RUNTIME_SRC = Path(__file__).parent / "inkly"
    RUNTIME_DST = LIB_DIR / "inkly"

    if not RUNTIME_SRC.exists():
        raise RuntimeError("inkly runtime package not found in installer directory")

    shutil.copytree(RUNTIME_SRC, RUNTIME_DST, dirs_exist_ok=True)


# Node & NVM Verification
def verify_nvm_and_node():
    """
    Ensure NVM and the configured Node version are available.

    - Verifies the requested Node version via nvm
    - Installs nvm if allowed and missing
    - Installs Node if missing and permitted by policy
    """
    if NODE_CFG is None:
        raise RuntimeError("NODE_CFG not initialized before verify_nvm_and_node()")

    node_cfg = NODE_CFG
    version = node_cfg.node_version

    # Check if requested Node version is already installed
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
            return  # Node version already present

    # Node missing and auto-install disabled
    if not node_cfg.install_if_missing:
        raise RuntimeError("Node missing and auto-install disabled in config")

    # Install nvm if necessary
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

    # Ensure nvm.sh exists after installation
    if not (NVM_DIR / "nvm.sh").exists():
        raise RuntimeError("NVM install completed but nvm.sh is missing")

    # Install and activate desired Node version
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


# NVM-Aware Command Execution
def run_with_nvm(cmd, check=True):
    """
    Run a command with NVM environment loaded.

    This ensures Node, npm, and Copilot are executed
    using the correct user-space runtime.
    """
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


# npm Configuration
def configure_npm():
    """
    Configure npm for user-space operation.

    - Forces a user-writable npm prefix
    - Removes conflicting npm settings
    - Optionally modifies shell rc to persist PATH changes
    """
    cfg = INSTALL_CFG

    if not cfg.allow_modify_shell_rc:
        return

    shell_rc = Path(cfg.shell_rc).expanduser()
    npmrc = HOME / ".npmrc"

    # Remove conflicting npm prefix/globalconfig entries
    if npmrc.exists():
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


# Copilot Installation
def install_copilot():
    """
    Install GitHub Copilot CLI using npm.

    Requires an NVM-managed Node runtime.
    """
    if not (NVM_DIR / "nvm.sh").exists():
        raise RuntimeError(
            "Inkly requires an NVM-managed Node runtime to install Copilot. "
            "Disable system Node or allow NVM install."
        )

    run_with_nvm("npm install -g @github/copilot")


# Ink Launcher Installation
def install_ink():
    """
    Install the Ink launcher.

    - Copies the ink script into Inkly’s persistent bin directory
    - Creates a user-visible symlink in ~/.npm-global/bin
    """
    ink_src = Path(__file__).parent / "ink"
    ink_dst = STATE_CFG.bin_dir / "ink"

    if not ink_src.exists():
        raise RuntimeError("ink launcher script missing from installer")

    ink_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ink_src, ink_dst)
    ink_dst.chmod(0o755)

    launcher = USER_BIN / "ink"
    launcher.parent.mkdir(parents=True, exist_ok=True)

    if launcher.exists() or launcher.is_symlink():
        launcher.unlink()

    launcher.symlink_to(ink_dst)


# Post-Install Verification
def verify():
    """
    Perform basic sanity checks after installation.

    Confirms Node, npm, and Copilot are usable.
    """
    if (NVM_DIR / "nvm.sh").exists():
        run_with_nvm("node -v")
        run_with_nvm("npm -v")
        run_with_nvm("copilot --version", check=False)
    else:
        raise RuntimeError("Verification failed: NVM missing")


# Installer Entry Point
def main():
    """
    Inkly installer entrypoint.

    Executes installation in a safe, deterministic order.
    """
    global NODE_CFG, INSTALL_CFG, STATE_CFG

    print("Installing Inkly (Python installer)")

    verify_default_config()

    parser = TomlParser(CONFIG_PATH)
    cfg = parser.load()

    NODE_CFG = cfg.node
    INSTALL_CFG = cfg.install
    STATE_CFG = cfg.state

    verify_dirs()
    verify_nvm_and_node()
    configure_npm()
    install_copilot()
    install_ink()
    verify()

    print("\nInstallation complete.")
    print("Open a new shell or run: source ~/.bashrc")
    print("Then run: ink\nThen /login to authenticate Copilot.")
    print(f"[ink] using config: {CONFIG_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
