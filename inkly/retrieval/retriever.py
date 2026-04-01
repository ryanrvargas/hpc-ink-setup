from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

from inkly.plugins.manager import Plugin

from .classifier import CategoryClassifier
from .embedding import TfidfEmbedder
from .vector_store import IndexedItem, JsonVectorStore


@dataclass(frozen=True)
class RetrievalResult:
    """
    Represents one ranked retrieval hit.

    This is the lightweight result structure returned after vector search.
    It contains enough information for the runtime to understand what matched
    and how strong the match was, without returning the full stored item.
    """

    # Stable identifier for the indexed item.
    item_id: str

    # Human-readable item name.
    name: str

    # Category assigned to the item.
    category: str

    # Similarity score between the query and the indexed item.
    score: float

    # Item type stored in the index.
    # Right now retrieval is plugin-focused, so the default is "plugin".
    item_type: str = "plugin"


class PluginRetriever:
    """
    Handles indexing and retrieval of plugins.

    High-level flow:
    1. Convert plugin metadata into searchable text
    2. Fit the embedder on that plugin text
    3. Encode plugins into vectors and save them in the vector store
    4. Classify likely categories for a user query
    5. Search only within relevant categories when possible
    6. Return ranked plugin matches

    This is the main retrieval layer used by runtime when retrieval is enabled.
    """

    def __init__(
        self,
        *,
        index_path: str | Path,
        top_k: int = 3,
        min_score: float = 0.0,
        fallback_to_all_plugins: bool = True,
    ) -> None:
        # Path where the JSON vector index will be stored on disk.
        self.index_path = Path(index_path).expanduser()

        # Default number of top results to return.
        self.top_k = top_k

        # Minimum score threshold for vector search results.
        self.min_score = min_score

        # If retrieval produces no useful result, this controls whether the
        # runtime falls back to all plugins instead of returning nothing.
        self.fallback_to_all_plugins = fallback_to_all_plugins

        # Embedder used to convert text into vectors.
        self.embedder = TfidfEmbedder()

        # Persistent JSON-backed vector store.
        self.store = JsonVectorStore(self.index_path)

        # Cache of the last plugin mapping seen by this retriever instance.
        # This is mostly useful for keeping the latest plugin view around.
        self._last_plugins: Dict[str, Plugin] = {}

    @staticmethod
    def build_plugin_text(plugin: Plugin) -> str:
        """
        Convert a plugin into a searchable text representation.

        This is the text that gets embedded and indexed.

        The idea is to include the fields that best describe what the plugin does:
        - name
        - category
        - description
        - example queries

        That gives retrieval more semantic information than just using the name.
        """
        parts: List[str] = [
            f"name: {plugin.name}",
            f"category: {plugin.category}",
            f"description: {plugin.description}",
        ]

        # Example queries are included because they often resemble the kinds
        # of real user queries the plugin should match.
        if plugin.example_queries:
            parts.append("example_queries:")
            parts.extend(f"- {query}" for query in plugin.example_queries)

        return "\n".join(parts)

    def rebuild_index(self, plugins: Mapping[str, Plugin]) -> None:
        """
        Rebuild the retrieval index from the current plugin set.

        Steps:
        - store the latest plugin mapping
        - build plugin text for every plugin
        - fit the embedder on plugin text + categories
        - clear any previous vector-store contents
        - encode each plugin
        - save indexed items and vectors to disk
        """
        # Keep a copy of the latest plugin mapping.
        self._last_plugins = dict(plugins)

        # Build text for all plugins so the embedder can learn token importance.
        texts = [self.build_plugin_text(plugin) for plugin in plugins.values()]

        # Fit on plugin text plus category names.
        # Including category names helps the classifier and retriever work
        # with category labels that may also appear in queries.
        self.embedder.fit(texts + list({p.category for p in plugins.values()}))

        # Remove any existing index contents before rebuilding.
        self.store.clear()

        rows = []
        for plugin in plugins.values():
            text = self.build_plugin_text(plugin)

            # IndexedItem stores metadata + original searchable text.
            item = IndexedItem(
                item_id=plugin.name,
                item_type="plugin",
                name=plugin.name,
                category=plugin.category,
                text=text,
                metadata={"example_queries": list(plugin.example_queries)},
            )

            # Encode the plugin text into a sparse vector.
            vector = self.embedder.encode(text)

            rows.append((item, vector))

        # Bulk insert all rows into the vector store, then persist to disk.
        self.store.bulk_add(rows)
        self.store.save()

    def _ensure_index(self, plugins: Mapping[str, Plugin]) -> None:
        """
        Ensure a usable retrieval index exists for the current plugin set.

        Reuse path:
        - load the saved index from disk
        - if indexed item IDs match current plugin IDs, reuse the store
        - refit the embedder from stored item text

        Rebuild path:
        - if the store is missing or plugin IDs changed, rebuild the index
        """
        # store.load() returns True if an index file exists and was loaded.
        # set(self.store.items) gives the indexed item IDs.
        # set(plugins) gives the current plugin mapping keys.
        if self.store.load() and set(self.store.items) == set(plugins):
            self._last_plugins = dict(plugins)

            # Refit the embedder from the stored item text so new queries can be encoded
            # against the same vocabulary used for the indexed vectors.
            texts = [item.text for item in self.store.items.values()]
            self.embedder.fit(texts + list({p.category for p in plugins.values()}))
            return

        # Rebuild if there is no usable index or the plugin set changed.
        self.rebuild_index(plugins)

    def classify_categories(
        self,
        query: str,
        plugins: Mapping[str, Plugin],
        *,
        top_n: int = 2,
    ) -> List[str]:
        """
        Predict the most relevant categories for the query.

        This is a pre-filtering step before vector search.

        Why this exists:
        - reduces search space
        - improves focus
        - avoids searching every plugin when only some categories are likely relevant

        Fallback behavior:
        - if all category scores are <= 0, return all categories
        """
        # Extract category labels from the current plugin set.
        categories = [plugin.category for plugin in plugins.values()]

        # Build a category classifier using the same embedder.
        classifier = CategoryClassifier(self.embedder, categories)

        # Score the query against category prototypes.
        predictions = classifier.predict(query, top_n=top_n)

        # Keep only positively scored categories.
        # If none score above zero, fall back to every category.
        return [row.category for row in predictions if row.score > 0.0] or list(
            dict.fromkeys(categories)
        )

    def search_plugins(
        self,
        query: str,
        plugins: Mapping[str, Plugin],
        *,
        top_k: int | None = None,
    ) -> List[RetrievalResult]:
        """
        Search for the best plugin matches for a query.

        High-level flow:
        - ensure the index exists
        - classify likely categories
        - restrict candidate plugin IDs to those categories
        - encode the query
        - run vector search
        - optionally fall back to all plugins if no hit is found

        Returns:
            Ranked retrieval results
        """
        # No plugins means nothing to search.
        if not plugins:
            return []

        # Make sure the vector store and embedder are ready.
        self._ensure_index(plugins)

        # Use provided top_k or fall back to configured default.
        top_k = top_k or self.top_k

        # Predict which categories are most relevant to the query.
        predicted_categories = set(self.classify_categories(query, plugins))

        # Restrict search to plugins in those predicted categories.
        allowed_ids = [
            plugin.name
            for plugin in plugins.values()
            if plugin.category in predicted_categories
        ]

        # If category filtering produces no candidates and fallback is enabled,
        # allow all plugins.
        if not allowed_ids and self.fallback_to_all_plugins:
            allowed_ids = list(plugins)

        # Encode the user query into a vector using the same fitted embedder.
        query_vector = self.embedder.encode(query)

        # Search the vector store for the best matching indexed items.
        hits = self.store.search(
            query_vector,
            top_k=top_k,
            allowed_item_ids=allowed_ids,
            min_score=self.min_score,
        )

        # If restricted search finds nothing and fallback is enabled,
        # rerun search across all plugins with a looser score threshold.
        if not hits and self.fallback_to_all_plugins:
            hits = self.store.search(
                query_vector,
                top_k=top_k,
                allowed_item_ids=list(plugins),
                min_score=0.0,
            )

        # Convert vector-store hits into lightweight retrieval results.
        return [
            RetrievalResult(
                item_id=hit.item.item_id,
                name=hit.item.name,
                category=hit.item.category,
                score=hit.score,
                item_type=hit.item.item_type,
            )
            for hit in hits
        ]

    def select_plugins(
        self,
        query: str,
        plugins: Mapping[str, Plugin],
        *,
        top_k: int | None = None,
    ) -> Sequence[Plugin]:
        """
        Return actual Plugin objects selected for execution.

        This is the final step the runtime cares about.

        Flow:
        - run search_plugins() to get ranked matches
        - if nothing is found and fallback is enabled, return all plugins
        - otherwise map retrieval results back to Plugin objects
        """
        results = self.search_plugins(query, plugins, top_k=top_k)

        # Final fallback path if retrieval produces nothing usable.
        if not results and self.fallback_to_all_plugins:
            return list(plugins.values())

        # Map result names back to the original plugin objects.
        return [plugins[result.name] for result in results if result.name in plugins]