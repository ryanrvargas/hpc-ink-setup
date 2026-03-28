from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from inkly.plugins.manager import Plugin
from inkly.retrieval.retriever import PluginRetriever


def build_plugins():
    return {
        "jobs_summary": Plugin(
            name="jobs_summary",
            description="Summarizes historical Slurm job outcomes and resource trends.",
            category="job-history",
            example_queries=[
                "Why are jobs failing on this cluster?",
                "Do high-memory jobs fail more often?",
            ],
            run=lambda: "historical job summary",
        ),
        "queue_status": Plugin(
            name="queue_status",
            description="Summarizes the current queue, running jobs, and pending jobs.",
            category="queue-status",
            example_queries=[
                "How busy is the cluster right now?",
                "How many jobs are pending?",
            ],
            run=lambda: "queue summary",
        ),
        "node_info": Plugin(
            name="node_info",
            description="Lists partition limits, node resources, and GPU availability.",
            category="node-info",
            example_queries=[
                "Which nodes have GPUs?",
                "What partitions are available?",
            ],
            run=lambda: "node summary",
        ),
        "docs_gaussian": Plugin(
            name="docs_gaussian",
            description="Provides documentation snippets for Gaussian jobs and examples.",
            category="documentation",
            example_queries=[
                "How do I run Gaussian jobs?",
                "Show me Gaussian documentation.",
            ],
            run=lambda: "gaussian docs",
        ),
    }


def test_retriever_ranks_job_history_query(tmp_path):
    plugins = build_plugins()
    retriever = PluginRetriever(index_path=tmp_path / "retrieval.json", top_k=2)

    results = retriever.search_plugins("Why are my jobs failing?", plugins)

    assert results
    assert results[0].name == "jobs_summary"


def test_retriever_ranks_queue_query(tmp_path):
    plugins = build_plugins()
    retriever = PluginRetriever(index_path=tmp_path / "retrieval.json", top_k=2)

    results = retriever.search_plugins("How busy is the queue right now?", plugins)

    assert results
    assert results[0].name == "queue_status"


def test_retriever_ranks_documentation_query(tmp_path):
    plugins = build_plugins()
    retriever = PluginRetriever(index_path=tmp_path / "retrieval.json", top_k=2)

    results = retriever.search_plugins("How do I run Gaussian on this cluster?", plugins)

    assert results
    assert results[0].name == "docs_gaussian"


def test_classifier_filters_to_relevant_categories(tmp_path):
    plugins = build_plugins()
    retriever = PluginRetriever(index_path=tmp_path / "retrieval.json", top_k=2)
    retriever.rebuild_index(plugins)

    categories = retriever.classify_categories("How many jobs are pending?", plugins)

    assert "queue-status" in categories


def test_retriever_falls_back_when_no_scores(tmp_path):
    plugins = build_plugins()
    retriever = PluginRetriever(index_path=tmp_path / "retrieval.json", top_k=2)

    results = retriever.search_plugins("zxqv unrelated tokens", plugins)

    assert results
    assert len(results) <= 2
