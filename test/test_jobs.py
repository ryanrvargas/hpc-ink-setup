from inkly.jobs import classify_job_success, parse_sacct_line, should_ingest
# Run: python -m pytest


def test_parse_top_level_completed_job():
    line = "1290158|ryan|users|general|64|64000M|01:10:05|COMPLETED|0:0"
    record = parse_sacct_line(line)

    assert record is not None
    assert record.job_id == "1290158"
    assert record.user == "ryan"
    assert record.partition == "general"
    assert record.alloc_cpus == 64
    assert record.state == "COMPLETED"
    assert record.exit_code == "0:0"


def test_filter_batch_job():
    line = "1290158.batch|ryan|users||64|64000M|01:10:05|COMPLETED|0:0"
    record = parse_sacct_line(line)

    assert record is not None
    assert should_ingest(record) is False


def test_filter_running_job():
    line = "1290165|ryan|users|general|4|4000M|00:01:10|RUNNING|0:0"
    record = parse_sacct_line(line)

    assert record is not None
    assert should_ingest(record) is False


def test_keep_failed_terminal_job():
    line = "1290162|ryan|users|general|16|16000M|00:03:00|FAILED|2:0"
    record = parse_sacct_line(line)

    assert record is not None
    assert should_ingest(record) is True


def test_completed_success():
    assert classify_job_success("COMPLETED", "0:0") == 1


def test_completed_nonzero_exit():
    assert classify_job_success("COMPLETED", "1:0") == 0


def test_timeout_even_if_zero_exit():
    assert classify_job_success("TIMEOUT", "0:0") == 0


def test_failed_job():
    assert classify_job_success("FAILED", "2:0") == 0
