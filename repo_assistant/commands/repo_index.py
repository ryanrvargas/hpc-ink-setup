from __future__ import annotations

from repo_assistant.repo_index.scanner import find_repo_root
from repo_assistant.repo_index.store import (
    JsonRepoIndexStore,
    default_index_path,
    load_repo_index,
    rebuild_repo_index,
)


def handle_rebuild(args) -> int:
    # Find the repo root starting from the current working directory.
    # This keeps the command flexible, so the user does not have to stand
    # in the exact root folder as long as they are somewhere inside the repo.
    repo_root = find_repo_root()

    # Build a fresh index in memory and save it to disk.
    # rebuild_repo_index(...) handles both of those steps.
    repo_index = rebuild_repo_index(repo_root)

    # Compute the default on-disk path where the JSON index lives.
    index_path = default_index_path(repo_root)

    print("[repochat] repo index rebuilt.")
    print(f"Repo root: {repo_root}")
    print(f"Index path: {index_path}")

    # len(...) returns how many items are in a list.
    # repo_index.files is the list of indexed file records.
    print(f"Indexed files: {len(repo_index.files)}")

    # repo_index.chunks is the flat list of stored text chunks.
    print(f"Indexed chunks: {len(repo_index.chunks)}")

    return 0


def handle_stats(args) -> int:
    # Find the repo root first so we know where the index should live.
    repo_root = find_repo_root()

    # load_repo_index(...) reads the saved index from disk without rebuilding it.
    repo_index = load_repo_index(repo_root)

    # If there is no saved index yet, load_repo_index(...) returns None.
    if repo_index is None:
        print("[repochat] no repo index found.")
        print(f"Expected path: {default_index_path(repo_root)}")
        print("Run: repochat repo-index rebuild")
        return 1

    print("[repochat] repo index stats")
    print(f"Repo root: {repo_index.repo_root}")
    print(f"Index version: {repo_index.index_version}")
    print(f"Build timestamp: {repo_index.build_timestamp}")
    print(f"Indexed files: {len(repo_index.files)}")
    print(f"Indexed chunks: {len(repo_index.chunks)}")

    return 0


def handle_doctor(args) -> int:
    # Find the repo root the same way the other commands do.
    repo_root = find_repo_root()

    # Create the JSON store object directly so we can inspect its expected path.
    store = JsonRepoIndexStore(repo_root)

    print("[repochat] repo index doctor")
    print(f"Repo root detected: {repo_root}")

    # Path.exists() returns True if the file/folder is present on disk.
    # Here we are checking whether the saved JSON index file already exists.
    if store.index_path.exists():
        print(f"Index found: {store.index_path}")
    else:
        print(f"Index missing: {store.index_path}")
        print("Run: repochat repo-index rebuild")
        return 1

    return 0