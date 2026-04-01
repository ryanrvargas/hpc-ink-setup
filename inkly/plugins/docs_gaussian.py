from __future__ import annotations

from inkly.plugins.common import format_plugin_output, validate_plugin_meta
from inkly.plugins.docs_data import DOC_SNIPPETS


# Metadata describing this plugin.
# This is used by:
# - plugin discovery
# - retrieval ranking
# - documentation / explainability
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

# Validate metadata at import time so invalid plugins fail fast.
validate_plugin_meta(PLUGIN_META)


def run() -> str:
    """
    Entry point for the Gaussian documentation plugin.

    This retrieves pre-defined documentation snippets and formats them
    into a consistent output block for the runtime and LLM.

    Behavior:
    - If snippets exist → return formatted title + body
    - If missing → return a fallback message
    """

    # Fetch Gaussian documentation snippets from shared data source.
    lines = DOC_SNIPPETS.get("gaussian", [])

    # If no documentation is available, return a safe fallback message.
    if not lines:
        return format_plugin_output(
            "Gaussian Documentation Snippets",
            ["Gaussian documentation snippets are unavailable."],
        )

    # First line is treated as the title, remaining lines as the body.
    title = lines[0]
    body = lines[1:]

    # Format into a clean, LLM-friendly block.
    return format_plugin_output(title, body)
