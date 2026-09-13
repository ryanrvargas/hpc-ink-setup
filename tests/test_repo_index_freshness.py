from __future__ import annotations

import os
from pathlib import Path

from repo_assistant.repo_index.store import (
    check_index_freshness,
    load_repo_index,
    refresh_repo_index,
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


def chunk_ids_for(repo_index, relative_path: str) -> list[str]:
    return [
        chunk.chunk_id
        for chunk in repo_index.chunks
        if chunk.relative_path == relative_path
    ]


def test_freshness_detects_added_modified_and_deleted_files(tmp_path: Path) -> None:
    repo_root = make_repo_root(tmp_path)
    keep = repo_root / "keep.py"
    remove = repo_root / "remove.py"
    keep.write_text("print('old')\n", encoding="utf-8")
    remove.write_text("print('remove')\n", encoding="utf-8")

    rebuilt = rebuild_repo_index(repo_root)

    old_stat = keep.stat()
    keep.write_text("print('new and longer')\n", encoding="utf-8")
    os.utime(keep, (old_stat.st_atime, old_stat.st_mtime + 2))
    remove.unlink()
    (repo_root / "added.md").write_text("# Added\n", encoding="utf-8")

    freshness = check_index_freshness(repo_root, repo_index=rebuilt)

    assert freshness.stale is True
    assert freshness.added == ("added.md",)
    assert freshness.modified == ("keep.py",)
    assert freshness.deleted == ("remove.py",)


def test_refresh_updates_only_changed_paths_and_removes_deleted_chunks(
    tmp_path: Path,
) -> None:
    repo_root = make_repo_root(tmp_path)
    unchanged = repo_root / "unchanged.py"
    changed = repo_root / "changed.py"
    deleted = repo_root / "deleted.py"
    unchanged.write_text("print('same')\n", encoding="utf-8")
    changed.write_text("print('before')\n", encoding="utf-8")
    deleted.write_text("print('gone')\n", encoding="utf-8")

    initial = rebuild_repo_index(repo_root)
    unchanged_chunks_before = [
        chunk
        for chunk in initial.chunks
        if chunk.relative_path == "unchanged.py"
    ]

    changed_stat = changed.stat()
    changed.write_text("print('after with more text')\n", encoding="utf-8")
    os.utime(changed, (changed_stat.st_atime, changed_stat.st_mtime + 2))
    deleted.unlink()
    (repo_root / "new.md").write_text("# New file\n", encoding="utf-8")

    result = refresh_repo_index(repo_root)
    refreshed = result.repo_index

    assert result.rebuilt is True
    assert result.freshness.added == ("new.md",)
    assert result.freshness.modified == ("changed.py",)
    assert result.freshness.deleted == ("deleted.py",)
    assert all(chunk.relative_path != "deleted.py" for chunk in refreshed.chunks)
    assert chunk_ids_for(refreshed, "changed.py")
    assert chunk_ids_for(refreshed, "new.md")

    unchanged_chunks_after = [
        chunk
        for chunk in refreshed.chunks
        if chunk.relative_path == "unchanged.py"
    ]
    assert unchanged_chunks_after == unchanged_chunks_before

    chunk_ids = [chunk.chunk_id for chunk in refreshed.chunks]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_refresh_is_stable_when_repository_has_not_changed(tmp_path: Path) -> None:
    repo_root = make_repo_root(tmp_path)
    (repo_root / "README.md").write_text("# Stable\n", encoding="utf-8")

    initial = rebuild_repo_index(repo_root)
    result = refresh_repo_index(repo_root)
    loaded = load_repo_index(repo_root)

    assert result.rebuilt is False
    assert result.freshness.stale is False
    assert result.repo_index == initial
    assert loaded == initial
    assert result.repo_index.build_timestamp == initial.build_timestamp


def test_refresh_builds_index_when_none_exists(tmp_path: Path) -> None:
    repo_root = make_repo_root(tmp_path)
    (repo_root / "README.md").write_text("# First build\n", encoding="utf-8")

    result = refresh_repo_index(repo_root)

    assert result.rebuilt is True
    assert result.repo_index.files
    assert result.freshness.added
    assert load_repo_index(repo_root) == result.repo_index
