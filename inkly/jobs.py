from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import subprocess
from typing import List, Optional

from inkly.db import DEFAULT_DB_PATH, JobsDatabase
from inkly.intelligence.analytics import rebuild_intelligence_summaries

# Ordered list of sacct fields requested during refresh.
#
# This now includes lifecycle timestamps and Slurm's DerivedExitCode so
# Issue 5 has enough raw data to:
# - store actual job timing
# - distinguish different failure types later
# - support rolling-window pruning based on real job timestamps
SACCT_FIELDS = [
    "JobID",
    "User",
    "Account",
    "Partition",
    "AllocCPUS",
    "ReqMem",
    "Submit",
    "Start",
    "End",
    "Elapsed",
    "State",
    "ExitCode",
    "DerivedExitCode",
]


@dataclass
class SacctJobRecord:
    """
    Structured top-level Slurm job record parsed from sacct output.

    Raw scheduler fields are preserved where useful, while common fields
    like memory and elapsed time are also normalized into database-ready
    values.
    """

    job_id: str
    user: Optional[str]
    account: Optional[str]
    partition: Optional[str]
    alloc_cpus: Optional[int]
    req_mem_raw: Optional[str]
    submit_time: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    elapsed_raw: Optional[str]
    state: str
    exit_code: Optional[str]
    derived_exit_code: Optional[str]
    success: Optional[int] = None
    req_mem_mb: Optional[int] = None
    elapsed_sec: Optional[int] = None


@dataclass
class RefreshSummary:
    """
    Summary returned after an ingestion refresh completes.
    """

    jobs_scanned: int
    jobs_inserted: int
    jobs_updated: int
    jobs_removed: int
    window_days: int


def build_sacct_command(window_days: int = 90) -> List[str]:
    """
    Build the sacct command for retrieving historical jobs.

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

    Args:
        window_days: Number of days of history to query.

    Returns:
        Raw stdout from sacct.

    Raises:
        RuntimeError: If sacct is missing or execution fails.
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
    Parse an integer field safely.

    Returns None for blank or invalid values instead of raising.
    """
    value = value.strip()
    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def normalize_slurm_state(state: Optional[str]) -> str:
    """
    Normalize Slurm state strings into stable labels.

    Example:
    - "CANCELLED by 12345" -> "CANCELLED"

    This keeps downstream logic cleaner without losing the original
    failure meaning.
    """
    if not state:
        return ""

    cleaned = state.strip().upper()

    if cleaned.startswith("CANCELLED"):
        return "CANCELLED"

    return cleaned


def parse_slurm_timestamp(value: Optional[str]) -> Optional[str]:
    """
    Parse a Slurm timestamp into ISO 8601 text for SQLite storage.

    Returns None for blank or unknown scheduler values.

    Common cases:
    - 2026-03-31T14:22:01
    - 2026-03-31 14:22:01
    - Unknown / N/A / None
    """
    if not value:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    normalized_upper = cleaned.upper()
    if normalized_upper in {"UNKNOWN", "N/A", "NONE"}:
        return None

    # Try Python's flexible ISO parsing first.
    try:
        return datetime.fromisoformat(cleaned).isoformat()
    except ValueError:
        pass

    # Fall back to a few common non-ISO-like layouts that still show up in tools.
    fallback_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]

    for fmt in fallback_formats:
        try:
            return datetime.strptime(cleaned, fmt).isoformat()
        except ValueError:
            continue

    return None


def parse_sacct_line(line: str) -> Optional[SacctJobRecord]:
    """
    Parse a single sacct --parsable2 line into a SacctJobRecord.

    Args:
        line: One line of sacct output.

    Returns:
        SacctJobRecord if parsing succeeds, otherwise None.
    """
    stripped = line.strip()
    if not stripped:
        return None

    parts = stripped.split("|")
    if len(parts) != len(SACCT_FIELDS):
        return None

    (
        job_id,
        user,
        account,
        partition,
        alloc_cpus,
        req_mem,
        submit_time,
        start_time,
        end_time,
        elapsed,
        state,
        exit_code,
        derived_exit_code,
    ) = parts

    return SacctJobRecord(
        job_id=job_id.strip(),
        user=user.strip() or None,
        account=account.strip() or None,
        partition=partition.strip() or None,
        alloc_cpus=parse_int(alloc_cpus),
        req_mem_raw=req_mem.strip() or None,
        submit_time=parse_slurm_timestamp(submit_time),
        start_time=parse_slurm_timestamp(start_time),
        end_time=parse_slurm_timestamp(end_time),
        elapsed_raw=elapsed.strip() or None,
        state=normalize_slurm_state(state),
        exit_code=exit_code.strip() or None,
        derived_exit_code=derived_exit_code.strip() or None,
    )


def is_top_level_job(job_id: str) -> bool:
    """
    Return True if the Slurm JobID is a top-level job.

    Step rows such as:
    - .batch
    - .extern

    are filtered out because the database is intended to store one row
    per top-level job, not all internal step rows.
    """
    return "." not in job_id


def is_terminal_job_state(state: str) -> bool:
    """
    Return True if the job state is not active.

    Active states are excluded so only completed lifecycle rows are ingested.
    """
    normalized = normalize_slurm_state(state)
    return normalized not in {"RUNNING", "PENDING"}


def should_ingest(record: SacctJobRecord) -> bool:
    """
    Apply job-ingestion rules.

    Rules:
    - Ignore non-top-level step rows like .batch and .extern
    - Ignore active jobs
    - Only ingest completed lifecycle jobs
    """
    if not is_top_level_job(record.job_id):
        return False

    if not is_terminal_job_state(record.state):
        return False

    return True


def classify_job_success(
    state: str,
    exit_code: Optional[str],
    derived_exit_code: Optional[str] = None,
) -> int:
    """
    Deterministically classify whether a Slurm job succeeded.

    Current rule:
    - success = 1 only if state == COMPLETED and exit_code starts with "0:"
    - success = 0 otherwise

    DerivedExitCode is accepted here so later logic can expand without
    changing the call signature again.
    """
    _ = derived_exit_code

    normalized = normalize_slurm_state(state)

    if normalized == "COMPLETED":
        if exit_code and exit_code.startswith("0:"):
            return 1

    return 0


def _parse_exit_status(code: Optional[str]) -> Optional[int]:
    """
    Extract the numeric status value from a Slurm ExitCode / DerivedExitCode field.

    Expected Slurm-style format:
        "<status>:<signal>"

    Examples:
        "0:0"   -> 0
        "1:0"   -> 1
        "9:0"   -> 9
        None    -> None

    Returns:
        Integer status code if parsing succeeds, otherwise None.
    """
    if not code:
        return None

    cleaned = code.strip()
    if not cleaned or ":" not in cleaned:
        return None

    status_part, _signal_part = cleaned.split(":", 1)

    try:
        return int(status_part)
    except ValueError:
        return None


def classify_failure_reason(
    state: str,
    exit_code: Optional[str],
    derived_exit_code: Optional[str],
) -> str:
    """
    Normalize Slurm outcomes into stable app-level categories.

    Interpretation priority:
    1. obvious state-based outcomes
    2. derived exit code when available
    3. raw exit code fallback

    Possible outputs:
    - SUCCESS
    - CANCELLED
    - TIMEOUT
    - OUT_OF_MEMORY
    - NODE_FAIL
    - FAILED
    - UNKNOWN

    Notes:
    - Raw scheduler values are still stored separately in the database
    - This function only provides a normalized interpretation layer
    """
    normalized = normalize_slurm_state(state)
    exit_status = _parse_exit_status(exit_code)
    derived_status = _parse_exit_status(derived_exit_code)

    # Successful completion should stay explicit.
    if normalized == "COMPLETED" and exit_status == 0:
        return "SUCCESS"

    # Strong state-based outcomes come first because Slurm already tells us
    # the scheduler-level reason directly.
    if normalized == "CANCELLED":
        return "CANCELLED"

    if normalized == "TIMEOUT":
        return "TIMEOUT"

    if normalized == "OUT_OF_MEMORY":
        return "OUT_OF_MEMORY"

    if normalized == "NODE_FAIL":
        return "NODE_FAIL"

    # Prefer DerivedExitCode over ExitCode when state is less specific.
    #
    # This does not try to over-interpret every possible Slurm status value.
    # It mainly distinguishes "clean" success from failure-like outcomes.
    if derived_status is not None:
        if derived_status == 0 and normalized == "COMPLETED":
            return "SUCCESS"
        return "FAILED"

    if exit_status is not None:
        if exit_status == 0 and normalized == "COMPLETED":
            return "SUCCESS"
        return "FAILED"

    if normalized:
        return "FAILED"

    return "UNKNOWN"


def fetch_sacct_job_records(window_days: int = 90) -> List[SacctJobRecord]:
    """
    Fetch and parse sacct job records for the given time window.

    Args:
        window_days: Number of days of history to query.

    Returns:
        Filtered list of normalized SacctJobRecord objects.
    """
    raw_output = run_sacct(window_days)
    records: List[SacctJobRecord] = []

    for line in raw_output.splitlines():
        record = parse_sacct_line(line)
        if record is None:
            continue

        if should_ingest(record):
            record.success = classify_job_success(
                record.state,
                record.exit_code,
                record.derived_exit_code,
            )
            record.req_mem_mb = parse_req_mem_mb(record.req_mem_raw)
            record.elapsed_sec = parse_elapsed_sec(record.elapsed_raw)
            records.append(record)

    return records


def ingest_jobs_to_db(
    records: List[SacctJobRecord],
    window_days: int = 90,
    db_path=DEFAULT_DB_PATH,
) -> RefreshSummary:
    """
    Ingest parsed job records into SQLite and enforce the rolling window.

    Returns a structured summary for CLI or script reporting.
    """
    with JobsDatabase(db_path) as db:
        # Load existing rows so we can detect real changes, not just ID matches.
        existing_rows = {
            row["job_id"]: row
            for row in db._conn.execute("SELECT * FROM jobs").fetchall()
        }

        jobs_inserted = 0
        jobs_updated = 0
        jobs_unchanged = 0  # optional, but useful for debugging

        for r in records:
            existing = existing_rows.get(r.job_id)

            # New job → insert
            if existing is None:
                jobs_inserted += 1
                continue

            # Compare key fields to detect actual changes
            changed = (
                existing["state"] != r.state
                or existing["exit_code"] != r.exit_code
                or existing["derived_exit_code"] != r.derived_exit_code
                or existing["elapsed_sec"] != r.elapsed_sec
                or existing["req_mem_mb"] != r.req_mem_mb
            )

            if changed:
                jobs_updated += 1
            else:
                jobs_unchanged += 1

        db.upsert_jobs(records)

        before_cleanup = db._conn.total_changes
        db.cleanup_old_jobs(window_days)
        after_cleanup = db._conn.total_changes

        jobs_removed = after_cleanup - before_cleanup

    rebuild_intelligence_summaries(db_path)

    return RefreshSummary(
        jobs_scanned=len(records),
        jobs_inserted=jobs_inserted,
        jobs_updated=jobs_updated,
        jobs_removed=jobs_removed,
        window_days=window_days,
    )


def refresh_jobs(window_days: int = 90, db_path=DEFAULT_DB_PATH) -> RefreshSummary:
    """
    Fetch historical jobs from sacct and ingest them into the SQLite dataset.
    """
    records = fetch_sacct_job_records(window_days=window_days)
    return ingest_jobs_to_db(records, window_days=window_days, db_path=db_path)


def parse_req_mem_mb(mem: Optional[str]) -> Optional[int]:
    """
    Convert Slurm ReqMem string into megabytes.

    Supported examples:
        64000M  -> 64000
        64G     -> 65536
        1.50G   -> 1536
        0.50G   -> 512
        4000K   -> 3 (approx, floor division)
        64000Mc -> 64000
        64000Mn -> 64000

    Notes:
    - Slurm may append per-cpu / per-node suffixes like 'c' or 'n'
    - Decimal values are supported for K, M, and G units
    - Results are normalized to integer MB
    """
    if not mem:
        return None

    mem = mem.strip().upper()
    if not mem:
        return None

    try:
        # Remove Slurm per-cpu / per-node suffixes like Mc / Mn / Gc / Gn.
        if len(mem) >= 2 and mem[-1] in {"C", "N"} and mem[-2] in {"K", "M", "G"}:
            mem = mem[:-1]

        if mem.endswith("M"):
            value_mb = float(mem[:-1])
            return int(value_mb)

        if mem.endswith("G"):
            value_gb = float(mem[:-1])
            return int(value_gb * 1024)

        if mem.endswith("K"):
            value_kb = float(mem[:-1])
            return int(value_kb // 1024)

    except ValueError:
        return None

    return None


def parse_elapsed_sec(elapsed: Optional[str]) -> Optional[int]:
    """
    Convert Slurm elapsed time into total seconds.

    Supported formats:
    - HH:MM:SS
    - MM:SS
    - D-HH:MM:SS
    """
    if not elapsed:
        return None

    elapsed = elapsed.strip()

    try:
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
    # Basic direct-run path for local testing while the dedicated refresh
    # script/CLI flow is still being refined.
    records = fetch_sacct_job_records(window_days=90)
    print(f"Fetched {len(records)} filtered jobs")

    summary = ingest_jobs_to_db(records, window_days=90)
    print(summary)

    for record in records[:8]:
        print(record)
