from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DEFAULT_DB_PATH = Path.home() / ".inkly" / "jobs.db"


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

CREATE INDEX IF NOT EXISTS idx_jobs_partition
    ON jobs(partition);

CREATE INDEX IF NOT EXISTS idx_jobs_success
    ON jobs(success);

CREATE INDEX IF NOT EXISTS idx_jobs_alloc_cpus
    ON jobs(alloc_cpus);

CREATE INDEX IF NOT EXISTS idx_jobs_req_mem_mb
    ON jobs(req_mem_mb);
"""

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
    """SQLite database wrapper for Inkly structured Slurm job intelligence."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row

    def create_schema(self) -> None:
        """Create the jobs table and indexes if they do not already exist."""
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        """Close the SQLite connection."""
        self._conn.close()

    def __enter__(self) -> "JobsDatabase":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def upsert_job(self, record):
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
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()

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

def initialize_jobs_db(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    """Initialize the Inkly jobs database and return its resolved path."""
    resolved_path = Path(db_path).expanduser()
    with JobsDatabase(resolved_path) as db:
        db.create_schema()
    return resolved_path
