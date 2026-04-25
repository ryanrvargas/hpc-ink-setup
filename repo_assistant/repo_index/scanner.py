from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

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

NORMALIZED_IGNORED_DIR_NAMES = {name.casefold() for name in IGNORED_DIR_NAMES}


@dataclass(frozen=True)  # Once a RepoFile object is created, it cannot be changed.
class RepoFile:
    """
        Represents one file that passed scanner filtering.
    `
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

    This walks upward from the starting location until it finds a directory
    that looks like the repo root. For the first scanner version, we treat
    a folder as the repo root if it contains a .git directory or a
    pyproject.toml file.
    """

    # If no starting path is provided, begin from the current working directory.
    current = start_path or Path.cwd()

    # If the caller passes a file path, move up to the directory first.
    if current.is_file():
        current = current.parent

    # Resolve the path so comparisons stay clean and predictable.
    current = current.resolve()

    # Check the current directory and then walk upward through all parents.
    for candidate in (current, *current.parents):
        if (candidate / ".git").is_dir():
            return candidate

        if (candidate / "pyproject.toml").is_file():
            return candidate

    raise ValueError(f"Could not find repository root from: {current}")


def should_ignore_dir(path: Path) -> bool:
    """
    Decide whether a directory should be skipped entirely.

    This is where directory-level ignore rules belong, such as:
    - .git
    - __pycache__
    - virtual environments
    """
    # Compare only the directory name, not the full path.
    # This keeps the rule simple and works during recursive walking.
    return path.name.casefold() in NORMALIZED_IGNORED_DIR_NAMES


def should_include_file(path: Path) -> bool:
    """
    Decide whether a file should be included in the scan results.

    This should handle extension filtering, file size filtering,
    and later any simple binary/generated file checks we add.
    """

    # Skip anything that is not a normal file.
    if not path.is_file():
        return False

    # Only include file types we care about for repo indexing.
    if path.suffix.lower() not in INCLUDED_EXTENSIONS:
        return False

    # Skip files that are too large for the first scanner version.
    try:
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            return False
    except OSError:
        # If the file cannot be read normally, fail closed.
        return False

    return True


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

    This is the main entry point for repository scanning.
    It walks the repo, applies ignore/include rules, collects metadata,
    and returns stable RepoFile objects.
    """

    # Detect the repo root if one was not provided directly.
    root = find_repo_root(repo_root)

    scanned_files: list[RepoFile] = []  # Store every RepoFile object we collect

    # topdown=True lets us remove ignored directories before os.walk
    # descends into them.
    for current_dir, dir_names, file_names in os.walk(root, topdown=True):
        current_path = Path(current_dir)

        # Prune ignored directories in place so they are never walked.
        dir_names[:] = [  # Modify the list in place using [:] along with os.walk
            name for name in dir_names if not should_ignore_dir(current_path / name)
        ]

        for file_name in file_names:
            file_path = current_path / file_name

            if not should_include_file(file_path):
                continue

            try:
                stat_result = file_path.stat()
            except OSError:
                # Skip files that cannot be read from the filesystem.
                continue

            scanned_files.append(
                RepoFile(
                    relative_path=file_path.relative_to(root).as_posix(),
                    absolute_path=file_path.resolve(),
                    size_bytes=stat_result.st_size,
                    modified_time=stat_result.st_mtime,
                    file_type=detect_file_type(file_path),
                )
            )

    # Sort results so repeated scans are stable and predictable.
    scanned_files.sort(key=lambda file: file.relative_path)

    return scanned_files
