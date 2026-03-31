import sqlite3
import time
import sys
from datetime import datetime

# Small in-memory cache to avoid recomputing intelligence metrics repeatedly.
# Key = db_path, Value = (result_dict, timestamp)
_CACHE = {}

# Cache TTL (seconds). After this, results are recomputed.
_CACHE_TTL_SECONDS = 30


def load_cluster_intelligence_summary(db_path: str):
    """
    Load precomputed intelligence summaries from SQLite.

    This reads from summary tables that were already built during refresh.
    No aggregation or heavy computation happens here.

    This is the fast path used at runtime when prompt generation needs
    cluster insights without paying SQL aggregation cost.
    """
    conn = sqlite3.connect(db_path)

    # Use row objects so results can be accessed by column name.
    conn.row_factory = sqlite3.Row

    try:
        # Each of these tables is precomputed and stored during refresh.

        # Partition-level success metrics
        partition_rows = conn.execute(
            "SELECT partition, total_jobs, successful_jobs, success_rate "
            "FROM intelligence_partition_stats"
        ).fetchall()

        # CPU bucket analysis (grouped by requested CPU ranges)
        cpu_rows = conn.execute(
            "SELECT cpu_bucket, total_jobs, successful_jobs, failed_jobs, "
            "timeout_jobs, failure_rate, timeout_rate "
            "FROM intelligence_cpu_bucket_stats"
        ).fetchall()

        # Memory bucket analysis (grouped by requested memory ranges)
        memory_rows = conn.execute(
            "SELECT mem_bucket, total_jobs, failure_rate "
            "FROM intelligence_memory_bucket_stats"
        ).fetchall()

        # Failure state distribution (FAILED, TIMEOUT, etc.)
        failure_rows = conn.execute(
            "SELECT state, count, percentage FROM intelligence_failure_stats"
        ).fetchall()

        # Metadata table used for quick-access values (no recomputation needed)
        dataset_row = conn.execute(
            "SELECT value FROM intelligence_metadata WHERE key = 'dataset_size'"
        ).fetchone()

        # Convert SQL rows into a structured dictionary.
        # This isolates SQL structure from the rest of the system.
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
            # Dataset size is stored as text → convert to int safely
            "dataset_size": int(dataset_row["value"]) if dataset_row else 0,

            # No computation happens here, so timing values are placeholders
            "timings": {
                "cache_hit": None,
                "total_intelligence_ms": 0.0,
            },
        }
    finally:
        conn.close()


def rebuild_intelligence_summaries(db_path: str) -> None:
    """
    Recompute all intelligence summary tables from the raw jobs table.

    This is the "heavy" path that performs aggregation.
    It is meant to run during refresh, not during prompt generation.

    Design goal:
    - Move expensive SQL work out of runtime
    - Store compact summary tables for fast reads later
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        now = datetime.utcnow().isoformat()

        # Clear existing summary tables before rebuilding.
        # This ensures summaries reflect the current dataset exactly.
        conn.execute("DELETE FROM intelligence_partition_stats")
        conn.execute("DELETE FROM intelligence_cpu_bucket_stats")
        conn.execute("DELETE FROM intelligence_memory_bucket_stats")
        conn.execute("DELETE FROM intelligence_failure_stats")
        conn.execute("DELETE FROM intelligence_metadata")

        # Partition success rates (core high-level metric)
        rows = conn.execute("""
            SELECT
                partition,
                COUNT(*) AS total_jobs,
                SUM(success) AS successful_jobs,
                ROUND(AVG(success), 3) AS success_rate
            FROM jobs
            GROUP BY partition
        """).fetchall()

        # Insert aggregated partition results into summary table
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

        # CPU bucket aggregation (detect scaling/failure patterns)
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

        # Memory bucket aggregation (detect memory-related failures)
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

        # Failure distribution across unsuccessful jobs only
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
            # Normalize percentage relative to total failures
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

        # Store dataset size separately for fast access (no aggregation needed later)
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
    Measure execution time of a query function and print it.

    Used for performance validation and debugging query cost.
    """
    start = time.perf_counter()
    result = fn()
    duration_ms = (time.perf_counter() - start) * 1000

    print(f"[ink][perf] {label}: {duration_ms:.2f} ms", file=sys.stderr)

    return result, duration_ms