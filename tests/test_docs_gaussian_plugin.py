from __future__ import annotations

from inkly.plugins import docs_gaussian


def test_run_returns_gaussian_snippets(monkeypatch):
    monkeypatch.setattr(
        docs_gaussian,
        "DOC_SNIPPETS",
        {
            "gaussian": [
                "Gaussian Usage Notes",
                "Load the Gaussian module before submitting the job.",
                "Request memory carefully in the Slurm script.",
                "Check output logs for memory-related failures.",
            ]
        },
    )

    output = docs_gaussian.run()

    assert "Gaussian Usage Notes" in output
    assert "Load the Gaussian module before submitting the job." in output
    assert "Request memory carefully in the Slurm script." in output
    assert "Check output logs for memory-related failures." in output


def test_run_handles_missing_gaussian_snippets(monkeypatch):
    monkeypatch.setattr(docs_gaussian, "DOC_SNIPPETS", {})

    output = docs_gaussian.run()

    assert "Gaussian Documentation Snippets" in output
    assert "Gaussian documentation snippets are unavailable." in output