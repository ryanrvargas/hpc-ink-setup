from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# File types we want the scanner to consider for indexing.
# These are the repo files that are most likely to help with codebase Q&A.
INCLUDED_EXTENSIONS = {
    ".py",
    ".md",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
}

# Directory names we do not want to scan.
# These are cache folders, virtual environments, or other noisy paths
# that should not be part of the repo assistant index.
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

# Hard size cutoff for files the scanner will consider.
# This helps avoid pulling in large generated files or other junk too early.
MAX_FILE_SIZE_BYTES = 1_000_000


@dataclass(frozen=True) #Once a RepoFile object is created, it can not be changed.
class RepoFile:
    """
    Represents one file that passed scanner filtering.

    This is the normalized file record that later steps can use for:
    - indexing
    - freshness checks
    - stats output
    """

    # Path relative to the detected repo root.
    # This should be the main path shown to the user later.
    relative_path: str

    # Full absolute path on disk.
    # Useful for reading the file or checking metadata.
    absolute_path: Path

    # File size in bytes at scan time.
    size_bytes: int

    # Last modified timestamp from the filesystem.
    # This will later help with stale index detection.
    modified_time: float

    # Normalized file type label such as "python", "markdown", or "toml".
    file_type: str


def find_repo_root(start_path: Path | None = None) -> Path:
    """
    Find the repository root starting from the given path.

    Later this should walk upward until it finds the repo boundary,
    instead of assuming the current working directory is always correct.
    """
    raise NotImplementedError


def should_ignore_dir(path: Path) -> bool:
    """
    Decide whether a directory should be skipped entirely.

    This is where directory-level ignore rules belong, such as:
    - .git
    - __pycache__
    - virtual environments
    """
    raise NotImplementedError


def should_include_file(path: Path) -> bool:
    """
    Decide whether a file should be included in the scan results.

    This should handle extension filtering, file size filtering,
    and later any simple binary/generated file checks we add.
    """
    raise NotImplementedError


def detect_file_type(path: Path) -> str:
    """
    Convert a file path into a stable file type label.

    This keeps scanner metadata predictable so later steps like indexing,
    stats, and tests are not guessing based on raw extensions everywhere.
    """
    suffix = path.suffix.lower()

    # Keep the labels simple and stable.
    # We only need enough detail to describe the kind of file.
    if suffix == ".py":
        return "python"
    if suffix == ".md":
        return "markdown"
    if suffix == ".toml":
        return "toml"
    if suffix in {".yml", ".yaml"}:
        return "yaml"
    if suffix == ".json":
        return "json"

    # This should not usually happen if include rules are working,
    # but returning a safe fallback keeps the function predictable.
    return "unknown"


def scan_repository(repo_root: Path | None = None) -> list[RepoFile]:
    """
    Scan the repository and return normalized file records.

    This will be the main entry point for repository scanning.
    It should walk the repo, apply ignore/include rules, collect metadata,
    and return stable RepoFile objects.
    """
    raise NotImplementedError