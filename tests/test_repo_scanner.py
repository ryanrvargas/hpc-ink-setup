from __future__ import annotations

from pathlib import Path

import pytest

from repo_assistant.repo_index.scanner import (
    MAX_FILE_SIZE_BYTES,
    RepoFile,
    detect_file_type,
    find_repo_root,
    scan_repository,
    should_ignore_dir,
    should_include_file,
)


def make_repo_root(tmp_path: Path) -> Path:
    """
    Create a minimal fake repo root for scanner tests.

    We use pyproject.toml as the repo marker because find_repo_root()
    accepts that as a valid root signal.
    """
    repo_root = tmp_path / "sample_repo"
    repo_root.mkdir()
    (repo_root / "pyproject.toml").write_text(
        "[project]\nname = 'sample-repo'\n",
        encoding="utf-8",
    )
    return repo_root


@pytest.mark.parametrize(
    ("file_name", "expected_type"),
    [
        ("script.py", "python"),
        ("README.md", "markdown"),
        ("pyproject.toml", "toml"),
        ("config.yml", "yaml"),
        ("config.yaml", "yaml"),
        ("data.json", "json"),
        ("notes.txt", "unknown"),
    ],
)
def test_detect_file_type_returns_expected_labels(
    file_name: str,
    expected_type: str,
) -> None:
    """
    detect_file_type() should return stable normalized labels.
    """
    assert detect_file_type(Path(file_name)) == expected_type


@pytest.mark.parametrize(
    ("dir_name", "expected"),
    [
        (".git", True),
        ("__pycache__", True),
        (".pytest_cache", True),
        (".ruff_cache", True),
        (".venv", True),
        ("venv", True),
        ("env", True),
        ("node_modules", True),
        ("src", False),
        ("docs", False),
    ],
)
def test_should_ignore_dir_skips_known_junk_dirs(
    dir_name: str,
    expected: bool,
) -> None:
    """
    should_ignore_dir() should only skip directories in the ignore list.
    """
    assert should_ignore_dir(Path(dir_name)) is expected


def test_should_include_file_allows_supported_extensions(tmp_path: Path) -> None:
    """
    should_include_file() should allow supported text/code file types.
    """
    repo_root = make_repo_root(tmp_path)

    for file_name in [
        "main.py",
        "README.md",
        "pyproject.toml",
        "config.yml",
        "config.yaml",
        "data.json",
    ]:
        file_path = repo_root / file_name
        file_path.write_text("test\n", encoding="utf-8")
        assert should_include_file(file_path) is True


def test_should_include_file_rejects_unsupported_extensions(tmp_path: Path) -> None:
    """
    should_include_file() should reject files with unsupported extensions.
    """
    repo_root = make_repo_root(tmp_path)

    file_path = repo_root / "perf.log"
    file_path.write_text("not included\n", encoding="utf-8")

    assert should_include_file(file_path) is False


def test_should_include_file_rejects_large_files(tmp_path: Path) -> None:
    """
    should_include_file() should reject files larger than the size limit.
    """
    repo_root = make_repo_root(tmp_path)

    file_path = repo_root / "large.md"
    file_path.write_text("a" * (MAX_FILE_SIZE_BYTES + 1), encoding="utf-8")

    assert should_include_file(file_path) is False


def test_should_include_file_returns_false_on_stat_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    If file metadata cannot be read, should_include_file() should fail closed.
    """
    repo_root = make_repo_root(tmp_path)
    file_path = repo_root / "broken.py"
    file_path.write_text("print('hello')\n", encoding="utf-8")

    monkeypatch.setattr(Path, "is_file", lambda self: True)

    def fake_stat(self: Path):
        raise OSError("cannot read file metadata")

    monkeypatch.setattr(Path, "stat", fake_stat)

    assert should_include_file(file_path) is False


def test_find_repo_root_from_nested_directory(tmp_path: Path) -> None:
    """
    find_repo_root() should walk upward from a nested directory.
    """
    repo_root = make_repo_root(tmp_path)

    nested_dir = repo_root / "repo_assistant" / "repo_index"
    nested_dir.mkdir(parents=True)

    assert find_repo_root(nested_dir) == repo_root.resolve()


def test_find_repo_root_from_nested_file(tmp_path: Path) -> None:
    """
    find_repo_root() should also work when the starting path is a file.
    """
    repo_root = make_repo_root(tmp_path)

    nested_file = repo_root / "repo_assistant" / "repo_index" / "scanner.py"
    nested_file.parent.mkdir(parents=True)
    nested_file.write_text("print('scanner')\n", encoding="utf-8")

    assert find_repo_root(nested_file) == repo_root.resolve()


def test_find_repo_root_raises_when_no_repo_root_found(tmp_path: Path) -> None:
    """
    find_repo_root() should raise a clear error when no repo marker exists.
    """
    start_dir = tmp_path / "not_a_repo" / "nested"
    start_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match="Could not find repository root"):
        find_repo_root(start_dir)


def test_scan_repository_empty_repo_returns_empty_list(tmp_path: Path) -> None:
    """
    A repo with only a .git directory and no supported files should scan as empty.
    """
    repo_root = tmp_path / "empty_repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()

    results = scan_repository(repo_root)

    assert results == []


def test_scan_repository_returns_repo_files_with_normalized_metadata(
    tmp_path: Path,
) -> None:
    """
    scan_repository() should return RepoFile objects with stable metadata.
    """
    repo_root = make_repo_root(tmp_path)

    readme = repo_root / "README.md"
    readme.write_text("# Sample Repo\n", encoding="utf-8")

    runtime_file = repo_root / "inkly" / "core" / "runtime.py"
    runtime_file.parent.mkdir(parents=True)
    runtime_file.write_text("print('runtime')\n", encoding="utf-8")

    results = scan_repository(repo_root)

    assert results
    assert all(isinstance(item, RepoFile) for item in results)

    relative_paths = [item.relative_path for item in results]
    assert relative_paths == sorted(relative_paths)

    runtime_entry = next(
        item for item in results if item.relative_path == "inkly/core/runtime.py"
    )

    assert runtime_entry.absolute_path.is_absolute()
    assert runtime_entry.size_bytes > 0
    assert isinstance(runtime_entry.modified_time, float)
    assert runtime_entry.file_type == "python"


def test_scan_repository_skips_ignored_directories(tmp_path: Path) -> None:
    """
    scan_repository() should never return files from ignored directories.
    """
    repo_root = make_repo_root(tmp_path)

    kept_file = repo_root / "src" / "keep.py"
    kept_file.parent.mkdir(parents=True)
    kept_file.write_text("print('keep')\n", encoding="utf-8")

    ignored_git_file = repo_root / ".git" / "config.py"
    ignored_git_file.parent.mkdir(parents=True)
    ignored_git_file.write_text("print('ignore')\n", encoding="utf-8")

    ignored_cache_file = repo_root / "__pycache__" / "cached.py"
    ignored_cache_file.parent.mkdir(parents=True)
    ignored_cache_file.write_text("print('ignore')\n", encoding="utf-8")

    results = scan_repository(repo_root)
    relative_paths = [item.relative_path for item in results]

    assert "src/keep.py" in relative_paths
    assert ".git/config.py" not in relative_paths
    assert "__pycache__/cached.py" not in relative_paths


def test_scan_repository_returns_posix_relative_paths_on_windows(
    tmp_path: Path,
) -> None:
    """
    relative_path should use forward slashes so path formatting stays stable.
    """
    repo_root = make_repo_root(tmp_path)

    file_path = repo_root / "pkg" / "nested" / "module.py"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("print('module')\n", encoding="utf-8")

    results = scan_repository(repo_root)

    entry = next(item for item in results if item.file_type == "python")
    assert entry.relative_path == "pkg/nested/module.py"
    assert "\\" not in entry.relative_path
