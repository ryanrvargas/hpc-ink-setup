from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from repo_assistant.repo_index.chunker import RepoChunk
from repo_assistant.repo_index.store import RepoIndex, load_repo_index


_TOKEN_RE = re.compile(r"[A-Za-z0-9_./\\-]+")


@dataclass(frozen=True)
class RetrievalResult:
    """One ranked repository chunk returned for a query."""

    chunk_id: str
    relative_path: str
    file_type: str
    start_line: int
    end_line: int
    text: str
    score: float


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text.lower()):
        normalized = raw.replace("\\", "/")
        tokens.append(normalized)
        tokens.extend(part for part in re.split(r"[/._-]+", normalized) if part)
    return tokens


def _document_tokens(chunk: RepoChunk) -> list[str]:
    # Repeat path tokens to intentionally bias retrieval toward explicit file/path queries.
    path_tokens = _tokenize(chunk.relative_path)
    return path_tokens + path_tokens + _tokenize(chunk.text)


def _idf(documents: list[list[str]]) -> dict[str, float]:
    total = len(documents)
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(set(document))
    return {
        token: math.log((1 + total) / (1 + frequency)) + 1.0
        for token, frequency in document_frequency.items()
    }


def _cosine_score(query: list[str], document: list[str], idf: dict[str, float]) -> float:
    if not query or not document:
        return 0.0

    query_counts = Counter(query)
    document_counts = Counter(document)
    vocabulary = set(query_counts) & set(document_counts)
    if not vocabulary:
        return 0.0

    query_weights = {
        token: query_counts[token] * idf.get(token, 1.0) for token in query_counts
    }
    document_weights = {
        token: document_counts[token] * idf.get(token, 1.0) for token in document_counts
    }
    dot = sum(query_weights[token] * document_weights[token] for token in vocabulary)
    query_norm = math.sqrt(sum(weight * weight for weight in query_weights.values()))
    document_norm = math.sqrt(sum(weight * weight for weight in document_weights.values()))
    if not query_norm or not document_norm:
        return 0.0
    return dot / (query_norm * document_norm)


def retrieve_chunks(
    query: str,
    repo_index: RepoIndex,
    *,
    top_k: int = 5,
    path_hint: str | None = None,
    file_types: set[str] | None = None,
) -> list[RetrievalResult]:
    """Rank indexed chunks with lightweight TF-IDF and optional path/file filters."""

    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    chunks = [
        chunk
        for chunk in repo_index.chunks
        if file_types is None or chunk.file_type in file_types
    ]
    if not chunks:
        return []

    query_tokens = _tokenize(query)
    path_hint_tokens = _tokenize(path_hint or "")
    documents = [_document_tokens(chunk) for chunk in chunks]
    idf = _idf(documents)

    ranked: list[RetrievalResult] = []
    for chunk, document in zip(chunks, documents, strict=True):
        score = _cosine_score(query_tokens, document, idf)
        if path_hint_tokens:
            path_tokens = set(_tokenize(chunk.relative_path))
            overlap = sum(1 for token in path_hint_tokens if token in path_tokens)
            score += 0.15 * overlap
        if score <= 0:
            continue
        ranked.append(
            RetrievalResult(
                chunk_id=chunk.chunk_id,
                relative_path=chunk.relative_path,
                file_type=chunk.file_type,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                text=chunk.text,
                score=score,
            )
        )

    ranked.sort(key=lambda result: (-result.score, result.relative_path, result.start_line))
    return ranked[:top_k]


def retrieve_from_index(
    query: str,
    repo_root: Path | None = None,
    *,
    index_path: Path | None = None,
    top_k: int = 5,
    path_hint: str | None = None,
    file_types: set[str] | None = None,
) -> list[RetrievalResult]:
    """Load the local repository index and return ranked chunks."""

    repo_index = load_repo_index(repo_root, index_path=index_path)
    if repo_index is None:
        raise FileNotFoundError("Repository index not found. Run repo-index rebuild first.")
    return retrieve_chunks(
        query,
        repo_index,
        top_k=top_k,
        path_hint=path_hint,
        file_types=file_types,
    )
