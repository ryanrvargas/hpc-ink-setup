from __future__ import annotations

from repo_assistant.repo_index.scanner import find_repo_root
from repo_assistant.repo_index.store import (
    JsonRepoIndexStore,
    check_index_freshness,
    default_index_path,
    load_repo_index,
    rebuild_repo_index,
)


def handle_rebuild(args) -> int:
    repo_root = find_repo_root()
    repo_index = rebuild_repo_index(repo_root)
    index_path = default_index_path(repo_root)

    print("[repochat] repo index rebuilt.")
    print(f"Repo root: {repo_root}")
    print(f"Index path: {index_path}")
    print(f"Indexed files: {len(repo_index.files)}")
    print(f"Indexed chunks: {len(repo_index.chunks)}")
    return 0


def handle_stats(args) -> int:
    repo_root = find_repo_root()
    repo_index = load_repo_index(repo_root)

    if repo_index is None:
        print("[repochat] no repo index found.")
        print(f"Expected path: {default_index_path(repo_root)}")
        print("Run: repochat repo-index rebuild")
        return 1

    freshness = check_index_freshness(repo_root, repo_index=repo_index)

    print("[repochat] repo index stats")
    print(f"Repo root: {repo_index.repo_root}")
    print(f"Index version: {repo_index.index_version}")
    print(f"Build timestamp: {repo_index.build_timestamp}")
    print(f"Indexed files: {len(repo_index.files)}")
    print(f"Indexed chunks: {len(repo_index.chunks)}")
    print(f"Stale: {'yes' if freshness.stale else 'no'}")
    print(f"Added files: {len(freshness.added)}")
    print(f"Modified files: {len(freshness.modified)}")
    print(f"Deleted files: {len(freshness.deleted)}")
    return 0


def handle_doctor(args) -> int:
    repo_root = find_repo_root()
    store = JsonRepoIndexStore(repo_root)

    print("[repochat] repo index doctor")
    print(f"Repo root detected: {repo_root}")

    repo_index = store.load()
    if repo_index is None:
        print(f"Index missing: {store.index_path}")
        print("Run: repochat repo-index rebuild")
        return 1

    print(f"Index found: {store.index_path}")
    freshness = check_index_freshness(repo_root, repo_index=repo_index)
    if freshness.stale:
        print("Index stale: yes")
        print(
            "Changes: "
            f"{len(freshness.added)} added, "
            f"{len(freshness.modified)} modified, "
            f"{len(freshness.deleted)} deleted"
        )
        return 1

    print("Index stale: no")
    return 0
