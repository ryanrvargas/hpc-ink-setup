from __future__ import annotations

import sys
import types
from types import SimpleNamespace

from inkly.plugins import docs_gaussian


def _install_search(monkeypatch, search_docs):
    package = types.ModuleType("gaussian_scraper")
    search = types.ModuleType("gaussian_scraper.search")
    search.search_docs = search_docs
    monkeypatch.setitem(sys.modules, "gaussian_scraper", package)
    monkeypatch.setitem(sys.modules, "gaussian_scraper.search", search)


def test_run_queries_scraper_and_includes_provenance(monkeypatch):
    calls = []

    def search_docs(domain, query, *, top_k):
        calls.append((domain, query, top_k))
        return [
            SimpleNamespace(
                label="Gaussian Slurm Guide",
                text="Load the Gaussian module before submitting the job.",
                score=0.75,
            )
        ]

    _install_search(monkeypatch, search_docs)

    output = docs_gaussian.run("How do I submit a Gaussian job?")

    assert calls == [("gaussian", "How do I submit a Gaussian job?", 5)]
    assert "Source: Gaussian Slurm Guide | relevance=0.750" in output
    assert "Load the Gaussian module before submitting the job." in output


def test_run_drops_zero_score_matches(monkeypatch):
    def search_docs(domain, query, *, top_k):
        return [SimpleNamespace(label="Unrelated", text="Other text", score=0.0)]

    _install_search(monkeypatch, search_docs)

    output = docs_gaussian.run("Gaussian memory")

    assert "No relevant Gaussian documentation was found for this query." in output
    assert "Other text" not in output


def test_run_handles_missing_scraper(monkeypatch):
    monkeypatch.delitem(sys.modules, "gaussian_scraper", raising=False)
    monkeypatch.delitem(sys.modules, "gaussian_scraper.search", raising=False)

    real_import = __import__

    def fail_scraper_import(name, *args, **kwargs):
        if name.startswith("gaussian_scraper"):
            raise ImportError("scraper unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fail_scraper_import)

    output = docs_gaussian.run("Gaussian")

    assert "Gaussian documentation is unavailable." in output
