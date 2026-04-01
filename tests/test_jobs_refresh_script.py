from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import scripts.jobs_refresh as jobs_refresh


@dataclass
class FakeSummary:
    """
    Lightweight stand-in for the real RefreshSummary object.

    This keeps the test focused on script behavior instead of requiring
    the full ingestion pipeline to run.
    """

    jobs_scanned: int
    jobs_inserted: int
    jobs_updated: int
    jobs_removed: int
    window_days: int


def test_build_parser_defaults():
    """
    The refresh script should expose stable default argument values.

    This verifies the CLI remains predictable even when no flags are passed.
    """
    parser = jobs_refresh.build_parser()
    args = parser.parse_args([])

    assert args.window_days == 90
    assert args.db_path == "~/.inkly/jobs.db"


def test_build_parser_custom_values():
    """
    The refresh script should accept custom window and database path values.
    """
    parser = jobs_refresh.build_parser()
    args = parser.parse_args(
        ["--window-days", "20", "--db-path", "/tmp/custom_jobs.db"]
    )

    assert args.window_days == 20
    assert args.db_path == "/tmp/custom_jobs.db"


def test_main_initializes_db_and_refreshes(monkeypatch, capsys, tmp_path):
    """
    main() should:
    - parse CLI args
    - initialize the database
    - call refresh_jobs with the resolved db path
    - print the summary fields
    """
    calls = {}

    def fake_initialize_jobs_db(db_path):
        calls["initialize_jobs_db"] = Path(db_path)
        return Path(db_path)

    def fake_refresh_jobs(window_days, db_path):
        calls["refresh_jobs"] = {
            "window_days": window_days,
            "db_path": Path(db_path),
        }
        return FakeSummary(
            jobs_scanned=123,
            jobs_inserted=45,
            jobs_updated=6,
            jobs_removed=7,
            window_days=window_days,
        )

    monkeypatch.setattr(jobs_refresh, "initialize_jobs_db", fake_initialize_jobs_db)
    monkeypatch.setattr(jobs_refresh, "refresh_jobs", fake_refresh_jobs)
    monkeypatch.setattr(
        "sys.argv",
        [
            "jobs_refresh.py",
            "--window-days",
            "20",
            "--db-path",
            str(tmp_path / "jobs.db"),
        ],
    )

    exit_code = jobs_refresh.main()
    captured = capsys.readouterr()

    assert exit_code == 0

    expected_db_path = tmp_path / "jobs.db"

    assert calls["initialize_jobs_db"] == expected_db_path
    assert calls["refresh_jobs"] == {
        "window_days": 20,
        "db_path": expected_db_path,
    }

    output = captured.out
    assert "Job refresh complete." in output
    assert "Window days: 20" in output
    assert "Jobs scanned: 123" in output
    assert "Jobs inserted: 45" in output
    assert "Jobs updated(changed): 6" in output
    assert "Jobs removed: 7" in output
    assert f"Database: {expected_db_path}" in output


def test_main_uses_default_db_path(monkeypatch, capsys):
    """
    When no db path is provided, the script should use its documented default.
    """
    calls = {}

    def fake_initialize_jobs_db(db_path):
        calls["initialize_jobs_db"] = Path(db_path).expanduser()
        return Path(db_path).expanduser()

    def fake_refresh_jobs(window_days, db_path):
        calls["refresh_jobs"] = {
            "window_days": window_days,
            "db_path": Path(db_path).expanduser(),
        }
        return FakeSummary(
            jobs_scanned=10,
            jobs_inserted=2,
            jobs_updated=1,
            jobs_removed=0,
            window_days=window_days,
        )

    monkeypatch.setattr(jobs_refresh, "initialize_jobs_db", fake_initialize_jobs_db)
    monkeypatch.setattr(jobs_refresh, "refresh_jobs", fake_refresh_jobs)
    monkeypatch.setattr(
        "sys.argv",
        ["jobs_refresh.py"],
    )

    exit_code = jobs_refresh.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert calls["refresh_jobs"]["window_days"] == 90
    assert calls["initialize_jobs_db"] == calls["refresh_jobs"]["db_path"]

    output = captured.out
    assert "Window days: 90" in output
    assert "Jobs scanned: 10" in output
    assert "Jobs inserted: 2" in output
    assert "Jobs updated(changed): 1" in output
    assert "Jobs removed: 0" in output