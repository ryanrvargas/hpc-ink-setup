from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Default location for the Inkly jobs database.
# This database stores both raw job records and computed intelligence summaries.
DEFAULT_DB_PATH = Path.home() / ".inkly" / "jobs.db"


# Full SQLite schema for Issue 5 job-history system.
#
# Main table:
# - jobs
#   Stores one normalized record per top-level Slurm job, including:
#   - resource requests
#   - lifecycle timestamps (submit/start/end)
#   - raw and derived exit information
#
# Indexes are created on commonly queried fields to support fast analytics.
#
# Summary tables:
# - intelligence_partition_stats
# - intelligence_cpu_bucket_stats
# - intelligence_memory_bucket_stats
# - intelligence_failure_stats
# - intelligence_metadata
#
# These are rebuilt from the jobs table and used by plug-ins to avoid
# expensive queries during runtime.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT UNIQUE NOT NULL,
    user TEXT,
    account TEXT,
    partition TEXT,
    alloc_cpus INTEGER,
    req_mem_mb INTEGER,
    submit_time TEXT,
    start_time TEXT,
    end_time TEXT,
    elapsed_sec INTEGER,
    state TEXT,
    exit_code TEXT,
    derived_exit_code TEXT,
    success INTEGER,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_partition ON jobs(partition);
CREATE INDEX IF NOT EXISTS idx_jobs_success ON jobs(success);
CREATE INDEX IF NOT EXISTS idx_jobs_alloc_cpus ON jobs(alloc_cpus);
CREATE INDEX IF NOT EXISTS idx_jobs_req_mem_mb ON jobs(req_mem_mb);
CREATE INDEX IF NOT EXISTS idx_jobs_submit_time ON jobs(submit_time);
CREATE INDEX IF NOT EXISTS idx_jobs_start_time ON jobs(start_time);
CREATE INDEX IF NOT EXISTS idx_jobs_end_time ON jobs(end_time);
CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS idx_jobs_derived_exit_code ON jobs(derived_exit_code);

CREATE TABLE IF NOT EXISTS intelligence_partition_stats (
    partition TEXT PRIMARY KEY,
    total_jobs INTEGER NOT NULL,
    successful_jobs INTEGER NOT NULL,
    success_rate REAL NOT NULL,
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intelligence_cpu_bucket_stats (
    cpu_bucket TEXT PRIMARY KEY,
    total_jobs INTEGER NOT NULL,
    successful_jobs INTEGER NOT NULL,
    failed_jobs INTEGER NOT NULL,
    timeout_jobs INTEGER NOT NULL,
    failure_rate REAL NOT NULL,
    timeout_rate REAL NOT NULL,
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intelligence_memory_bucket_stats (
    mem_bucket TEXT PRIMARY KEY,
    total_jobs INTEGER NOT NULL,
    failure_rate REAL NOT NULL,
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intelligence_failure_stats (
    state TEXT PRIMARY KEY,
    count INTEGER NOT NULL,
    percentage REAL NOT NULL,
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS intelligence_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    computed_at TEXT NOT NULL
);
"""


# Upsert statement for job ingestion.
#
# Behavior:
# - inserts new rows when job_id is unseen
# - updates existing rows when job_id already exists
#
# This makes ingestion idempotent when sacct windows overlap.
UPSERT_JOB_SQL = """
INSERT INTO jobs (
    job_id,
    user,
    account,
    partition,
    alloc_cpus,
    req_mem_mb,
    submit_time,
    start_time,
    end_time,
    elapsed_sec,
    state,
    exit_code,
    derived_exit_code,
    success,
    ingested_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

ON CONFLICT(job_id) DO UPDATE SET
    user=excluded.user,
    account=excluded.account,
    partition=excluded.partition,
    alloc_cpus=excluded.alloc_cpus,
    req_mem_mb=excluded.req_mem_mb,
    submit_time=excluded.submit_time,
    start_time=excluded.start_time,
    end_time=excluded.end_time,
    elapsed_sec=excluded.elapsed_sec,
    state=excluded.state,
    exit_code=excluded.exit_code,
    derived_exit_code=excluded.derived_exit_code,
    success=excluded.success,
    ingested_at=excluded.ingested_at
"""


class JobsDatabase:
    """
    SQLite wrapper for Inkly job-history storage.

    Handles:
    - database connection lifecycle
    - schema creation
    - job ingestion (single + batch)
    - rolling window cleanup

    Centralizing this logic avoids duplicating SQLite handling across the codebase.
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        # Resolve the database path and ensure the parent directory exists.
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Open SQLite connection.
        self._conn = sqlite3.connect(self.db_path)

        # Enable dict-like access to rows (column name indexing).
        self._conn.row_factory = sqlite3.Row

    def create_schema(self) -> None:
        """
        Create all required tables and indexes if they do not already exist.
        """
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        """
        Close the SQLite connection.
        """
        self._conn.close()

    def __enter__(self) -> "JobsDatabase":
        """
        Support context manager usage.

        Example:
            with JobsDatabase() as db:
                ...
        """
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """
        Ensure the connection is closed when leaving the context.
        """
        self.close()

    def upsert_job(self, record) -> None:
        """
        Insert or update a single job record.

        ingested_at is refreshed on every write so it reflects
        the most recent ingestion pass.
        """
        now = datetime.now(timezone.utc).isoformat()

        self._conn.execute(
            UPSERT_JOB_SQL,
            (
                record.job_id,
                record.user,
                record.account,
                record.partition,
                record.alloc_cpus,
                record.req_mem_mb,
                record.submit_time,
                record.start_time,
                record.end_time,
                record.elapsed_sec,
                record.state,
                record.exit_code,
                record.derived_exit_code,
                record.success,
                now,
            ),
        )
        self._conn.commit()

    def upsert_jobs(self, records) -> None:
        """
        Insert or update multiple job records in a batch.

        This is the primary ingestion path since executemany is more efficient
        than issuing one insert per row.
        """
        now = datetime.now(timezone.utc).isoformat()

        rows = [
            (
                r.job_id,
                r.user,
                r.account,
                r.partition,
                r.alloc_cpus,
                r.req_mem_mb,
                r.submit_time,
                r.start_time,
                r.end_time,
                r.elapsed_sec,
                r.state,
                r.exit_code,
                r.derived_exit_code,
                r.success,
                now,
            )
            for r in records
        ]

        self._conn.executemany(UPSERT_JOB_SQL, rows)
        self._conn.commit()

    def cleanup_old_jobs(self, window_days: int = 90) -> None:
        """
        Remove jobs outside the rolling window.

        IMPORTANT:
        This uses a date-based boundary (YYYY-MM-DD) to match how sacct
        fetches data using --starttime.

        This prevents boundary churn where jobs near the cutoff are repeatedly
        inserted and removed across refresh runs.
        """

        # Use timezone-aware UTC time so the cutoff stays explicit and avoids
        # deprecated naive UTC datetime behavior.
        cutoff_date = (
            datetime.now(timezone.utc) - timedelta(days=window_days)
        ).strftime("%Y-%m-%d")

        query = """
        DELETE FROM jobs
        WHERE DATE(COALESCE(end_time, start_time, submit_time, ingested_at))
            < DATE(?)
        """

        cursor = self._conn.execute(query, (cutoff_date,))
        print(f"Removed {cursor.rowcount} old jobs (cutoff: {cutoff_date})")
        self._conn.commit()


def initialize_jobs_db(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    """
    Initialize the jobs database and return the resolved path.

    Ensures:
    - database file exists
    - schema is fully created

    Used during installation and runtime bootstrap.
    """
    resolved_path = Path(db_path).expanduser()

    with JobsDatabase(resolved_path) as db:
        db.create_schema()

    return resolved_path
