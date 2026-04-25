from __future__ import annotations

import argparse

from repo_assistant.commands.ask import handle_ask
from repo_assistant.commands.explain import handle_explain
from repo_assistant.commands.trace import handle_trace
from repo_assistant.commands.repo_index import (
    handle_doctor,
    handle_rebuild,
    handle_stats,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repochat",
        description="Repository-aware assistant CLI.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser("ask", help="Ask a repo question.")
    ask_parser.add_argument("question", help="Question about the repository.")
    ask_parser.set_defaults(handler=handle_ask)

    explain_parser = subparsers.add_parser("explain", help="Explain a file.")
    explain_parser.add_argument("path", help="Path to the file to explain.")
    explain_parser.set_defaults(handler=handle_explain)

    trace_parser = subparsers.add_parser("trace", help="Trace a repo flow.")
    trace_parser.add_argument("question", help="Flow or behavior to trace.")
    trace_parser.set_defaults(handler=handle_trace)

    index_parser = subparsers.add_parser("repo-index", help="Manage the repo index.")
    index_subparsers = index_parser.add_subparsers(
        dest="index_command",
        required=True,
    )

    rebuild_parser = index_subparsers.add_parser("rebuild", help="Rebuild index.")
    rebuild_parser.set_defaults(handler=handle_rebuild)

    stats_parser = index_subparsers.add_parser("stats", help="Show index stats.")
    stats_parser.set_defaults(handler=handle_stats)

    doctor_parser = index_subparsers.add_parser("doctor", help="Run health checks.")
    doctor_parser.set_defaults(handler=handle_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
