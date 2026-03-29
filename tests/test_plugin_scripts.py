from __future__ import annotations

import runpy
from pathlib import Path


SCRIPT_EXPECTATIONS = {
    "queue_status.py": "Queue Status",
    "node_info.py": "Node / Partition Information",
    "jobs_summary.py": "Job History Summary",
    "docs_gaussian.py": "Gaussian",
}


def _run_script(path: Path, monkeypatch, capsys) -> str:
    monkeypatch.chdir(path.parent.parent)
    runpy.run_path(str(path), run_name="__main__")
    captured = capsys.readouterr()
    return captured.out.strip()


def test_queue_status_script_runs(monkeypatch, capsys):
    import inkly.plugins.queue_status as plugin

    monkeypatch.setattr(plugin, "run", lambda: "Queue Status\nok")

    script = Path("scripts/queue_status.py")
    output = _run_script(script, monkeypatch, capsys)

    assert "Queue Status" in output


def test_node_info_script_runs(monkeypatch, capsys):
    import inkly.plugins.node_info as plugin

    monkeypatch.setattr(
        plugin, "run", lambda: "Node / Partition Information\nok"
    )

    script = Path("scripts/node_info.py")
    output = _run_script(script, monkeypatch, capsys)

    assert "Node / Partition Information" in output


def test_jobs_summary_script_runs(monkeypatch, capsys):
    import inkly.plugins.jobs_summary as plugin

    monkeypatch.setattr(plugin, "run", lambda: "Job History Summary\nok")

    script = Path("scripts/jobs_summary.py")
    output = _run_script(script, monkeypatch, capsys)

    assert "Job History Summary" in output


def test_docs_gaussian_script_runs(monkeypatch, capsys):
    import inkly.plugins.docs_gaussian as plugin

    monkeypatch.setattr(plugin, "run", lambda: "Gaussian Usage Notes\nok")

    script = Path("scripts/docs_gaussian.py")
    output = _run_script(script, monkeypatch, capsys)

    assert "Gaussian Usage Notes" in output