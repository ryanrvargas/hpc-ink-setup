#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from inkly.db import initialize_jobs_db
from inkly.jobs import refresh_jobs


def build_parser() -> argparse.ArgumentParser:
    """
    Build the command-line parser for the job refresh script.

    Supported options:
    - --window-days
        Controls how many days of job history sacct should query.

    - --db-path
        Allows refreshes against a non-default database path for testing
        or alternate deployments.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the Inkly job-history SQLite database from sacct "
            "and rebuild intelligence summaries."
        )
    )

    parser.add_argument(
        "--window-days",
        type=int,
        default=90,
        help="Number of days of sacct history to ingest (default: 90).",
    )

    parser.add_argument(
        "--db-path",
        default="~/.inkly/jobs.db",
        help="Path to the SQLite jobs database (default: ~/.inkly/jobs.db).",
    )

    return parser


def main() -> int:
    """
    Refresh the job-history database and print a human-readable summary.

    Flow:
    - parse command-line arguments
    - ensure the database/schema exists
    - run refresh against sacct
    - print a compact summary for the user or scheduler log
    """
    parser = build_parser()
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser()

    # Make sure the database exists before refresh starts.
    # This keeps the script safe to run on a fresh install.
    initialize_jobs_db(db_path)

    summary = refresh_jobs(
        window_days=args.window_days,
        db_path=db_path,
    )

    print("Job refresh complete.")
    print(f"Window days: {summary.window_days}")
    print(f"Jobs scanned: {summary.jobs_scanned}")
    print(f"Jobs inserted: {summary.jobs_inserted}")
    print(f"Jobs updated(changed): {summary.jobs_updated}")
    print(f"Jobs removed: {summary.jobs_removed}")
    print(f"Database: {db_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
