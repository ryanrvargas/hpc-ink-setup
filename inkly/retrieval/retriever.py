from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

from inkly.plugins.manager import Plugin

from .classifier import CategoryClassifier
from .embedding import TfidfEmbedder
from .vector_store import IndexedItem, JsonVectorStore


@dataclass(frozen=True)
class RetrievalResult:
    item_id: str
    name: str
    category: str
    score: float
    item_type: str = "plugin"


class PluginRetriever:
    def __init__(
        self,
        *,
        index_path: str | Path,
        top_k: int = 3,
        min_score: float = 0.0,
        fallback_to_all_plugins: bool = True,
    ) -> None:
        self.index_path = Path(index_path).expanduser()
        self.top_k = top_k
        self.min_score = min_score
        self.fallback_to_all_plugins = fallback_to_all_plugins
        self.embedder = TfidfEmbedder()
        self.store = JsonVectorStore(self.index_path)
        self._last_plugins: Dict[str, Plugin] = {}

    @staticmethod
    def build_plugin_text(plugin: Plugin) -> str:
        parts: List[str] = [
            f"name: {plugin.name}",
            f"category: {plugin.category}",
            f"description: {plugin.description}",
        ]
        if plugin.example_queries:
            parts.append("example_queries:")
            parts.extend(f"- {query}" for query in plugin.example_queries)
        return "\n".join(parts)

    def rebuild_index(self, plugins: Mapping[str, Plugin]) -> None:
        self._last_plugins = dict(plugins)
        texts = [self.build_plugin_text(plugin) for plugin in plugins.values()]
        self.embedder.fit(texts + list({p.category for p in plugins.values()}))
        self.store.clear()

        rows = []
        for plugin in plugins.values():
            text = self.build_plugin_text(plugin)
            item = IndexedItem(
                item_id=plugin.name,
                item_type="plugin",
                name=plugin.name,
                category=plugin.category,
                text=text,
                metadata={"example_queries": list(plugin.example_queries)},
            )
            vector = self.embedder.encode(text)
            rows.append((item, vector))

        self.store.bulk_add(rows)
        self.store.save()

    def _ensure_index(self, plugins: Mapping[str, Plugin]) -> None:
        if self.store.load() and set(self.store.items) == set(plugins):
            self._last_plugins = dict(plugins)
            texts = [item.text for item in self.store.items.values()]
            self.embedder.fit(texts + list({p.category for p in plugins.values()}))
            return
        self.rebuild_index(plugins)

    def classify_categories(
        self,
        query: str,
        plugins: Mapping[str, Plugin],
        *,
        top_n: int = 2,
    ) -> List[str]:
        categories = [plugin.category for plugin in plugins.values()]
        classifier = CategoryClassifier(self.embedder, categories)
        predictions = classifier.predict(query, top_n=top_n)
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
        if not plugins:
            return []

        self._ensure_index(plugins)
        top_k = top_k or self.top_k
        predicted_categories = set(self.classify_categories(query, plugins))

        allowed_ids = [
            plugin.name
            for plugin in plugins.values()
            if plugin.category in predicted_categories
        ]
        if not allowed_ids and self.fallback_to_all_plugins:
            allowed_ids = list(plugins)

        query_vector = self.embedder.encode(query)
        hits = self.store.search(
            query_vector,
            top_k=top_k,
            allowed_item_ids=allowed_ids,
            min_score=self.min_score,
        )

        if not hits and self.fallback_to_all_plugins:
            hits = self.store.search(
                query_vector,
                top_k=top_k,
                allowed_item_ids=list(plugins),
                min_score=0.0,
            )

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
        results = self.search_plugins(query, plugins, top_k=top_k)
        if not results and self.fallback_to_all_plugins:
            return list(plugins.values())
        return [plugins[result.name] for result in results if result.name in plugins]
