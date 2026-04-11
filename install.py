#!/usr/bin/env python3

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

# Default location of Inkly configuration file
CONFIG_PATH = DEFAULT_INKLY_HOME / "config.toml"

# Global config objects populated after parsing config.toml
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


# Directory Verification & Setup
def setup_runtime_dirs():
    """
    Create all required Inkly directories.

    This includes persistent state, executables, logs,
    and Inkly's private lib directory.
    """
    if STATE_CFG is None:
        raise RuntimeError("STATE_CFG not initialized before setup_runtime_dirs()")

    STATE_CFG.inkly_home.mkdir(parents=True, exist_ok=True)
    STATE_CFG.bin_dir.mkdir(parents=True, exist_ok=True)
    STATE_CFG.log_dir.mkdir(parents=True, exist_ok=True)

    # Internal library directory for Inkly runtime code
    LIB_DIR = STATE_CFG.inkly_home / "lib"
    LIB_DIR.mkdir(parents=True, exist_ok=True)

    # Copy entire inkly runtime package into private lib directory
    RUNTIME_SRC = Path(__file__).parent / "inkly"
    RUNTIME_DST = LIB_DIR / "inkly"

    if not RUNTIME_SRC.exists():
        raise RuntimeError("inkly runtime package not found in installer directory")

    shutil.copytree(RUNTIME_SRC, RUNTIME_DST, dirs_exist_ok=True)


def initialize_jobs_database():
    """
    Initialize the Inkly structured job intelligence database.

    This creates ~/.inkly/jobs.db with the required schema so the
    runtime has a ready-to-use database after installation.
    """
    if STATE_CFG is None:
        raise RuntimeError(
            "STATE_CFG not initialized before initialize_jobs_database()"
        )

    from inkly.db import initialize_jobs_db

    initialize_jobs_db(STATE_CFG.inkly_home / "jobs.db")


# Ink Launcher Installation
def install_ink():
    """
    Install the Ink launcher into Inkly's bin directory.
    """
    if STATE_CFG is None:
        raise RuntimeError("STATE_CFG not initialized before install_ink()")

    ink_src = Path(__file__).parent / "ink"
    ink_dst = STATE_CFG.bin_dir / "ink"

    if not ink_src.exists():
        raise RuntimeError("ink launcher script missing from installer")

    ink_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ink_src, ink_dst)
    ink_dst.chmod(0o755)


# Post-Install Verification
def verify():
    """
    Perform basic sanity checks after installation.
    """
    if STATE_CFG is None:
        raise RuntimeError("STATE_CFG not initialized before verify()")

    ink_path = STATE_CFG.bin_dir / "ink"
    lib_path = STATE_CFG.inkly_home / "lib" / "inkly"
    db_path = STATE_CFG.inkly_home / "jobs.db"

    if not ink_path.exists():
        raise RuntimeError(f"Verification failed: ink launcher missing at {ink_path}")

    if not lib_path.exists():
        raise RuntimeError(f"Verification failed: runtime package missing at {lib_path}")

    if not db_path.exists():
        raise RuntimeError(f"Verification failed: jobs database missing at {db_path}")


def configure_shell_path():
    """
    Optionally add Inkly's bin directory to the user's shell PATH.
    """
    if INSTALL_CFG is None or STATE_CFG is None:
        raise RuntimeError(
            "Installer config not initialized before configure_shell_path()"
        )

    if not INSTALL_CFG.allow_path_injection or not INSTALL_CFG.allow_modify_shell_rc:
        return

    shell_rc = Path(INSTALL_CFG.shell_rc).expanduser()
    path_line = f'\nexport PATH="{STATE_CFG.bin_dir}:$PATH"\n'

    if shell_rc.exists():
        rc_text = shell_rc.read_text(encoding="utf-8")
        if str(STATE_CFG.bin_dir) in rc_text:
            return

    with shell_rc.open("a", encoding="utf-8") as f:
        f.write(path_line)

# Installer Entry Point
def main():
    """
    Inkly installer entrypoint.

    Executes installation in a safe, deterministic order.
    """
    global INSTALL_CFG, STATE_CFG

    print("Installing Inkly (Python installer)")

    verify_default_config()

    parser = TomlParser(CONFIG_PATH)
    cfg = parser.load()

    INSTALL_CFG = cfg.install
    STATE_CFG = cfg.state

    setup_runtime_dirs()
    initialize_jobs_database()
    install_ink()
    configure_shell_path()
    verify()

    print("\nInstallation complete.")
    if INSTALL_CFG.allow_path_injection and INSTALL_CFG.allow_modify_shell_rc:
        print("Open a new shell or run: source ~/.bashrc")
        print("Then run: ink <prompt> \nto start using Inkly.")
    else:
        print(f"Run Inkly with: {STATE_CFG.bin_dir / 'ink'}")

    print(f"[ink] using config: {CONFIG_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
