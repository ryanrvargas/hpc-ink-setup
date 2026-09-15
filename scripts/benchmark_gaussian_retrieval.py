#!/usr/bin/env python3
"""Benchmark Phase 1 Gaussian documentation retrieval latency."""

from __future__ import annotations

import argparse
import statistics
import time

from inkly.plugins.docs_gaussian import run


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark local Gaussian scraper-to-Inkly retrieval."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="How do I run Gaussian on this cluster?",
        help="Gaussian documentation query to benchmark.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="Number of timed retrievals (default: 10).",
    )
    args = parser.parse_args()

    if args.runs < 1:
        parser.error("--runs must be at least 1")

    durations_ms: list[float] = []
    output = ""
    for _ in range(args.runs):
        started = time.perf_counter()
        output = run(args.query)
        durations_ms.append((time.perf_counter() - started) * 1000)

    print(f"query: {args.query}")
    print(f"runs: {args.runs}")
    print(f"min_ms: {min(durations_ms):.3f}")
    print(f"median_ms: {statistics.median(durations_ms):.3f}")
    print(f"p95_ms: {_percentile(durations_ms, 0.95):.3f}")
    print(f"max_ms: {max(durations_ms):.3f}")
    print(f"output_chars: {len(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
