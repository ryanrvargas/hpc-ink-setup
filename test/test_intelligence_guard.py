from pathlib import Path
import sqlite3
from types import SimpleNamespace

from inkly.db import initialize_jobs_db
from inkly.intelligence.prompt_builder import maybe_inject_intelligence


def make_config(min_jobs_required=500, enabled=True, window_days=90):
    intelligence = SimpleNamespace(
        enabled=enabled,
        min_jobs_required=min_jobs_required,
        window_days=window_days,
    )
    return SimpleNamespace(intelligence=intelligence)


def insert_job_rows(db_path: Path, count: int):
    conn = sqlite3.connect(db_path)
    try:
        for i in range(count):
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, user, account, partition, alloc_cpus,
                    req_mem_mb, elapsed_sec, state, exit_code, success, ingested_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    f"job-{i}",
                    "ryan",
                    "users",
                    "general",
                    4,
                    4096,
                    60,
                    "COMPLETED",
                    "0:0",
                    1,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def test_guard_skips_intelligence_when_database_empty(tmp_path):
    db_path = tmp_path / "jobs.db"
    initialize_jobs_db(db_path)

    cfg = make_config(min_jobs_required=5)
    prompt = "Generate a Slurm script."

    result = maybe_inject_intelligence(prompt, cfg, str(db_path))

    assert result.prompt == prompt
    assert result.injected is False
    assert result.dataset_size == 0
    assert result.message is not None
    assert "too small" in result.message.lower()


def test_guard_skips_intelligence_when_dataset_below_threshold(tmp_path):
    db_path = tmp_path / "jobs.db"
    initialize_jobs_db(db_path)
    insert_job_rows(db_path, 3)

    cfg = make_config(min_jobs_required=5)
    prompt = "Generate a Slurm script."

    result = maybe_inject_intelligence(prompt, cfg, str(db_path))

    assert result.prompt == prompt
    assert result.injected is False
    assert result.dataset_size == 3
    assert result.message is not None
    assert "5 required" in result.message


def test_intelligence_injected_when_threshold_met(tmp_path):
    db_path = tmp_path / "jobs.db"
    initialize_jobs_db(db_path)
    insert_job_rows(db_path, 5)

    cfg = make_config(min_jobs_required=5)
    prompt = "Generate a Slurm script."

    result = maybe_inject_intelligence(prompt, cfg, str(db_path))

    assert result.injected is True
    assert result.dataset_size == 5
    assert result.message is None
    assert "Cluster Intelligence" in result.prompt