from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from repo_assistant.repo_index.chunker import RepoChunk, chunk_repo_file, chunk_repo_files
from repo_assistant.repo_index.scanner import RepoFile, find_repo_root, scan_repository


INDEX_VERSION = 1
DEFAULT_INDEX_DIR_NAME = ".repochat"
DEFAULT_INDEX_FILE_NAME = "index.json"


@dataclass(frozen=True)
class IndexedFile:
    """Metadata for one file stored in the repository index."""

    relative_path: str
    size_bytes: int
    modified_time: float
    file_type: str
    chunk_ids: list[str]


@dataclass(frozen=True)
class RepoIndex:
    """Full on-disk repository index structure."""

    index_version: int
    build_timestamp: str
    repo_root: str
    files: list[IndexedFile]
    chunks: list[RepoChunk]


@dataclass(frozen=True)
class IndexFreshness:
    """Difference between the current repository and a saved index."""

    added: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()
    deleted: tuple[str, ...] = ()
    unchanged: tuple[str, ...] = ()

    @property
    def stale(self) -> bool:
        return bool(self.added or self.modified or self.deleted)


@dataclass(frozen=True)
class RefreshResult:
    """Result of an incremental index refresh."""

    repo_index: RepoIndex
    freshness: IndexFreshness
    rebuilt: bool


def default_index_path(repo_root: Path) -> Path:
    return repo_root / DEFAULT_INDEX_DIR_NAME / DEFAULT_INDEX_FILE_NAME


class JsonRepoIndexStore:
    """JSON-backed repository index store."""

    def __init__(self, repo_root: Path, index_path: Path | None = None) -> None:
        self.repo_root = repo_root.resolve()
        self.index_path = index_path or default_index_path(self.repo_root)

    def save(self, repo_index: RepoIndex) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "index_version": repo_index.index_version,
            "build_timestamp": repo_index.build_timestamp,
            "repo_root": repo_index.repo_root,
            "files": [asdict(file) for file in repo_index.files],
            "chunks": [asdict(chunk) for chunk in repo_index.chunks],
        }
        self.index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> RepoIndex | None:
        if not self.index_path.exists():
            return None

        payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        files = [
            IndexedFile(
                relative_path=row["relative_path"],
                size_bytes=int(row["size_bytes"]),
                modified_time=float(row["modified_time"]),
                file_type=row["file_type"],
                chunk_ids=list(row.get("chunk_ids", [])),
            )
            for row in payload.get("files", [])
        ]
        chunks = [
            RepoChunk(
                chunk_id=row["chunk_id"],
                relative_path=row["relative_path"],
                file_type=row["file_type"],
                modified_time=float(row["modified_time"]),
                start_line=int(row["start_line"]),
                end_line=int(row["end_line"]),
                text=row["text"],
            )
            for row in payload.get("chunks", [])
        ]
        return RepoIndex(
            index_version=int(payload["index_version"]),
            build_timestamp=payload["build_timestamp"],
            repo_root=payload["repo_root"],
            files=files,
            chunks=chunks,
        )


def _indexed_file(repo_file: RepoFile, chunk_ids: list[str]) -> IndexedFile:
    return IndexedFile(
        relative_path=repo_file.relative_path,
        size_bytes=repo_file.size_bytes,
        modified_time=repo_file.modified_time,
        file_type=repo_file.file_type,
        chunk_ids=chunk_ids,
    )


def _group_chunk_ids(chunks: list[RepoChunk]) -> dict[str, list[str]]:
    chunks_by_path: dict[str, list[str]] = {}
    for chunk in chunks:
        chunks_by_path.setdefault(chunk.relative_path, []).append(chunk.chunk_id)
    return chunks_by_path


def build_repo_index(repo_root: Path | None = None) -> RepoIndex:
    root = find_repo_root(repo_root)
    repo_files = scan_repository(root)
    chunks = chunk_repo_files(repo_files)
    chunks_by_path = _group_chunk_ids(chunks)
    indexed_files = [
        _indexed_file(
            repo_file,
            chunks_by_path.get(repo_file.relative_path, []),
        )
        for repo_file in repo_files
    ]
    return RepoIndex(
        index_version=INDEX_VERSION,
        build_timestamp=datetime.now(timezone.utc).isoformat(),
        repo_root=str(root),
        files=indexed_files,
        chunks=chunks,
    )


def rebuild_repo_index(
    repo_root: Path | None = None,
    *,
    index_path: Path | None = None,
) -> RepoIndex:
    root = find_repo_root(repo_root)
    repo_index = build_repo_index(root)
    JsonRepoIndexStore(repo_root=root, index_path=index_path).save(repo_index)
    return repo_index


def load_repo_index(
    repo_root: Path | None = None,
    *,
    index_path: Path | None = None,
) -> RepoIndex | None:
    root = find_repo_root(repo_root)
    return JsonRepoIndexStore(repo_root=root, index_path=index_path).load()


def check_index_freshness(
    repo_root: Path | None = None,
    *,
    repo_index: RepoIndex | None = None,
    index_path: Path | None = None,
) -> IndexFreshness:
    """Compare the saved index metadata with the repository's current state."""

    root = find_repo_root(repo_root)
    current_files = scan_repository(root)
    saved = repo_index
    if saved is None:
        saved = load_repo_index(root, index_path=index_path)

    current_by_path = {file.relative_path: file for file in current_files}
    if saved is None:
        return IndexFreshness(added=tuple(sorted(current_by_path)))

    saved_by_path = {file.relative_path: file for file in saved.files}
    current_paths = set(current_by_path)
    saved_paths = set(saved_by_path)

    added = current_paths - saved_paths
    deleted = saved_paths - current_paths
    modified: set[str] = set()
    unchanged: set[str] = set()

    for path in current_paths & saved_paths:
        current = current_by_path[path]
        indexed = saved_by_path[path]
        if (
            current.size_bytes != indexed.size_bytes
            or current.modified_time != indexed.modified_time
            or current.file_type != indexed.file_type
        ):
            modified.add(path)
        else:
            unchanged.add(path)

    return IndexFreshness(
        added=tuple(sorted(added)),
        modified=tuple(sorted(modified)),
        deleted=tuple(sorted(deleted)),
        unchanged=tuple(sorted(unchanged)),
    )


def refresh_repo_index(
    repo_root: Path | None = None,
    *,
    index_path: Path | None = None,
) -> RefreshResult:
    """Incrementally refresh changed files and preserve unchanged chunks."""

    root = find_repo_root(repo_root)
    store = JsonRepoIndexStore(repo_root=root, index_path=index_path)
    saved = store.load()

    if (
        saved is None
        or saved.index_version != INDEX_VERSION
        or Path(saved.repo_root).resolve() != root
    ):
        rebuilt = build_repo_index(root)
        store.save(rebuilt)
        freshness = IndexFreshness(added=tuple(file.relative_path for file in rebuilt.files))
        return RefreshResult(repo_index=rebuilt, freshness=freshness, rebuilt=True)

    current_files = scan_repository(root)
    current_by_path = {file.relative_path: file for file in current_files}
    freshness = check_index_freshness(root, repo_index=saved)

    if not freshness.stale:
        return RefreshResult(repo_index=saved, freshness=freshness, rebuilt=False)

    changed_paths = set(freshness.added) | set(freshness.modified)
    deleted_paths = set(freshness.deleted)

    kept_chunks = [
        chunk
        for chunk in saved.chunks
        if chunk.relative_path not in changed_paths | deleted_paths
    ]
    refreshed_chunks: list[RepoChunk] = []
    for path in sorted(changed_paths):
        refreshed_chunks.extend(chunk_repo_file(current_by_path[path]))

    chunks = kept_chunks + refreshed_chunks
    chunks.sort(key=lambda chunk: (chunk.relative_path, chunk.start_line, chunk.chunk_id))
    chunks_by_path = _group_chunk_ids(chunks)

    indexed_files = [
        _indexed_file(
            repo_file,
            chunks_by_path.get(repo_file.relative_path, []),
        )
        for repo_file in current_files
    ]

    refreshed = RepoIndex(
        index_version=INDEX_VERSION,
        build_timestamp=datetime.now(timezone.utc).isoformat(),
        repo_root=str(root),
        files=indexed_files,
        chunks=chunks,
    )
    store.save(refreshed)
    return RefreshResult(repo_index=refreshed, freshness=freshness, rebuilt=True)
