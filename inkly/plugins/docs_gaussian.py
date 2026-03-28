from __future__ import annotations

PLUGIN_META = {
    "name": "docs_gaussian",
    "description": "Provides documentation snippets and usage guidance for Gaussian jobs and software-specific scheduler examples.",
    "category": "documentation",
    "example_queries": [
        "How do I run Gaussian on this cluster?",
        "Show me Gaussian job examples.",
        "What documentation exists for Gaussian jobs?",
    ],
}


def run() -> str:
    return "Gaussian docs: load the Gaussian module, request adequate memory, and use scheduler examples from the cluster documentation."
