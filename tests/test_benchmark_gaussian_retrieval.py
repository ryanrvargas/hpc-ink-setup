from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_benchmark_script_runs_from_repository_root():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/benchmark_gaussian_retrieval.py",
            "How do I run Gaussian on this cluster?",
            "--runs",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "runs: 1" in result.stdout
    assert "output_chars:" in result.stdout
