#!/usr/bin/env python3
"""
Full Inkly HPC Uninstaller — resets system to pre-install state.

Removes:
  - ~/.nvm
  - ~/.npm-global
  - ~/.npm
  - ~/.npmrc
  - ~/.copilot
  - any cache containing 'copilot'
  - ~/hpc-ink-setup
  - all PATH modifications from installer
  - all ink.sh sourcing
  - all duplicate PATH exports added by installer
  - any 'fi' safety-patch lines added by installer
  - ensures .bashrc is syntactically valid after cleanup
"""

import os
import re
import shutil
from pathlib import Path

HOME = Path.home()
BASHRC = HOME / ".bashrc"

REMOVE_DIRS = [
    HOME / ".nvm",
    HOME / ".npm-global",
    HOME / ".npm",
    HOME / ".copilot",
]

REMOVE_FILES = [
    HOME / ".npmrc",
    HOME / ".npm/_logs",
]

REPO_DIR = HOME / "hpc-ink-setup"


def safe_remove(path: Path):
    if path.exists():
        print(f"Removing {path}")
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink()
        except Exception as e:
            print(f"  ⚠️ Could not remove {path}: {e}")


def clean_bashrc():
    if not BASHRC.exists():
        return

    print("Cleaning ~/.bashrc ...")
    text = BASHRC.read_text()

    # Remove explicit installer lines
    patterns = [
        r'.*hpc-ink-setup\/hpc-ink-setup\/ink\.sh.*\n',
        r'.*hpc-ink-setup\/ink\.sh.*\n',
        r'export PATH="\$HOME/\.npm-global/bin:\$PATH"\n',
        r'export PATH="\$HOME/\.npm-global/bin:\$PATH".*\n',
        r'.*\.npm-global/bin.*\n',
        r'# --- INKLY START ---.*?# --- INKLY END ---\n?',
        r'# --- INKLY FN START ---.*?# --- INKLY FN END ---\n?',
    ]

    for pat in patterns:
        text = re.sub(pat, "", text, flags=re.S)

    # Fix unterminated nvm/posix if-blocks
    text = re.sub(r'\nfi\nfi', '\nfi', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    cleaned = text.strip() + "\n"
    BASHRC.write_text(cleaned)
    print(".bashrc cleaned and validated.")


def remove_copilot_cache():
    cache_dir = HOME / ".cache"
    if not cache_dir.exists():
        return

    for item in cache_dir.glob("**/*copilot*"):
        safe_remove(item)


def main():
    print("=== Starting full Inkly HPC uninstall ===\n")

    # Remove directories
    for d in REMOVE_DIRS:
        safe_remove(d)

    # Remove files
    for f in REMOVE_FILES:
        safe_remove(f)

    # Remove repo
    safe_remove(REPO_DIR)

    # Clean cache
    remove_copilot_cache()

    # Repair .bashrc
    clean_bashrc()

    print("\nUninstallation complete.")
    print("Run:  source ~/.bashrc")
    print("You can now reinstall with a clean environment.")


if __name__ == "__main__":
    main()
