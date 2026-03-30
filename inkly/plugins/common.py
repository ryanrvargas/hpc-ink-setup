from __future__ import annotations

from typing import Any, Mapping


REQUIRED_PLUGIN_META_FIELDS = (
    "name",
    "description",
    "category",
    "example_queries",
)


def validate_plugin_meta(meta: Mapping[str, Any]) -> None:
    """
    Validate the required metadata fields for an Inkly plug-in.

    This keeps retrieval metadata predictable and avoids malformed plug-ins.
    Raises ValueError if the metadata is invalid.
    """
    if not isinstance(meta, Mapping):
        raise ValueError("PLUGIN_META must be a mapping")

    for field in REQUIRED_PLUGIN_META_FIELDS:
        if field not in meta:
            raise ValueError(f"PLUGIN_META missing required field: {field}")

    if not isinstance(meta["name"], str) or not meta["name"].strip():
        raise ValueError("PLUGIN_META['name'] must be a non-empty string")

    if not isinstance(meta["description"], str) or not meta["description"].strip():
        raise ValueError("PLUGIN_META['description'] must be a non-empty string")

    if not isinstance(meta["category"], str) or not meta["category"].strip():
        raise ValueError("PLUGIN_META['category'] must be a non-empty string")

    example_queries = meta["example_queries"]
    if not isinstance(example_queries, list):
        raise ValueError("PLUGIN_META['example_queries'] must be a list of strings")

    if not example_queries:
        raise ValueError("PLUGIN_META['example_queries'] must not be empty")

    for query in example_queries:
        if not isinstance(query, str) or not query.strip():
            raise ValueError(
                "PLUGIN_META['example_queries'] entries must be non-empty strings"
            )


def format_plugin_output(title: str, body_lines: list[str]) -> str:
    """
    Format plug-in output into a simple, LLM-friendly block.

    Rules:
    - first line is a short heading
    - remaining lines are concise informational lines
    - blank / whitespace-only lines are removed
    """
    clean_title = title.strip()
    clean_lines = [line.strip() for line in body_lines if line and line.strip()]

    if not clean_title:
        raise ValueError("Plugin output title must be non-empty")

    return "\n".join([clean_title, *clean_lines])
