from __future__ import annotations

from pathlib import Path

from repo_assistant.repo_index.store import (
    INDEX_VERSION,
    JsonRepoIndexStore,
    build_repo_index,
    default_index_path,
    load_repo_index,
    rebuild_repo_index,
)


def make_repo_root(tmp_path: Path) -> Path:
    repo_root = tmp_path / "sample_repo"
    repo_root.mkdir()
    (repo_root / "pyproject.toml").write_text(
        "[project]\nname = 'sample-repo'\n",
        encoding="utf-8",
    )
    return repo_root


def test_build_repo_index_uses_scanner_output(tmp_path: Path) -> None:
    repo_root = make_repo_root(tmp_path)

    source = repo_root / "repo_assistant" / "cli.py"
    source.parent.mkdir()
    source.write_text("print('hello')\n", encoding="utf-8")

    repo_index = build_repo_index(repo_root)

    indexed_paths = [file.relative_path for file in repo_index.files]

    assert "repo_assistant/cli.py" in indexed_paths
    assert repo_index.index_version == INDEX_VERSION
    assert repo_index.chunks


def test_rebuild_repo_index_writes_json_index(tmp_path: Path) -> None:
    repo_root = make_repo_root(tmp_path)

    source = repo_root / "README.md"
    source.write_text("# Sample\n", encoding="utf-8")

    repo_index = rebuild_repo_index(repo_root)

    index_path = default_index_path(repo_root)

    assert index_path.exists()
    assert len(repo_index.files) >= 1
    assert len(repo_index.chunks) >= 1


def test_load_repo_index_loads_without_rebuilding(tmp_path: Path) -> None:
    repo_root = make_repo_root(tmp_path)

    source = repo_root / "README.md"
    source.write_text("# Sample\n", encoding="utf-8")

    rebuilt = rebuild_repo_index(repo_root)
    loaded = load_repo_index(repo_root)

    assert loaded is not None
    assert loaded.index_version == rebuilt.index_version
    assert loaded.build_timestamp == rebuilt.build_timestamp
    assert len(loaded.files) == len(rebuilt.files)
    assert len(loaded.chunks) == len(rebuilt.chunks)


def test_store_load_returns_none_when_index_missing(tmp_path: Path) -> None:
    repo_root = make_repo_root(tmp_path)

    store = JsonRepoIndexStore(repo_root)

    assert store.load() is None


def test_default_index_path_lives_under_repochat_directory(tmp_path: Path) -> None:
    repo_root = make_repo_root(tmp_path)

    assert default_index_path(repo_root) == repo_root / ".repochat" / "index.json"