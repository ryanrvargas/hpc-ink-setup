#!/usr/bin/env python3
"""
Inkly HPC Uninstaller — fully removes Inkly, Ink, Copilot CLI, Node (nvm), and all related configs.
Removes:
  - ~/.nvm
  - ~/.npm-global
  - ~/.npm
  - ~/.copilot
  - ~/.cache (safe)
  - ~/.bashrc edits from installer
  - ~/hpc-ink-setup (repo itself)
"""

import os
import re
import shutil
from pathlib import Path

HOME = Path.home()
BASHRC = HOME / ".bashrc"
NVM_DIR = HOME / ".nvm"
NPM_GLOBAL = HOME / ".npm-global"
NPM_DIR = HOME / ".npm"
COPILOT_DIR = HOME / ".copilot"
CACHE_DIR = HOME / ".cache"
REPO_DIR = HOME / "hpc-ink-setup"
BIN_DIR = NPM_GLOBAL / "bin"
INKLY_PATH = BIN_DIR / "inkly"
INK_PATH = BIN_DIR / "ink"

def safe_remove(path: Path):
    """Delete file or directory if it exists."""
    if path.exists():
        print(f"🧹 Removing {path}")
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                path.unlink()
            except Exception as e:
                print(f"  ⚠️ Could not remove {path}: {e}")

def clean_bashrc():
    """Remove Inkly and Ink-related edits from ~/.bashrc."""
    if not BASHRC.exists():
        return
    print(f"🧹 Cleaning ~/.bashrc ...")
    text = BASHRC.read_text()

    # Remove lines added by installer
    cleaned = re.sub(r'# --- INKLY START ---.*?# --- INKLY END ---\n?', '', text, flags=re.S)
    cleaned = re.sub(r'# --- INKLY FN START ---.*?# --- INKLY FN END ---\n?', '', cleaned, flags=re.S)
    cleaned = re.sub(r'.*hpc-ink-setup/ink\.sh.*\n?', '', cleaned)
    cleaned = re.sub(r'export PATH="\$HOME/\.npm-global/bin:\$PATH"\n?', '', cleaned)

    # Strip trailing blank lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip() + "\n"

    BASHRC.write_text(cleaned)
    print("✅ .bashrc cleaned successfully.")

def main():
    print("🧽 Starting Inkly HPC uninstallation...")

    # Remove directories
    for d in [NVM_DIR, NPM_GLOBAL, NPM_DIR, COPILOT_DIR]:
        safe_remove(d)

    # Optional: remove ~/.cache but skip system-critical caches
    if CACHE_DIR.exists():
        print(f"🧹 Clearing Copilot cache entries from {CACHE_DIR}")
        for p in CACHE_DIR.glob("*copilot*"):
            safe_remove(p)

    # Remove repo itself
    safe_remove(REPO_DIR)

    # Remove individual binaries in case the dirs were manually moved
    for f in [INKLY_PATH, INK_PATH]:
        safe_remove(f)

    # Clean .bashrc modifications
    clean_bashrc()

    print("\n✅ Uninstallation complete.")
    print("You can reopen your terminal or run:  source ~/.bashrc")

if __name__ == "__main__":
    main()
