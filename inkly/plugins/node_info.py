from __future__ import annotations

PLUGIN_META = {
    "name": "node_info",
    "description": "Lists node and partition resource characteristics such as CPUs, memory, GPU availability, and partition limits.",
    "category": "node-info",
    "example_queries": [
        "What partitions are available?",
        "Which nodes have GPUs?",
        "How much memory can I request?",
    ],
}


def run() -> str:
    return "Partitions: general, gpu. GPU nodes provide 4 GPUs and 256GB RAM."
