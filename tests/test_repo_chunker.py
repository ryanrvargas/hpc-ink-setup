from __future__ import annotations

from pathlib import Path

import pytest

from repo_assistant.repo_index.chunker import (
    RepoChunk,
    chunk_repo_file,
    split_text_into_chunks,
)
from repo_assistant.repo_index.scanner import RepoFile


def make_repo_file(path: Path, relative_path: str = "sample.py") -> RepoFile:
    return RepoFile(
        relative_path=relative_path,
        absolute_path=path,
        size_bytes=path.stat().st_size,
        modified_time=path.stat().st_mtime,
        file_type="python",
    )


def test_split_text_into_chunks_is_deterministic() -> None:
    text = "\n".join(f"line {number}" for number in range(1, 11))

    first = split_text_into_chunks(text, max_chunk_lines=4)
    second = split_text_into_chunks(text, max_chunk_lines=4)

    assert first == second


def test_split_text_into_chunks_uses_stable_line_boundaries() -> None:
    text = "\n".join(
        [
            "def one():",
            "    return 1",
            "",
            "def two():",
            "    return 2",
        ]
    )

    chunks = split_text_into_chunks(text, max_chunk_lines=3)

    assert chunks[0] == (1, 3, "def one():\n    return 1")
    assert chunks[1] == (4, 5, "def two():\n    return 2")


def test_chunk_repo_file_adds_expected_metadata(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("print('hello')\n", encoding="utf-8")

    repo_file = make_repo_file(source)

    chunks = chunk_repo_file(repo_file)

    assert len(chunks) == 1

    chunk = chunks[0]

    assert isinstance(chunk, RepoChunk)
    assert chunk.chunk_id == "sample.py::chunk-0001"
    assert chunk.relative_path == "sample.py"
    assert chunk.file_type == "python"
    assert chunk.start_line == 1
    assert chunk.end_line == 1
    assert chunk.text == "print('hello')"


def test_chunk_repo_file_returns_empty_list_for_empty_file(tmp_path: Path) -> None:
    source = tmp_path / "empty.py"
    source.write_text("", encoding="utf-8")

    repo_file = make_repo_file(source, relative_path="empty.py")

    assert chunk_repo_file(repo_file) == []


def test_split_text_into_chunks_rejects_invalid_chunk_size() -> None:
    with pytest.raises(ValueError, match="max_chunk_lines"):
        split_text_into_chunks("hello", max_chunk_lines=0)
