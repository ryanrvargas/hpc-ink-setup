from inkly.intelligence.analytics import compute_cluster_intelligence


def build_intelligence_block(db_path):
    metrics = compute_cluster_intelligence(db_path)

    dataset_size = metrics["dataset_size"]

    lines = []
    lines.append("Cluster Intelligence (last 90 days):\n")

    # Partition success
    partition = metrics["partition_success"].get("general")
    if partition:
        rate = round(partition["success_rate"] * 100)
        lines.append(f"- General partition success rate: {rate}%")

    # CPU bucket insight
    cpu = metrics["cpu_analysis"].get("65+")
    if cpu:
        rate = round(cpu["failure_rate"] * 100)
        lines.append(f"- 65+ CPU jobs fail {rate}% of the time")

    # Memory insight
    mem = metrics["memory_analysis"].get("<4GB")
    if mem:
        rate = round(mem["failure_rate"] * 100)
        lines.append(f"- Jobs requesting <4GB memory fail {rate}% of the time")

    # Failure distribution
    failures = metrics["failure_distribution"]
    if failures:
        top = max(failures, key=failures.get)
        lines.append(f"- {top} is the most common failure")

    lines.append("\nOptimize resource allocation accordingly.")

    return "\n".join(lines), dataset_size