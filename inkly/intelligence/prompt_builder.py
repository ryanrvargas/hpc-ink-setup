import sys
from dataclasses import dataclass
from typing import Optional

from inkly.intelligence.analytics import (
    compute_cluster_intelligence,
    get_dataset_size,
)


@dataclass
class IntelligenceInjectionResult:
    prompt: str
    injected: bool
    dataset_size: int
    message: Optional[str] = None


def build_intelligence_block(db_path: str, config):
    """
    Build the structured intelligence prompt block from analytics output.

    Returns:
        tuple[str, int]: (formatted block, dataset_size)
    """
    metrics = compute_cluster_intelligence(db_path)
    dataset_size = metrics["dataset_size"]

    lines = [f"Cluster Intelligence (last {config.intelligence.window_days} days):"]

    partition = metrics["partition_success"].get("general")
    if partition and partition.get("success_rate") is not None:
        rate = round(partition["success_rate"] * 100)
        lines.append(f"- General partition success rate: {rate}%")

    cpu = metrics["cpu_analysis"].get("65+")
    if cpu:
        failure_rate = cpu.get("failure_rate")
        timeout_rate = cpu.get("timeout_rate")

        if failure_rate is not None and timeout_rate is not None:
            failure_pct = round(failure_rate * 100)
            timeout_pct = round(timeout_rate * 100)

            if failure_rate > 0.8:
                lines.append(
                    f"- 65+ CPU jobs fail {failure_pct}% of the time (very high failure rate)"
                )
            elif timeout_rate > 0.2:
                lines.append(f"- 65+ CPU jobs timeout {timeout_pct}% of the time")
            else:
                lines.append(f"- 65+ CPU jobs fail {failure_pct}% of the time")

    mem = metrics["memory_analysis"].get("<4GB")
    if mem and mem.get("failure_rate") is not None:
        rate = round(mem["failure_rate"] * 100)
        lines.append(f"- Jobs requesting <4GB memory fail {rate}% of the time")

    failures = metrics["failure_distribution"]
    if failures:
        top = max(failures, key=lambda k: failures[k]["count"])
        pct = round(failures[top]["percentage"] * 100)
        lines.append(f"- {top} is the most common failure ({pct}%)")

    lines.append("")
    lines.append("Optimize resource allocation accordingly.")

    return "\n".join(lines), dataset_size


def maybe_inject_intelligence(
    prompt: str, config, db_path: str
) -> IntelligenceInjectionResult:
    """
    Conditionally append structured cluster intelligence to the prompt.

    Guard conditions:
    - intelligence.enabled must be true
    - dataset_size must meet min_jobs_required

    Returns a structured result so the runtime can surface a
    user-facing notice when intelligence is skipped.
    """
    if not config.intelligence.enabled:
        return IntelligenceInjectionResult(
            prompt=prompt,
            injected=False,
            dataset_size=0,
            message=None,
        )

    dataset_size = get_dataset_size(db_path)

    if dataset_size < config.intelligence.min_jobs_required:
        message = (
            "Cluster intelligence was not added because the job dataset is still too small "
            f"({dataset_size} jobs available, {config.intelligence.min_jobs_required} required). "
            "Continue using Inkly normally and refresh again after more jobs accumulate."
        )
        return IntelligenceInjectionResult(
            prompt=prompt,
            injected=False,
            dataset_size=dataset_size,
            message=message,
        )

    block, dataset_size = build_intelligence_block(db_path, config)

    print(f"[ink] dataset_size={dataset_size}", file=sys.stderr)

    return IntelligenceInjectionResult(
        prompt=f"{prompt}\n\n{block}\n",
        injected=True,
        dataset_size=dataset_size,
        message=None,
    )
