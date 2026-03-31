import sqlite3
import time
import sys
from datetime import datetime

# I keep a very small in-memory cache here so I do not recompute the same
# intelligence metrics over and over if this gets called repeatedly.
_CACHE = {}
_CACHE_TTL_SECONDS = 30


def load_cluster_intelligence_summary(db_path: str):
    """
    I use this to load precomputed intelligence summaries from SQLite.

    This function does not recompute anything. It just reads from the
    summary tables that were already built earlier and returns everything
    in a structured dictionary that the rest of Inkly can use.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Load partition-level success summaries
        partition_rows = conn.execute(
            "SELECT partition, total_jobs, successful_jobs, success_rate "
            "FROM intelligence_partition_stats"
        ).fetchall()

        # Load CPU bucket summaries
        cpu_rows = conn.execute(
            "SELECT cpu_bucket, total_jobs, successful_jobs, failed_jobs, "
            "timeout_jobs, failure_rate, timeout_rate "
            "FROM intelligence_cpu_bucket_stats"
        ).fetchall()

        # Load memory bucket summaries
        memory_rows = conn.execute(
            "SELECT mem_bucket, total_jobs, failure_rate "
            "FROM intelligence_memory_bucket_stats"
        ).fetchall()

        # Load failure-state summaries
        failure_rows = conn.execute(
            "SELECT state, count, percentage FROM intelligence_failure_stats"
        ).fetchall()

        # Load dataset size metadata
        dataset_row = conn.execute(
            "SELECT value FROM intelligence_metadata WHERE key = 'dataset_size'"
        ).fetchone()

        # I return everything in a nested structure so plugin/runtime code
        # can consume it without needing to know SQL details.
        return {
            "partition_success": {
                r["partition"]: {
                    "total_jobs": r["total_jobs"],
                    "successful_jobs": r["successful_jobs"],
                    "success_rate": r["success_rate"],
                }
                for r in partition_rows
            },
            "cpu_analysis": {
                r["cpu_bucket"]: {
                    "total_jobs": r["total_jobs"],
                    "successful_jobs": r["successful_jobs"],
                    "failed_jobs": r["failed_jobs"],
                    "timeout_jobs": r["timeout_jobs"],
                    "failure_rate": r["failure_rate"],
                    "timeout_rate": r["timeout_rate"],
                }
                for r in cpu_rows
            },
            "memory_analysis": {
                r["mem_bucket"]: {
                    "total_jobs": r["total_jobs"],
                    "failure_rate": r["failure_rate"],
                }
                for r in memory_rows
            },
            "failure_distribution": {
                r["state"]: {
                    "count": r["count"],
                    "percentage": r["percentage"],
                }
                for r in failure_rows
            },
            "dataset_size": int(dataset_row["value"]) if dataset_row else 0,
            # These timing fields are placeholders here because this function
            # is only loading already-built summaries, not computing them.
            "timings": {
                "cache_hit": None,
                "total_intelligence_ms": 0.0,
            },
        }
    finally:
        conn.close()


def rebuild_intelligence_summaries(db_path: str) -> None:
    """
    I use this to recompute all intelligence summary tables from the raw jobs table.

    The main idea here is to move the heavier aggregation work out of prompt-time
    and into refresh-time. That way prompt generation can read small summary tables
    instead of re-running all of these SQL aggregations every time.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        now = datetime.utcnow().isoformat()

        # I clear all old summary rows first so the rebuilt summaries reflect
        # the current state of the jobs table exactly.
        conn.execute("DELETE FROM intelligence_partition_stats")
        conn.execute("DELETE FROM intelligence_cpu_bucket_stats")
        conn.execute("DELETE FROM intelligence_memory_bucket_stats")
        conn.execute("DELETE FROM intelligence_failure_stats")
        conn.execute("DELETE FROM intelligence_metadata")

        # I compute partition-level success data here.
        rows = conn.execute("""
            SELECT
                partition,
                COUNT(*) AS total_jobs,
                SUM(success) AS successful_jobs,
                ROUND(AVG(success), 3) AS success_rate
            FROM jobs
            GROUP BY partition
        """).fetchall()

        for r in rows:
            conn.execute(
                """
                INSERT INTO intelligence_partition_stats
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    r["partition"],
                    r["total_jobs"],
                    r["successful_jobs"],
                    r["success_rate"],
                    now,
                ),
            )

        # I bucket jobs by CPU count here so I can see how success/failure
        # changes across different CPU request ranges.
        rows = conn.execute("""
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
        """).fetchall()

        for r in rows:
            conn.execute(
                """
                INSERT INTO intelligence_cpu_bucket_stats
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    r["cpu_bucket"],
                    r["total_jobs"],
                    r["successful_jobs"],
                    r["failed_jobs"],
                    r["timeout_jobs"],
                    r["failure_rate"],
                    r["timeout_rate"],
                    now,
                ),
            )

        # I bucket jobs by requested memory here for the same reason:
        # to understand how failure patterns change by memory request size.
        rows = conn.execute("""
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
        """).fetchall()

        for r in rows:
            conn.execute(
                """
                INSERT INTO intelligence_memory_bucket_stats
                VALUES (?, ?, ?, ?)
            """,
                (
                    r["mem_bucket"],
                    r["total_jobs"],
                    r["failure_rate"],
                    now,
                ),
            )

        # I compute failure distribution only across unsuccessful jobs.
        # This lets me see which failure states show up the most.
        rows = conn.execute("""
            SELECT
                state,
                COUNT(*) AS count
            FROM jobs
            WHERE success = 0
            GROUP BY state
            ORDER BY count DESC
        """).fetchall()

        total_failures = sum(r["count"] for r in rows)

        for r in rows:
            pct = round(r["count"] / total_failures, 3) if total_failures else 0.0

            conn.execute(
                """
                INSERT INTO intelligence_failure_stats
                VALUES (?, ?, ?, ?)
            """,
                (
                    r["state"],
                    r["count"],
                    pct,
                    now,
                ),
            )

        # I store dataset size as metadata so other code can quickly check
        # how much data is available without rerunning a lot of logic.
        row = conn.execute("SELECT COUNT(*) AS total FROM jobs").fetchone()

        conn.execute(
            """
            INSERT INTO intelligence_metadata
            VALUES (?, ?, ?)
        """,
            (
                "dataset_size",
                str(row["total"]),
                now,
            ),
        )

        conn.commit()

    finally:
        conn.close()


def _timed_query(label: str, fn):
    """
    I use this helper to time a query function and print the duration.

    This is mainly for visibility while checking whether the analytics work
    is staying fast enough.
    """
    start = time.perf_counter()
    result = fn()
    duration_ms = (time.perf_counter() - start) * 1000

    print(f"[ink][perf] {label}: {duration_ms:.2f} ms", file=sys.stderr)

    return result, duration_ms


def get_dataset_size(db_path) -> int:
    """
    I use this as the lightweight dataset guard query.

    This only checks how many rows exist in the jobs table. It is much cheaper
    than computing the full intelligence summary, so it is useful before doing
    anything more expensive.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        row = conn.execute("SELECT COUNT(*) AS total FROM jobs").fetchone()
        return row["total"] if row is not None else 0
    finally:
        conn.close()


def compute_cluster_intelligence(db_path):
    """
    I use this to compute the full intelligence dictionary directly from the jobs table.

    This path is different from load_cluster_intelligence_summary():
    - load_cluster_intelligence_summary() reads already-built summary tables
    - compute_cluster_intelligence() computes everything live from the jobs table

    I also use a small cache here so repeated calls do not keep re-running
    the same queries within a short time window.
    """
    now = time.time()
    cache_key = str(db_path)

    # If I already computed this recently, return the cached copy instead.
    cached = _CACHE.get(cache_key)
    if cached is not None:
        cached_result, cached_at = cached
        age = now - cached_at
        if age < _CACHE_TTL_SECONDS:
            cached_copy = dict(cached_result)
            cached_timings = dict(cached_copy.get("timings", {}))
            cached_timings["cache_hit"] = True
            cached_timings["total_intelligence_ms"] = 0.0
            cached_copy["timings"] = cached_timings
            print(
                f"[ink][perf] intelligence_cache_hit: age={age:.2f}s",
                file=sys.stderr,
            )
            return cached_copy

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        total_start = time.perf_counter()

        # I compute each summary section separately so the code stays modular
        # and so I can time each section independently.
        partition_result, partition_ms = partition_success_rate(conn)
        cpu_result, cpu_ms = cpu_bucket_analysis(conn)
        memory_result, memory_ms = memory_bucket_analysis(conn)
        failure_result, failure_ms = failure_distribution(conn)
        dataset_size_value = dataset_size(conn)

        total_ms = (time.perf_counter() - total_start) * 1000
        print(f"[ink][perf] total_intelligence: {total_ms:.2f} ms", file=sys.stderr)

        intelligence = {
            "partition_success": partition_result,
            "cpu_analysis": cpu_result,
            "memory_analysis": memory_result,
            "failure_distribution": failure_result,
            "dataset_size": dataset_size_value,
            "timings": {
                "partition_success_ms": round(partition_ms, 2),
                "cpu_analysis_ms": round(cpu_ms, 2),
                "memory_analysis_ms": round(memory_ms, 2),
                "failure_distribution_ms": round(failure_ms, 2),
                "total_intelligence_ms": round(total_ms, 2),
                "cache_hit": False,
            },
        }

        # I cache the computed result so the next call can reuse it if it happens soon.
        _CACHE[cache_key] = (intelligence, now)
        return intelligence
    finally:
        conn.close()


def partition_success_rate(conn):
    """
    I use this to compute success rates grouped by partition.
    """
    query = """
    SELECT
        partition,
        COUNT(*) AS total_jobs,
        SUM(success) AS successful_jobs,
        ROUND(AVG(success), 3) AS success_rate
    FROM jobs
    GROUP BY partition
    """

    def _query():
        return conn.execute(query).fetchall()

    rows, duration_ms = _timed_query("partition_success", _query)

    result = {}
    for r in rows:
        result[r["partition"]] = {
            "total_jobs": r["total_jobs"],
            "successful_jobs": r["successful_jobs"],
            "success_rate": r["success_rate"],
        }

    return result, duration_ms


def cpu_bucket_analysis(conn):
    """
    I use this to group jobs into CPU-count buckets and measure how each bucket performs.

    This helps show whether certain CPU request sizes are associated with
    more failures or more timeouts.
    """
    query = """
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
    """

    def _query():
        return conn.execute(query).fetchall()

    rows, duration_ms = _timed_query("cpu_bucket_analysis", _query)

    result = {}

    for r in rows:
        result[r["cpu_bucket"]] = {
            "total_jobs": r["total_jobs"],
            "successful_jobs": r["successful_jobs"],
            "failed_jobs": r["failed_jobs"],
            "timeout_jobs": r["timeout_jobs"],
            "failure_rate": r["failure_rate"],
            "timeout_rate": r["timeout_rate"],
        }

    return result, duration_ms


def memory_bucket_analysis(conn):
    """
    I use this to group jobs into memory buckets and compute failure rates for each bucket.
    """
    query = """
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
    """

    def _query():
        return conn.execute(query).fetchall()

    rows, duration_ms = _timed_query("memory_analysis", _query)

    result = {}

    for r in rows:
        result[r["mem_bucket"]] = {
            "total_jobs": r["total_jobs"],
            "failure_rate": r["failure_rate"],
        }

    return result, duration_ms


def failure_distribution(conn):
    """
    I use this to measure how failure states are distributed across unsuccessful jobs.
    """
    query = """
    SELECT
        state,
        COUNT(*) AS count
    FROM jobs
    WHERE success = 0
    GROUP BY state
    ORDER BY count DESC
    """

    def _query():
        return conn.execute(query).fetchall()

    rows, duration_ms = _timed_query("failure_distribution", _query)

    total_failures = sum(r["count"] for r in rows)

    result = {}

    for r in rows:
        pct = round(r["count"] / total_failures, 3) if total_failures > 0 else 0.0
        result[r["state"]] = {
            "count": r["count"],
            "percentage": pct,
        }

    return result, duration_ms


def dataset_size(conn):
    """
    I use this internal helper when I already have an open database connection.

    This is different from get_dataset_size() because that one opens its own connection.
    """
    query = "SELECT COUNT(*) AS total FROM jobs"
    row = conn.execute(query).fetchone()

    return row["total"]