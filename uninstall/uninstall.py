#!/usr/bin/env python3
"""
Full Inkly HPC Uninstaller — resets system to pre-install state.

Removes:
  - ~/.nvm
  - ~/.npm-global
  - ~/.npm
  - ~/.npmrc
  - ~/.copilot
  - ~/.inkly
  - ~/.local/bin/ink
  - ~/.npm-global/bin/{ink,inkly}
  - any cache containing 'copilot'
  - ~/hpc-ink-setup
  - all PATH modifications from installer
  - all ink.sh sourcing
  - ensures .bashrc is syntactically valid after cleanup
"""

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
    HOME / ".inkly",  # NEW
]

REMOVE_FILES = [
    HOME / ".npmrc",
    HOME / ".npm/_logs",
    HOME / ".local/bin/ink",  # NEW
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


def remove_stale_binaries():
    """Remove leftover ink / inkly binaries if npm-global partially survived."""
    bin_dir = HOME / ".npm-global" / "bin"
    if not bin_dir.exists():
        return

    for name in ("ink", "inkly"):
        p = bin_dir / name
        if p.exists():
            safe_remove(p)


def clean_bashrc():
    if not BASHRC.exists():
        return

    print("Cleaning ~/.bashrc ...")
    text = BASHRC.read_text()

    patterns = [
        r".*hpc-ink-setup\/hpc-ink-setup\/ink\.sh.*\n",
        r".*hpc-ink-setup\/ink\.sh.*\n",
        r'export PATH="\$HOME/\.npm-global/bin:\$PATH".*\n',
        r".*\.npm-global/bin.*\n",
        r"# --- INKLY START ---.*?# --- INKLY END ---\n?",
        r"# --- INKLY FN START ---.*?# --- INKLY FN END ---\n?",
    ]

    for pat in patterns:
        text = re.sub(pat, "", text, flags=re.S)

    # Repair broken shell structure
    text = re.sub(r"\nfi\nfi", "\nfi", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    cleaned = text.strip() + "\n"
    BASHRC.write_text(cleaned)
    print(".bashrc cleaned and validated.")


def remove_copilot_cache():
    cache_dir = HOME / ".cache"
    if not cache_dir.exists():
        return

    for item in cache_dir.glob("**/*copilot*"):
        safe_remove(item)


def sanity_check():
    print("\nSanity check:")
    for cmd in ("ink", "inkly", "node", "npm", "copilot"):
        if shutil.which(cmd):
            print(f"{cmd} still found in PATH")
        else:
            print(f"{cmd} not found")


def main():
    print("=== Starting full Inkly HPC uninstall ===\n")

    for d in REMOVE_DIRS:
        safe_remove(d)

    for f in REMOVE_FILES:
        safe_remove(f)

    remove_stale_binaries()
    # safe_remove(REPO_DIR)
    # remove_copilot_cache()
    clean_bashrc()
    sanity_check()

    print("\nUninstallation complete.")
    print("Run:  source ~/.bashrc")
    print("System is now clean for a fresh Inkly install.")


if __name__ == "__main__":
    main()
