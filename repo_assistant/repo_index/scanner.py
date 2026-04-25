from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


INCLUDED_EXTENSIONS = {
    ".py",
    ".md",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
}

IGNORED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
}

MAX_FILE_SIZE_BYTES = 1_000_000