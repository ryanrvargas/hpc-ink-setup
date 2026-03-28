from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .embedding import cosine_similarity


@dataclass(frozen=True)
class IndexedItem:
    item_id: str
    item_type: str
    name: str
    category: str
    text: str
    metadata: Dict[str, object]


@dataclass(frozen=True)
class SearchHit:
    item: IndexedItem
    score: float


class JsonVectorStore:
    """
    Lightweight persistent vector store.

    Stores normalized sparse vectors and metadata in JSON so the retriever can:
    - rebuild the index
    - persist embeddings between runs
    - search with cosine similarity

    This is intentionally small and easy to replace later with FAISS/SQLite/etc.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.items: Dict[str, IndexedItem] = {}
        self.vectors: Dict[str, Dict[str, float]] = {}

    def clear(self) -> None:
        self.items.clear()
        self.vectors.clear()

    def add(self, item: IndexedItem, vector: Dict[str, float]) -> None:
        self.items[item.item_id] = item
        self.vectors[item.item_id] = dict(vector)

    def bulk_add(self, rows: Iterable[tuple[IndexedItem, Dict[str, float]]]) -> None:
        for item, vector in rows:
            self.add(item, vector)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "items": [asdict(item) for item in self.items.values()],
            "vectors": self.vectors,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> bool:
        if not self.path.exists():
            return False

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.items = {
            row["item_id"]: IndexedItem(**row) for row in payload.get("items", [])
        }
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
        allowed = set(allowed_item_ids) if allowed_item_ids is not None else None
        hits: List[SearchHit] = []

        for item_id, vector in self.vectors.items():
            if allowed is not None and item_id not in allowed:
                continue
            score = cosine_similarity(query_vector, vector)
            if score < min_score:
                continue
            item = self.items[item_id]
            hits.append(SearchHit(item=item, score=score))

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]
