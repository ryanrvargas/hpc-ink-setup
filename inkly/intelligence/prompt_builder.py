from inkly.intelligence.analytics import compute_cluster_intelligence


def build_intelligence_block(db_path: str):
    """
    Build the structured intelligence prompt block from analytics output.

    Returns:
        tuple[str, int]: (formatted block, dataset_size)
    """
    metrics = compute_cluster_intelligence(db_path)
    dataset_size = metrics["dataset_size"]

    lines = ["Cluster Intelligence (last 90 days):"]

    # Partition success
    partition = metrics["partition_success"].get("general")
    if partition and partition.get("success_rate") is not None:
        rate = round(partition["success_rate"] * 100)
        lines.append(f"- General partition success rate: {rate}%")

    # CPU bucket insight
    cpu = metrics["cpu_analysis"].get("65+")
    if cpu and cpu.get("failure_rate") is not None:
        rate = round(cpu["failure_rate"] * 100)
        lines.append(f"- 65+ CPU jobs fail {rate}% of the time")

    # Memory insight
    mem = metrics["memory_analysis"].get("<4GB")
    if mem and mem.get("failure_rate") is not None:
        rate = round(mem["failure_rate"] * 100)
        lines.append(f"- Jobs requesting <4GB memory fail {rate}% of the time")

    # Most common failure
    failures = metrics["failure_distribution"]
    if failures:
        top = max(failures, key=failures.get)
        lines.append(f"- {top} is the most common failure")

    lines.append("")
    lines.append("Optimize resource allocation accordingly.")

    return "\n".join(lines), dataset_size


def maybe_inject_intelligence(prompt: str, config, db_path: str) -> str:
    """
    Conditionally append structured cluster intelligence to the prompt.

    Guard conditions:
    - intelligence.enabled must be true
    - dataset_size must meet min_jobs_required
    """
    if not config.intelligence.enabled:
        return prompt

    block, dataset_size = build_intelligence_block(db_path)

    if dataset_size < config.intelligence.min_jobs_required:
        return prompt

    return f"{prompt}\n\n{block}\n"