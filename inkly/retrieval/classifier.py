from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from .embedding import TfidfEmbedder, cosine_similarity


# These are the default prototype texts for each plugin category.
# Each category is represented by a short bag of words describing the kind of
# queries that category should match.
#
# Example:
# - "queue-status" is associated with words like queue, running, pending, squeue
# - "documentation" is associated with words like docs, examples, modules, gaussian
#
# The classifier compares the user's query against these prototype texts
# to estimate which categories are most relevant.
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
    """
    Represents one category-scoring result.

    Fields:
    - category: category name, such as "queue-status"
    - score: similarity score between the query and that category prototype
    """

    category: str
    score: float


class CategoryClassifier:
    """
    Lightweight embedding-based category classifier.

    This classifier does not use a trained ML model.
    Instead, it compares the user query against a small prototype text
    for each category and scores similarity using embeddings.

    Why this exists:
    - keeps retrieval simple and deterministic
    - avoids heavyweight dependencies
    - gives retrieval a first-pass category filter before plugin ranking

    High-level idea:
    1. Turn the query into an embedding
    2. Turn each category prototype into an embedding
    3. Compare the query to each category
    4. Return the top scoring categories
    """

    def __init__(
        self,
        embedder: TfidfEmbedder,
        categories: Iterable[str],
        category_prototypes: Dict[str, str] | None = None,
    ) -> None:
        # Shared embedder used to encode both queries and category text.
        self.embedder = embedder

        # Remove duplicates while preserving order.
        # This avoids scoring the same category multiple times.
        self.categories = list(dict.fromkeys(categories))

        # Start with built-in prototype text.
        # Custom prototypes can override or extend these defaults.
        prototypes = dict(DEFAULT_CATEGORY_PROTOTYPES)
        if category_prototypes:
            prototypes.update(category_prototypes)

        # Build the final lookup of category -> prototype text.
        #
        # If a category does not exist in the prototype dictionary,
        # fall back to a simple version of its name with hyphens replaced by spaces.
        # Example:
        # "queue-status" -> "queue status"
        self.category_text = {
            category: prototypes.get(category, category.replace("-", " "))
            for category in self.categories
        }

    def predict(self, query: str, top_n: int = 2) -> List[CategoryPrediction]:
        """
        Score the query against all categories and return the top matches.

        Flow:
        - encode the query into a vector
        - encode each category prototype into a vector
        - compute cosine similarity between the query and each category
        - sort by score descending
        - return the top N predictions

        Args:
            query: User query text
            top_n: Number of best-scoring categories to return

        Returns:
            A list of CategoryPrediction objects sorted by score descending
        """
        # Encode the user query once.
        query_vec = self.embedder.encode(query)

        predictions: List[CategoryPrediction] = []

        # Compare the query to each category prototype.
        for category in self.categories:
            category_vec = self.embedder.encode(self.category_text[category])
            score = cosine_similarity(query_vec, category_vec)

            predictions.append(CategoryPrediction(category=category, score=score))

        # Highest score means the query is most similar to that category.
        predictions.sort(key=lambda row: row.score, reverse=True)

        # Return only the top requested number of matches.
        return predictions[:top_n]
