from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import subprocess
from typing import List, Optional
from inkly.db import JobsDatabase


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
    """Structured top-level Slurm job record parsed from sacct output."""

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


def build_sacct_command(window_days: int = 90) -> List[str]:
    """
    Build the sacct command for retrieving historical jobs.

    Args:
        window_days: Number of days of history to query.

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
    """Parse an integer field safely."""
    value = value.strip()
    if not value:
        return None

    try:
        return int(value)
    except ValueError:
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
    """Return True if the Slurm JobID is a top-level job and not a batch/extern step."""
    return "." not in job_id


def is_terminal_job_state(state: str) -> bool:
    """
    Return True if the job state is not active.

    For Issue 2 we exclude active states so only completed lifecycle
    rows remain for later processing.
    """
    normalized = state.strip().upper()
    return normalized not in {"RUNNING", "PENDING"}


def should_ingest(record: SacctJobRecord) -> bool:
    """
    Appling milestone v0.2.0 ingestion rules.

    Rules:
    - Ignore JobIDs containing '.', meaning they are batch or extern steps rather than top-level jobs
    - Ignore RUNNING jobs
    - Ignore PENDING jobs
    - Only ingest completed lifecycle jobs
    """
    if not is_top_level_job(record.job_id):
        return False

    if not is_terminal_job_state(record.state):
        return False

    return True


def fetch_sacct_job_records(window_days: int = 90) -> List[SacctJobRecord]:
    """
    Fetch and parse sacct job records for the given time window.

    Args:
        window_days: Number of days of history to query.

    Returns:
        Filtered list of SacctJobRecord objects.
    """
    raw_output = run_sacct(window_days)
    records: List[SacctJobRecord] = []

    for line in raw_output.splitlines():
        record = parse_sacct_line(line)
        if record is None:
            continue
        if should_ingest(record):
            record.success = classify_job_success(record.state, record.exit_code)
            record.req_mem_mb = parse_req_mem_mb(record.req_mem_raw)
            record.elapsed_sec = parse_elapsed_sec(record.elapsed_raw)
            records.append(record)

    return records


def classify_job_success(state: str, exit_code: Optional[str]) -> int:
    """
    Deterministically classify whether a Slurm job succeeded.

    Rules:
    - success = 1 if state == COMPLETED AND exit_code starts with "0:"
    - success = 0 otherwise

    Special case:
    - TIMEOUT 0:0 is still considered failure
    """

    if state is None:
        return 0

    normalized = state.strip().upper()

    if normalized == "COMPLETED":
        if exit_code and exit_code.startswith("0:"):
            return 1

    return 0

def ingest_jobs_to_db(records):
    with JobsDatabase() as db:
        db.upsert_jobs(records)
        db.cleanup_old_jobs()

def parse_req_mem_mb(mem: Optional[str]) -> Optional[int]:
    """
    Convert Slurm ReqMem string into megabytes.

    Examples:
        64000M -> 64000
        64G    -> 65536
        4000K  -> 3 (approx)
        64000Mc -> 64000
        64000Mn -> 64000
    """
    if not mem:
        return None

    mem = mem.strip().upper()

    try:
        # Remove Slurm per-cpu / per-node suffix
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
    Convert Slurm elapsed time into seconds.

    Formats observed in sacct:
        HH:MM:SS
        MM:SS
        D-HH:MM:SS
    """
    if not elapsed:
        return None

    elapsed = elapsed.strip()

    try:
        # Handle day prefix
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
    records = fetch_sacct_job_records()
    print(f"Fetched {len(records)} filtered jobs")
    ingest_jobs_to_db(records)

    for record in records[:8]:
        print(record)
