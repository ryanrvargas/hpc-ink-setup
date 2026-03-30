from __future__ import annotations

from inkly.plugins import jobs_summary


def test_run_formats_job_history_summary(monkeypatch, tmp_path):
    fake_home = tmp_path
    inkly_dir = fake_home / ".inkly"
    inkly_dir.mkdir()
    (inkly_dir / "jobs.db").write_text("placeholder")

    monkeypatch.setattr(jobs_summary.Path, "home", lambda: fake_home)

    def fake_load_cluster_intelligence_summary(db_path: str) -> dict:
        return {
            "dataset_size": 12345,
            "partition_success": {
                "general": {
                    "successful_jobs": 9000,
                    "total_jobs": 10000,
                    "success_rate": 0.900,
                },
                "gpu": {
                    "successful_jobs": 1900,
                    "total_jobs": 2000,
                    "success_rate": 0.950,
                },
            },
            "memory_analysis": {
                "4-8GB": {
                    "total_jobs": 8000,
                    "failure_rate": 0.050,
                },
                "64GB+": {
                    "total_jobs": 500,
                    "failure_rate": 0.300,
                },
            },
            "failure_distribution": {
                "FAILED": {"count": 200, "percentage": 0.500},
                "TIMEOUT": {"count": 120, "percentage": 0.300},
                "CANCELLED by 12345": {"count": 50, "percentage": 0.125},
                "CANCELLED": {"count": 30, "percentage": 0.075},
            },
        }

    monkeypatch.setattr(
        jobs_summary,
        "load_cluster_intelligence_summary",
        fake_load_cluster_intelligence_summary,
    )

    output = jobs_summary.run()

    assert "Job History Summary" in output
    assert "Dataset size: 12345 jobs" in output

    assert "Top partition success rates:" in output
    assert "- general: 9000/10000 successful (0.900)" in output
    assert "- gpu: 1900/2000 successful (0.950)" in output

    assert "Memory bucket failure rates:" in output
    assert "- 4-8GB: 0.050 failure rate over 8000 jobs" in output
    assert "- 64GB+: 0.300 failure rate over 500 jobs" in output

    assert "Most common failure states:" in output
    assert "- FAILED: 200 (0.500)" in output
    assert "- TIMEOUT: 120 (0.300)" in output
    assert "- CANCELLED: 80 (0.200)" in output


def test_run_handles_missing_database(monkeypatch, tmp_path):
    fake_home = tmp_path
    monkeypatch.setattr(jobs_summary.Path, "home", lambda: fake_home)

    output = jobs_summary.run()

    assert "Job History Summary" in output
    assert "Job-history database not found." in output


def test_run_handles_analytics_failure(monkeypatch, tmp_path):
    fake_home = tmp_path
    inkly_dir = fake_home / ".inkly"
    inkly_dir.mkdir()
    (inkly_dir / "jobs.db").write_text("placeholder")

    monkeypatch.setattr(jobs_summary.Path, "home", lambda: fake_home)

    def fake_load_cluster_intelligence_summary(db_path: str) -> dict:
        raise RuntimeError("analytics unavailable")

    monkeypatch.setattr(
        jobs_summary,
        "load_cluster_intelligence_summary",
        fake_load_cluster_intelligence_summary,
    )

    output = jobs_summary.run()

    assert "Job History Summary" in output
    assert "Unable to load job-history summary: analytics unavailable" in output
