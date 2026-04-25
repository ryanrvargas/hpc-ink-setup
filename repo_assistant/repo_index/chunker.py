from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repo_assistant.repo_index.scanner import RepoFile


# Default maximum number of lines allowed in one chunk.
# Keeping this as a constant makes the default easy to change later.
DEFAULT_MAX_CHUNK_LINES = 80


@dataclass(frozen=True)
class RepoChunk:
    """
    Represents one retrieval-friendly chunk from one repository file.

    Each chunk keeps enough metadata to trace it back to the original file.
    """

    # Stable chunk identifier.
    # Example: "repo_assistant/cli.py::chunk-0001"
    chunk_id: str

    # Path relative to the repo root.
    relative_path: str

    # Normalized file type from scanner.py.
    file_type: str

    # File modified time copied from the scanner metadata.
    modified_time: float

    # First line number included in this chunk.
    # This is 1-based because that is easier for users to understand.
    start_line: int

    # Last line number included in this chunk.
    end_line: int

    # Actual text content stored for retrieval.
    text: str


def normalize_text(text: str) -> str:
    """
    Normalize line endings so chunking is stable across Windows and Unix.

    Windows files often use \\r\\n.
    Unix files usually use \\n.
    This converts both into one predictable format.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def split_text_into_chunks(
    text: str,
    *,
    max_chunk_lines: int = DEFAULT_MAX_CHUNK_LINES,
) -> list[tuple[int, int, str]]:
    """
    Split text into stable line-based chunks.

    Returns:
        A list of tuples:
        (start_line, end_line, chunk_text)

    Important:
    - start_line and end_line are 1-based.
    - chunking is deterministic.
    - blank lines are used as preferred boundaries when possible.
    """

    # The * means max_chunk_lines must be passed by keyword.
    # Example:
    # split_text_into_chunks(text, max_chunk_lines=50)
    if max_chunk_lines <= 0:
        raise ValueError("max_chunk_lines must be greater than 0")

    normalized = normalize_text(text)
    lines = normalized.splitlines()

    if not lines:
        return []

    # Each chunk is stored as:
    # (start_line, end_line, chunk_text)
    chunks: list[tuple[int, int, str]] = []
    start_index = 0

    while start_index < len(lines):
        # hard_end_index is the farthest this chunk is allowed to go.
        hard_end_index = min(start_index + max_chunk_lines, len(lines))

        end_index = find_chunk_boundary(
            lines,
            start_index=start_index,
            hard_end_index=hard_end_index,
            max_chunk_lines=max_chunk_lines,
        )

        # Slicing uses [start:end], including start and stopping before end.
        chunk_lines = lines[start_index:end_index]

        # Join the selected lines back into one block of text.
        # strip() removes blank space/newlines at the start and end.
        chunk_text = "\n".join(chunk_lines).strip()

        if chunk_text:
            chunks.append(
                (
                    # Convert from 0-based list index to 1-based line number.
                    start_index + 1,
                    end_index,
                    chunk_text,
                )
            )

        # Move forward so the next loop starts where this chunk ended.
        start_index = end_index

    return chunks


def find_chunk_boundary(
    lines: list[str],
    *,
    start_index: int,
    hard_end_index: int,
    max_chunk_lines: int,
) -> int:
    """
    Find a clean chunk boundary.

    The hard boundary is the latest line the chunk may include.
    This function tries to move the boundary backward to a blank line,
    but only if that does not create a tiny chunk.
    """
    if hard_end_index >= len(lines):
        return len(lines)

    # max_chunk_lines // 2 uses integer division.
    # This gives a lower bound so we do not back up so far that the chunk becomes tiny.
    minimum_reasonable_end = start_index + max(1, max_chunk_lines // 2)

    # Walk backward looking for a blank line near the end of the chunk.
    for index in range(hard_end_index - 1, minimum_reasonable_end - 1, -1):
        if not lines[index].strip():
            return index + 1

    return hard_end_index


def read_repo_file(repo_file: RepoFile) -> str:
    """
    Read a scanned repository file as text.

    UTF-8 is the normal path.
    If decoding fails, errors='replace' keeps the index rebuild from crashing
    on one unusual character.
    """
    path = Path(repo_file.absolute_path)

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def chunk_repo_file(
    repo_file: RepoFile,
    *,
    max_chunk_lines: int = DEFAULT_MAX_CHUNK_LINES,
) -> list[RepoChunk]:
    """
    Convert one scanned RepoFile into RepoChunk objects.
    """
    try:
        text = read_repo_file(repo_file)
    except OSError:
        return []

    # First create raw chunk tuples shaped like:
    # (start_line, end_line, chunk_text)
    raw_chunks = split_text_into_chunks(
        text,
        max_chunk_lines=max_chunk_lines,
    )

    chunks: list[RepoChunk] = []

    # enumerate(...) gives both a counter and the current item.
    # start=1 makes the counter begin at 1 instead of 0.
    #
    # The current raw chunk tuple is unpacked into:
    # start_line, end_line, chunk_text
    for index, (start_line, end_line, chunk_text) in enumerate(raw_chunks, start=1):
        chunks.append(
            RepoChunk(
                # :04d formats the number as 4 digits with leading zeros.
                # Example: 1 -> 0001
                chunk_id=f"{repo_file.relative_path}::chunk-{index:04d}",
                relative_path=repo_file.relative_path,
                file_type=repo_file.file_type,
                modified_time=repo_file.modified_time,
                start_line=start_line,
                end_line=end_line,
                text=chunk_text,
            )
        )

    return chunks


def chunk_repo_files(
    repo_files: list[RepoFile],
    *,
    max_chunk_lines: int = DEFAULT_MAX_CHUNK_LINES,
) -> list[RepoChunk]:
    """
    Convert many scanned RepoFile objects into one flat chunk list.
    """
    chunks: list[RepoChunk] = []

    for repo_file in repo_files:
        # chunk_repo_file(...) returns a list of RepoChunk objects for one file.
        # extend(...) adds each item from that returned list into chunks.
        #
        # This keeps chunks as one flat list.
        # Using append(...) here would add the whole returned list as one item.
        chunks.extend(
            chunk_repo_file(
                repo_file,
                max_chunk_lines=max_chunk_lines,
            )
        )

    return chunks
