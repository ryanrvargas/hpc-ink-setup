from __future__ import annotations

PLUGIN_META = {
    "name": "queue_status",
    "description": "Summarizes the current cluster queue, running jobs, pending jobs, and near-term scheduler pressure.",
    "category": "queue-status",
    "example_queries": [
        "How busy is the cluster right now?",
        "Are there many pending jobs?",
        "What does the current queue look like?",
    ],
}


def run() -> str:
    return "Queue snapshot: 24 running jobs, 6 pending jobs, gpu partition moderately loaded."
