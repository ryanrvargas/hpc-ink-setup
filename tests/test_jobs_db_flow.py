from __future__ import annotations

from pathlib import Path

from inkly.db import JobsDatabase, initialize_jobs_db
from inkly.jobs import SacctJobRecord, ingest_jobs_to_db


# These tests focus on the database-facing ingestion flow.
#
# Main goals:
# - verify rolling-window cleanup removes rows older than the cutoff date
# - verify unchanged rows are not counted as updates
# - verify changed rows on the same job_id are counted as updates
# - verify repeated ingests stabilize instead of churning


def make_record(
    *,
    job_id: str,
    state: str = "COMPLETED",
    exit_code: str | None = "0:0",
    derived_exit_code: str | None = "0:0",
    req_mem_raw: str | None = "4G",
    req_mem_mb: int | None = 4096,
    elapsed_raw: str | None = "00:10:00",
    elapsed_sec: int | None = 600,
    submit_time: str | None = "2026-03-20T08:00:00",
    start_time: str | None = "2026-03-20T08:01:00",
    end_time: str | None = "2026-03-20T08:10:00",
    partition: str | None = "general",
    alloc_cpus: int | None = 4,
    success: int | None = 1,
) -> SacctJobRecord:
    """
    Build a compact SacctJobRecord for DB-flow tests.

    Keeping record construction in one helper makes the tests easier to read
    and easier to modify if the dataclass grows later.
    """
    return SacctJobRecord(
        job_id=job_id,
        user="ryan",
        account="users",
        partition=partition,
        alloc_cpus=alloc_cpus,
        req_mem_raw=req_mem_raw,
        submit_time=submit_time,
        start_time=start_time,
        end_time=end_time,
        elapsed_raw=elapsed_raw,
        state=state,
        exit_code=exit_code,
        derived_exit_code=derived_exit_code,
        success=success,
        req_mem_mb=req_mem_mb,
        elapsed_sec=elapsed_sec,
    )


def test_cleanup_old_jobs_removes_rows_before_cutoff(tmp_path):
    """
    cleanup_old_jobs() should remove rows whose effective job date falls
    before the aligned date-based cutoff.
    """
    db_path = tmp_path / "jobs.db"
    initialize_jobs_db(db_path)

    old_record = make_record(
        job_id="old-job",
        submit_time="2025-12-20T08:00:00",
        start_time="2025-12-20T08:01:00",
        end_time="2025-12-20T08:10:00",
    )
    recent_record = make_record(
        job_id="recent-job",
        submit_time="2026-03-20T08:00:00",
        start_time="2026-03-20T08:01:00",
        end_time="2026-03-20T08:10:00",
    )

    with JobsDatabase(db_path) as db:
        db.upsert_jobs([old_record, recent_record])

        # Force a short cleanup window so the old row is pruned.
        db.cleanup_old_jobs(window_days=30)

        rows = db._conn.execute("SELECT job_id FROM jobs ORDER BY job_id").fetchall()

    remaining_ids = [row["job_id"] for row in rows]
    assert "recent-job" in remaining_ids
    assert "old-job" not in remaining_ids


def test_ingest_jobs_to_db_counts_new_rows_as_inserted(tmp_path):
    """
    A first ingestion of unseen job IDs should count them as inserted,
    not updated.
    """
    db_path = tmp_path / "jobs.db"
    initialize_jobs_db(db_path)

    records = [
        make_record(job_id="job-1"),
        make_record(job_id="job-2"),
    ]

    summary = ingest_jobs_to_db(records, window_days=90, db_path=db_path)

    assert summary.jobs_scanned == 2
    assert summary.jobs_inserted == 2
    assert summary.jobs_updated == 0
    assert summary.jobs_removed == 0


def test_ingest_jobs_to_db_does_not_count_unchanged_rows_as_updated(tmp_path):
    """
    Re-ingesting the same job rows without field changes should not produce
    fake updates.
    """
    db_path = tmp_path / "jobs.db"
    initialize_jobs_db(db_path)

    records = [
        make_record(job_id="job-1"),
        make_record(job_id="job-2"),
    ]

    first_summary = ingest_jobs_to_db(records, window_days=90, db_path=db_path)
    second_summary = ingest_jobs_to_db(records, window_days=90, db_path=db_path)

    assert first_summary.jobs_inserted == 2
    assert first_summary.jobs_updated == 0

    assert second_summary.jobs_inserted == 0
    assert second_summary.jobs_updated == 0
    assert second_summary.jobs_removed == 0


def test_ingest_jobs_to_db_counts_changed_rows_as_updated(tmp_path):
    """
    Re-ingesting an existing job with changed fields should count as a real
    update instead of being treated as unchanged.
    """
    db_path = tmp_path / "jobs.db"
    initialize_jobs_db(db_path)

    original = make_record(
        job_id="job-1",
        state="FAILED",
        exit_code="1:0",
        derived_exit_code="1:0",
        success=0,
        elapsed_sec=120,
    )
    changed = make_record(
        job_id="job-1",
        state="COMPLETED",
        exit_code="0:0",
        derived_exit_code="0:0",
        success=1,
        elapsed_sec=180,
    )

    first_summary = ingest_jobs_to_db([original], window_days=90, db_path=db_path)
    second_summary = ingest_jobs_to_db([changed], window_days=90, db_path=db_path)

    assert first_summary.jobs_inserted == 1
    assert first_summary.jobs_updated == 0

    assert second_summary.jobs_inserted == 0
    assert second_summary.jobs_updated == 1
    assert second_summary.jobs_removed == 0

    with JobsDatabase(db_path) as db:
        row = db._conn.execute(
            """
            SELECT state, exit_code, derived_exit_code, success, elapsed_sec
            FROM jobs
            WHERE job_id = ?
            """,
            ("job-1",),
        ).fetchone()

    assert row["state"] == "COMPLETED"
    assert row["exit_code"] == "0:0"
    assert row["derived_exit_code"] == "0:0"
    assert row["success"] == 1
    assert row["elapsed_sec"] == 180


def test_ingest_jobs_to_db_window_stabilizes_on_repeat(tmp_path):
    """
    Repeated ingests with the same already-in-window records should settle
    into zero inserts, zero updates, and zero removals.
    """
    db_path = tmp_path / "jobs.db"
    initialize_jobs_db(db_path)

    records = [
        make_record(job_id="job-1"),
        make_record(job_id="job-2"),
        make_record(job_id="job-3"),
    ]

    ingest_jobs_to_db(records, window_days=20, db_path=db_path)
    repeat_summary = ingest_jobs_to_db(records, window_days=20, db_path=db_path)

    assert repeat_summary.jobs_inserted == 0
    assert repeat_summary.jobs_updated == 0
    assert repeat_summary.jobs_removed == 0
