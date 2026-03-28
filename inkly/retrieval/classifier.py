from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from .embedding import TfidfEmbedder, cosine_similarity


DEFAULT_CATEGORY_PROTOTYPES: Dict[str, str] = {
    "job-history": (
        "historical jobs failures success rates analytics sacct job database "
        "resource trends partitions memory cpu"
    ),
    "queue-status": (
        "current queue running jobs pending jobs cluster load queue status "
        "squeue sinfo availability"
    ),
    "node-info": (
        "node partition hardware limits resources gpu cpu memory cluster nodes"
    ),
    "documentation": (
        "documentation usage guide software examples gaussian cuda modules docs"
    ),
}


@dataclass(frozen=True)
class CategoryPrediction:
    category: str
    score: float


class CategoryClassifier:
    """
    Lightweight embedding-based classifier.

    It uses category prototype texts instead of a trained ML model so the
    behavior stays deterministic and easy to debug while still satisfying the
    milestone requirement for a simple category classifier.
    """

    def __init__(
        self,
        embedder: TfidfEmbedder,
        categories: Iterable[str],
        category_prototypes: Dict[str, str] | None = None,
    ) -> None:
        self.embedder = embedder
        self.categories = list(dict.fromkeys(categories))
        prototypes = dict(DEFAULT_CATEGORY_PROTOTYPES)
        if category_prototypes:
            prototypes.update(category_prototypes)
        self.category_text = {
            category: prototypes.get(category, category.replace("-", " "))
            for category in self.categories
        }

    def predict(self, query: str, top_n: int = 2) -> List[CategoryPrediction]:
        query_vec = self.embedder.encode(query)
        predictions: List[CategoryPrediction] = []

        for category in self.categories:
            category_vec = self.embedder.encode(self.category_text[category])
            score = cosine_similarity(query_vec, category_vec)
            predictions.append(CategoryPrediction(category=category, score=score))

        predictions.sort(key=lambda row: row.score, reverse=True)
        return predictions[:top_n]
