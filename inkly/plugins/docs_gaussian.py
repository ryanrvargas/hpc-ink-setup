from __future__ import annotations

from inkly.plugins.common import format_plugin_output, validate_plugin_meta


PLUGIN_META = {
    "name": "docs_gaussian",
    "description": (
        "Provides documentation snippets and usage guidance for Gaussian and related "
        "cluster software workflows, including scheduler-oriented usage notes."
    ),
    "category": "documentation",
    "example_queries": [
        "How do I run Gaussian on this cluster?",
        "Show me Gaussian job examples.",
        "What documentation exists for Gaussian jobs?",
        "How should I request resources for Gaussian?",
    ],
}

validate_plugin_meta(PLUGIN_META)


def run(query: str) -> str:
    """Retrieve Gaussian documentation passages relevant to the user's query."""
    try:
        from gaussian_scraper.search import search_docs

        matches = search_docs("gaussian", query, top_k=5)
    except (ImportError, OSError, ValueError):
        return format_plugin_output(
            "Gaussian Documentation",
            ["Gaussian documentation is unavailable."],
        )

    relevant = [match for match in matches if match.score > 0.0]
    if not relevant:
        return format_plugin_output(
            "Gaussian Documentation",
            ["No relevant Gaussian documentation was found for this query."],
        )

    lines: list[str] = []
    for match in relevant:
        lines.append(f"Source: {match.label} | relevance={match.score:.3f}")
        lines.append(match.text)

    return format_plugin_output("Gaussian Documentation", lines)
