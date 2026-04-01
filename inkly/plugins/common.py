from __future__ import annotations

from typing import Any, Mapping


# Required metadata fields every plugin must define.
# Keeping this centralized ensures consistent validation across all plugins.
REQUIRED_PLUGIN_META_FIELDS = (
    "name",
    "description",
    "category",
    "example_queries",
)


def validate_plugin_meta(meta: Mapping[str, Any]) -> None:
    """
    Validates that a plugin's PLUGIN_META follows the expected structure.

    This is used to:
    - enforce consistent plugin metadata
    - prevent malformed plugins from entering the system
    - ensure retrieval and discovery logic have reliable inputs

    Raises:
        ValueError: If metadata is missing required fields or contains invalid values.
    """
    # PLUGIN_META must behave like a dictionary/mapping.
    if not isinstance(meta, Mapping):
        raise ValueError("PLUGIN_META must be a mapping")

    # Ensure all required fields are present.
    for field in REQUIRED_PLUGIN_META_FIELDS:
        if field not in meta:
            raise ValueError(f"PLUGIN_META missing required field: {field}")

    # Validate name field.
    if not isinstance(meta["name"], str) or not meta["name"].strip():
        raise ValueError("PLUGIN_META['name'] must be a non-empty string")

    # Validate description field.
    if not isinstance(meta["description"], str) or not meta["description"].strip():
        raise ValueError("PLUGIN_META['description'] must be a non-empty string")

    # Validate category field.
    if not isinstance(meta["category"], str) or not meta["category"].strip():
        raise ValueError("PLUGIN_META['category'] must be a non-empty string")

    # Validate example_queries field.
    example_queries = meta["example_queries"]
    if not isinstance(example_queries, list):
        raise ValueError("PLUGIN_META['example_queries'] must be a list of strings")

    # Must contain at least one example query for retrieval usefulness.
    if not example_queries:
        raise ValueError("PLUGIN_META['example_queries'] must not be empty")

    # Ensure all example queries are valid strings.
    for query in example_queries:
        if not isinstance(query, str) or not query.strip():
            raise ValueError(
                "PLUGIN_META['example_queries'] entries must be non-empty strings"
            )


def format_plugin_output(title: str, body_lines: list[str]) -> str:
    """
    Formats plugin output into a consistent, LLM-friendly text block.

    Rules:
    - First line is the title
    - Remaining lines are the body
    - Empty or whitespace-only lines are removed
    - Title must not be empty

    Returns:
        A newline-separated string with the title followed by body lines.

    Raises:
        ValueError: If the title is empty after trimming.
    """
    # Normalize title to avoid whitespace-only values.
    clean_title = title.strip()

    # Normalize body lines and remove empty entries.
    clean_lines = [line.strip() for line in body_lines if line and line.strip()]

    if not clean_title:
        raise ValueError("Plugin output title must be non-empty")

    # Combine title and body into a single formatted block.
    return "\n".join([clean_title, *clean_lines])
