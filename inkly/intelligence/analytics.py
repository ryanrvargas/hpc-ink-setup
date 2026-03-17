import sqlite3


def compute_cluster_intelligence(db_path):
    """
    Compute deterministic cluster intelligence metrics from the jobs dataset.
    """

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    intelligence = {}

    intelligence["partition_success"] = partition_success_rate(conn)
    intelligence["cpu_analysis"] = cpu_bucket_analysis(conn)
    intelligence["memory_analysis"] = memory_bucket_analysis(conn)
    intelligence["failure_distribution"] = failure_distribution(conn)
    intelligence["dataset_size"] = dataset_size(conn)

    conn.close()

    return intelligence


def partition_success_rate(conn):
    query = """
    SELECT
        partition,
        COUNT(*) AS total_jobs,
        SUM(success) AS successful_jobs,
        ROUND(AVG(success), 3) AS success_rate
    FROM jobs
    GROUP BY partition
    """

    rows = conn.execute(query).fetchall()

    result = {}
    for r in rows:
        result[r["partition"]] = {
            "total_jobs": r["total_jobs"],
            "successful_jobs": r["successful_jobs"],
            "success_rate": r["success_rate"],
        }

    return result


def cpu_bucket_analysis(conn):
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

    rows = conn.execute(query).fetchall()

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

    return result


def memory_bucket_analysis(conn):
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

    rows = conn.execute(query).fetchall()

    result = {}

    for r in rows:
        result[r["mem_bucket"]] = {
            "total_jobs": r["total_jobs"],
            "failure_rate": r["failure_rate"],
        }

    return result


def failure_distribution(conn):
    query = """
    SELECT
        state,
        COUNT(*) AS count
    FROM jobs
    WHERE success = 0
    GROUP BY state
    ORDER BY count DESC
    """

    rows = conn.execute(query).fetchall()

    total_failures = sum(r["count"] for r in rows)

    result = {}

    for r in rows:
        pct = round(r["count"] / total_failures, 3) if total_failures > 0 else 0.0
        result[r["state"]] = {
            "count": r["count"],
            "percentage": pct,
        }

    return result


def dataset_size(conn):
    query = "SELECT COUNT(*) AS total FROM jobs"
    row = conn.execute(query).fetchone()

    return row["total"]
