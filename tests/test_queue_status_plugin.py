from __future__ import annotations

from inkly.plugins import queue_status


def test_run_reports_queue_counts_and_partitions(monkeypatch):
    def fake_command_exists(cmd: str) -> bool:
        return cmd in {"squeue", "sinfo"}

    def fake_run_capture(cmd: list[str]) -> str | None:
        if cmd == ["squeue", "-h", "-t", "RUNNING"]:
            return "job1\njob2\njob3"
        if cmd == ["squeue", "-h", "-t", "PENDING"]:
            return "job4\njob5"
        if cmd == ["sinfo", "-h", "-o", "%P|%D|%C"]:
            return "general|10|120/136/0/256\ngpu|4|16/48/0/64"
        return None

    monkeypatch.setattr(queue_status, "_command_exists", fake_command_exists)
    monkeypatch.setattr(queue_status, "_run_capture", fake_run_capture)

    output = queue_status.run()

    assert "Queue Status" in output
    assert "Running jobs: 3" in output
    assert "Pending jobs: 2" in output
    assert "Partitions:" in output
    assert "- general: 10 nodes, CPU summary 120/136/0/256" in output
    assert "- gpu: 4 nodes, CPU summary 16/48/0/64" in output


def test_run_handles_missing_squeue_and_sinfo(monkeypatch):
    monkeypatch.setattr(queue_status, "_command_exists", lambda cmd: False)

    output = queue_status.run()

    assert "Queue Status" in output
    assert "Queue counts unavailable: squeue not found or failed." in output
    assert "Partitions:" in output
    assert "Partition summary unavailable: sinfo not found." in output


def test_run_handles_sinfo_parse_failure(monkeypatch):
    def fake_command_exists(cmd: str) -> bool:
        return cmd in {"squeue", "sinfo"}

    def fake_run_capture(cmd: list[str]) -> str | None:
        if cmd == ["squeue", "-h", "-t", "RUNNING"]:
            return "job1"
        if cmd == ["squeue", "-h", "-t", "PENDING"]:
            return ""
        if cmd == ["sinfo", "-h", "-o", "%P|%D|%C"]:
            return "badly-formatted-line-with-no-separators"
        return None

    monkeypatch.setattr(queue_status, "_command_exists", fake_command_exists)
    monkeypatch.setattr(queue_status, "_run_capture", fake_run_capture)

    output = queue_status.run()

    assert "Running jobs: 1" in output
    assert "Pending jobs: 0" in output
    assert "Partition summary unavailable: could not parse sinfo output." in output
