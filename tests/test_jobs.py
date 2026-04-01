from __future__ import annotations

from inkly.jobs import (
    classify_failure_reason,
    classify_job_success,
    parse_elapsed_sec,
    parse_req_mem_mb,
    parse_sacct_line,
    parse_slurm_timestamp,
    should_ingest,
)


# These tests cover the expanded Issue 5 ingestion behavior.
#
# Focus areas:
# - parsing full sacct rows with timestamps and derived exit code
# - filtering out step rows like .batch and .extern
# - excluding active jobs from ingestion
# - validating success/failure interpretation rules
# - validating normalization helpers used before DB insertion


def test_parse_top_level_completed_job_with_new_fields():
    """
    Parse a normal top-level completed job using the expanded sacct format.
    """
    line = (
        "1290158|ryan|users|general|64|64000M|2026-03-20T09:10:00|"
        "2026-03-20T09:12:00|2026-03-20T10:22:05|01:10:05|COMPLETED|0:0|0:0"
    )

    record = parse_sacct_line(line)

    assert record is not None
    assert record.job_id == "1290158"
    assert record.user == "ryan"
    assert record.account == "users"
    assert record.partition == "general"
    assert record.alloc_cpus == 64
    assert record.req_mem_raw == "64000M"
    assert record.submit_time == "2026-03-20T09:10:00"
    assert record.start_time == "2026-03-20T09:12:00"
    assert record.end_time == "2026-03-20T10:22:05"
    assert record.elapsed_raw == "01:10:05"
    assert record.state == "COMPLETED"
    assert record.exit_code == "0:0"
    assert record.derived_exit_code == "0:0"


def test_parse_cancelled_state_is_normalized():
    """
    Slurm sometimes appends 'by <uid>' to cancelled jobs.
    That suffix should be normalized away during parsing.
    """
    line = (
        "1290159|ryan|users|general|16|16000M|2026-03-20T09:10:00|"
        "2026-03-20T09:12:00|2026-03-20T09:20:00|00:08:00|"
        "CANCELLED by 12345|0:15|0:15"
    )

    record = parse_sacct_line(line)

    assert record is not None
    assert record.state == "CANCELLED"


def test_parse_invalid_line_returns_none():
    """
    A malformed sacct row should fail closed instead of partially parsing.
    """
    line = "1290158|ryan|users|general"
    record = parse_sacct_line(line)

    assert record is None


def test_filter_batch_job():
    """
    .batch rows are step rows, not top-level jobs, so they should not be ingested.
    """
    line = (
        "1290158.batch|ryan|users|general|64|64000M|2026-03-20T09:10:00|"
        "2026-03-20T09:12:00|2026-03-20T10:22:05|01:10:05|COMPLETED|0:0|0:0"
    )

    record = parse_sacct_line(line)

    assert record is not None
    assert should_ingest(record) is False


def test_filter_extern_job():
    """
    .extern rows are also internal step rows and should be excluded.
    """
    line = (
        "1290158.extern|ryan|users|general|64|64000M|2026-03-20T09:10:00|"
        "2026-03-20T09:12:00|2026-03-20T10:22:05|01:10:05|COMPLETED|0:0|0:0"
    )

    record = parse_sacct_line(line)

    assert record is not None
    assert should_ingest(record) is False


def test_filter_running_job():
    """
    Active jobs should be excluded so the database only stores completed lifecycle rows.
    """
    line = (
        "1290165|ryan|users|general|4|4000M|2026-03-20T09:10:00|"
        "2026-03-20T09:12:00||00:01:10|RUNNING|0:0|0:0"
    )

    record = parse_sacct_line(line)

    assert record is not None
    assert should_ingest(record) is False


def test_filter_pending_job():
    """
    Pending jobs should also be excluded from ingestion.
    """
    line = (
        "1290166|ryan|users|general|4|4000M|2026-03-20T09:10:00|||00:00|PENDING|0:0|0:0"
    )

    record = parse_sacct_line(line)

    assert record is not None
    assert should_ingest(record) is False


def test_keep_failed_terminal_job():
    """
    Failed terminal jobs are still valid historical records and should be ingested.
    """
    line = (
        "1290162|ryan|users|general|16|16000M|2026-03-20T09:10:00|"
        "2026-03-20T09:12:00|2026-03-20T09:15:00|00:03:00|FAILED|2:0|2:0"
    )

    record = parse_sacct_line(line)

    assert record is not None
    assert should_ingest(record) is True


def test_completed_success():
    """
    A completed job with a zero exit code is considered successful.
    """
    assert classify_job_success("COMPLETED", "0:0", "0:0") == 1


def test_completed_nonzero_exit():
    """
    A completed job with a nonzero exit code is still treated as failed.
    """
    assert classify_job_success("COMPLETED", "1:0", "1:0") == 0


def test_timeout_even_if_zero_exit():
    """
    Timeout is still failure even when exit_code looks clean.
    """
    assert classify_job_success("TIMEOUT", "0:0", "0:0") == 0


def test_failed_job():
    """
    Standard failed jobs are classified as unsuccessful.
    """
    assert classify_job_success("FAILED", "2:0", "2:0") == 0


def test_classify_failure_reason_success():
    """
    App-level failure classification should label clean completed jobs as SUCCESS.
    """
    assert classify_failure_reason("COMPLETED", "0:0", "0:0") == "SUCCESS"


def test_classify_failure_reason_cancelled():
    """
    Cancelled jobs should stay distinct from generic failures.
    """
    assert classify_failure_reason("CANCELLED by 12345", "0:15", "0:15") == "CANCELLED"


def test_classify_failure_reason_timeout():
    """
    Timeout should map to TIMEOUT.
    """
    assert classify_failure_reason("TIMEOUT", "0:0", "0:0") == "TIMEOUT"


def test_classify_failure_reason_out_of_memory():
    """
    Out-of-memory failures should stay distinct for later analytics.
    """
    assert classify_failure_reason("OUT_OF_MEMORY", "0:125", "0:125") == "OUT_OF_MEMORY"


def test_classify_failure_reason_node_fail():
    """
    Node failures should stay distinct for later summaries.
    """
    assert classify_failure_reason("NODE_FAIL", "0:0", "0:0") == "NODE_FAIL"


def test_classify_failure_reason_generic_failed():
    """
    Generic failed states should fall back to FAILED.
    """
    assert classify_failure_reason("FAILED", "2:0", "2:0") == "FAILED"


def test_classify_failure_reason_unknown():
    """
    Blank or missing status information should not crash classification.
    """
    assert classify_failure_reason("", None, None) == "UNKNOWN"


def test_parse_slurm_timestamp_iso_value():
    """
    ISO-like timestamps should round-trip cleanly.
    """
    assert parse_slurm_timestamp("2026-03-31T14:22:01") == "2026-03-31T14:22:01"


def test_parse_slurm_timestamp_space_separated_value():
    """
    Space-separated datetime strings should also normalize to ISO format.
    """
    assert parse_slurm_timestamp("2026-03-31 14:22:01") == "2026-03-31T14:22:01"


def test_parse_slurm_timestamp_unknown_value():
    """
    Unknown/N/A scheduler values should become None.
    """
    assert parse_slurm_timestamp("Unknown") is None
    assert parse_slurm_timestamp("N/A") is None
    assert parse_slurm_timestamp("") is None


def test_parse_req_mem_mb_values():
    """
    ReqMem parsing should normalize common Slurm units into MB.
    """
    assert parse_req_mem_mb("64000M") == 64000
    assert parse_req_mem_mb("64G") == 65536
    assert parse_req_mem_mb("4000K") == 3
    assert parse_req_mem_mb("64000Mc") == 64000
    assert parse_req_mem_mb("64000Mn") == 64000


def test_parse_req_mem_mb_invalid_value():
    """
    Invalid memory strings should safely return None.
    """
    assert parse_req_mem_mb("bad-value") is None
    assert parse_req_mem_mb(None) is None


def test_parse_elapsed_sec_hms():
    """
    Standard HH:MM:SS elapsed values should convert to seconds.
    """
    assert parse_elapsed_sec("01:10:05") == 4205


def test_parse_elapsed_sec_ms():
    """
    MM:SS elapsed values should also be supported.
    """
    assert parse_elapsed_sec("03:15") == 195


def test_parse_elapsed_sec_days():
    """
    Day-prefixed elapsed values should convert correctly.
    """
    assert parse_elapsed_sec("2-01:00:00") == 176400


def test_parse_elapsed_sec_invalid():
    """
    Invalid elapsed values should safely return None.
    """
    assert parse_elapsed_sec("bad-value") is None
    assert parse_elapsed_sec(None) is None
