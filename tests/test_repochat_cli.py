from __future__ import annotations

import pytest

import repo_assistant.cli as cli


def test_build_parser_shows_expected_commands() -> None:
    """
    Make sure the main help text shows the planned command surface.
    """
    parser = cli.build_parser()
    help_text = parser.format_help()

    assert "ask" in help_text
    assert "explain" in help_text
    assert "trace" in help_text
    assert "repo-index" in help_text


def test_build_parser_shows_repo_index_subcommands() -> None:
    """
    Make sure repo-index exposes rebuild, stats, and doctor.
    """
    parser = cli.build_parser()
    index_action = next(
        action
        for action in parser._actions
        if getattr(action, "dest", None) == "command"
    )

    repo_index_parser = index_action.choices["repo-index"]
    repo_index_help = repo_index_parser.format_help()

    assert "rebuild" in repo_index_help
    assert "stats" in repo_index_help
    assert "doctor" in repo_index_help


def test_main_dispatches_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    main() should route ask to the ask handler and pass parsed args.
    """
    captured: dict[str, object] = {}

    def fake_handle_ask(args) -> int:
        captured["question"] = args.question
        return 11

    monkeypatch.setattr(cli, "handle_ask", fake_handle_ask)

    exit_code = cli.main(["ask", "How does the backend work?"])

    assert exit_code == 11
    assert captured["question"] == "How does the backend work?"


def test_main_dispatches_explain(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    main() should route explain to the explain handler and pass parsed args.
    """
    captured: dict[str, object] = {}

    def fake_handle_explain(args) -> int:
        captured["path"] = args.path
        return 12

    monkeypatch.setattr(cli, "handle_explain", fake_handle_explain)

    exit_code = cli.main(["explain", "inkly/core/runtime.py"])

    assert exit_code == 12
    assert captured["path"] == "inkly/core/runtime.py"


def test_main_dispatches_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    main() should route trace to the trace handler and pass parsed args.
    """
    captured: dict[str, object] = {}

    def fake_handle_trace(args) -> int:
        captured["question"] = args.question
        return 13

    monkeypatch.setattr(cli, "handle_trace", fake_handle_trace)

    exit_code = cli.main(["trace", "How does a query flow through the system?"])

    assert exit_code == 13
    assert captured["question"] == "How does a query flow through the system?"


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected_code"),
    [
        (["repo-index", "rebuild"], "handle_rebuild", 21),
        (["repo-index", "stats"], "handle_stats", 22),
        (["repo-index", "doctor"], "handle_doctor", 23),
    ],
)
def test_main_dispatches_repo_index_subcommands(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    handler_name: str,
    expected_code: int,
) -> None:
    """
    main() should route each repo-index subcommand to the correct handler.
    """
    calls: dict[str, bool] = {}

    def fake_handler(args) -> int:
        calls["called"] = True
        return expected_code

    monkeypatch.setattr(cli, handler_name, fake_handler)

    exit_code = cli.main(argv)

    assert exit_code == expected_code
    assert calls["called"] is True


def test_main_invalid_command_exits_cleanly() -> None:
    """
    Invalid command usage should raise SystemExit from argparse.
    """
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["bad-command"])

    assert exc_info.value.code == 2


def test_main_missing_repo_index_subcommand_exits_cleanly() -> None:
    """
    repo-index without rebuild/stats/doctor should fail with argparse usage error.
    """
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["repo-index"])

    assert exc_info.value.code == 2