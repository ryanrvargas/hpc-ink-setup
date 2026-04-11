from __future__ import annotations

import os
import sys
from pathlib import Path

from inkly.config import TomlParser
from inkly.core.runtime import InklyRuntime


# Default Inkly home directory.
# This is where config and other runtime data are expected to live.
DEFAULT_INKLY_HOME = Path.home() / ".inkly"

# Path to the main configuration file.
CONFIG_PATH = DEFAULT_INKLY_HOME / "config.toml"


def _load_config():
    """
    Load the Inkly configuration from the TOML file.

    This uses the TomlParser abstraction so config parsing logic
    stays centralized and consistent across the project.
    """
    parser = TomlParser(CONFIG_PATH)
    return parser.load()


def _build_user_id() -> str:
    """
    Build a user identifier for conversation tracking.

    Uses the USER environment variable when available.
    Falls back to "default" if not set.
    """
    return os.environ.get("USER", "default")


def _build_query(argv: list[str]) -> str:
    """
    Build the query string from CLI arguments.

    All arguments after the command are joined into a single string.
    Leading and trailing whitespace is removed.
    """
    return " ".join(argv).strip()


def main() -> int:
    """
    Main CLI entry point.

    Flow:
    - read CLI arguments and build query string
    - load configuration
    - initialize runtime
    - execute the query
    - print the response

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Build query from command-line arguments.
    query = _build_query(sys.argv[1:])

    # Require a non-empty query.
    if not query:
        print("Usage: ink <prompt>", file=sys.stderr)
        return 1

    try:
        # Load configuration from disk.
        cfg = _load_config()
    except Exception as exc:
        # Fail early if config cannot be loaded or parsed.
        print(f"Inkly config error: {exc}", file=sys.stderr)
        return 1

    try:
        # Initialize runtime and process the query.
        runtime = InklyRuntime(cfg)
        user_id = _build_user_id()
        response = runtime.handle_query(user_id, query)

        # In interactive terminals, the Ollama backend already streams the
        # response directly to stdout. This avoids printing it out once its done.
        if not sys.stdout.isatty():
            print(response)
        elif response and not response.endswith("\n"):
            print()

        return 0
    except Exception as exc:
        # Catch runtime-level failures and report them cleanly.
        print(f"Inkly runtime error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    # Run main() and exit with its return code.
    raise SystemExit(main())
