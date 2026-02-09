"""Benchmark visualization plots for SecBASH LLM comparison results.

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
    """Generate Cost vs SecBASH Score scatter plot.

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
        score = composite.get("secbash_score", 0.0)
        costs.append(cost)
        scores.append(score)
        models.append(model)

        color = get_provider_color(model)
        ax.scatter(
            cost, score, c=color, s=100, zorder=5, edgecolors="white", linewidth=0.5
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
        y=0.85, color="green", linestyle="--", alpha=0.5, label="Target Score (0.85)"
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
            label="Target Score (0.85)",
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
    ax.set_ylabel("SecBASH Score")
    ax.set_title("Cost vs SecBASH Score")

    save_plot(fig, output_dir / "cost_vs_score")


def plot_detection_vs_pass(results: dict, output_dir: Path) -> None:
    """Generate Detection Rate vs Pass Rate scatter plot.

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

        pass_rate = harm.get("pass_rate", 0.0) * 100
        detection_rate = gtfo.get("detection_rate", 0.0) * 100

        color = get_provider_color(model)
        ax.scatter(
            pass_rate,
            detection_rate,
            c=color,
            s=100,
            zorder=5,
            edgecolors="white",
            linewidth=0.5,
        )
        texts.append(
            ax.text(
                pass_rate,
                detection_rate,
                get_short_name(model),
                fontsize=8,
            )
        )
        models_plotted.append(model)

    # Set axis limits before drawing target zone
    # Ensure both threshold lines (x=90, y=95) are visible
    all_pass = [
        harm.get("pass_rate", 0.0) * 100
        for d in successful.values()
        for harm in [d.get("datasets", {}).get("harmless", {})]
        if harm
    ]
    all_det = [
        gtfo.get("detection_rate", 0.0) * 100
        for d in successful.values()
        for gtfo in [d.get("datasets", {}).get("gtfobins", {})]
        if gtfo
    ]
    if all_pass and all_det:
        x_min = min(min(all_pass) - 5, 88)
        y_min = max(0, min(all_det) - 5)
        ax.set_xlim(x_min, 101.5)
        ax.set_ylim(y_min, 101.5)
        ax.set_xticks([t for t in ax.get_xticks() if t <= 100])
        ax.set_yticks([t for t in ax.get_yticks() if t <= 100])

    # Target zone (green shaded rectangle) - clamped to axis bounds
    target_rect = plt.Rectangle(
        (90, 95), 10, 5, fill=True, alpha=0.08, color="green", label="Target Zone"
    )
    ax.add_patch(target_rect)

    # Threshold lines with separate labels
    ax.axhline(
        y=95, color="green", linestyle="--", alpha=0.5, label="Detection Target (95%)"
    )
    ax.axvline(
        x=90, color="green", linestyle="--", alpha=0.5, label="Pass Rate Target (90%)"
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
            label="Detection \u226595%",
        ),
        plt.Line2D(
            [0],
            [0],
            color="green",
            linestyle="--",
            alpha=0.5,
            label="Pass Rate \u226590%",
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

    ax.set_xlabel("Pass Rate (Harmless Allowed %)")
    ax.set_ylabel("Detection Rate (Malicious Flagged %)")
    ax.set_title("Detection Rate vs Pass Rate")

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
        composite = data.get("composite", {})
        avg_latency = composite.get("avg_latency_ms", 0.0)
        if avg_latency <= 0:
            continue

        # Get per-dataset latency for p50 and p90
        datasets = data.get("datasets", {})
        p50_values = []
        p90_values = []
        for ds_data in datasets.values():
            if ds_data and "latency" in ds_data:
                p50_values.append(ds_data["latency"].get("p50", 0.0))
                p90_values.append(ds_data["latency"].get("p90", 0.0))

        avg_p50 = sum(p50_values) / len(p50_values) if p50_values else avg_latency
        avg_p90 = sum(p90_values) / len(p90_values) if p90_values else avg_latency

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
    """Generate model ranking table as a figure.

    Args:
        results: The "results" dict from comparison JSON.
        ranking: Sorted ranking list from comparison JSON.
        output_dir: Directory to save output files.
    """
    _apply_style()

    if not ranking:
        return

    # Build table data
    columns = ["Rank", "Model", "Detection%", "Pass%", "Score", "Cost/1k", "Latency"]
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

        det_rate = gtfo.get("detection_rate", 0.0) if gtfo else 0.0
        pass_rate = harm.get("pass_rate", 0.0) if harm else 0.0
        score = composite.get("secbash_score", 0.0)
        cost = composite.get("cost_per_1000_combined", 0.0)
        latency = composite.get("avg_latency_ms", 0.0)

        # Check/cross indicators for targets
        det_check = " \u2713" if det_rate >= 0.95 else ""
        pass_check = " \u2713" if pass_rate >= 0.90 else ""
        score_check = " \u2713" if score >= 0.85 else ""

        row = [
            str(entry["rank"]),
            get_short_name(model),
            f"{det_rate * 100:.1f}%{det_check}",
            f"{pass_rate * 100:.1f}%{pass_check}",
            f"{score:.3f}{score_check}",
            f"${cost:.2f}" if cost > 0 else "$0.00",
            f"{latency / 1000:.1f}s",
        ]
        cell_data.append(row)

        # Color by performance tier
        if det_rate >= 0.95 and pass_rate >= 0.90 and score >= 0.85:
            row_colors.append("#d4edda")  # green
        elif score >= 0.50:
            row_colors.append("#fff3cd")  # yellow
        else:
            row_colors.append("#f8d7da")  # red

    if not cell_data:
        return

    fig, ax = plt.subplots(figsize=(14, max(4, len(cell_data) * 0.5 + 2)))
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

    # Style header row
    for j in range(len(columns)):
        cell = table[0, j]
        cell.set_facecolor("#343a40")
        cell.set_text_props(color="white", fontweight="bold")

    # Style data rows
    for i in range(len(cell_data)):
        for j in range(len(columns)):
            cell = table[i + 1, j]
            cell.set_facecolor(row_colors[i])

    ax.set_title("SecBASH Model Ranking", fontsize=14, fontweight="bold", pad=20)

    save_plot(fig, output_dir / "ranking_table")


def plot_category_heatmap(results: dict, output_dir: Path) -> None:
    """Generate per-category detection rate heatmap (models x categories).

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
        per_cat = gtfo.get("per_category_detection_rates", {})
        if not per_cat:
            continue
        short = get_short_name(model)
        model_names.append(short)
        model_category_rates[short] = {
            cat: vals["detection_rate"] for cat, vals in per_cat.items()
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
        cbar_kws={"label": "Detection Rate (%)"},
        ax=ax,
    )
    # Rotate x-axis labels for readability
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_title("Per-Category Detection Rates by Model (%)")

    save_plot(fig, output_dir / "category_heatmap")


def plot_micro_vs_macro(results: dict, output_dir: Path) -> None:
    """Generate grouped bar chart comparing micro and macro detection rates.

    Highlights models with uneven performance across categories
    (large gap between micro and macro averages).

    Args:
        results: The "results" dict from comparison JSON.
        output_dir: Directory to save output files.
    """
    _apply_style()
    successful = _get_successful_models(results)

    # Collect micro/macro pairs
    data_points: list[tuple[str, float, float, str]] = []  # (short_name, micro, macro, full_model)

    for model, data in successful.items():
        gtfo = data.get("datasets", {}).get("gtfobins")
        if not gtfo:
            continue
        micro = gtfo.get("detection_rate")
        macro = gtfo.get("detection_rate_macro")
        if micro is None or macro is None:
            continue
        data_points.append((get_short_name(model), micro * 100, macro * 100, model))

    if not data_points:
        return

    # Sort by micro detection rate descending
    data_points.sort(key=lambda x: x[1], reverse=True)

    model_names = [d[0] for d in data_points]
    micros = [d[1] for d in data_points]
    macros = [d[2] for d in data_points]
    full_models = [d[3] for d in data_points]

    x = np.arange(len(model_names))
    bar_width = 0.35

    fig, ax = plt.subplots(figsize=(max(10, len(model_names) * 1.5), 7))

    bars_micro = ax.bar(
        x - bar_width / 2,
        micros,
        bar_width,
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
        label="Macro Avg (per-category mean)",
        color=[get_provider_color(m) for m in full_models],
        alpha=0.45,
        edgecolor="white",
        linewidth=0.5,
        hatch="//",
    )

    # Value labels on bars
    for bar in bars_micro:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.3,
            f"{bar.get_height():.1f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    for bar in bars_macro:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.3,
            f"{bar.get_height():.1f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    # Target line
    ax.axhline(y=95, color="green", linestyle="--", alpha=0.5, label="Target (95%)")

    ax.set_xticks(x)
    ax.set_xticklabels(model_names, rotation=45, ha="right")
    ax.set_ylabel("Detection Rate (%)")
    ax.set_title("Micro vs Macro Average Detection Rate")
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
        description="Generate SecBASH benchmark comparison plots"
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
