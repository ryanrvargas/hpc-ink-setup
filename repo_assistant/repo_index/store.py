from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from repo_assistant.repo_index.chunker import RepoChunk, chunk_repo_files
from repo_assistant.repo_index.scanner import RepoFile, find_repo_root, scan_repository


# Bump this if the JSON index structure changes in a way that older files
# should no longer be treated as the same format.
INDEX_VERSION = 1

# Default hidden folder name used to store repochat index data inside the repo.
DEFAULT_INDEX_DIR_NAME = ".repochat"

# Default JSON file name for the on-disk index.
DEFAULT_INDEX_FILE_NAME = "index.json"


@dataclass(frozen=True)
class IndexedFile:
    """
    Metadata for one file stored in the repository index.
    """

    relative_path: str
    size_bytes: int
    modified_time: float
    file_type: str

    # chunk_ids links this file to the chunks stored elsewhere in the index.
    # Keeping chunk IDs here makes it easy to know which chunks belong to which file
    # without duplicating full chunk text inside the file record.
    chunk_ids: list[str]


@dataclass(frozen=True)
class RepoIndex:
    """
    Full on-disk repository index structure.

    This is the object that gets serialized to JSON.
    """

    index_version: int
    build_timestamp: str
    repo_root: str
    files: list[IndexedFile]
    chunks: list[RepoChunk]


def default_index_path(repo_root: Path) -> Path:
    """
    Return the default index path for a repository.
    """

    # The / operator on Path objects joins path parts together.
    # Example:
    # repo_root / ".repochat" / "index.json"
    return repo_root / DEFAULT_INDEX_DIR_NAME / DEFAULT_INDEX_FILE_NAME


class JsonRepoIndexStore:
    """
    JSON-backed repository index store.

    This is intentionally simple for the MVP:
    - one JSON file
    - readable by humans
    - easy to test
    - replaceable later if needed
    """

    def __init__(self, repo_root: Path, index_path: Path | None = None) -> None:
        # resolve() turns the repo root into an absolute normalized path.
        self.repo_root = repo_root.resolve()

        # Use the provided index path if one was passed in.
        # Otherwise fall back to the default path inside the repo.
        #
        # "or" here means:
        # - use index_path if it is truthy / not None
        # - otherwise use default_index_path(...)
        self.index_path = index_path or default_index_path(self.repo_root)

    def save(self, repo_index: RepoIndex) -> None:
        """
        Save a RepoIndex to disk.
        """

        # Make sure the parent folder exists before writing the JSON file.
        # parents=True lets Python create missing parent folders too.
        # exist_ok=True prevents an error if the directory already exists.
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        # Build a plain dictionary payload that can be serialized to JSON.
        payload = {
            "index_version": repo_index.index_version,
            "build_timestamp": repo_index.build_timestamp,
            "repo_root": repo_index.repo_root,

            # asdict(...) converts each dataclass object into a plain dictionary.
            # That is helpful because json.dumps(...) does not know how to directly
            # serialize custom dataclass objects.
            "files": [asdict(file) for file in repo_index.files],
            "chunks": [asdict(chunk) for chunk in repo_index.chunks],
        }

        # json.dumps(...) converts the Python dictionary into a JSON string.
        # indent=2 makes the output readable instead of one long compressed line.
        self.index_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def load(self) -> RepoIndex | None:
        """
        Load the saved index.

        Returns None when the index does not exist yet.
        """

        # RepoIndex | None means this function can return either:
        # - a RepoIndex object
        # - or None
        if not self.index_path.exists():
            return None

        # Read the JSON file as text, then parse it into normal Python objects.
        payload = json.loads(self.index_path.read_text(encoding="utf-8"))

        # Rebuild IndexedFile dataclass objects from the raw JSON rows.
        files = [
            IndexedFile(
                relative_path=row["relative_path"],
                size_bytes=int(row["size_bytes"]),
                modified_time=float(row["modified_time"]),
                file_type=row["file_type"],

                # row.get("chunk_ids", []) safely returns an empty list if the key
                # does not exist. list(...) makes sure the result is a real list.
                chunk_ids=list(row.get("chunk_ids", [])),
            )
            for row in payload.get("files", [])
        ]

        # Rebuild RepoChunk dataclass objects from the raw JSON rows.
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

        # Return the fully rebuilt RepoIndex object in memory.
        return RepoIndex(
            index_version=int(payload["index_version"]),
            build_timestamp=payload["build_timestamp"],
            repo_root=payload["repo_root"],
            files=files,
            chunks=chunks,
        )


def build_repo_index(repo_root: Path | None = None) -> RepoIndex:
    """
    Build a full repository index in memory.

    This uses scanner.py as the source of truth for which files belong.
    """

    # First find the real repo root.
    root = find_repo_root(repo_root)

    # scanner.py decides which files are valid for indexing.
    repo_files = scan_repository(root)

    # chunker.py turns those files into smaller retrieval-friendly chunks.
    chunks = chunk_repo_files(repo_files)

    # This dictionary maps:
    # relative file path -> list of chunk IDs for that file
    #
    # Example:
    # {
    #   "repo_assistant/cli.py": ["repo_assistant/cli.py::chunk-0001", ...]
    # }
    chunks_by_path: dict[str, list[str]] = {}

    for chunk in chunks:
        # setdefault(key, default_value) means:
        # - if the key exists, use its current value
        # - if the key does not exist yet, create it with the default value
        #
        # That makes it a clean way to build grouped lists in a dictionary.
        chunks_by_path.setdefault(chunk.relative_path, []).append(chunk.chunk_id)

    # Build one IndexedFile record per scanned file.
    indexed_files = [
        IndexedFile(
            relative_path=repo_file.relative_path,
            size_bytes=repo_file.size_bytes,
            modified_time=repo_file.modified_time,
            file_type=repo_file.file_type,

            # Use the chunk IDs for this file if they exist.
            # If no chunks were created, fall back to an empty list.
            chunk_ids=chunks_by_path.get(repo_file.relative_path, []),
        )
        for repo_file in repo_files
    ]

    return RepoIndex(
        index_version=INDEX_VERSION,

        # timezone.utc makes the timestamp explicitly UTC instead of local time.
        # isoformat() turns it into a standard string form for JSON storage.
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
    """
    Build and save a fresh repository index.
    """

    # Find the repo root first so both building and saving agree on the same base path.
    root = find_repo_root(repo_root)

    # Build the full index in memory.
    repo_index = build_repo_index(root)

    store = JsonRepoIndexStore(
        repo_root=root,
        index_path=index_path,
    )

    # Save the finished index to disk.
    store.save(repo_index)

    return repo_index


def load_repo_index(
    repo_root: Path | None = None,
    *,
    index_path: Path | None = None,
) -> RepoIndex | None:
    """
    Load an existing repository index without rebuilding.
    """
    root = find_repo_root(repo_root)

    store = JsonRepoIndexStore(
        repo_root=root,
        index_path=index_path,
    )

    return store.load()