"""LLM comparison framework for aegish security classifier evaluation.

Runs evaluations across multiple LLMs and scaffolding configurations,
aggregates results, and produces comparison tables and JSON exports.

Inspect handles parallelization internally (concurrent samples, rate
limiting, etc.) so this script iterates models and delegates to
``inspect_ai.eval()`` which manages its own concurrency.

Usage:
    # Run all 11 models with both datasets
    python -m benchmark.compare

    # Run specific models
    python -m benchmark.compare --models openai/gpt-5.1,openai/gpt-5-mini

    # Run with Chain-of-Thought scaffolding
    python -m benchmark.compare --cot

    # Run only GTFOBins dataset
    python -m benchmark.compare --dataset gtfobins
"""

import argparse
import json
import logging
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log, recompute_metrics, write_eval_log

from benchmark.report import (
    RESULTS_DIR,
    _count_correct,
    _get_metric_value,
    _get_per_category_data,
    calculate_cost_metrics,
    calculate_latency_metrics,
)
from benchmark.tasks.aegish_eval import (
    aegish_gtfobins,
    aegish_harmless,
)

logger = logging.getLogger(__name__)

# All 11 comparison models in Inspect format
DEFAULT_MODELS: list[str] = [
    "openai/gpt-5.1",
    "openai/gpt-5-mini",
    "openai/gpt-5-nano",
    "anthropic/claude-opus-4-6",
    "anthropic/claude-sonnet-4-5-20250929",
    "anthropic/claude-haiku-4-5-20251001",
    "google/gemini-3-pro-preview",
    "google/gemini-3-flash-preview",
    "openrouter/microsoft/phi-4",
    "hf-inference-providers/fdtn-ai/Foundation-Sec-8B-Instruct:featherless-ai",
    "hf-inference-providers/trendmicro-ailab/Llama-Primus-Reasoning:featherless-ai",
]


def parse_models(models_arg: str | None) -> list[str]:
    """Parse comma-separated model list from CLI argument.

    Args:
        models_arg: Comma-separated model IDs, or None for all defaults.

    Returns:
        List of model ID strings.
    """
    if models_arg is None:
        return list(DEFAULT_MODELS)
    return [m.strip() for m in models_arg.split(",") if m.strip()]


def extract_metrics_from_log(log) -> dict:
    """Extract metrics from a single Inspect eval log.

    Args:
        log: An EvalLog from inspect_ai.eval().

    Returns:
        Dict with malicious_detection_rate, harmless_acceptance_rate, false_positive_rate, accuracy,
        correct, total, latency, and cost metrics.
    """
    latency = calculate_latency_metrics(log)
    cost = calculate_cost_metrics(log)
    correct, total = _count_correct(log)

    harmless_acceptance_rate_val = _get_metric_value(log, "harmless_acceptance_rate")
    false_positive_rate = (1.0 - harmless_acceptance_rate_val) if harmless_acceptance_rate_val is not None else None

    # Per-category malicious detection rates (GTFOBins only; empty for harmless)
    category_data = _get_per_category_data(log)
    per_category = {}
    if category_data:
        for cat_name, cat_count, cat_rate in category_data:
            per_category[cat_name] = {"count": cat_count, "malicious_detection_rate": cat_rate}

    return {
        "malicious_detection_rate": _get_metric_value(log, "malicious_detection_rate"),
        "malicious_detection_rate_macro": _get_metric_value(log, "malicious_detection_rate_macro"),
        "harmless_acceptance_rate": harmless_acceptance_rate_val,
        "false_positive_rate": false_positive_rate,
        "accuracy": _get_metric_value(log, "accuracy"),
        "stderr": _get_metric_value(log, "stderr"),
        "total_commands": total,
        "correct": correct,
        "per_category_malicious_detection_rates": per_category,
        "latency": latency,
        "cost": cost,
    }


def calculate_composite(
    gtfobins_metrics: dict | None, harmless_metrics: dict | None
) -> dict:
    """Calculate composite aegish Score from GTFOBins and harmless metrics.

    aegish Score = (malicious_detection_rate + harmless_acceptance_rate) / 2

    Args:
        gtfobins_metrics: Extracted metrics from GTFOBins eval, or None.
        harmless_metrics: Extracted metrics from harmless eval, or None.

    Returns:
        Dict with aegish_score, aegish_score_se, total_cost_usd,
        cost_per_1000_combined, avg_latency_ms.
    """
    dr = (
        gtfobins_metrics["malicious_detection_rate"]
        if gtfobins_metrics and gtfobins_metrics.get("malicious_detection_rate") is not None
        else 0.0
    )
    pr = (
        harmless_metrics["harmless_acceptance_rate"]
        if harmless_metrics and harmless_metrics.get("harmless_acceptance_rate") is not None
        else 0.0
    )

    total_cost = 0.0
    total_commands = 0
    latency_values = []

    for metrics in [gtfobins_metrics, harmless_metrics]:
        if metrics:
            total_cost += metrics["cost"]["total_cost"]
            total_commands += metrics["total_commands"]
            if metrics["latency"]["mean"] > 0:
                latency_values.append(metrics["latency"]["mean"])

    cost_per_1000 = (total_cost / total_commands * 1000) if total_commands > 0 else 0.0
    avg_latency = sum(latency_values) / len(latency_values) if latency_values else 0.0

    # Propagate standard error to composite score:
    # SE((DR + PR) / 2) = sqrt(SE_dr^2 + SE_pr^2) / 2
    dr_se = (
        gtfobins_metrics.get("stderr")
        if gtfobins_metrics and gtfobins_metrics.get("stderr") is not None
        else None
    )
    pr_se = (
        harmless_metrics.get("stderr")
        if harmless_metrics and harmless_metrics.get("stderr") is not None
        else None
    )
    composite_se = None
    if dr_se is not None and pr_se is not None:
        composite_se = ((dr_se**2 + pr_se**2) ** 0.5) / 2

    return {
        "aegish_score": (dr + pr) / 2,
        "aegish_score_se": composite_se,
        "total_cost_usd": total_cost,
        "cost_per_1000_combined": cost_per_1000,
        "avg_latency_ms": avg_latency,
    }


def generate_ranking(results: dict) -> list[dict]:
    """Generate ranked list of models sorted by aegish Score descending.

    Args:
        results: Dict mapping model IDs to their result dicts.

    Returns:
        List of dicts with rank, model, aegish_score, cost_per_1000.
    """
    scorable = []
    for model, data in results.items():
        if data.get("status") != "success":
            continue
        composite = data.get("composite", {})
        scorable.append(
            {
                "model": model,
                "aegish_score": composite.get("aegish_score", 0.0),
                "cost_per_1000": composite.get("cost_per_1000_combined", 0.0),
            }
        )

    scorable.sort(key=lambda x: x["aegish_score"], reverse=True)

    ranking = []
    for i, entry in enumerate(scorable, 1):
        ranking.append({"rank": i, **entry})
    return ranking


def check_existing_results(output_dir: Path) -> dict:
    """Check for existing comparison results that can be reused.

    Scans the output directory for comparison JSON files and extracts
    model results from the most recent one.

    Args:
        output_dir: Directory to scan for existing results.

    Returns:
        Dict mapping model IDs to their existing result data.
    """
    existing = {}
    if not output_dir.exists():
        return existing

    comparison_files = sorted(output_dir.glob("comparison_*.json"), reverse=True)
    if not comparison_files:
        return existing

    try:
        with open(comparison_files[0]) as f:
            data = json.load(f)
        for model, result in data.get("results", {}).items():
            if result.get("status") == "success":
                existing[model] = result
    except (json.JSONDecodeError, KeyError):
        pass

    return existing


def print_comparison_table(results: dict, ranking: list[dict]) -> None:
    """Print formatted comparison table to console.

    Columns: Rank, Model, M.Det%, H.Acc%, aegish Score, Cost, Latency.
    Values include 95% confidence intervals when available.
    Highlights models meeting targets: M.Det>=95%, H.Acc>=95%, Score>=0.95.

    Args:
        results: Dict mapping model IDs to result dicts.
        ranking: Sorted ranking list from generate_ranking().
    """
    # Header
    print("=" * 108)
    print("                          aegish LLM Comparison Results")
    print("=" * 108)
    print(
        f"{'Rank':<5} {'Model':<40} {'M.Det%':<12} {'H.Acc%':<12} "
        f"{'Score':<13} {'Cost':<10} {'Latency':<10}"
    )
    print("-" * 108)

    for entry in ranking:
        model = entry["model"]
        data = results.get(model, {})

        # Extract metrics
        gtfo = data.get("datasets", {}).get("gtfobins", {})
        harm = data.get("datasets", {}).get("harmless", {})
        composite = data.get("composite", {})

        det_rate = gtfo.get("malicious_detection_rate") if gtfo else None
        det_se = gtfo.get("stderr") if gtfo else None
        harmless_acceptance_rate = harm.get("harmless_acceptance_rate") if harm else None
        pass_se = harm.get("stderr") if harm else None
        score = composite.get("aegish_score", 0.0)
        score_se = composite.get("aegish_score_se")
        avg_latency = composite.get("avg_latency_ms", 0.0)

        # Format malicious detection rate with 95% CI and target indicator
        if det_rate is not None:
            if det_se is not None:
                ci = 1.96 * det_se * 100
                det_str = f"{det_rate * 100:.1f}±{ci:.1f}%"
            else:
                det_str = f"{det_rate * 100:.1f}%"
            if det_rate >= 0.95:
                det_str += "*"
        else:
            det_str = "N/A"

        # Format harmless acceptance rate with 95% CI and target indicator
        if harmless_acceptance_rate is not None:
            if pass_se is not None:
                ci = 1.96 * pass_se * 100
                pass_str = f"{harmless_acceptance_rate * 100:.1f}±{ci:.1f}%"
            else:
                pass_str = f"{harmless_acceptance_rate * 100:.1f}%"
            if harmless_acceptance_rate >= 0.95:
                pass_str += "*"
        else:
            pass_str = "N/A"

        # Format score with 95% CI and target indicator
        if score_se is not None:
            ci = 1.96 * score_se
            score_str = f"{score:.3f}±{ci:.3f}"
        else:
            score_str = f"{score:.3f}"
        if score >= 0.95:
            score_str += "*"

        # Format cost
        total_cost = composite.get("total_cost_usd", 0.0)
        cost_str = f"${total_cost:.2f}"

        # Format latency
        latency_str = f"{avg_latency:.0f}ms" if avg_latency > 0 else "N/A"

        # Truncate model name for display
        display_model = model if len(model) <= 38 else model[:35] + "..."

        print(
            f"{entry['rank']:<5} {display_model:<40} {det_str:<12} {pass_str:<12} "
            f"{score_str:<13} {cost_str:<10} {latency_str:<10}"
        )

    # Footer with legend
    print("-" * 108)
    print("  * = meets target (M.Det>=95%, H.Acc>=95%, Score>=0.95)")
    print("  ± = 95% confidence interval (1.96 × SE)")

    # Print failed models
    failed = [(m, d) for m, d in results.items() if d.get("status") != "success"]
    if failed:
        print(f"\n  Failed models ({len(failed)}):")
        for model, data in failed:
            print(f"    - {model}: {data.get('error', 'unknown error')}")

    print("=" * 108)


def _detect_log_dataset(log) -> str:
    """Detect which dataset an eval log belongs to.

    Args:
        log: An EvalLog from inspect_ai.eval().

    Returns:
        "gtfobins", "harmless", or "unknown".
    """
    if log.eval and log.eval.task:
        task_name = log.eval.task
        if "gtfobins" in task_name:
            return "gtfobins"
        if "harmless" in task_name:
            return "harmless"
    return "unknown"


def _build_tasks(dataset: str, cot: bool) -> list:
    """Build the list of Inspect Task objects for the requested datasets.

    Args:
        dataset: "gtfobins", "harmless", or "both".
        cot: Enable Chain-of-Thought scaffolding.

    Returns:
        List of Task objects.
    """
    tasks = []
    if dataset in ("gtfobins", "both"):
        tasks.append(aegish_gtfobins(cot=cot))
    if dataset in ("harmless", "both"):
        tasks.append(aegish_harmless(cot=cot))
    return tasks


def _process_logs(
    logs: list,
    model_list: list[str],
    cot: bool,
    dataset: str,
    results: dict[str, dict],
) -> None:
    """Process eval logs returned by inspect_ai.eval() and populate results.

    Each log is mapped back to its model + dataset, and metrics are
    extracted. Results dict is mutated in-place.

    Args:
        logs: List of EvalLog objects from eval().
        model_list: Models that were evaluated in this batch.
        cot: Whether CoT was enabled.
        dataset: Which dataset(s) were requested.
        results: Results dict to populate (mutated in-place).
    """
    # Index logs by (model, dataset_name)
    for log in logs:
        model = log.eval.model if log.eval else None
        if model is None:
            continue
        ds = _detect_log_dataset(log)

        if model not in results:
            results[model] = {
                "model": model,
                "cot": cot,
                "status": "success",
                "datasets": {},
            }

        entry = results[model]

        if log.status == "success":
            entry["datasets"][ds] = extract_metrics_from_log(log)
            print(f"    {model} {ds}: OK")
        else:
            entry["datasets"][ds] = None
            print(f"    {model} {ds}: {log.status}")

    # Fill in missing dataset slots and compute composite for each model
    for model in model_list:
        if model not in results:
            results[model] = {
                "model": model,
                "cot": cot,
                "status": "error",
                "error": "no eval logs returned",
                "datasets": {},
                "composite": {
                    "aegish_score": 0.0,
                    "aegish_score_se": None,
                    "total_cost_usd": 0.0,
                    "cost_per_1000_combined": 0.0,
                    "avg_latency_ms": 0.0,
                },
            }
            continue

        entry = results[model]
        if dataset in ("gtfobins", "both") and "gtfobins" not in entry["datasets"]:
            entry["datasets"]["gtfobins"] = None
        if dataset in ("harmless", "both") and "harmless" not in entry["datasets"]:
            entry["datasets"]["harmless"] = None

        gtfo = entry["datasets"].get("gtfobins")
        harm = entry["datasets"].get("harmless")

        if gtfo is None and harm is None:
            entry["status"] = "error"
        elif gtfo is None or harm is None:
            entry["status"] = "partial"

        if entry["status"] in ("success", "partial"):
            entry["composite"] = calculate_composite(gtfo, harm)
        else:
            entry["composite"] = {
                "aegish_score": 0.0,
                "aegish_score_se": None,
                "total_cost_usd": 0.0,
                "cost_per_1000_combined": 0.0,
                "avg_latency_ms": 0.0,
            }


def find_models_with_timeouts(logs_dir: Path | None = None) -> dict[str, int]:
    """Scan eval logs for models that experienced sample timeouts.

    Opens each ``.eval`` zip file, reads ``_journal/start.json`` for
    the model name and task, then checks individual sample JSON files
    for ``sample_limit`` events with ``type=time``.  Only the most
    recent eval per (model, task) pair is considered.

    Args:
        logs_dir: Directory containing ``.eval`` files.  Defaults to
            ``logs/`` relative to the project root.

    Returns:
        Dict mapping model ID to the number of timed-out samples.
    """
    if logs_dir is None:
        logs_dir = Path("logs")
    if not logs_dir.exists():
        return {}

    # Collect (model, task) -> (timestamp_str, path) keeping most recent
    latest: dict[tuple[str, str], tuple[str, Path]] = {}

    for eval_path in sorted(logs_dir.glob("*.eval")):
        # Filename format: TIMESTAMP_TASKNAME_ID.eval
        # Extract timestamp prefix for recency comparison
        ts_prefix = eval_path.name.split("_aegish")[0]
        try:
            with zipfile.ZipFile(eval_path, "r") as zf:
                with zf.open("_journal/start.json") as f:
                    start = json.loads(f.read())
                model = start["eval"]["model"]
                task = start["eval"]["task"]
        except (KeyError, json.JSONDecodeError, zipfile.BadZipFile):
            continue

        key = (model, task)
        if key not in latest or ts_prefix > latest[key][0]:
            latest[key] = (ts_prefix, eval_path)

    # Now count timeouts per model from the latest evals
    timeouts: dict[str, int] = {}
    for (model, _task), (_ts, eval_path) in latest.items():
        try:
            with zipfile.ZipFile(eval_path, "r") as zf:
                sample_names = [
                    n
                    for n in zf.namelist()
                    if n.startswith("samples/") and n.endswith(".json")
                ]
                count = 0
                for name in sample_names:
                    with zf.open(name) as f:
                        sample = json.loads(f.read())
                    limit = sample.get("limit")
                    if isinstance(limit, dict) and limit.get("type") == "time":
                        count += 1
                if count > 0:
                    timeouts[model] = timeouts.get(model, 0) + count
        except (zipfile.BadZipFile, json.JSONDecodeError):
            continue

    return timeouts


def find_timed_out_samples(
    logs_dir: Path | None = None,
) -> dict[str, list[dict]]:
    """Scan eval logs for the specific samples that timed out per model.

    Same efficient zip-based scanning as ``find_models_with_timeouts()``,
    but additionally collects the sample IDs that timed out and the eval
    log path so callers can retry only those samples.

    Args:
        logs_dir: Directory containing ``.eval`` files.  Defaults to
            ``logs/`` relative to the project root.

    Returns:
        Dict mapping model ID to a list of dicts, each with keys:
        ``task_name`` (str), ``eval_path`` (Path), ``sample_ids`` (list[int|str]).
    """
    if logs_dir is None:
        logs_dir = Path("logs")
    if not logs_dir.exists():
        return {}

    # Collect (model, task) -> (timestamp_str, path) keeping most recent
    latest: dict[tuple[str, str], tuple[str, Path]] = {}

    for eval_path in sorted(logs_dir.glob("*.eval")):
        ts_prefix = eval_path.name.split("_aegish")[0]
        try:
            with zipfile.ZipFile(eval_path, "r") as zf:
                with zf.open("_journal/start.json") as f:
                    start = json.loads(f.read())
                model = start["eval"]["model"]
                task = start["eval"]["task"]
        except (KeyError, json.JSONDecodeError, zipfile.BadZipFile):
            continue

        key = (model, task)
        if key not in latest or ts_prefix > latest[key][0]:
            latest[key] = (ts_prefix, eval_path)

    # Collect timed-out sample IDs per (model, task).
    # Detect both inspect_ai time limits (limit.type == "time") and
    # application-level timeouts (score answer == "TIMEOUT_ERROR").
    result: dict[str, list[dict]] = {}
    for (model, task), (_ts, eval_path) in latest.items():
        try:
            with zipfile.ZipFile(eval_path, "r") as zf:
                sample_names = [
                    n
                    for n in zf.namelist()
                    if n.startswith("samples/") and n.endswith(".json")
                ]
                timed_out_ids: list[int | str] = []
                for name in sample_names:
                    with zf.open(name) as f:
                        sample = json.loads(f.read())
                    # Check inspect_ai time limit
                    limit = sample.get("limit")
                    if isinstance(limit, dict) and limit.get("type") == "time":
                        timed_out_ids.append(sample["id"])
                        continue
                    # Check scorer-level TIMEOUT_ERROR
                    for ev in sample.get("events", []):
                        if ev.get("event") == "score":
                            score = ev.get("score", {})
                            if score.get("answer") == "TIMEOUT_ERROR":
                                timed_out_ids.append(sample["id"])
                                break
                if timed_out_ids:
                    if model not in result:
                        result[model] = []
                    result[model].append(
                        {
                            "task_name": task,
                            "eval_path": eval_path,
                            "sample_ids": timed_out_ids,
                        }
                    )
        except (zipfile.BadZipFile, json.JSONDecodeError):
            continue

    return result


def retry_timed_out_samples(
    timed_out_info: dict[str, list[dict]],
    cot: bool,
    time_limit: int,
) -> dict[tuple[str, str], list]:
    """Retry only the specific timed-out samples for each (model, task).

    Args:
        timed_out_info: Output of ``find_timed_out_samples()``.
        cot: Enable Chain-of-Thought scaffolding.
        time_limit: Per-sample time limit in seconds for retry.

    Returns:
        Dict mapping ``(model, task_name)`` to the list of EvalLog objects
        returned by ``inspect_eval()``.
    """
    retry_logs: dict[tuple[str, str], list] = {}

    for model, task_entries in timed_out_info.items():
        for entry in task_entries:
            task_name = entry["task_name"]
            sample_ids = entry["sample_ids"]

            # Build the matching Task object
            if "gtfobins" in task_name:
                task = aegish_gtfobins(cot=cot)
            elif "harmless" in task_name:
                task = aegish_harmless(cot=cot)
            else:
                print(f"  SKIP unknown task: {task_name}")
                continue

            print(
                f"  Retrying {len(sample_ids)} timed-out samples "
                f"for {model} / {task_name}"
            )
            try:
                logs = inspect_eval(
                    task,
                    model=model,
                    sample_id=sample_ids,
                    log_dir="logs/retry",
                    time_limit=time_limit,
                    fail_on_error=0.5,
                    retry_on_error=5,
                    seed=42,
                )
                retry_logs[(model, task_name)] = logs
            except Exception as e:
                print(f"    FAILED: {e}")
                retry_logs[(model, task_name)] = []

    return retry_logs


def _sample_timed_out(sample) -> bool:
    """Check if an EvalSample timed out (either limit or scorer level)."""
    # inspect_ai time limit
    if sample.limit and sample.limit.type == "time":
        return True
    # Scorer-level TIMEOUT_ERROR
    if sample.scores:
        for score in sample.scores.values():
            if getattr(score, "answer", None) == "TIMEOUT_ERROR":
                return True
    return False


def fix_timeout_labels(logs_dir: Path | None = None) -> None:
    """Fix mislabeled TIMEOUT_ERROR scores in existing eval logs.

    Reads each latest eval log, checks samples with TIMEOUT_ERROR,
    and relabels based on the model output's stop_reason:
    - ``content_filter`` -> ``CONTENT_FILTER``
    - ``max_tokens`` / ``model_length`` -> ``TOKEN_LIMIT``

    Backs up originals to ``logs/originals/`` before overwriting.

    Args:
        logs_dir: Directory containing ``.eval`` files.  Defaults to
            ``logs/`` relative to the project root.
    """
    if logs_dir is None:
        logs_dir = Path("logs")

    # Find latest log per (model, task)
    latest: dict[tuple[str, str], tuple[str, Path]] = {}
    for eval_path in sorted(logs_dir.glob("*.eval")):
        ts_prefix = eval_path.name.split("_aegish")[0]
        try:
            with zipfile.ZipFile(eval_path, "r") as zf:
                with zf.open("_journal/start.json") as f:
                    start = json.loads(f.read())
                model = start["eval"]["model"]
                task = start["eval"]["task"]
        except (KeyError, json.JSONDecodeError, zipfile.BadZipFile):
            continue
        key = (model, task)
        if key not in latest or ts_prefix > latest[key][0]:
            latest[key] = (ts_prefix, eval_path)

    total_fixed = 0
    for (model, task), (_ts, eval_path) in sorted(latest.items()):
        try:
            log = read_eval_log(eval_path)
        except Exception as e:
            print(f"  Could not read {eval_path.name}: {e}")
            continue

        if log.samples is None:
            continue

        fixed = 0
        for sample in log.samples:
            if sample.scores is None:
                continue
            for score in sample.scores.values():
                if getattr(score, "answer", None) != "TIMEOUT_ERROR":
                    continue
                if sample.output and sample.output.choices:
                    stop = sample.output.choices[0].stop_reason
                else:
                    stop = None
                if stop == "content_filter":
                    new_label = "CONTENT_FILTER"
                elif stop in ("max_tokens", "model_length"):
                    new_label = "TOKEN_LIMIT"
                else:
                    continue
                score.answer = new_label
                if score.metadata:
                    score.metadata["actual"] = new_label
                    score.metadata["stop_reason"] = stop
                fixed += 1

        if fixed > 0:
            # Back up original (only if not already backed up)
            backup_dir = Path("logs/originals")
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / eval_path.name
            if not backup_path.exists():
                shutil.copy2(eval_path, backup_path)

            recompute_metrics(log)
            write_eval_log(log, location=eval_path)
            print(f"  {model} / {task}: fixed {fixed} labels")
            total_fixed += fixed

    if total_fixed:
        print(f"\nFixed {total_fixed} mislabeled samples across all logs.")
    else:
        print("No mislabeled samples found.")


def merge_eval_logs(
    original_path: Path,
    retry_logs: list,
) -> "EvalLog | None":
    """Merge successful retry samples back into an original eval log.

    Timed-out samples in the original are replaced with retry results,
    but only if the retry did NOT time out again.  Aggregate metrics
    are recomputed on the merged log.  The original is backed up to
    ``logs/originals/`` and the merged log replaces it in ``logs/``.

    Args:
        original_path: Path to the original ``.eval`` file.
        retry_logs: List of EvalLog objects from the retry run for
            the same (model, task).

    Returns:
        The merged EvalLog, or None if merging was not possible.
    """
    try:
        original = read_eval_log(original_path)
    except Exception as e:
        print(f"  Could not read {original_path}: {e}")
        return None

    if original.samples is None:
        print(f"  No samples in {original_path}")
        return None

    # Collect successful retry samples (ones that did NOT time out again)
    retry_by_id: dict[int | str, "EvalSample"] = {}
    for rlog in retry_logs:
        if rlog.samples is None:
            continue
        for sample in rlog.samples:
            if _sample_timed_out(sample):
                # Still timed out – skip
                continue
            retry_by_id[sample.id] = sample

    if not retry_by_id:
        print(f"  No successful retries to merge for {original_path.name}")
        return None

    # Replace timed-out samples in original with successful retries
    replaced = 0
    merged_samples = []
    for sample in original.samples:
        if _sample_timed_out(sample) and sample.id in retry_by_id:
            merged_samples.append(retry_by_id[sample.id])
            replaced += 1
        else:
            merged_samples.append(sample)

    original.samples = merged_samples

    # Recompute aggregate metrics from merged samples
    recompute_metrics(original)

    # Back up original to logs/originals/ (only on first merge, to preserve
    # the true original across repeated --retry-timeouts runs)
    backup_dir = Path("logs/originals")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / original_path.name
    if not backup_path.exists():
        shutil.copy2(original_path, backup_path)
        print(f"  Backed up original -> {backup_path}")

    write_eval_log(original, location=original_path)
    print(f"  Merged {replaced} samples -> {original_path}")

    return original


def read_latest_eval_logs(logs_dir: Path | None = None) -> list:
    """Read the most recent eval log per (model, task) from disk.

    Args:
        logs_dir: Directory containing ``.eval`` files.  Defaults to
            ``logs/`` relative to the project root.

    Returns:
        List of EvalLog objects (one per latest (model, task) pair).
    """
    if logs_dir is None:
        logs_dir = Path("logs")
    if not logs_dir.exists():
        return []

    # Find latest eval path per (model, task) — same logic as find_timed_out_samples
    latest: dict[tuple[str, str], tuple[str, Path]] = {}
    for eval_path in sorted(logs_dir.glob("*.eval")):
        ts_prefix = eval_path.name.split("_aegish")[0]
        try:
            with zipfile.ZipFile(eval_path, "r") as zf:
                with zf.open("_journal/start.json") as f:
                    start = json.loads(f.read())
                model = start["eval"]["model"]
                task = start["eval"]["task"]
        except (KeyError, json.JSONDecodeError, zipfile.BadZipFile):
            continue
        key = (model, task)
        if key not in latest or ts_prefix > latest[key][0]:
            latest[key] = (ts_prefix, eval_path)

    logs = []
    for (_model, _task), (_ts, eval_path) in latest.items():
        try:
            logs.append(read_eval_log(eval_path))
        except Exception as e:
            print(f"  Warning: could not read {eval_path.name}: {e}")
    return logs


def run_comparison(
    models: list[str],
    cot: bool = False,
    dataset: str = "both",
    resume: bool = True,
    time_limit: int = 180,
) -> dict:
    """Run comparison evaluation across multiple models in parallel.

    Passes the full model list to ``inspect_ai.eval()`` so Inspect
    handles parallelization (concurrent samples and models, rate
    limiting, retries) internally.

    Args:
        models: List of model IDs in Inspect format.
        cot: Enable Chain-of-Thought scaffolding.
        dataset: Which dataset to run: "gtfobins", "harmless", or "both".
        resume: If True, skip models with existing results.
        time_limit: Per-sample time limit in seconds.

    Returns:
        Dict with metadata, results per model, and ranking.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing_results = check_existing_results(RESULTS_DIR) if resume else {}

    results: dict[str, dict] = {}
    skipped: list[str] = []

    models_to_eval: list[str] = []
    for model in models:
        if model in existing_results:
            print(f"  SKIP: {model} (existing results found)")
            results[model] = existing_results[model]
            skipped.append(model)
        else:
            models_to_eval.append(model)

    # Batch-eval all models (Inspect parallelizes internally)
    if models_to_eval:
        tasks = _build_tasks(dataset, cot)
        print(
            f"\n  Evaluating {len(models_to_eval)} models "
            f"x {len(tasks)} tasks (Inspect parallelizes internally)\n"
        )
        try:
            logs = inspect_eval(
                tasks,
                model=models_to_eval,
                fail_on_error=0.5,
                retry_on_error=5,
                time_limit=time_limit,
                # seed at eval level overrides task-level GenerateConfig;
                # set explicitly so comparison runs are reproducible even
                # if task defaults change later.
                seed=42,
            )
            _process_logs(logs, models_to_eval, cot, dataset, results)
        except Exception as e:
            print(f"  Batch FAILED: {e}")
            for model in models_to_eval:
                results[model] = {
                    "model": model,
                    "cot": cot,
                    "status": "error",
                    "error": str(e),
                    "datasets": {},
                    "composite": {
                        "aegish_score": 0.0,
                        "aegish_score_se": None,
                        "total_cost_usd": 0.0,
                        "cost_per_1000_combined": 0.0,
                        "avg_latency_ms": 0.0,
                    },
                }

    # Generate ranking
    ranking = generate_ranking(results)

    # Build output
    datasets_used = []
    if dataset in ("gtfobins", "both"):
        datasets_used.append("gtfobins")
    if dataset in ("harmless", "both"):
        datasets_used.append("harmless")

    # Compute dataset counts dynamically from actual data files
    gtfobins_count = 0
    harmless_count = 0
    data_dir = Path(__file__).parent / "data"
    try:
        with open(data_dir / "gtfobins_commands.json") as f:
            gtfobins_count = len(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    try:
        with open(data_dir / "harmless_commands.json") as f:
            harmless_count = len(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    comparison = {
        "metadata": {
            "timestamp": timestamp,
            "models_evaluated": len(models),
            "datasets": datasets_used,
            "scaffolding": "cot" if cot else "standard",
            "gtfobins_count": gtfobins_count,
            "harmless_count": harmless_count,
            "skipped_models": skipped,
        },
        "results": results,
        "ranking": ranking,
    }

    return comparison


def save_comparison(comparison: dict) -> Path:
    """Save comparison results to JSON file.

    Args:
        comparison: Full comparison results dict.

    Returns:
        Path to the saved JSON file.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = RESULTS_DIR / f"comparison_{timestamp}.json"

    with open(output_path, "w") as f:
        json.dump(comparison, f, indent=2)

    print(f"\nResults saved to: {output_path}")
    return output_path


def main() -> None:
    """CLI entry point for LLM comparison framework."""
    parser = argparse.ArgumentParser(description="aegish LLM Comparison Framework")
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated model IDs to evaluate (default: all 11 models)",
    )
    parser.add_argument(
        "--cot",
        action="store_true",
        help="Enable Chain-of-Thought scaffolding",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        choices=["gtfobins", "harmless", "both"],
        default="both",
        help="Dataset to evaluate: gtfobins, harmless, or both (default: both)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable resume: re-run all models even if results exist",
    )
    parser.add_argument(
        "--retry-timeouts",
        action="store_true",
        help="Re-run only models that had sample timeouts in previous evals",
    )
    parser.add_argument(
        "--time-limit",
        type=int,
        default=180,
        help="Per-sample time limit in seconds (default: 180)",
    )
    parser.add_argument(
        "--exclude-models",
        type=str,
        default=None,
        help="Comma-separated model substrings to exclude (e.g. 'gemini-3-pro,phi-4')",
    )
    parser.add_argument(
        "--fix-labels",
        action="store_true",
        help="Fix mislabeled TIMEOUT_ERROR scores (e.g. content filters) in existing logs",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild comparison JSON from existing eval logs without re-running evaluations",
    )
    args = parser.parse_args()

    # Handle --fix-labels: patch score labels in existing logs
    if args.fix_labels:
        fix_timeout_labels()
        return

    # Handle --rebuild: re-extract metrics from existing eval logs on disk
    if args.rebuild:
        print("Rebuilding comparison from existing eval logs...")
        all_logs = read_latest_eval_logs()
        if not all_logs:
            print("No eval logs found in logs/.")
            return

        # Filter to requested models if --models is provided
        models_filter = None
        if args.models:
            models_filter = set(parse_models(args.models))

        # Apply --exclude-models filter
        excludes = []
        if args.exclude_models:
            excludes = [s.strip() for s in args.exclude_models.split(",")]

        filtered_logs = []
        for log in all_logs:
            model = log.eval.model if log.eval else None
            if model is None:
                continue
            if models_filter and model not in models_filter:
                continue
            if any(ex in model for ex in excludes):
                print(f"  SKIP (excluded): {model}")
                continue
            filtered_logs.append(log)

        if not filtered_logs:
            print("No matching eval logs after filtering.")
            return

        model_list = sorted(
            {log.eval.model for log in filtered_logs if log.eval and log.eval.model}
        )
        print(f"  Found logs for {len(model_list)} models:")
        for m in model_list:
            print(f"    - {m}")

        results: dict[str, dict] = {}
        _process_logs(filtered_logs, model_list, args.cot, "both", results)
        ranking = generate_ranking(results)
        print_comparison_table(results, ranking)

        comparison = {
            "metadata": {
                "timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "rebuild": True,
            },
            "results": results,
            "ranking": ranking,
        }
        output_path = save_comparison(comparison)
        print(f"\nRebuild complete. Results: {output_path}")
        return

    # Handle --retry-timeouts: retry only the specific timed-out samples
    if args.retry_timeouts:
        timed_out_info = find_timed_out_samples()

        # Apply --exclude-models filter
        if args.exclude_models:
            excludes = [s.strip() for s in args.exclude_models.split(",")]
            excluded = {
                m for m in timed_out_info
                if any(ex in m for ex in excludes)
            }
            for m in excluded:
                del timed_out_info[m]
            if excluded:
                print(f"Excluded: {', '.join(sorted(excluded))}\n")

        if not timed_out_info:
            print("No timed-out samples found in logs/. Nothing to retry.")
            return

        # Summary
        print("Timed-out samples to retry:")
        total_samples = 0
        for model, entries in sorted(timed_out_info.items()):
            for entry in entries:
                n = len(entry["sample_ids"])
                total_samples += n
                print(f"  {model} / {entry['task_name']}: {n} samples")
        print(f"  Total: {total_samples} samples\n")

        # Retry
        retry_results = retry_timed_out_samples(
            timed_out_info, cot=args.cot, time_limit=args.time_limit
        )

        # Merge retry results back into originals
        print("\nMerging retry results into original logs...")
        merged_logs = []
        for model, entries in timed_out_info.items():
            for entry in entries:
                key = (model, entry["task_name"])
                rlogs = retry_results.get(key, [])
                if rlogs:
                    merged = merge_eval_logs(entry["eval_path"], rlogs)
                    if merged is not None:
                        merged_logs.append(merged)

        # Build full comparison from ALL latest logs in logs/
        print("\nBuilding full comparison from all logs...")
        all_logs = read_latest_eval_logs()
        if all_logs:
            all_models = list(
                {log.eval.model for log in all_logs if log.eval and log.eval.model}
            )
            results: dict[str, dict] = {}
            _process_logs(all_logs, all_models, args.cot, "both", results)
            ranking = generate_ranking(results)
            print_comparison_table(results, ranking)
            comparison = {
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "retry_timeouts": True,
                    "models_retried": list(timed_out_info.keys()),
                    "total_samples_retried": total_samples,
                },
                "results": results,
                "ranking": ranking,
            }
            output_path = save_comparison(comparison)
            print(f"\nRetry complete. Results: {output_path}")
        else:
            print("\nNo eval logs found in logs/.")
        return

    else:
        models = parse_models(args.models)
        resume = not args.no_resume

    print("aegish LLM Comparison")
    print(f"Models: {len(models)}")
    print(f"Dataset: {args.dataset}")
    print(f"Scaffolding: {'CoT' if args.cot else 'Standard'}")
    print(f"Resume: {'disabled' if not resume else 'enabled'}")
    print(f"Time limit: {args.time_limit}s")
    print()

    comparison = run_comparison(
        models=models,
        cot=args.cot,
        dataset=args.dataset,
        resume=resume,
        time_limit=args.time_limit,
    )

    # Print comparison table
    print_comparison_table(comparison["results"], comparison["ranking"])

    # Save results
    output_path = save_comparison(comparison)
    print(f"\nComparison complete. Results: {output_path}")


if __name__ == "__main__":
    main()
