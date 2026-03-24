"""
This module provides utilities to measure the performance of SQL queries
against the Inkly job‑history SQLite database and verify that appropriate
indexes are being used.  The intent is to ensure that analytics queries
run quickly and scale to larger datasets without degrading the user
experience.  The functions defined here can be invoked directly in
Python code or from a command line for ad‑hoc validation.

Usage example:

```
from performance_validation import PerformanceValidator

# Define a set of representative queries for your analytics engine.
QUERIES = [
    "SELECT COUNT(*) FROM jobs",  # total job count
    "SELECT user, COUNT(*) FROM jobs GROUP BY user",  # jobs per user
    "SELECT state, COUNT(*) FROM jobs GROUP BY state",  # jobs per state
]

validator = PerformanceValidator("/path/to/job_history.db", QUERIES, max_latency_ms=500)
results = validator.validate()
for q, info in results.items():
    print(f"Query: {q}\n  Latency (ms): {info['latency_ms']:.2f}\n  Uses index: {info['uses_index']}\n")
```

When run as a script, ``performance_validation.py`` accepts a path to
the SQLite database and performs validation on a set of predefined
queries.  See the ``__main__`` section for details.

NOTE: The performance thresholds and queries here are illustrative.
They should be tailored to match the actual schema and workload of
your job‑history database.  Consult the milestone documentation for
guidance on which analytics operations need to meet latency targets.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List


@dataclass
class QueryResult:
    """Represents the performance characteristics of a single SQL query."""

    latency_ms: float
    uses_index: bool


@dataclass
class PerformanceValidator:
    """
    Validates the performance of analytics queries on a SQLite database.

    Parameters
    ----------
    db_path: str
        Path to the SQLite database file containing the job history.
    queries: Iterable[str]
        A collection of SQL queries to validate.  Queries should be
        representative of the workload executed by the analytics engine.
    max_latency_ms: float, optional
        The maximum acceptable average latency (in milliseconds) for each
        query.  If ``None``, no latency threshold will be enforced.
    runs_per_query: int, optional
        Number of times to execute each query when measuring latency.
        Running queries multiple times helps mitigate caching effects.
    """

    db_path: str
    queries: Iterable[str]
    max_latency_ms: float | None = None
    runs_per_query: int = 3
    _conn: sqlite3.Connection | None = field(default=None, init=False, repr=False)

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
        return self._conn

    def _measure_latency(self, cursor: sqlite3.Cursor, query: str) -> float:
        """
        Measure the average latency of executing a query.

        Parameters
        ----------
        cursor: sqlite3.Cursor
            Cursor object for executing queries.
        query: str
            The SQL query to execute.

        Returns
        -------
        float
            The average latency in milliseconds.
        """
        latencies: List[float] = []
        for _ in range(self.runs_per_query):
            start = time.perf_counter()
            cursor.execute(query)
            # fetch all results to ensure the full query is executed
            cursor.fetchall()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)
        return sum(latencies) / len(latencies) if latencies else 0.0

    def _uses_index(self, cursor: sqlite3.Cursor, query: str) -> bool:
        """
        Determine whether a query uses an index by inspecting the query plan.

        Parameters
        ----------
        cursor: sqlite3.Cursor
            Cursor object for executing queries.
        query: str
            The SQL query to examine.

        Returns
        -------
        bool
            True if the query plan indicates that an index is used, False otherwise.

        Notes
        -----
        This function uses ``EXPLAIN QUERY PLAN`` to inspect how SQLite will
        execute the query.  It checks for the phrase "USING INDEX" in any
        output row.  For more complex queries, additional analysis may be
        required.
        """
        plan = cursor.execute(f"EXPLAIN QUERY PLAN {query}").fetchall()
        # The third column of each row contains a textual description of the plan
        for row in plan:
            # SQLite's query plan output is typically (id, parent, notUsed, detail)
            # The detail field (index 3) may mention "USING INDEX"
            if any(
                isinstance(col, str) and "USING INDEX" in col.upper() for col in row
            ):
                return True
        return False

    def validate(self) -> Dict[str, QueryResult]:
        """
        Execute and evaluate all queries.

        Returns
        -------
        Dict[str, QueryResult]
            A mapping from the original query string to its measured
            performance characteristics.  Each entry contains the average
            latency in milliseconds and whether an index was used.
        """
        conn = self._connect()
        cursor = conn.cursor()
        results: Dict[str, QueryResult] = {}
        for query in self.queries:
            latency = self._measure_latency(cursor, query)
            uses_index = self._uses_index(cursor, query)
            results[query] = QueryResult(latency_ms=latency, uses_index=uses_index)
        return results

    def assert_valid(self) -> None:
        """
        Validate queries and raise an exception if any fail the latency threshold.

        Raises
        ------
        AssertionError
            If ``max_latency_ms`` is set and any query exceeds the threshold.
        """
        results = self.validate()
        if self.max_latency_ms is not None:
            for query, result in results.items():
                if result.latency_ms > self.max_latency_ms:
                    raise AssertionError(
                        f"Query exceeded max latency: {query!r} ({result.latency_ms:.2f} ms > {self.max_latency_ms:.2f} ms)"
                    )


def _default_queries() -> List[str]:
    """
    Default query set for performance validation.

    These queries are intentionally aligned with the analytics workload
    implemented in `inkly/intelligence/analytics.py`. The goal is to ensure
    that the same queries used for prompt enrichment are performant at scale.

    This function serves two purposes:
    1. Validate that core analytics queries execute within acceptable latency.
    2. Verify that indexed columns are being utilized where expected.

    Query Categories:
    -----------------
    - Dataset Size:
        Ensures COUNT(*) operations remain fast for dataset guard logic.

    - Partition Analytics:
        Mirrors partition-level success rate calculations used in prompt injection.

    - CPU Bucket Analytics:
        Validates CASE-based bucketing logic and aggregation performance.

    - Memory Bucket Analytics:
        Tests memory-based grouping and failure rate calculations.

    - Failure Distribution:
        Ensures grouping + filtering on failed jobs is efficient.

    - Indexed Filters:
        Directly tests whether indexes on key columns are being used:
            - partition
            - success
            - alloc_cpus
            - req_mem_mb

    Important:
    ----------
    These queries MUST stay in sync with analytics.py.
    If analytics logic changes, this list must be updated accordingly.

    This validator does NOT measure total system latency (including caching
    and prompt construction). It strictly measures raw SQL execution cost.

    Returns:
        List[str]: SQL queries used for performance validation.
    """
    return [
        # dataset size guard query
        "SELECT COUNT(*) AS total FROM jobs",

        # partition analytics
        """
        SELECT
            partition,
            COUNT(*) AS total_jobs,
            SUM(success) AS successful_jobs,
            ROUND(AVG(success), 3) AS success_rate
        FROM jobs
        GROUP BY partition
        """,

        # cpu bucket analytics
        """
        SELECT
            CASE
                WHEN alloc_cpus BETWEEN 1 AND 4 THEN '1-4'
                WHEN alloc_cpus BETWEEN 5 AND 16 THEN '5-16'
                WHEN alloc_cpus BETWEEN 17 AND 64 THEN '17-64'
                ELSE '65+'
            END AS cpu_bucket,
            COUNT(*) AS total_jobs,
            SUM(success) AS successful_jobs,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failed_jobs,
            SUM(CASE WHEN state = 'TIMEOUT' THEN 1 ELSE 0 END) AS timeout_jobs,
            ROUND(1.0 - AVG(success), 3) AS failure_rate,
            ROUND(
                CAST(SUM(CASE WHEN state = 'TIMEOUT' THEN 1 ELSE 0 END) AS FLOAT)
                / COUNT(*),
                3
            ) AS timeout_rate
        FROM jobs
        GROUP BY cpu_bucket
        """,

        # memory bucket analytics
        """
        SELECT
            CASE
                WHEN req_mem_mb < 4096 THEN '<4GB'
                WHEN req_mem_mb < 8192 THEN '4-8GB'
                WHEN req_mem_mb < 16384 THEN '8-16GB'
                WHEN req_mem_mb < 32768 THEN '16-32GB'
                WHEN req_mem_mb < 65536 THEN '32-64GB'
                ELSE '64GB+'
            END AS mem_bucket,
            COUNT(*) AS total_jobs,
            ROUND(1 - AVG(success), 3) AS failure_rate
        FROM jobs
        GROUP BY mem_bucket
        """,

        # failure distribution
        """
        SELECT
            state,
            COUNT(*) AS count
        FROM jobs
        WHERE success = 0
        GROUP BY state
        ORDER BY count DESC
        """,

        # simple indexed filter checks
        "SELECT * FROM jobs WHERE partition = 'general'",
        "SELECT * FROM jobs WHERE success = 0",
        "SELECT * FROM jobs WHERE alloc_cpus = 4",
        "SELECT * FROM jobs WHERE req_mem_mb = 4096",
    ]


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Validate the performance of analytics queries against an Inkly job history database."
        )
    )
    parser.add_argument(
        "db",
        help="Path to the SQLite database file",
    )
    parser.add_argument(
        "--max-latency",
        type=float,
        default=500.0,
        help="Maximum allowed average latency per query in milliseconds (default: 500)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of times to run each query when measuring latency (default: 3)",
    )
    parser.add_argument(
        "--queries",
        nargs="*",
        help=(
            "Custom queries to validate.  If omitted, a set of default queries is used."
        ),
    )
    args = parser.parse_args()
    queries = args.queries or _default_queries()
    validator = PerformanceValidator(
        db_path=args.db,
        queries=queries,
        max_latency_ms=args.max_latency,
        runs_per_query=args.runs,
    )
    try:
        validator.assert_valid()
    except AssertionError as e:
        print(f"Performance validation failed:\n{e}")
    else:
        results = validator.validate()
        print("Performance validation passed. Results:")
        for query, info in results.items():
            print(
                f"Query: {query}\n  Avg latency (ms): {info.latency_ms:.2f}\n  Uses index: {'Yes' if info.uses_index else 'No'}\n"
            )


if __name__ == "__main__":
    main()
