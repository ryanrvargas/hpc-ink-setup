from pathlib import Path

import pytest

from repo_assistant.repo_index.chunker import RepoChunk
from repo_assistant.repo_index.retriever import retrieve_chunks, retrieve_from_index
from repo_assistant.repo_index.store import JsonRepoIndexStore, RepoIndex


def _chunk(chunk_id: str, path: str, file_type: str, text: str) -> RepoChunk:
    return RepoChunk(
        chunk_id=chunk_id,
        relative_path=path,
        file_type=file_type,
        modified_time=1.0,
        start_line=1,
        end_line=max(1, len(text.splitlines())),
        text=text,
    )


def _index(tmp_path: Path) -> RepoIndex:
    chunks = [
        _chunk(
            "slurm",
            "inkly/plugins/slurm.py",
            "python",
            'def queue_status():\n    """Inspect Slurm queue partitions and pending jobs."""\n',
        ),
        _chunk(
            "gaussian",
            "docs/gaussian/troubleshooting.md",
            "markdown",
            "# Gaussian failures\nUse the checkpoint file after a Gaussian convergence failure.",
        ),
        _chunk(
            "windows",
            "repochat.cmd",
            "batch",
            "@echo off\npython -m repo_assistant.cli %*",
        ),
        _chunk(
            "noise",
            "LICENSE",
            "text",
            "Permission terms for noncommercial distribution.",
        ),
    ]
    return RepoIndex(
        index_version=1,
        build_timestamp="2026-09-14T00:00:00+00:00",
        repo_root=str(tmp_path),
        files=[],
        chunks=chunks,
    )


def test_retrieves_semantically_matching_chunk(tmp_path: Path) -> None:
    results = retrieve_chunks("why did my Gaussian job fail", _index(tmp_path), top_k=2)

    assert results
    assert results[0].relative_path == "docs/gaussian/troubleshooting.md"
    assert results[0].score > 0
    assert all(result.relative_path != "LICENSE" for result in results)


def test_path_terms_bias_matching_file(tmp_path: Path) -> None:
    results = retrieve_chunks(
        "entry point",
        _index(tmp_path),
        top_k=3,
        path_hint="repochat.cmd",
    )

    assert results[0].relative_path == "repochat.cmd"


def test_file_type_filter_distinguishes_runtime_surface(tmp_path: Path) -> None:
    results = retrieve_chunks(
        "python queue status",
        _index(tmp_path),
        file_types={"python"},
    )

    assert [result.relative_path for result in results] == ["inkly/plugins/slurm.py"]


def test_top_k_is_configurable(tmp_path: Path) -> None:
    results = retrieve_chunks("job python gaussian", _index(tmp_path), top_k=1)
    assert len(results) == 1


def test_invalid_top_k_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="top_k"):
        retrieve_chunks("anything", _index(tmp_path), top_k=0)


def test_loader_reads_saved_index(tmp_path: Path) -> None:
    repo_index = _index(tmp_path)
    index_path = tmp_path / ".repochat" / "index.json"
    JsonRepoIndexStore(tmp_path, index_path=index_path).save(repo_index)

    results = retrieve_from_index(
        "Slurm partitions",
        tmp_path,
        index_path=index_path,
        top_k=1,
    )

    assert results[0].chunk_id == "slurm"


def test_missing_index_has_actionable_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="repo-index rebuild"):
        retrieve_from_index("anything", tmp_path, index_path=tmp_path / "missing.json")
