from __future__ import annotations

from inkly.plugins.common import format_plugin_output, validate_plugin_meta
from inkly.plugins.docs_data import DOC_SNIPPETS


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


def run() -> str:
    lines = DOC_SNIPPETS.get("gaussian", [])

    if not lines:
        return format_plugin_output(
            "Gaussian Documentation Snippets",
            ["Gaussian documentation snippets are unavailable."],
        )

    title = lines[0]
    body = lines[1:]

    return format_plugin_output(title, body)
