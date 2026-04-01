from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .embedding import cosine_similarity


@dataclass(frozen=True)
class IndexedItem:
    """
    Represents one indexed object stored in the vector store.

    This keeps both human-readable metadata and the original searchable text
    alongside the vector representation stored separately.

    Fields:
    - item_id: stable unique identifier for the indexed item
    - item_type: type label such as "plugin"
    - name: display name
    - category: category label used by retrieval
    - text: source text that was embedded
    - metadata: additional structured metadata kept with the item
    """

    item_id: str
    item_type: str
    name: str
    category: str
    text: str
    metadata: Dict[str, object]


@dataclass(frozen=True)
class SearchHit:
    """
    Represents one search result from the vector store.

    Fields:
    - item: the matched indexed item
    - score: cosine similarity score for that match
    """

    item: IndexedItem
    score: float


class JsonVectorStore:
    """
    Lightweight persistent vector store.

    This stores:
    - indexed item metadata
    - sparse embedding vectors

    Storage format:
    - JSON on disk
    - item metadata in one section
    - vectors in another section

    Why this exists:
    - allows retrieval indexes to persist between runs
    - keeps retrieval deterministic and easy to inspect
    - avoids adding heavier dependencies too early

    This is intentionally simple and can be replaced later with a more
    scalable backend such as SQLite, FAISS, or another vector database.
    """

    def __init__(self, path: str | Path):
        # Path where the JSON index file is stored.
        self.path = Path(path).expanduser()

        # Maps item_id -> IndexedItem
        self.items: Dict[str, IndexedItem] = {}

        # Maps item_id -> sparse vector dictionary
        # Example:
        # {
        #   "queue_status": {"queue": 0.42, "running": 0.33},
        #   "docs_gaussian": {"gaussian": 0.61, "docs": 0.20},
        # }
        self.vectors: Dict[str, Dict[str, float]] = {}

    def clear(self) -> None:
        """
        Clear all in-memory indexed items and vectors.

        This only affects in-memory state until save() is called.
        """
        self.items.clear()
        self.vectors.clear()

    def add(self, item: IndexedItem, vector: Dict[str, float]) -> None:
        """
        Add one indexed item and its vector to the in-memory store.

        The item_id is used as the shared key between metadata and vector data.
        """
        self.items[item.item_id] = item
        self.vectors[item.item_id] = dict(vector)

    def bulk_add(self, rows: Iterable[tuple[IndexedItem, Dict[str, float]]]) -> None:
        """
        Add multiple indexed items in one pass.

        Each row is expected to be:
        (IndexedItem, vector_dict)
        """
        for item, vector in rows:
            self.add(item, vector)

    def save(self) -> None:
        """
        Persist the current in-memory store to disk as JSON.

        File contents include:
        - serialized IndexedItem rows
        - vector dictionaries

        The parent directory is created automatically if needed.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Convert dataclass items into plain dictionaries so they can be serialized.
        payload = {
            "items": [asdict(item) for item in self.items.values()],
            "vectors": self.vectors,
        }

        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> bool:
        """
        Load indexed items and vectors from the JSON file on disk.

        Returns:
            True if the file existed and was loaded
            False if no index file exists yet
        """
        if not self.path.exists():
            return False

        payload = json.loads(self.path.read_text(encoding="utf-8"))

        # Rebuild IndexedItem objects from serialized dictionaries.
        self.items = {
            row["item_id"]: IndexedItem(**row) for row in payload.get("items", [])
        }

        # Rebuild vectors and normalize values to float.
        self.vectors = {
            key: {token: float(value) for token, value in vec.items()}
            for key, vec in payload.get("vectors", {}).items()
        }

        return True

    def search(
        self,
        query_vector: Dict[str, float],
        *,
        top_k: int,
        allowed_item_ids: Optional[Iterable[str]] = None,
        min_score: float = 0.0,
    ) -> List[SearchHit]:
        """
        Search the vector store using cosine similarity.

        Flow:
        - optionally restrict search to a subset of item IDs
        - compare the query vector against each stored vector
        - ignore results below the minimum score threshold
        - sort matches by score descending
        - return the top K hits

        Args:
            query_vector: encoded vector for the user query
            top_k: maximum number of results to return
            allowed_item_ids: optional subset of item IDs to search
            min_score: minimum similarity score required to keep a hit

        Returns:
            Ranked list of SearchHit objects
        """
        # If a subset was provided, convert it to a set for fast membership checks.
        allowed = set(allowed_item_ids) if allowed_item_ids is not None else None

        hits: List[SearchHit] = []

        # Compare the query vector against every stored vector that is allowed.
        for item_id, vector in self.vectors.items():
            if allowed is not None and item_id not in allowed:
                continue

            score = cosine_similarity(query_vector, vector)

            # Skip weak matches below the configured threshold.
            if score < min_score:
                continue

            item = self.items[item_id]
            hits.append(SearchHit(item=item, score=score))

        # Highest-scoring results should come first.
        hits.sort(key=lambda hit: hit.score, reverse=True)

        # Return only the requested number of top results.
        return hits[:top_k]
