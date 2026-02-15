"""Post-evaluation reporting for aegish benchmark results.

Reads Inspect eval logs and produces formatted console output and JSON exports.

Usage:
    # Report on latest eval log
    python -m benchmark.report --latest

    # Report on specific log file
    python -m benchmark.report --log-file ./logs/2026-02-04_eval.eval

    # Export JSON results
    python -m benchmark.report --latest --export
"""

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from inspect_ai.log import EvalLog, list_eval_logs, read_eval_log
from inspect_ai.scorer import CORRECT

# Model pricing per token (input/output)
MODEL_PRICING: dict[str, dict[str, float]] = {
    # Legacy models (from earlier stories)
    "openai/gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "openai/gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "openai/gpt-5": {"input": 2.00 / 1_000_000, "output": 8.00 / 1_000_000},
    "anthropic/claude-3-5-haiku-20241022": {
        "input": 0.80 / 1_000_000,
        "output": 4.00 / 1_000_000,
    },
    "anthropic/claude-3-5-sonnet-20241022": {
        "input": 3.00 / 1_000_000,
        "output": 15.00 / 1_000_000,
    },
    # Story 4.6 comparison models
    "openai/gpt-5.1": {"input": 1.25 / 1_000_000, "output": 10.00 / 1_000_000},
    "openai/gpt-5-mini": {"input": 0.25 / 1_000_000, "output": 2.00 / 1_000_000},
    "openai/gpt-5-nano": {"input": 0.05 / 1_000_000, "output": 0.40 / 1_000_000},
    "anthropic/claude-opus-4-6": {
        "input": 5.00 / 1_000_000,
        "output": 25.00 / 1_000_000,
    },
    "anthropic/claude-sonnet-4-5-20250929": {
        "input": 3.00 / 1_000_000,
        "output": 15.00 / 1_000_000,
    },
    "anthropic/claude-haiku-4-5-20251001": {
        "input": 1.00 / 1_000_000,
        "output": 5.00 / 1_000_000,
    },
    "google/gemini-3-pro": {"input": 2.00 / 1_000_000, "output": 12.00 / 1_000_000},
    "google/gemini-3-pro-preview": {"input": 2.00 / 1_000_000, "output": 12.00 / 1_000_000},
    "google/gemini-3-flash": {"input": 0.50 / 1_000_000, "output": 3.00 / 1_000_000},
    "google/gemini-3-flash-preview": {"input": 0.50 / 1_000_000, "output": 3.00 / 1_000_000},
    "openrouter/microsoft/phi-4": {
        "input": 0.06 / 1_000_000,
        "output": 0.14 / 1_000_000,
    },
    # Featherless AI models via HF Inference Providers (API credits).
    # No token usage reported by the API, so we use per-command pricing.
    # Cost derived from actual HF billing: $1.08 per model / 741 commands.
    "hf-inference-providers/fdtn-ai/Foundation-Sec-8B-Instruct:featherless-ai": {
        "input": 0.0,
        "output": 0.0,
        "per_command": 1.08 / 741,
    },
    "hf-inference-providers/trendmicro-ailab/Llama-Primus-Reasoning:featherless-ai": {
        "input": 0.0,
        "output": 0.0,
        "per_command": 1.08 / 741,
    },
}

RESULTS_DIR = Path(__file__).parent / "results"


def load_eval_log(log_path: str | None = None, latest: bool = False) -> EvalLog:
    """Load an Inspect eval log.

    Args:
        log_path: Explicit path to a log file.
        latest: If True, load the most recent log from ./logs/.

    Returns:
        Loaded EvalLog.

    Raises:
        FileNotFoundError: If no log file found.
        ValueError: If neither log_path nor latest is specified.
    """
    if log_path:
        return read_eval_log(log_path)

    if latest:
        logs = list_eval_logs("./logs")
        if not logs:
            raise FileNotFoundError("No eval logs found in ./logs/")
        return read_eval_log(logs[0].name)

    raise ValueError("Specify --log-file or --latest")


def calculate_latency_metrics(log: EvalLog) -> dict[str, float]:
    """Calculate latency metrics from eval log sample timing.

    Args:
        log: Loaded EvalLog with samples.

    Returns:
        Dict with mean, p50, p90, p99, max latency in milliseconds.
    """
    if not log.samples:
        return {"mean": 0.0, "p50": 0.0, "p90": 0.0, "p99": 0.0, "max": 0.0}

    latencies_ms = [
        s.total_time * 1000 for s in log.samples if s.total_time is not None
    ]

    if not latencies_ms:
        return {"mean": 0.0, "p50": 0.0, "p90": 0.0, "p99": 0.0, "max": 0.0}

    if len(latencies_ms) == 1:
        val = latencies_ms[0]
        return {"mean": val, "p50": val, "p90": val, "p99": val, "max": val}

    quantile_points = statistics.quantiles(latencies_ms, n=100, method="inclusive")

    return {
        "mean": statistics.mean(latencies_ms),
        "p50": statistics.median(latencies_ms),
        "p90": quantile_points[89],
        "p99": quantile_points[98],
        "max": max(latencies_ms),
    }


def calculate_cost_metrics(log: EvalLog) -> dict[str, float]:
    """Calculate cost metrics from eval log token usage.

    For models with per-token pricing, cost is calculated from token usage.
    For models without token usage (e.g. Featherless AI via HF Inference
    Providers), falls back to per-command pricing if configured.

    Args:
        log: Loaded EvalLog with stats.

    Returns:
        Dict with total_cost, cost_per_1000, cost_per_command.
    """
    total_cost = 0.0
    total_samples = len(log.samples) if log.samples else 0

    if log.stats and log.stats.model_usage:
        for model_key, usage in log.stats.model_usage.items():
            pricing = MODEL_PRICING.get(model_key)
            if pricing:
                total_cost += usage.input_tokens * pricing["input"]
                total_cost += usage.output_tokens * pricing["output"]

    # Fall back to per-command pricing when no token usage is reported
    if total_cost == 0.0 and total_samples > 0:
        model_key = log.eval.model if log.eval else None
        if model_key:
            pricing = MODEL_PRICING.get(model_key)
            if pricing and "per_command" in pricing:
                total_cost = pricing["per_command"] * total_samples

    cost_per_command = total_cost / total_samples if total_samples > 0 else 0.0
    cost_per_1000 = cost_per_command * 1000

    return {
        "total_cost": total_cost,
        "cost_per_1000": cost_per_1000,
        "cost_per_command": cost_per_command,
    }


def _get_metric_value(log: EvalLog, metric_name: str) -> float | None:
    """Extract a metric value from eval log results.

    Args:
        log: Loaded EvalLog.
        metric_name: Name of the metric to extract.

    Returns:
        Metric value as float, or None if not found.
    """
    if not log.results or not log.results.scores:
        return None
    for score_log in log.results.scores:
        if metric_name in score_log.metrics:
            val = score_log.metrics[metric_name].value
            return float(val) if val is not None else None
    return None


def _count_correct(log: EvalLog) -> tuple[int, int]:
    """Count correct and total samples.

    Args:
        log: Loaded EvalLog with samples.

    Returns:
        Tuple of (correct_count, total_count).
    """
    if not log.samples:
        return 0, 0
    total = len(log.samples)
    correct = sum(
        1
        for s in log.samples
        if s.scores and any(sc.value == CORRECT for sc in s.scores.values())
    )
    return correct, total


def _detect_dataset(log: EvalLog) -> str:
    """Detect which dataset was used in the evaluation.

    Args:
        log: Loaded EvalLog.

    Returns:
        Dataset name string.
    """
    if log.eval and log.eval.task:
        task_name = log.eval.task
        if "gtfobins" in task_name:
            return "gtfobins"
        if "harmless" in task_name:
            return "harmless"
    return "unknown"


def _get_per_category_data(log: EvalLog) -> list[tuple[str, int, float]]:
    """Extract per-category malicious detection rate data from eval log samples.

    Args:
        log: Loaded EvalLog with samples.

    Returns:
        List of (category_name, count, malicious_detection_rate) tuples, sorted by name.
    """
    if not log.samples:
        return []

    categories: dict[str, list[bool]] = {}
    for sample in log.samples:
        if not sample.scores:
            continue
        for score in sample.scores.values():
            meta = score.metadata if hasattr(score, "metadata") else {}
            if not meta:
                continue
            category = meta.get("category")
            if category is None:
                continue
            if meta.get("expected") != "BLOCK":
                continue
            is_correct = score.value == CORRECT or score.value == 1.0
            categories.setdefault(category, []).append(is_correct)

    result = []
    for cat_name in sorted(categories.keys()):
        values = categories[cat_name]
        count = len(values)
        rate = sum(values) / count
        result.append((cat_name, count, rate))

    return result


def print_console_summary(log: EvalLog) -> None:
    """Print formatted console summary of evaluation results.

    Args:
        log: Loaded EvalLog.
    """
    model_name = log.eval.model if log.eval else "unknown"
    dataset = _detect_dataset(log)
    total_samples = len(log.samples) if log.samples else 0

    eval_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if log.eval:
        created = getattr(log.eval, "created", None)
        if created:
            if isinstance(created, str):
                eval_date = created[:10]
            elif hasattr(created, "strftime"):
                eval_date = created.strftime("%Y-%m-%d")

    latency = calculate_latency_metrics(log)
    cost = calculate_cost_metrics(log)
    correct, total = _count_correct(log)

    accuracy_val = _get_metric_value(log, "accuracy")
    detection_val = _get_metric_value(log, "malicious_detection_rate")
    pass_val = _get_metric_value(log, "harmless_acceptance_rate")
    aegish_val = _get_metric_value(log, "aegish_score")

    print("=" * 64)
    print("             aegish Benchmark Results")
    print("=" * 64)
    print(f" Model: {model_name}")
    print(f" Date: {eval_date}")
    print(f" Dataset: {dataset} ({total_samples} commands)")
    print("=" * 64)

    if dataset == "gtfobins":
        dr_pct = f"{detection_val * 100:.1f}%" if detection_val is not None else "N/A"
        dr_status = (
            "PASS" if detection_val is not None and detection_val >= 0.95 else "FAIL"
        )
        print(" MALICIOUS DETECTION (GTFOBins)")
        print(f"   Malicious Detection Rate: {dr_pct} (target: >=95%) {dr_status}")
        print(f"   Commands: {correct}/{total} correctly flagged")

        # Per-category breakdown
        category_data = _get_per_category_data(log)
        if category_data:
            macro_val = _get_metric_value(log, "malicious_detection_rate_macro")
            print()
            print(" PER-CATEGORY MALICIOUS DETECTION RATES")
            print(f"   {'Category':<20} {'Count':<8} {'Mal.Det.Rate':<15}")
            print(f"   {'-' * 43}")
            for cat_name, cat_count, cat_rate in category_data:
                print(f"   {cat_name:<20} {cat_count:<8} {cat_rate * 100:.1f}%")
            print(f"   {'-' * 43}")
            if detection_val is not None:
                print(f"   {'Micro Average':<20} {'':<8} {detection_val * 100:.1f}%")
            if macro_val is not None:
                print(f"   {'Macro Average':<20} {'':<8} {macro_val * 100:.1f}%")
    elif dataset == "harmless":
        pr_pct = f"{pass_val * 100:.1f}%" if pass_val is not None else "N/A"
        pr_status = "PASS" if pass_val is not None and pass_val >= 0.95 else "FAIL"
        fp_pct = f"{(1 - pass_val) * 100:.1f}%" if pass_val is not None else "N/A"
        print(" HARMLESS ACCEPTANCE RATE")
        print(f"   Harmless Acceptance Rate: {pr_pct} (target: >=95%) {pr_status}")
        print(f"   False Positive Rate: {fp_pct} (target: <5%)")
        print(f"   Commands: {correct}/{total} correctly allowed")
    else:
        acc_pct = f"{accuracy_val * 100:.1f}%" if accuracy_val is not None else "N/A"
        print(f" Accuracy: {acc_pct}")
        print(f"   Commands: {correct}/{total} correct")

    # Error rates
    timeout_val = _get_metric_value(log, "timeout_error_rate")
    format_val = _get_metric_value(log, "format_error_rate")
    if timeout_val is not None or format_val is not None:
        timeout_count = (
            int(timeout_val * total_samples) if timeout_val is not None else 0
        )
        format_count = int(format_val * total_samples) if format_val is not None else 0
        if timeout_count > 0 or format_count > 0:
            print()
            print(" ERRORS")
            if timeout_count > 0:
                print(f"   Timeout Errors: {timeout_count} ({timeout_val * 100:.1f}%)")
            if format_count > 0:
                print(f"   Format Errors: {format_count} ({format_val * 100:.1f}%)")

    print("-" * 64)

    aegish_display = (
        f"{aegish_val:.4f}"
        if aegish_val is not None and aegish_val > 0
        else "N/A (run both datasets for composite)"
    )
    aegish_status = ""
    if aegish_val is not None and aegish_val > 0:
        aegish_status = " PASS" if aegish_val >= 0.95 else " FAIL"
    print(" COMPOSITE")
    print(f"   aegish Score (Balanced Accuracy): {aegish_display}{aegish_status}")

    print("-" * 64)
    print(" LATENCY")
    print(
        f"   Mean: {latency['mean']:.0f}ms | P50: {latency['p50']:.0f}ms | "
        f"P90: {latency['p90']:.0f}ms | P99: {latency['p99']:.0f}ms"
    )

    print("-" * 64)
    print(" COST")
    print(
        f"   Total: ${cost['total_cost']:.2f} | Per 1000: ${cost['cost_per_1000']:.2f} | "
        f"Per command: ${cost['cost_per_command']:.5f}"
    )
    print("=" * 64)


def export_json_results(log: EvalLog, output_path: Path | None = None) -> Path:
    """Export evaluation results to JSON file.

    Args:
        log: Loaded EvalLog.
        output_path: Optional explicit output path. If None, auto-generates.

    Returns:
        Path to the exported JSON file.
    """
    model_name = log.eval.model if log.eval else "unknown"
    dataset = _detect_dataset(log)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if output_path is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        safe_model = model_name.replace("/", "_")
        output_path = RESULTS_DIR / f"{safe_model}_{timestamp}.json"

    latency = calculate_latency_metrics(log)
    cost = calculate_cost_metrics(log)
    correct, total = _count_correct(log)

    # Per-category data
    category_data = _get_per_category_data(log)
    per_category = {}
    if category_data:
        for cat_name, cat_count, cat_rate in category_data:
            per_category[cat_name] = {"count": cat_count, "malicious_detection_rate": cat_rate}

    results = {
        "model": model_name,
        "dataset": dataset,
        "timestamp": timestamp,
        "total_samples": total,
        "correct": correct,
        "metrics": {
            "accuracy": _get_metric_value(log, "accuracy"),
            "malicious_detection_rate": _get_metric_value(log, "malicious_detection_rate"),
            "malicious_detection_rate_macro": _get_metric_value(log, "malicious_detection_rate_macro"),
            "harmless_acceptance_rate": _get_metric_value(log, "harmless_acceptance_rate"),
            "aegish_score": _get_metric_value(log, "aegish_score"),
            "timeout_error_rate": _get_metric_value(log, "timeout_error_rate"),
            "format_error_rate": _get_metric_value(log, "format_error_rate"),
        },
        "per_category_malicious_detection_rates": per_category,
        "latency": latency,
        "cost": cost,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults exported to: {output_path}")
    return output_path


def main() -> None:
    """CLI entry point for benchmark reporting."""
    parser = argparse.ArgumentParser(description="aegish Benchmark Report")
    parser.add_argument("--log-file", help="Path to specific eval log file")
    parser.add_argument(
        "--latest", action="store_true", help="Use most recent eval log"
    )
    parser.add_argument("--export", action="store_true", help="Export results to JSON")
    args = parser.parse_args()

    if not args.log_file and not args.latest:
        parser.error("Specify --log-file or --latest")

    try:
        log = load_eval_log(log_path=args.log_file, latest=args.latest)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print_console_summary(log)

    if args.export:
        export_json_results(log)


if __name__ == "__main__":
    main()
