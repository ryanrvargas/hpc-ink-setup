from __future__ import annotations

import os
import sys
from pathlib import Path

from inkly.config import TomlParser
from inkly.core.runtime import InklyRuntime


DEFAULT_INKLY_HOME = Path.home() / ".inkly"
CONFIG_PATH = DEFAULT_INKLY_HOME / "config.toml"


def _load_config():
    parser = TomlParser(CONFIG_PATH)
    return parser.load()


def _build_user_id() -> str:
    return os.environ.get("USER", "default")


def _build_query(argv: list[str]) -> str:
    return " ".join(argv).strip()


def main() -> int:
    query = _build_query(sys.argv[1:])

    if not query:
        print("Usage: ink <prompt>", file=sys.stderr)
        return 1

    try:
        cfg = _load_config()
    except Exception as exc:
        print(f"Inkly config error: {exc}", file=sys.stderr)
        return 1

    try:
        runtime = InklyRuntime(cfg)
        user_id = _build_user_id()
        response = runtime.handle_query(user_id, query)
    except Exception as exc:
        print(f"Inkly runtime error: {exc}", file=sys.stderr)
        return 1

    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
