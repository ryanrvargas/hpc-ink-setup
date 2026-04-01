from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

# Default location for the Inkly jobs database.
# This database stores both raw ingested job records and precomputed
# intelligence summary tables.
DEFAULT_DB_PATH = Path.home() / ".inkly" / "jobs.db"


# Full SQLite schema used by Inkly job intelligence.
#
# Main table:
# - jobs
#   Stores one normalized record per top-level Slurm job
#
# Summary tables:
# - intelligence_partition_stats
# - intelligence_cpu_bucket_stats
# - intelligence_memory_bucket_stats
# - intelligence_failure_stats
# - intelligence_metadata
#
# These summary tables are rebuilt from the raw jobs table and are meant
# to support fast reads at runtime.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT UNIQUE NOT NULL,
    user TEXT,
    account TEXT,
    partition TEXT,
    alloc_cpus INTEGER,
    req_mem_mb INTEGER,
    elapsed_sec INTEGER,
    state TEXT,
    exit_code TEXT,
    success INTEGER,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_partition ON jobs(partition);
CREATE INDEX IF NOT EXISTS idx_jobs_success ON jobs(success);
CREATE INDEX IF NOT EXISTS idx_jobs_alloc_cpus ON jobs(alloc_cpus);
CREATE INDEX IF NOT EXISTS idx_jobs_req_mem_mb ON jobs(req_mem_mb);

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


# Upsert statement for raw job ingestion.
#
# Behavior:
# - inserts a new job if job_id does not exist yet
# - updates the existing row if job_id already exists
#
# This keeps ingestion idempotent for repeated refreshes over overlapping
# sacct time windows.
UPSERT_JOB_SQL = """
INSERT INTO jobs (
    job_id,
    user,
    account,
    partition,
    alloc_cpus,
    req_mem_mb,
    elapsed_sec,
    state,
    exit_code,
    success,
    ingested_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

ON CONFLICT(job_id) DO UPDATE SET
    user=excluded.user,
    account=excluded.account,
    partition=excluded.partition,
    alloc_cpus=excluded.alloc_cpus,
    req_mem_mb=excluded.req_mem_mb,
    elapsed_sec=excluded.elapsed_sec,
    state=excluded.state,
    exit_code=excluded.exit_code,
    success=excluded.success,
    ingested_at=excluded.ingested_at
"""


class JobsDatabase:
    """
    SQLite wrapper for Inkly job-history storage.

    This class handles:
    - opening the SQLite database
    - creating schema and indexes
    - inserting or updating job records
    - removing jobs outside the rolling window

    The goal is to keep database access in one place instead of scattering
    raw SQLite setup across the project.
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        # Resolve the database path and ensure the parent directory exists.
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Open the SQLite connection.
        self._conn = sqlite3.connect(self.db_path)

        # Use Row objects so query results can be accessed by column name.
        self._conn.row_factory = sqlite3.Row

    def create_schema(self) -> None:
        """
        Create all required tables and indexes if they do not already exist.

        This executes the full schema script, including raw job storage
        and intelligence summary tables.
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
        Support use as a context manager.

        Example:
            with JobsDatabase() as db:
                ...
        """
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """
        Ensure the database connection is closed when leaving the context.
        """
        self.close()

    def upsert_job(self, record):
        """
        Insert or update a single job record.

        The ingested_at timestamp is refreshed on every upsert so the row
        reflects the latest ingestion pass.
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
                record.elapsed_sec,
                record.state,
                record.exit_code,
                record.success,
                now,
            ),
        )

    def upsert_jobs(self, records):
        """
        Insert or update multiple job records in one batch.

        This is the main ingestion path used during refresh because batching
        is more efficient than executing one statement per row.
        """
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()

        # Build the full parameter rows once, then execute in bulk.
        rows = [
            (
                r.job_id,
                r.user,
                r.account,
                r.partition,
                r.alloc_cpus,
                r.req_mem_mb,
                r.elapsed_sec,
                r.state,
                r.exit_code,
                r.success,
                now,
            )
            for r in records
        ]

        self._conn.executemany(UPSERT_JOB_SQL, rows)
        self._conn.commit()

    def cleanup_old_jobs(self, window_days: int = 90) -> None:
        """
        Remove jobs older than the configured rolling window.

        This keeps the dataset bounded so the database does not grow forever
        and analytics remain focused on recent cluster history.
        """

        # SQLite datetime modifier for relative date filtering.
        threshold = f"-{window_days} days"

        query = """
        DELETE FROM jobs
        WHERE ingested_at < datetime('now', ?)
        """
        cursor = self._conn.execute(query, (threshold,))

        # Row count is printed for visibility during refresh/debug runs.
        print(f"Removed {cursor.rowcount} old jobs")
        self._conn.commit()


def initialize_jobs_db(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    """
    Initialize the Inkly jobs database and return the resolved path.

    This is the safe setup entry point used by installation or bootstrap code.
    It ensures the database exists and that the full schema has been created.
    """
    resolved_path = Path(db_path).expanduser()

    with JobsDatabase(resolved_path) as db:
        db.create_schema()

    return resolved_path