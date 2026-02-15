"""Benchmark visualization plots for aegish LLM comparison results.

Generates scatter plots, bar charts, and summary tables from comparison
JSON files produced by ``benchmark.compare``.

Usage:
    # Generate all plots from comparison results
    python -m benchmark.plots benchmark/results/comparison_20260206_181702.json

    # Specify output directory
    python -m benchmark.plots results.json --output-dir ./plots
"""

import argparse
import json
import logging
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import seaborn
from adjustText import adjust_text

matplotlib.use("Agg")

logger = logging.getLogger(__name__)

# Provider color mapping for consistent chart styling
PROVIDER_COLORS: dict[str, str] = {
    "openai": "#10A37F",
    "anthropic": "#D97706",
    "google": "#4285F4",
    "openrouter": "#8B5CF6",
    "hf-inference-providers": "#FF6B6B",
}

# Default fallback color for unknown providers
_DEFAULT_COLOR = "#888888"

# Gemini Flash rate-limit correction: 76.7% of measured latency was
# rate-limit queuing in the batch benchmark.  Production latency removes
# this artifact.  See docs/analysis/benchmark-results-analysis.md §6.
_RATE_LIMIT_FRACTION = 0.767
_GEMINI_FLASH_MODEL = "google/gemini-3-flash-preview"


def _apply_style() -> None:
    """Apply consistent matplotlib style for all plots."""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.labelsize": 12,
        }
    )


def load_comparison_results(filepath: Path) -> dict:
    """Load comparison results from a JSON file.

    Args:
        filepath: Path to comparison JSON file.

    Returns:
        Parsed JSON dict with metadata, results, and ranking.

    Raises:
        FileNotFoundError: If file does not exist.
        json.JSONDecodeError: If file is not valid JSON.
    """
    with open(filepath) as f:
        return json.load(f)


def get_provider(model: str) -> str:
    """Extract provider prefix from a model ID.

    Args:
        model: Full model ID (e.g., "openai/gpt-5.1").

    Returns:
        Provider prefix string (e.g., "openai").
    """
    return model.split("/")[0]


def get_short_name(model: str) -> str:
    """Extract a short display name from a model ID.

    Handles multi-segment paths and colon suffixes.

    Args:
        model: Full model ID.

    Returns:
        Short display name suitable for plot labels.
    """
    # Get last path segment
    name = model.split("/")[-1]
    # Remove colon suffix (e.g., ":featherless-ai")
    name = name.split(":")[0]
    # Truncate long version suffixes for Anthropic models
    # e.g., "claude-sonnet-4-5-20250929" -> "claude-sonnet-4-5"
    parts = name.split("-")
    # If last part is a long numeric string (date), drop it
    if len(parts) > 1 and len(parts[-1]) >= 8 and parts[-1].isdigit():
        name = "-".join(parts[:-1])
    return name


def get_provider_color(model: str) -> str:
    """Get the color for a model based on its provider.

    Args:
        model: Full model ID.

    Returns:
        Hex color string.
    """
    provider = get_provider(model)
    return PROVIDER_COLORS.get(provider, _DEFAULT_COLOR)


def save_plot(fig: matplotlib.figure.Figure, filepath: Path) -> None:
    """Save a figure as both PNG and SVG, then close it.

    Args:
        fig: Matplotlib figure to save.
        filepath: Base path without extension. Both .png and .svg
            will be created.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filepath.with_suffix(".png"), dpi=150, bbox_inches="tight")
    fig.savefig(filepath.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def _get_successful_models(results: dict) -> dict:
    """Filter results to only successful models.

    Args:
        results: The "results" dict from comparison JSON.

    Returns:
        Dict of model_id -> result_data for successful models only.
    """
    return {
        model: data
        for model, data in results.items()
        if data.get("status") == "success"
    }


def _get_latency_ms(model: str, data: dict) -> float:
    """Return latency in milliseconds, correcting for rate-limit artifacts.

    Gemini Flash measured latency is dominated by rate-limit queuing
    (76.7%).  This helper strips that component so plots reflect
    production-representative latency.
    """
    raw = data.get("composite", {}).get("avg_latency_ms", 0.0)
    if model == _GEMINI_FLASH_MODEL:
        return raw * (1.0 - _RATE_LIMIT_FRACTION)
    return raw


def compute_pareto_frontier(
    costs: list[float], scores: list[float]
) -> list[tuple[float, float]]:
    """Return Pareto-optimal points (minimize cost, maximize score).

    A point is Pareto-optimal if no other point has both lower cost
    and higher score.

    Args:
        costs: List of cost values.
        scores: List of score values (same length as costs).

    Returns:
        List of (cost, score) tuples on the Pareto frontier,
        sorted by cost ascending.
    """
    points = sorted(zip(costs, scores), key=lambda p: p[0])
    frontier: list[tuple[float, float]] = []
    max_score = -1.0
    for cost, score in points:
        if score > max_score:
            frontier.append((cost, score))
            max_score = score
    return frontier


def plot_cost_vs_score(results: dict, output_dir: Path) -> None:
    """Generate Cost vs aegish Score scatter plot.

    Args:
        results: The "results" dict from comparison JSON.
        output_dir: Directory to save output files.
    """
    _apply_style()
    successful = _get_successful_models(results)

    fig, ax = plt.subplots(figsize=(12, 8))

    costs: list[float] = []
    scores: list[float] = []
    models: list[str] = []

    for model, data in successful.items():
        composite = data.get("composite", {})
        cost = composite.get("cost_per_1000_combined", 0.0)
        score = composite.get("aegish_score", 0.0)
        score_se = composite.get("aegish_score_se", 0.0) or 0.0
        costs.append(cost)
        scores.append(score)
        models.append(model)

        color = get_provider_color(model)
        ax.errorbar(
            cost, score, yerr=score_se,
            fmt="o", color=color, markersize=10,
            markeredgecolor="white", markeredgewidth=0.5, zorder=5,
            elinewidth=1, capsize=3, ecolor="gray",
        )
        ax.annotate(
            get_short_name(model),
            (cost, score),
            textcoords="offset points",
            xytext=(8, 5),
            fontsize=8,
            ha="left",
        )

    # Pareto frontier
    if costs and scores:
        frontier = compute_pareto_frontier(costs, scores)
        if len(frontier) >= 2:
            f_costs, f_scores = zip(*frontier)
            ax.plot(
                f_costs,
                f_scores,
                "r--",
                linewidth=1.5,
                alpha=0.7,
                label="Pareto Frontier",
            )

    # Target line
    ax.axhline(
        y=0.95, color="green", linestyle="--", alpha=0.5, label="Target Score (0.95)"
    )

    # Provider legend with Pareto frontier and target line
    legend_handles = []
    if costs and scores:
        frontier = compute_pareto_frontier(costs, scores)
        if len(frontier) >= 2:
            legend_handles.append(
                plt.Line2D(
                    [0],
                    [0],
                    color="red",
                    linestyle="--",
                    alpha=0.7,
                    label="Pareto Frontier",
                )
            )
    legend_handles.append(
        plt.Line2D(
            [0],
            [0],
            color="green",
            linestyle="--",
            alpha=0.5,
            label="Target Score (0.95)",
        )
    )
    for provider, color in PROVIDER_COLORS.items():
        if any(get_provider(m) == provider for m in models):
            legend_handles.append(
                plt.Line2D(
                    [0],
                    [0],
                    marker="o",
                    color="w",
                    markerfacecolor=color,
                    markersize=8,
                    label=provider,
                )
            )
    if legend_handles:
        ax.legend(handles=legend_handles, loc="lower right", fontsize=9)

    ax.set_xlabel("Cost per 1000 Commands ($)")
    ax.set_ylabel("aegish Score")
    ax.set_title("Cost vs aegish Score")

    save_plot(fig, output_dir / "cost_vs_score")


def plot_cost_vs_malicious_detection_rate(results: dict, output_dir: Path) -> None:
    """Generate Cost vs Malicious Detection Rate scatter plot with Pareto frontier.

    Args:
        results: The "results" dict from comparison JSON.
        output_dir: Directory to save output files.
    """
    _apply_style()
    successful = _get_successful_models(results)

    fig, ax = plt.subplots(figsize=(12, 8))

    costs: list[float] = []
    scores: list[float] = []
    models: list[str] = []

    for model, data in successful.items():
        composite = data.get("composite", {})
        cost = composite.get("cost_per_1000_combined", 0.0)
        gtfo = data.get("datasets", {}).get("gtfobins", {})
        det_rate = gtfo.get("malicious_detection_rate", 0.0)
        det_se = gtfo.get("stderr", 0.0) or 0.0
        costs.append(cost)
        scores.append(det_rate)
        models.append(model)

        color = get_provider_color(model)
        ax.errorbar(
            cost, det_rate, yerr=det_se,
            fmt="o", color=color, markersize=10,
            markeredgecolor="white", markeredgewidth=0.5, zorder=5,
            elinewidth=1, capsize=3, ecolor="gray",
        )

    # Pad x-axis for labels
    if costs:
        x_range = max(costs) - min(costs)
        ax.set_xlim(
            min(costs) - x_range * 0.05,
            max(costs) + x_range * 0.20,
        )

    texts = []
    for i, model in enumerate(models):
        texts.append(
            ax.text(
                costs[i], scores[i],
                "  " + get_short_name(model),
                fontsize=8, ha="left", va="center",
            )
        )
    if texts:
        adjust_text(
            texts, x=costs, y=scores, ax=ax,
            force_text=(0.5, 0.8), force_points=(0.3, 0.5),
            expand=(1.2, 1.4),
            arrowprops=dict(arrowstyle="-", color="gray", alpha=0.4, lw=0.5),
        )

    # Pareto frontier
    if costs and scores:
        frontier = compute_pareto_frontier(costs, scores)
        if len(frontier) >= 2:
            f_costs, f_scores = zip(*frontier)
            ax.plot(
                f_costs, f_scores, "r--", linewidth=1.5, alpha=0.7,
                label="Pareto Frontier",
            )

    # Target line
    ax.axhline(
        y=0.95, color="green", linestyle="--", alpha=0.5,
        label="Target Detection (0.95)",
    )

    # Legend
    legend_handles = []
    if costs and scores:
        frontier = compute_pareto_frontier(costs, scores)
        if len(frontier) >= 2:
            legend_handles.append(
                plt.Line2D(
                    [0], [0], color="red", linestyle="--", alpha=0.7,
                    label="Pareto Frontier",
                )
            )
    legend_handles.append(
        plt.Line2D(
            [0], [0], color="green", linestyle="--", alpha=0.5,
            label="Target Detection (0.95)",
        )
    )
    for provider, color in PROVIDER_COLORS.items():
        if any(get_provider(m) == provider for m in models):
            legend_handles.append(
                plt.Line2D(
                    [0], [0], marker="o", color="w",
                    markerfacecolor=color, markersize=8, label=provider,
                )
            )
    if legend_handles:
        ax.legend(handles=legend_handles, loc="lower right", fontsize=9)

    ax.set_xlabel("Cost per 1000 Commands ($)")
    ax.set_ylabel("Malicious Detection Rate")
    ax.set_title("Cost vs Malicious Detection Rate")

    save_plot(fig, output_dir / "cost_vs_malicious_detection_rate")


def _plot_latency_vs_score_impl(
    results: dict,
    output_dir: Path,
    *,
    score_key: str,
    score_label: str,
    title: str,
    filename: str,
) -> None:
    """Shared implementation for latency-vs-score Pareto frontier plots.

    Args:
        results: The "results" dict from comparison JSON.
        output_dir: Directory to save output files.
        score_key: Either "aegish_score" (composite) or "malicious_detection_rate"
            (gtfobins dataset).
        score_label: Y-axis label.
        title: Plot title.
        filename: Output filename (without extension).
    """
    _apply_style()
    successful = _get_successful_models(results)

    fig, ax = plt.subplots(figsize=(12, 8))

    latencies: list[float] = []
    scores: list[float] = []
    models: list[str] = []

    for model, data in successful.items():
        latency_ms = _get_latency_ms(model, data)
        if latency_ms <= 0:
            continue
        latency_s = latency_ms / 1000.0

        if score_key == "aegish_score":
            score = data.get("composite", {}).get("aegish_score", 0.0)
            score_se = data.get("composite", {}).get("aegish_score_se", 0.0) or 0.0
        else:
            gtfo = data.get("datasets", {}).get("gtfobins", {})
            score = gtfo.get("malicious_detection_rate", 0.0)
            score_se = gtfo.get("stderr", 0.0) or 0.0

        latencies.append(latency_s)
        scores.append(score)
        models.append(model)

        color = get_provider_color(model)
        ax.errorbar(
            latency_s, score, yerr=score_se,
            fmt="o", color=color, markersize=10,
            markeredgecolor="white", markeredgewidth=0.5, zorder=5,
            elinewidth=1, capsize=3, ecolor="gray",
        )

    # Pad x-axis so rightmost labels are not clipped
    if latencies:
        x_range = max(latencies) - min(latencies)
        ax.set_xlim(
            min(latencies) - x_range * 0.05,
            max(latencies) + x_range * 0.20,
        )

    # Label placement with adjustText to avoid overlaps
    texts = []
    for i, model in enumerate(models):
        texts.append(
            ax.text(
                latencies[i],
                scores[i],
                "  " + get_short_name(model),
                fontsize=8,
                ha="left",
                va="center",
            )
        )
    if texts:
        adjust_text(
            texts,
            x=latencies,
            y=scores,
            ax=ax,
            force_text=(0.5, 0.8),
            force_points=(0.3, 0.5),
            expand=(1.2, 1.4),
            arrowprops=dict(arrowstyle="-", color="gray", alpha=0.4, lw=0.5),
        )

    # Pareto frontier (minimize latency, maximize score)
    if latencies and scores:
        frontier = compute_pareto_frontier(latencies, scores)
        if len(frontier) >= 2:
            f_lat, f_scores = zip(*frontier)
            ax.plot(
                f_lat,
                f_scores,
                "r--",
                linewidth=1.5,
                alpha=0.7,
                label="Pareto Frontier",
            )

    # Target line
    ax.axhline(
        y=0.95,
        color="green",
        linestyle="--",
        alpha=0.5,
        label="Target (0.95)",
    )

    # Legend
    legend_handles = []
    if latencies and scores:
        frontier = compute_pareto_frontier(latencies, scores)
        if len(frontier) >= 2:
            legend_handles.append(
                plt.Line2D(
                    [0],
                    [0],
                    color="red",
                    linestyle="--",
                    alpha=0.7,
                    label="Pareto Frontier",
                )
            )
    legend_handles.append(
        plt.Line2D(
            [0],
            [0],
            color="green",
            linestyle="--",
            alpha=0.5,
            label="Target (0.95)",
        )
    )
    for provider, color in PROVIDER_COLORS.items():
        if any(get_provider(m) == provider for m in models):
            legend_handles.append(
                plt.Line2D(
                    [0],
                    [0],
                    marker="o",
                    color="w",
                    markerfacecolor=color,
                    markersize=8,
                    label=provider,
                )
            )
    if legend_handles:
        ax.legend(handles=legend_handles, loc="lower right", fontsize=9)

    ax.set_xlabel("Average Latency (seconds)")
    ax.set_ylabel(score_label)
    ax.set_title(title)

    save_plot(fig, output_dir / filename)


def plot_latency_vs_score(results: dict, output_dir: Path) -> None:
    """Generate Latency vs aegish Score Pareto frontier plot.

    Args:
        results: The "results" dict from comparison JSON.
        output_dir: Directory to save output files.
    """
    _plot_latency_vs_score_impl(
        results,
        output_dir,
        score_key="aegish_score",
        score_label="aegish Score",
        title="Latency vs aegish Score",
        filename="latency_vs_score",
    )


def plot_latency_vs_malicious_detection_rate(results: dict, output_dir: Path) -> None:
    """Generate Latency vs Malicious Detection Rate Pareto frontier plot.

    Args:
        results: The "results" dict from comparison JSON.
        output_dir: Directory to save output files.
    """
    _plot_latency_vs_score_impl(
        results,
        output_dir,
        score_key="malicious_detection_rate",
        score_label="Malicious Detection Rate",
        title="Latency vs Malicious Detection Rate",
        filename="latency_vs_malicious_detection_rate",
    )


def plot_detection_vs_pass(results: dict, output_dir: Path) -> None:
    """Generate Malicious Detection Rate vs Harmless Acceptance Rate scatter plot.

    Args:
        results: The "results" dict from comparison JSON.
        output_dir: Directory to save output files.
    """
    _apply_style()
    successful = _get_successful_models(results)

    fig, ax = plt.subplots(figsize=(12, 8))

    models_plotted: list[str] = []
    texts: list = []

    for model, data in successful.items():
        datasets = data.get("datasets", {})
        gtfo = datasets.get("gtfobins", {})
        harm = datasets.get("harmless", {})
        if not gtfo or not harm:
            continue

        harmless_acceptance_rate = harm.get("harmless_acceptance_rate", 0.0) * 100
        malicious_detection_rate = gtfo.get("malicious_detection_rate", 0.0) * 100
        pass_se = (harm.get("stderr", 0.0) or 0.0) * 100
        det_se = (gtfo.get("stderr", 0.0) or 0.0) * 100

        color = get_provider_color(model)
        ax.errorbar(
            harmless_acceptance_rate, malicious_detection_rate,
            xerr=pass_se, yerr=det_se,
            fmt="o", color=color, markersize=10,
            markeredgecolor="white", markeredgewidth=0.5, zorder=5,
            elinewidth=1, capsize=3, ecolor="gray",
        )
        texts.append(
            ax.text(
                harmless_acceptance_rate,
                malicious_detection_rate,
                get_short_name(model),
                fontsize=8,
            )
        )
        models_plotted.append(model)

    # Set axis limits before drawing target zone
    # Ensure both threshold lines (x=90, y=95) are visible
    all_pass = [
        harm.get("harmless_acceptance_rate", 0.0) * 100
        for d in successful.values()
        for harm in [d.get("datasets", {}).get("harmless", {})]
        if harm
    ]
    all_det = [
        gtfo.get("malicious_detection_rate", 0.0) * 100
        for d in successful.values()
        for gtfo in [d.get("datasets", {}).get("gtfobins", {})]
        if gtfo
    ]
    if all_pass and all_det:
        x_min = min(min(all_pass) - 5, 93)
        y_min = max(0, min(all_det) - 5)
        ax.set_xlim(x_min, 101.5)
        ax.set_ylim(y_min, 101.5)
        ax.set_xticks([t for t in ax.get_xticks() if t <= 100])
        ax.set_yticks([t for t in ax.get_yticks() if t <= 100])

    # Target zone (green shaded rectangle) - clamped to axis bounds
    target_rect = plt.Rectangle(
        (95, 95), 5, 5, fill=True, alpha=0.08, color="green", label="Target Zone"
    )
    ax.add_patch(target_rect)

    # Threshold lines with separate labels
    ax.axhline(
        y=95, color="green", linestyle="--", alpha=0.5, label="M.Det Target (95%)"
    )
    ax.axvline(
        x=95, color="green", linestyle="--", alpha=0.5, label="H.Acc Target (95%)"
    )

    # Use adjustText to prevent label overlaps
    adjust_text(
        texts,
        ax=ax,
        arrowprops=dict(arrowstyle="-", color="gray", alpha=0.5, lw=0.5),
        force_points=(1, 1),
        expand=(1.5, 1.5),
    )

    # Provider legend with both threshold lines shown separately
    legend_handles = [
        plt.Line2D(
            [0],
            [0],
            color="green",
            linestyle="--",
            alpha=0.5,
            label="M.Det \u226595%",
        ),
        plt.Line2D(
            [0],
            [0],
            color="green",
            linestyle="--",
            alpha=0.5,
            label="H.Acc \u226595%",
        ),
    ]
    for provider, color in PROVIDER_COLORS.items():
        if any(get_provider(m) == provider for m in models_plotted):
            legend_handles.append(
                plt.Line2D(
                    [0],
                    [0],
                    marker="o",
                    color="w",
                    markerfacecolor=color,
                    markersize=8,
                    label=provider,
                )
            )
    ax.legend(handles=legend_handles, loc="lower left", fontsize=9)

    ax.set_xlabel("Harmless Acceptance Rate (%)")
    ax.set_ylabel("Malicious Detection Rate (%)")
    ax.set_title("Malicious Detection Rate vs Harmless Acceptance Rate")

    save_plot(fig, output_dir / "detection_vs_pass")


def plot_latency_distribution(results: dict, output_dir: Path) -> None:
    """Generate latency distribution horizontal bar chart.

    Uses mean latency with p50 and p90 markers since per-command
    latency arrays are not available in the comparison JSON.

    Args:
        results: The "results" dict from comparison JSON.
        output_dir: Directory to save output files.
    """
    _apply_style()
    successful = _get_successful_models(results)

    # Collect latency data
    latency_data: list[tuple[str, float, float, float]] = []  # (model, mean, p50, p90)
    for model, data in successful.items():
        avg_latency = _get_latency_ms(model, data)
        if avg_latency <= 0:
            continue

        # Get per-dataset latency for p50 and p90
        correction = avg_latency / max(
            data.get("composite", {}).get("avg_latency_ms", avg_latency), 1.0
        )
        datasets = data.get("datasets", {})
        p50_values = []
        p90_values = []
        for ds_data in datasets.values():
            if ds_data and "latency" in ds_data:
                p50_values.append(ds_data["latency"].get("p50", 0.0))
                p90_values.append(ds_data["latency"].get("p90", 0.0))

        avg_p50 = (sum(p50_values) / len(p50_values) if p50_values else avg_latency) * correction
        avg_p90 = (sum(p90_values) / len(p90_values) if p90_values else avg_latency) * correction

        latency_data.append((model, avg_latency, avg_p50, avg_p90))

    # Sort by mean latency ascending
    latency_data.sort(key=lambda x: x[1])

    if not latency_data:
        return

    fig, ax = plt.subplots(figsize=(12, max(6, len(latency_data) * 0.6)))

    model_names = [get_short_name(m) for m, _, _, _ in latency_data]
    means = [lat for _, lat, _, _ in latency_data]
    colors = [get_provider_color(m) for m, _, _, _ in latency_data]
    p90s = [p90 for _, _, _, p90 in latency_data]

    y_pos = range(len(latency_data))

    # Mean latency bars
    ax.barh(y_pos, means, color=colors, alpha=0.8, edgecolor="white", linewidth=0.5)

    # P90 markers
    ax.scatter(
        p90s, y_pos, marker="|", color="red", s=100, zorder=5, linewidths=2, label="P90"
    )

    # Value labels
    for i, (mean_val, p90_val) in enumerate(zip(means, p90s)):
        label_x = max(mean_val, p90_val)
        ax.text(
            label_x + label_x * 0.02,
            i,
            f"{mean_val / 1000:.1f}s",
            va="center",
            fontsize=9,
        )

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(model_names)
    ax.set_xlabel("Latency (ms)")
    ax.set_title("Average Latency by Model")
    ax.legend(loc="lower right", fontsize=9)

    save_plot(fig, output_dir / "latency_distribution")


def plot_cost_comparison(results: dict, output_dir: Path) -> None:
    """Generate cost per 1000 commands horizontal bar chart.

    Args:
        results: The "results" dict from comparison JSON.
        output_dir: Directory to save output files.
    """
    _apply_style()
    successful = _get_successful_models(results)

    # Collect cost data
    cost_data: list[tuple[str, float]] = []
    for model, data in successful.items():
        composite = data.get("composite", {})
        cost = composite.get("cost_per_1000_combined", 0.0)
        cost_data.append((model, cost))

    # Sort by cost ascending
    cost_data.sort(key=lambda x: x[1])

    if not cost_data:
        return

    fig, ax = plt.subplots(figsize=(12, max(6, len(cost_data) * 0.6)))

    model_names = [get_short_name(m) for m, _ in cost_data]
    costs = [c for _, c in cost_data]
    colors = [get_provider_color(m) for m, _ in cost_data]

    y_pos = range(len(cost_data))

    ax.barh(y_pos, costs, color=colors, alpha=0.8, edgecolor="white", linewidth=0.5)

    # Value labels
    for i, cost in enumerate(costs):
        if cost == 0.0:
            ax.text(0.1, i, "$0.00 (free tier)", va="center", fontsize=9)
        else:
            ax.text(cost + cost * 0.02, i, f"${cost:.2f}", va="center", fontsize=9)

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(model_names)
    ax.set_xlabel("Cost per 1000 Commands ($)")
    ax.set_title("Cost per 1000 Commands by Model")

    # Provider legend
    legend_handles = []
    plotted_models = [m for m, _ in cost_data]
    for provider, color in PROVIDER_COLORS.items():
        if any(get_provider(m) == provider for m in plotted_models):
            legend_handles.append(
                plt.Line2D(
                    [0],
                    [0],
                    marker="s",
                    color="w",
                    markerfacecolor=color,
                    markersize=8,
                    label=provider,
                )
            )
    if legend_handles:
        ax.legend(handles=legend_handles, loc="lower right", fontsize=9)

    save_plot(fig, output_dir / "cost_comparison")


def plot_ranking_table(results: dict, ranking: list[dict], output_dir: Path) -> None:
    """Generate model ranking table with 95% confidence intervals.

    Args:
        results: The "results" dict from comparison JSON.
        ranking: Sorted ranking list from comparison JSON.
        output_dir: Directory to save output files.
    """
    _apply_style()

    if not ranking:
        return

    columns = [
        "Rank",
        "Model",
        "M.Det% (±SE)",
        "H.Acc% (±SE)",
        "Score (±SE)",
        "Cost/1k",
        "Latency",
    ]
    cell_data: list[list[str]] = []
    row_colors: list[str] = []

    for entry in ranking:
        model = entry["model"]
        data = results.get(model, {})
        if data.get("status") != "success":
            continue

        datasets = data.get("datasets", {})
        composite = data.get("composite", {})
        gtfo = datasets.get("gtfobins", {})
        harm = datasets.get("harmless", {})

        det_rate = gtfo.get("malicious_detection_rate", 0.0) if gtfo else 0.0
        det_se = gtfo.get("stderr", 0.0) if gtfo else 0.0
        harmless_acceptance_rate = harm.get("harmless_acceptance_rate", 0.0) if harm else 0.0
        pass_se = harm.get("stderr", 0.0) if harm else 0.0
        score = composite.get("aegish_score", 0.0)
        score_se = composite.get("aegish_score_se", 0.0) or 0.0
        cost = composite.get("cost_per_1000_combined", 0.0)
        latency = _get_latency_ms(model, data)

        # ±1 SE
        det_ci = det_se * 100
        pass_ci = pass_se * 100
        score_ci = score_se

        det_check = " \u2713" if det_rate >= 0.95 else ""
        pass_check = " \u2713" if harmless_acceptance_rate >= 0.95 else ""
        score_check = " \u2713" if score >= 0.95 else ""

        row = [
            str(entry["rank"]),
            get_short_name(model),
            f"{det_rate * 100:.1f}% ±{det_ci:.1f}{det_check}",
            f"{harmless_acceptance_rate * 100:.1f}% ±{pass_ci:.1f}{pass_check}",
            f"{score:.3f} ±{score_ci:.3f}{score_check}",
            f"${cost:.2f}" if cost > 0 else "$0.00",
            f"{latency / 1000:.1f}s",
        ]
        cell_data.append(row)

        if det_rate >= 0.95 and harmless_acceptance_rate >= 0.95 and score >= 0.95:
            row_colors.append("#d4edda")  # green
        elif score >= 0.50:
            row_colors.append("#fff3cd")  # yellow
        else:
            row_colors.append("#f8d7da")  # red

    if not cell_data:
        return

    fig, ax = plt.subplots(figsize=(16, max(4, len(cell_data) * 0.5 + 2)))
    ax.axis("off")

    table = ax.table(
        cellText=cell_data,
        colLabels=columns,
        loc="center",
        cellLoc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.auto_set_column_width(list(range(len(columns))))
    table.scale(1, 1.5)

    for j in range(len(columns)):
        cell = table[0, j]
        cell.set_facecolor("#343a40")
        cell.set_text_props(color="white", fontweight="bold")

    for i in range(len(cell_data)):
        for j in range(len(columns)):
            cell = table[i + 1, j]
            cell.set_facecolor(row_colors[i])

    ax.set_title("aegish Model Ranking", fontsize=14, fontweight="bold", pad=20)

    # Footnotes
    footnote = (
        "\u2713 = meets target (M.Det ≥95%, H.Acc ≥95%, Score ≥0.95).  "
        "Green = meets all targets.  Yellow = misses detection target.  "
        "Red = significantly below.\n"
        f"* Gemini Flash latency corrected for rate-limiting "
        f"({_RATE_LIMIT_FRACTION:.0%} rate-limit queuing removed)."
    )
    fig.text(
        0.5, 0.02, footnote, ha="center", fontsize=8, style="italic",
        wrap=True,
    )

    save_plot(fig, output_dir / "ranking_table_full")


def plot_category_heatmap(results: dict, output_dir: Path) -> None:
    """Generate per-category malicious detection rate heatmap (models x categories).

    Args:
        results: The "results" dict from comparison JSON.
        output_dir: Directory to save output files.
    """
    _apply_style()
    successful = _get_successful_models(results)

    # Collect per-category data across models
    model_names: list[str] = []
    all_categories: set[str] = set()
    model_category_rates: dict[str, dict[str, float]] = {}

    for model, data in successful.items():
        gtfo = data.get("datasets", {}).get("gtfobins")
        if not gtfo:
            continue
        per_cat = gtfo.get("per_category_malicious_detection_rates", {})
        if not per_cat:
            continue
        short = get_short_name(model)
        model_names.append(short)
        model_category_rates[short] = {
            cat: vals["malicious_detection_rate"] for cat, vals in per_cat.items()
        }
        all_categories.update(per_cat.keys())

    if not model_names or not all_categories:
        return

    categories = sorted(all_categories)

    # Build matrix (models x categories)
    matrix = np.full((len(model_names), len(categories)), np.nan)
    for i, model in enumerate(model_names):
        for j, cat in enumerate(categories):
            if cat in model_category_rates[model]:
                matrix[i, j] = model_category_rates[model][cat] * 100

    fig, ax = plt.subplots(figsize=(max(10, len(categories) * 1.2), max(6, len(model_names) * 0.7)))

    heatmap = seaborn.heatmap(
        matrix,
        annot=True,
        fmt=".1f",
        cmap="RdYlGn",
        vmin=0,
        vmax=100,
        xticklabels=categories,
        yticklabels=model_names,
        linewidths=0.5,
        linecolor="white",
        cbar_kws={"label": "Malicious Detection Rate (%)"},
        ax=ax,
    )
    # Rotate x-axis labels for readability
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_title("Per-Category Malicious Detection Rates by Model (%)")

    save_plot(fig, output_dir / "category_heatmap")


def plot_micro_vs_macro(results: dict, output_dir: Path) -> None:
    """Generate grouped bar chart comparing micro and macro malicious detection rates.

    Highlights models with uneven performance across categories
    (large gap between micro and macro averages).

    Args:
        results: The "results" dict from comparison JSON.
        output_dir: Directory to save output files.
    """
    _apply_style()
    successful = _get_successful_models(results)

    # Collect micro/macro pairs with standard errors
    # (short_name, micro%, macro%, full_model, micro_se%, macro_se%)
    data_points: list[tuple[str, float, float, str, float, float]] = []

    for model, data in successful.items():
        gtfo = data.get("datasets", {}).get("gtfobins")
        if not gtfo:
            continue
        micro = gtfo.get("malicious_detection_rate")
        macro = gtfo.get("malicious_detection_rate_macro")
        if micro is None or macro is None:
            continue
        micro_se = (gtfo.get("stderr", 0.0) or 0.0) * 100

        # Compute macro SE via variance propagation:
        # macro = (1/K) * Σ p_i  →  SE = (1/K) * √(Σ p_i(1-p_i)/n_i)
        per_cat = gtfo.get("per_category_malicious_detection_rates", {})
        if per_cat:
            var_sum = sum(
                cd["malicious_detection_rate"] * (1 - cd["malicious_detection_rate"]) / cd["count"]
                for cd in per_cat.values()
            )
            macro_se = (np.sqrt(var_sum) / len(per_cat)) * 100
        else:
            macro_se = 0.0

        data_points.append((
            get_short_name(model), micro * 100, macro * 100, model, micro_se, macro_se,
        ))

    if not data_points:
        return

    # Sort by micro malicious detection rate descending
    data_points.sort(key=lambda x: x[1], reverse=True)

    model_names = [d[0] for d in data_points]
    micros = [d[1] for d in data_points]
    macros = [d[2] for d in data_points]
    full_models = [d[3] for d in data_points]
    micro_ses = [d[4] for d in data_points]
    macro_ses = [d[5] for d in data_points]

    x = np.arange(len(model_names))
    bar_width = 0.35

    fig, ax = plt.subplots(figsize=(max(10, len(model_names) * 1.5), 7))

    error_kw = dict(elinewidth=1, capsize=3, ecolor="gray")
    bars_micro = ax.bar(
        x - bar_width / 2,
        micros,
        bar_width,
        yerr=micro_ses,
        error_kw=error_kw,
        label="Micro Avg (overall)",
        color=[get_provider_color(m) for m in full_models],
        alpha=0.85,
        edgecolor="white",
        linewidth=0.5,
    )
    bars_macro = ax.bar(
        x + bar_width / 2,
        macros,
        bar_width,
        yerr=macro_ses,
        error_kw=error_kw,
        label="Macro Avg (per-category mean)",
        color=[get_provider_color(m) for m in full_models],
        alpha=0.45,
        edgecolor="white",
        linewidth=0.5,
        hatch="//",
    )

    # Value labels on bars (offset above error bars)
    for bar, se in zip(bars_micro, micro_ses):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + se + 0.3,
            f"{bar.get_height():.1f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    for bar, se in zip(bars_macro, macro_ses):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + se + 0.3,
            f"{bar.get_height():.1f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    # Target line
    ax.axhline(y=95, color="green", linestyle="--", alpha=0.5, label="Target (95%)")

    ax.set_xticks(x)
    ax.set_xticklabels(model_names, rotation=45, ha="right")
    ax.set_ylabel("Malicious Detection Rate (%)")
    ax.set_title("Micro vs Macro Average Malicious Detection Rate")
    ax.legend(loc="lower right", fontsize=9)

    # Set y-axis to show relevant range
    y_min = max(0, min(min(micros), min(macros)) - 5)
    ax.set_ylim(y_min, 102)

    save_plot(fig, output_dir / "micro_vs_macro")


def generate_all_plots(comparison_file: Path, output_dir: Path) -> list[Path]:
    """Generate all benchmark visualization plots.

    Args:
        comparison_file: Path to comparison JSON file.
        output_dir: Directory to save output files.

    Returns:
        List of paths to generated files.
    """
    data = load_comparison_results(comparison_file)
    results = data.get("results", {})
    ranking = data.get("ranking", [])

    output_dir.mkdir(parents=True, exist_ok=True)

    plot_cost_vs_score(results, output_dir)
    plot_cost_vs_malicious_detection_rate(results, output_dir)
    plot_latency_vs_score(results, output_dir)
    plot_latency_vs_malicious_detection_rate(results, output_dir)
    plot_detection_vs_pass(results, output_dir)
    plot_latency_distribution(results, output_dir)
    plot_cost_comparison(results, output_dir)
    plot_ranking_table(results, ranking, output_dir)
    plot_category_heatmap(results, output_dir)
    plot_micro_vs_macro(results, output_dir)

    # Collect generated files
    generated = sorted(output_dir.glob("*.png")) + sorted(output_dir.glob("*.svg"))

    print(f"\nGenerated {len(generated)} files in {output_dir}/:")
    for path in generated:
        print(f"  {path.name}")

    return generated


def main() -> None:
    """CLI entry point for plot generation."""
    parser = argparse.ArgumentParser(
        description="Generate aegish benchmark comparison plots"
    )
    parser.add_argument(
        "comparison_file",
        type=Path,
        help="Path to comparison JSON file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for plots (default: benchmark/results/plots/)",
    )
    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = Path("benchmark/results/plots")

    generate_all_plots(args.comparison_file, args.output_dir)


if __name__ == "__main__":
    main()
