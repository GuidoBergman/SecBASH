# Story 4.7: Generate Comparison Plots

**Epic:** Epic 4 - Benchmark Evaluation
**Status:** Pending
**Priority:** should-have

---

## User Story

As a **developer**,
I want **visualization plots comparing model performance and cost**,
So that **I can identify optimal cost/performance trade-offs**.

---

## Acceptance Criteria

### AC1: Cost vs SecBASH Score (Scatter Plot)
**Given** comparison results from multiple model evaluations
**When** the cost vs score plot is generated
**Then** it displays:
- X-axis: Cost per 1000 commands ($)
- Y-axis: SecBASH Score
- Points labeled by model name
- Pareto frontier highlighted

### AC2: Detection Rate vs Pass Rate (Scatter Plot)
**Given** comparison results
**When** the detection vs pass rate plot is generated
**Then** it displays:
- X-axis: Pass Rate (harmless allowed %)
- Y-axis: Detection Rate (malicious flagged %)
- Trade-off visualization
- Target zone highlighted (≥95% detection, ≥90% pass)

### AC3: Latency Distribution (Box Plot)
**Given** comparison results
**When** the latency distribution plot is generated
**Then** it displays:
- One box per model
- Shows median, quartiles, outliers
- Models sorted by median latency

### AC4: Cost per 1000 Commands (Bar Chart)
**Given** comparison results
**When** the cost bar chart is generated
**Then** it displays:
- Horizontal bars sorted by cost
- Color-coded by provider (OpenAI=blue, Anthropic=orange, Google=green, OpenRouter=purple)

### AC5: Model Ranking Table (Summary)
**Given** comparison results
**When** the summary table is generated
**Then** it displays:
- Columns: Model, Detection Rate, Pass Rate, Score, Cost, Latency
- Sorted by SecBASH Score
- Targets indicated with checkmarks

### AC6: Output Formats
**Given** plots are generated
**When** saved
**Then** they are saved to `tests/benchmark/results/plots/`
**And** both PNG and SVG formats are generated

### AC7: Consistent Styling
**Given** all plots
**When** styling is applied
**Then** consistent colors, fonts, and themes are used

---

## Technical Requirements

### Implementation Location
- **Plotting script:** `tests/benchmark/plots.py`
- **Output directory:** `tests/benchmark/results/plots/`

### Dependencies
```bash
uv add matplotlib seaborn
# Optional for interactive plots:
# uv add plotly
```

### Plotting Script Structure
```python
#!/usr/bin/env python
"""Generate benchmark comparison plots."""

import json
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Provider colors
PROVIDER_COLORS = {
    "openai": "#10A37F",      # OpenAI green
    "anthropic": "#D97706",   # Anthropic orange
    "google": "#4285F4",      # Google blue
    "openrouter": "#8B5CF6",  # Purple
}


def load_comparison_results(filepath: Path) -> dict:
    """Load comparison results from JSON."""
    with open(filepath) as f:
        return json.load(f)


def plot_cost_vs_score(results: dict, output_dir: Path):
    """Generate Cost vs SecBASH Score scatter plot."""
    fig, ax = plt.subplots(figsize=(10, 8))

    models = []
    costs = []
    scores = []
    colors = []

    for model, data in results["results"].items():
        models.append(model.split("/")[-1])  # Short name
        costs.append(data["composite"]["total_cost_usd"] / 800 * 1000)  # Per 1000
        scores.append(data["composite"]["secbash_score"])

        provider = model.split("/")[0]
        colors.append(PROVIDER_COLORS.get(provider, "#666666"))

    ax.scatter(costs, scores, c=colors, s=100, alpha=0.8)

    # Add labels
    for i, model in enumerate(models):
        ax.annotate(model, (costs[i], scores[i]), fontsize=9,
                   xytext=(5, 5), textcoords='offset points')

    # Pareto frontier
    pareto_points = compute_pareto_frontier(costs, scores)
    if len(pareto_points) > 1:
        pareto_costs, pareto_scores = zip(*pareto_points)
        ax.plot(pareto_costs, pareto_scores, 'r--', alpha=0.5, label='Pareto frontier')

    # Target zone
    ax.axhline(y=0.85, color='green', linestyle=':', alpha=0.5, label='Score target (0.85)')

    ax.set_xlabel('Cost per 1000 commands ($)')
    ax.set_ylabel('SecBASH Score')
    ax.set_title('Cost vs Performance Trade-off')
    ax.legend()
    ax.grid(True, alpha=0.3)

    save_plot(fig, output_dir / 'cost_vs_score')


def plot_detection_vs_pass(results: dict, output_dir: Path):
    """Generate Detection Rate vs Pass Rate scatter plot."""
    fig, ax = plt.subplots(figsize=(10, 8))

    models = []
    detection_rates = []
    pass_rates = []
    colors = []

    for model, data in results["results"].items():
        models.append(model.split("/")[-1])
        detection_rates.append(data["datasets"]["gtfobins"]["detection_rate"] * 100)
        pass_rates.append(data["datasets"]["harmless"]["pass_rate"] * 100)

        provider = model.split("/")[0]
        colors.append(PROVIDER_COLORS.get(provider, "#666666"))

    ax.scatter(pass_rates, detection_rates, c=colors, s=100, alpha=0.8)

    # Add labels
    for i, model in enumerate(models):
        ax.annotate(model, (pass_rates[i], detection_rates[i]), fontsize=9,
                   xytext=(5, 5), textcoords='offset points')

    # Target zone (highlighted rectangle)
    from matplotlib.patches import Rectangle
    target_zone = Rectangle((90, 95), 10, 5, alpha=0.1, color='green')
    ax.add_patch(target_zone)

    # Target lines
    ax.axhline(y=95, color='green', linestyle=':', alpha=0.5, label='Detection target (95%)')
    ax.axvline(x=90, color='blue', linestyle=':', alpha=0.5, label='Pass rate target (90%)')

    ax.set_xlabel('Pass Rate (%)')
    ax.set_ylabel('Detection Rate (%)')
    ax.set_title('Detection vs False Positive Trade-off')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlim(85, 100)
    ax.set_ylim(85, 100)

    save_plot(fig, output_dir / 'detection_vs_pass')


def plot_latency_distribution(results: dict, output_dir: Path):
    """Generate Latency Distribution box plot."""
    fig, ax = plt.subplots(figsize=(12, 6))

    # Prepare data for box plot
    latency_data = []
    model_names = []

    for model, data in results["results"].items():
        # Would need per-command latencies for true box plot
        # Using summary stats as approximation
        model_names.append(model.split("/")[-1])
        latency_data.append({
            "mean": data["composite"]["avg_latency_ms"],
            "model": model.split("/")[-1]
        })

    # Sort by mean latency
    latency_data.sort(key=lambda x: x["mean"])
    model_names = [d["model"] for d in latency_data]
    means = [d["mean"] for d in latency_data]

    ax.barh(model_names, means, color='steelblue', alpha=0.7)
    ax.set_xlabel('Mean Latency (ms)')
    ax.set_title('Response Latency by Model')
    ax.grid(True, alpha=0.3, axis='x')

    save_plot(fig, output_dir / 'latency_distribution')


def plot_cost_comparison(results: dict, output_dir: Path):
    """Generate Cost per 1000 Commands bar chart."""
    fig, ax = plt.subplots(figsize=(12, 6))

    cost_data = []
    for model, data in results["results"].items():
        provider = model.split("/")[0]
        cost_per_1000 = data["composite"]["total_cost_usd"] / 800 * 1000
        cost_data.append({
            "model": model.split("/")[-1],
            "cost": cost_per_1000,
            "color": PROVIDER_COLORS.get(provider, "#666666")
        })

    # Sort by cost
    cost_data.sort(key=lambda x: x["cost"])

    models = [d["model"] for d in cost_data]
    costs = [d["cost"] for d in cost_data]
    colors = [d["color"] for d in cost_data]

    ax.barh(models, costs, color=colors, alpha=0.8)
    ax.set_xlabel('Cost per 1000 commands ($)')
    ax.set_title('API Cost Comparison')
    ax.grid(True, alpha=0.3, axis='x')

    # Add value labels
    for i, (model, cost) in enumerate(zip(models, costs)):
        ax.text(cost + 0.05, i, f'${cost:.2f}', va='center', fontsize=9)

    save_plot(fig, output_dir / 'cost_comparison')


def save_plot(fig, filepath: Path):
    """Save plot in PNG and SVG formats."""
    fig.tight_layout()
    fig.savefig(f'{filepath}.png', dpi=150)
    fig.savefig(f'{filepath}.svg')
    plt.close(fig)


def generate_all_plots(comparison_file: Path, output_dir: Path):
    """Generate all comparison plots."""
    output_dir.mkdir(parents=True, exist_ok=True)

    results = load_comparison_results(comparison_file)

    plot_cost_vs_score(results, output_dir)
    plot_detection_vs_pass(results, output_dir)
    plot_latency_distribution(results, output_dir)
    plot_cost_comparison(results, output_dir)

    print(f"Plots saved to {output_dir}")


if __name__ == "__main__":
    import sys
    comparison_file = Path(sys.argv[1])
    output_dir = Path("tests/benchmark/results/plots")
    generate_all_plots(comparison_file, output_dir)
```

### CLI Usage
```bash
# Generate plots from comparison results
python tests/benchmark/plots.py tests/benchmark/results/comparison_20260203_143000.json

# Plots saved to:
# tests/benchmark/results/plots/cost_vs_score.png
# tests/benchmark/results/plots/cost_vs_score.svg
# tests/benchmark/results/plots/detection_vs_pass.png
# tests/benchmark/results/plots/detection_vs_pass.svg
# tests/benchmark/results/plots/latency_distribution.png
# tests/benchmark/results/plots/latency_distribution.svg
# tests/benchmark/results/plots/cost_comparison.png
# tests/benchmark/results/plots/cost_comparison.svg
```

---

## Implementation Notes

### Matplotlib Configuration
```python
# Set consistent style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.figsize'] = (10, 8)
plt.rcParams['font.size'] = 11
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12
```

### Pareto Frontier
The Pareto frontier shows models that are not dominated (no other model is both cheaper AND better scoring).

### Color Accessibility
Provider colors chosen for color-blind accessibility. Consider adding shape markers as additional differentiation.

---

## Test Requirements

### Unit Tests
1. Test plot generation doesn't error
2. Test output files created
3. Test both PNG and SVG formats

### Visual Tests (Manual)
1. Verify plots are readable
2. Check label placement
3. Confirm colors distinguish providers

---

## Definition of Done

- [ ] `matplotlib` and `seaborn` added to dependencies
- [ ] All 4 plot types generated correctly
- [ ] PNG and SVG formats for each plot
- [ ] Consistent styling across plots
- [ ] Provider color coding works
- [ ] Plots saved to `tests/benchmark/results/plots/`
- [ ] Script can be run from CLI

---

## Dependencies

- **Blocked by:** Story 4.6 (comparison results)
- **Blocks:** None (final story)

---

## Estimated Complexity

**Implementation:** Low
- Standard matplotlib plotting
- Well-defined visualizations

**Testing:** Low
- Mostly visual verification
- File existence tests

**Risk:** Low
- No API dependencies
- Standard visualization library
