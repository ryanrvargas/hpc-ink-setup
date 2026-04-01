from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import subprocess
from typing import List, Optional
from inkly.db import JobsDatabase
from inkly.intelligence.analytics import rebuild_intelligence_summaries
from inkly.db import DEFAULT_DB_PATH

# sacct fields requested from Slurm.
# The order here matters because parse_sacct_line() expects output columns
# to match this exact layout.
SACCT_FIELDS = [
    "JobID",
    "User",
    "Account",
    "Partition",
    "AllocCPUS",
    "ReqMem",
    "Elapsed",
    "State",
    "ExitCode",
]


@dataclass
class SacctJobRecord:
    """
    Structured representation of one parsed sacct job row.

    This stores both raw values from sacct and normalized fields added later
    during ingestion preparation.

    Raw fields:
    - req_mem_raw
    - elapsed_raw

    Derived fields:
    - success
    - req_mem_mb
    - elapsed_sec
    """

    job_id: str
    user: Optional[str]
    account: Optional[str]
    partition: Optional[str]
    alloc_cpus: Optional[int]
    req_mem_raw: Optional[str]
    elapsed_raw: Optional[str]
    state: str
    exit_code: Optional[str]
    success: Optional[int] = None
    req_mem_mb: Optional[int] = None
    elapsed_sec: Optional[int] = None


@dataclass
class RefreshSummary:
    """
    Summary of one refresh / ingestion pass.

    This is used to report what happened after pulling job history
    and syncing it into the database.
    """

    jobs_scanned: int
    jobs_inserted: int
    jobs_updated: int
    jobs_removed: int
    window_days: int


def build_sacct_command(window_days: int = 90) -> List[str]:
    """
    Build the sacct command used to retrieve historical jobs.

    The start date is calculated from the rolling window so only recent
    history is requested.

    Args:
        window_days: Number of days of job history to query.

    Returns:
        Command list suitable for subprocess.run().
    """
    start_date = (datetime.now() - timedelta(days=window_days)).strftime("%Y-%m-%d")

    return [
        "sacct",
        "-a",
        "--starttime",
        start_date,
        "--format",
        ",".join(SACCT_FIELDS),
        "--parsable2",
        "--noheader",
    ]


def run_sacct(window_days: int = 90) -> str:
    """
    Execute sacct and return raw stdout.

    This is the low-level command execution step before parsing.

    Args:
        window_days: Number of days of history to query.

    Returns:
        Raw stdout from sacct.

    Raises:
        RuntimeError: If sacct is missing or the command fails.
    """
    cmd = build_sacct_command(window_days)

    try:
        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("sacct not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(f"sacct failed: {stderr}") from exc

    return result.stdout


def parse_int(value: str) -> Optional[int]:
    """
    Parse an integer safely.

    Returns None if the value is empty or cannot be converted.
    """
    value = value.strip()
    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def parse_sacct_line(line: str) -> Optional[SacctJobRecord]:
    """
    Parse one sacct --parsable2 output line into a SacctJobRecord.

    Expected behavior:
    - blank lines are ignored
    - malformed rows are ignored
    - valid rows are converted into structured records

    Args:
        line: One raw line from sacct output.

    Returns:
        SacctJobRecord if parsing succeeds, otherwise None.
    """
    stripped = line.strip()
    if not stripped:
        return None

    parts = stripped.split("|")

    # The number of columns must match the requested sacct fields exactly.
    if len(parts) != len(SACCT_FIELDS):
        return None

    (
        job_id,
        user,
        account,
        partition,
        alloc_cpus,
        req_mem,
        elapsed,
        state,
        exit_code,
    ) = parts

    return SacctJobRecord(
        job_id=job_id.strip(),
        user=user.strip() or None,
        account=account.strip() or None,
        partition=partition.strip() or None,
        alloc_cpus=parse_int(alloc_cpus),
        req_mem_raw=req_mem.strip() or None,
        elapsed_raw=elapsed.strip() or None,
        state=state.strip(),
        exit_code=exit_code.strip() or None,
    )


def is_top_level_job(job_id: str) -> bool:
    """
    Return True if the Slurm JobID represents a top-level job.

    Slurm step records such as .batch or .extern are excluded because
    the ingestion logic is focused on one row per top-level job.
    """
    return "." not in job_id


def is_terminal_job_state(state: str) -> bool:
    """
    Return True if the job is in a terminal state.

    Active states such as RUNNING and PENDING are excluded because this
    ingestion path is meant to capture completed lifecycle outcomes.
    """
    normalized = state.strip().upper()
    return normalized not in {"RUNNING", "PENDING"}


def should_ingest(record: SacctJobRecord) -> bool:
    """
    Apply ingestion rules for deciding whether a parsed record should be kept.

    Rules:
    - Ignore JobIDs containing '.' because those are usually batch/extern steps
    - Ignore RUNNING jobs
    - Ignore PENDING jobs
    - Keep only top-level jobs in terminal states
    """
    if not is_top_level_job(record.job_id):
        return False

    if not is_terminal_job_state(record.state):
        return False

    return True


def fetch_sacct_job_records(window_days: int = 90) -> List[SacctJobRecord]:
    """
    Fetch, parse, filter, and enrich sacct job records.

    Flow:
    - run sacct
    - parse each output line
    - filter out rows that should not be ingested
    - derive normalized fields used by analytics and storage

    Derived fields added here:
    - success
    - req_mem_mb
    - elapsed_sec

    Args:
        window_days: Number of days of history to query.

    Returns:
        Filtered and enriched SacctJobRecord objects.
    """
    raw_output = run_sacct(window_days)
    records: List[SacctJobRecord] = []

    for line in raw_output.splitlines():
        record = parse_sacct_line(line)
        if record is None:
            continue

        if should_ingest(record):
            # Add normalized fields before the record is stored.
            record.success = classify_job_success(record.state, record.exit_code)
            record.req_mem_mb = parse_req_mem_mb(record.req_mem_raw)
            record.elapsed_sec = parse_elapsed_sec(record.elapsed_raw)
            records.append(record)

    return records


def classify_job_success(state: str, exit_code: Optional[str]) -> int:
    """
    Classify whether a Slurm job should be treated as successful.

    Rules:
    - success = 1 only if state == COMPLETED and exit_code starts with "0:"
    - success = 0 otherwise

    Important:
    - TIMEOUT with exit code 0:0 is still treated as failure
    """
    if state is None:
        return 0

    normalized = state.strip().upper()

    if normalized == "COMPLETED":
        if exit_code and exit_code.startswith("0:"):
            return 1

    return 0


def ingest_jobs_to_db(records, window_days: int = 90) -> RefreshSummary:
    """
    Ingest parsed job records into the jobs database and apply window cleanup.

    Flow:
    - read existing job IDs
    - determine inserted vs updated counts
    - upsert all incoming records
    - remove rows outside the rolling window
    - rebuild intelligence summary tables
    - return a refresh summary

    Returns:
        RefreshSummary describing the ingestion results.
    """
    with JobsDatabase() as db:
        # Load current job IDs so insert/update counts can be estimated.
        existing_ids = {
            row["job_id"]
            for row in db._conn.execute("SELECT job_id FROM jobs").fetchall()
        }

        incoming_ids = {r.job_id for r in records}

        jobs_updated = sum(1 for job_id in incoming_ids if job_id in existing_ids)
        jobs_inserted = sum(1 for job_id in incoming_ids if job_id not in existing_ids)

        # Upsert all incoming rows in bulk.
        db.upsert_jobs(records)

        # Measure cleanup impact using SQLite's total_changes counter.
        before_cleanup = db._conn.total_changes
        db.cleanup_old_jobs(window_days)
        after_cleanup = db._conn.total_changes

        jobs_removed = after_cleanup - before_cleanup

    # Rebuild summary tables after raw job data changes.
    rebuild_intelligence_summaries(DEFAULT_DB_PATH)

    return RefreshSummary(
        jobs_scanned=len(records),
        jobs_inserted=jobs_inserted,
        jobs_updated=jobs_updated,
        jobs_removed=jobs_removed,
        window_days=window_days,
    )


def refresh_jobs(window_days: int = 90) -> RefreshSummary:
    """
    Refresh the local jobs dataset from sacct.

    This is the main high-level entry point for job-history ingestion.
    """
    records = fetch_sacct_job_records(window_days=window_days)
    return ingest_jobs_to_db(records, window_days=window_days)


def parse_req_mem_mb(mem: Optional[str]) -> Optional[int]:
    """
    Convert Slurm ReqMem strings into megabytes.

    Supported examples:
        64000M  -> 64000
        64G     -> 65536
        4000K   -> 3
        64000Mc -> 64000
        64000Mn -> 64000

    Notes:
    - Slurm may append per-CPU / per-node suffixes such as c or n
    - Unsupported or malformed values return None
    """
    if not mem:
        return None

    mem = mem.strip().upper()

    try:
        # Remove Slurm per-cpu / per-node suffix.
        # After uppercasing:
        # - Mc -> MC
        # - Mn -> MN
        if mem.endswith("MC") or mem.endswith("MN"):
            mem = mem[:-1]

        if mem.endswith("M"):
            return int(mem[:-1])

        if mem.endswith("G"):
            return int(mem[:-1]) * 1024

        if mem.endswith("K"):
            return int(mem[:-1]) // 1024

    except ValueError:
        return None

    return None


def parse_elapsed_sec(elapsed: Optional[str]) -> Optional[int]:
    """
    Convert Slurm elapsed-time strings into total seconds.

    Supported formats seen in sacct:
        HH:MM:SS
        MM:SS
        D-HH:MM:SS

    Returns:
        Total elapsed seconds, or None if parsing fails.
    """
    if not elapsed:
        return None

    elapsed = elapsed.strip()

    try:
        # Handle optional day prefix.
        if "-" in elapsed:
            days_part, time_part = elapsed.split("-", 1)
            days = int(days_part)
        else:
            days = 0
            time_part = elapsed

        parts = time_part.split(":")

        if len(parts) == 3:
            h, m, s = parts
            seconds = int(h) * 3600 + int(m) * 60 + int(s)

        elif len(parts) == 2:
            m, s = parts
            seconds = int(m) * 60 + int(s)

        else:
            return None

        return days * 86400 + seconds

    except ValueError:
        return None


if __name__ == "__main__":
    # Simple manual execution path for local testing/debugging.
    records = fetch_sacct_job_records(window_days=90)
    print(f"Fetched {len(records)} filtered jobs")
    ingest_jobs_to_db(records, window_days=90)

    for record in records[:8]:
        print(record)