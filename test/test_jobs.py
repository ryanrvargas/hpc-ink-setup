from inkly.jobs import parse_sacct_line, should_ingest
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
