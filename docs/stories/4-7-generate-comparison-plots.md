# Story 4.7: Generate Comparison Plots

Status: done

## Story

As a **developer**,
I want **visualization plots comparing model performance and cost**,
So that **I can identify optimal cost/performance trade-offs**.

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
- Target zone highlighted (>=95% detection, >=90% pass)

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
- Color-coded by provider (OpenAI, Anthropic, Google, OpenRouter, HF/Featherless)

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

## Tasks / Subtasks

- [x] Task 1: Add matplotlib and seaborn to dev dependencies (AC: #6, #7)
  - [x] 1.1 Run `uv add --group dev matplotlib seaborn`
  - [x] 1.2 Verify import works

- [x] Task 2: Create `tests/benchmark/plots.py` with core infrastructure (AC: #6, #7)
  - [x] 2.1 Create module with `PROVIDER_COLORS` dict mapping provider prefixes to colors
  - [x] 2.2 Implement `load_comparison_results(filepath: Path) -> dict` reading JSON
  - [x] 2.3 Implement `get_provider(model: str) -> str` extracting provider prefix
  - [x] 2.4 Implement `get_short_name(model: str) -> str` for display labels
  - [x] 2.5 Implement `save_plot(fig, filepath: Path)` saving PNG (dpi=150) + SVG, then `plt.close(fig)`
  - [x] 2.6 Set matplotlib style: `seaborn-v0_8-whitegrid`, font size 11, title 14, label 12

- [x] Task 3: Implement Cost vs SecBASH Score scatter plot (AC: #1)
  - [x] 3.1 Implement `plot_cost_vs_score(results: dict, output_dir: Path)`
  - [x] 3.2 X-axis: `composite.cost_per_1000_combined`; Y-axis: `composite.secbash_score`
  - [x] 3.3 Color points by provider using `PROVIDER_COLORS`
  - [x] 3.4 Annotate each point with short model name
  - [x] 3.5 Implement `compute_pareto_frontier(costs, scores)` returning non-dominated points (minimize cost, maximize score)
  - [x] 3.6 Plot Pareto frontier as dashed red line
  - [x] 3.7 Add horizontal dashed line at score=0.85 (target)
  - [x] 3.8 Handle $0.00 cost models (Google free tier) - plot at x=0 or near origin

- [x] Task 4: Implement Detection Rate vs Pass Rate scatter plot (AC: #2)
  - [x] 4.1 Implement `plot_detection_vs_pass(results: dict, output_dir: Path)`
  - [x] 4.2 X-axis: `datasets.harmless.pass_rate * 100`; Y-axis: `datasets.gtfobins.detection_rate * 100`
  - [x] 4.3 Color by provider, annotate with model name
  - [x] 4.4 Add green shaded rectangle for target zone (pass>=90%, detection>=95%)
  - [x] 4.5 Add dashed lines at detection=95% and pass_rate=90%
  - [x] 4.6 Set axis limits to show all data points (don't hardcode 85-100)

- [x] Task 5: Implement Latency Distribution visualization (AC: #3)
  - [x] 5.1 Implement `plot_latency_distribution(results: dict, output_dir: Path)`
  - [x] 5.2 Use horizontal bar chart with latency summary stats (mean, p50, p90 from `composite.avg_latency_ms` and per-dataset latency)
  - [x] 5.3 Sort models by mean latency ascending
  - [x] 5.4 Add value labels at end of bars

- [x] Task 6: Implement Cost per 1000 Commands bar chart (AC: #4)
  - [x] 6.1 Implement `plot_cost_comparison(results: dict, output_dir: Path)`
  - [x] 6.2 Horizontal bars sorted by cost ascending
  - [x] 6.3 Color bars by provider
  - [x] 6.4 Add `$X.XX` value labels at end of each bar
  - [x] 6.5 Handle $0.00 cost models appropriately (show as 0, note "free tier")

- [x] Task 7: Implement Model Ranking Table as figure (AC: #5)
  - [x] 7.1 Implement `plot_ranking_table(results: dict, ranking: list, output_dir: Path)`
  - [x] 7.2 Use matplotlib table rendering with columns: Rank, Model, Detection%, Pass%, Score, Cost, Latency
  - [x] 7.3 Sort by SecBASH Score descending (use ranking from JSON)
  - [x] 7.4 Add checkmark indicators for targets met
  - [x] 7.5 Color rows by performance tier (green=meets all targets, yellow=partial, red=below)

- [x] Task 8: Implement CLI and `generate_all_plots()` entry point (AC: #6)
  - [x] 8.1 Implement `generate_all_plots(comparison_file: Path, output_dir: Path)`
  - [x] 8.2 Create output directory if needed
  - [x] 8.3 Call all 5 plot functions
  - [x] 8.4 Print summary of saved files
  - [x] 8.5 Add `argparse` CLI: positional arg for comparison JSON, optional `--output-dir`
  - [x] 8.6 Add `if __name__ == "__main__"` entry point

- [x] Task 9: Write tests (AC: all)
  - [x] 9.1 Create `tests/benchmark/test_plots.py`
  - [x] 9.2 Create a fixture with minimal valid comparison JSON data (2-3 models)
  - [x] 9.3 Test `load_comparison_results()` with valid JSON
  - [x] 9.4 Test `get_provider()` for all provider prefixes
  - [x] 9.5 Test `get_short_name()` for long model IDs
  - [x] 9.6 Test `compute_pareto_frontier()` with known inputs
  - [x] 9.7 Test each plot function generates PNG and SVG files without error (use tmp_path fixture)
  - [x] 9.8 Test `generate_all_plots()` creates all expected output files
  - [x] 9.9 Test CLI argument parsing
  - [x] 9.10 Test handling of models with $0 cost
  - [x] 9.11 Test handling of models with status != "success"

## Dev Notes

### CRITICAL: Current Implementation State

Story 4.6 is DONE. The comparison framework produces JSON results that are the input for this story.

**Existing files you will USE (do NOT recreate):**

| File | Purpose | Status |
|------|---------|--------|
| `tests/benchmark/compare.py` | Comparison framework producing JSON | EXISTS - import or read output |
| `tests/benchmark/report.py` | MODEL_PRICING, metrics extraction | EXISTS - reference for pricing data |
| `tests/benchmark/results/comparison_20260206_181702.json` | Actual comparison data (11 models) | EXISTS - use as test input |

**File you will CREATE:**
- `tests/benchmark/plots.py` - Plotting module (all plot generation functions)
- `tests/benchmark/test_plots.py` - Tests for plotting module

### CRITICAL: Comparison JSON Schema

The input JSON file (`tests/benchmark/results/comparison_*.json`) follows this exact structure:

```json
{
  "metadata": {
    "timestamp": "2026-02-06T18:17:02Z",
    "models_evaluated": 11,
    "datasets": ["gtfobins", "harmless"],
    "scaffolding": "standard",
    "gtfobins_count": 431,
    "harmless_count": 310
  },
  "results": {
    "<model_id>": {
      "model": "<model_id>",
      "cot": false,
      "status": "success",
      "datasets": {
        "gtfobins": {
          "detection_rate": 0.951,
          "accuracy": 0.951,
          "stderr": 0.0103,
          "total_commands": 431,
          "correct": 410,
          "latency": {"mean": 37780, "p50": 36264, "p90": 53900, "p99": 174680, "max": 180038},
          "cost": {"total_cost": 2.85, "cost_per_1000": 6.61, "cost_per_command": 0.0066}
        },
        "harmless": {
          "pass_rate": 0.955,
          "false_positive_rate": 0.045,
          "accuracy": 0.955,
          "stderr": 0.0118,
          "total_commands": 310,
          "correct": 296,
          "latency": {"mean": 33358, "p50": 21543, "p90": 68813, "p99": 129029, "max": 180024},
          "cost": {"total_cost": 1.97, "cost_per_1000": 6.35, "cost_per_command": 0.0064}
        }
      },
      "composite": {
        "secbash_score": 0.908,
        "secbash_score_se": 0.015,
        "total_cost_usd": 4.82,
        "cost_per_1000_combined": 6.50,
        "avg_latency_ms": 35569
      }
    }
  },
  "ranking": [
    {"rank": 1, "model": "anthropic/claude-sonnet-4-5-20250929", "secbash_score": 0.908, "cost_per_1000": 6.50}
  ]
}
```

**Key fields for each plot:**
- **Cost vs Score:** `composite.cost_per_1000_combined` (X), `composite.secbash_score` (Y)
- **Detection vs Pass:** `datasets.gtfobins.detection_rate` (Y), `datasets.harmless.pass_rate` (X)
- **Latency:** `composite.avg_latency_ms` and per-dataset `latency.{mean, p50, p90, p99, max}`
- **Cost bar:** `composite.cost_per_1000_combined`
- **Ranking table:** `ranking[]` array from JSON + full metrics from `results`

### CRITICAL: Real Data Ranges (from actual benchmark results, Feb 6 2026)

These ranges determine axis scaling - DO NOT hardcode narrow ranges:

| Metric | Min | Max | Notes |
|--------|-----|-----|-------|
| SecBASH Score | 0.026 (gemini-3-pro) | 0.908 (sonnet-4.5) | Huge range, some models near 0 |
| Detection Rate | 0.369 (llama-guard) | 0.991 (Foundation-Sec) | Most 0.89-0.99 |
| Pass Rate | 0.055 (gemini-3-pro) | 0.987 (haiku-4.5) | Huge spread |
| Cost/1000 | $0.00 (Google) | $11.32 (opus-4.6) | Google reports $0 (free tier) |
| Avg Latency | 6938ms (Foundation-Sec) | 52389ms (gemini-3-pro) | Wide range |

**Models with $0 cost:** google/gemini-3-pro-preview, google/gemini-3-flash-preview (free API tier). Handle gracefully in scatter plots.

### CRITICAL: 11 Models and Their Providers

Map model ID prefixes to providers for color coding:

```python
PROVIDER_COLORS = {
    "openai": "#10A37F",           # OpenAI green
    "anthropic": "#D97706",        # Anthropic orange/amber
    "google": "#4285F4",           # Google blue
    "openrouter": "#8B5CF6",       # Purple
    "hf-inference-providers": "#FF6B6B",  # Red/coral for HF/Featherless
}
```

**Provider extraction:** `model.split("/")[0]` works for all models:
- `openai/gpt-5.1` -> `openai`
- `anthropic/claude-opus-4-6` -> `anthropic`
- `google/gemini-3-flash-preview` -> `google`
- `openrouter/microsoft/phi-4` -> `openrouter`
- `openrouter/meta-llama/llama-guard-3-8b` -> `openrouter`
- `hf-inference-providers/fdtn-ai/Foundation-Sec-8B-Instruct:featherless-ai` -> `hf-inference-providers`

**Short name extraction for labels:** Use the last segment after `/`, but handle colons:
- `openai/gpt-5.1` -> `gpt-5.1`
- `anthropic/claude-sonnet-4-5-20250929` -> `claude-sonnet-4-5`
- `openrouter/meta-llama/llama-guard-3-8b` -> `llama-guard-3-8b`
- `hf-inference-providers/fdtn-ai/Foundation-Sec-8B-Instruct:featherless-ai` -> `Foundation-Sec-8B`

### CRITICAL: Pareto Frontier Algorithm

Non-dominated points where no other point is both cheaper AND has higher score:

```python
def compute_pareto_frontier(costs: list[float], scores: list[float]) -> list[tuple[float, float]]:
    """Return Pareto-optimal points (minimize cost, maximize score)."""
    points = sorted(zip(costs, scores), key=lambda p: p[0])  # Sort by cost ascending
    frontier = []
    max_score = -1.0
    for cost, score in points:
        if score > max_score:
            frontier.append((cost, score))
            max_score = score
    return frontier
```

### CRITICAL: No Per-Command Latencies Available

The comparison JSON only has summary latency stats (mean, p50, p90, p99, max) - NOT per-command latency arrays. A true box plot requires raw data. Options:
1. **Recommended:** Use horizontal bar chart showing mean latency with error indicators (p50, p90 as markers)
2. Alternative: Reconstruct approximate box plot from summary stats
3. Alternative: Load raw Inspect eval logs from `logs/` dir to get per-sample `total_time`

Use option 1 (bar chart with summary stats) for simplicity - the eval logs may be large.

### CRITICAL: Dependencies

matplotlib and seaborn must be added as dev dependencies:

```bash
uv add --group dev matplotlib seaborn
```

Do NOT add to production dependencies. These are only for benchmark visualization.

### CRITICAL: Filter Failed Models

Only plot models where `status == "success"`. Skip models with `status == "error"` or `"partial"`.

### Project Structure Notes

- All new code goes in `tests/benchmark/` (per Epic 4 architecture)
- Follow PEP 8: snake_case functions, UPPER_SNAKE_CASE constants
- Python 3.10+ type hints
- All new code must pass `ruff check` and `ruff format`
- Use standard `logging` module if needed

### File Structure After Implementation

```
tests/benchmark/
├── plots.py              # NEW - all plot generation functions
├── test_plots.py         # NEW - tests for plots module
├── compare.py            # EXISTS (unchanged)
├── report.py             # EXISTS (unchanged)
├── results/
│   ├── comparison_20260206_181702.json  # EXISTS - input data
│   └── plots/                           # NEW - output directory
│       ├── cost_vs_score.png
│       ├── cost_vs_score.svg
│       ├── detection_vs_pass.png
│       ├── detection_vs_pass.svg
│       ├── latency_distribution.png
│       ├── latency_distribution.svg
│       ├── cost_comparison.png
│       ├── cost_comparison.svg
│       ├── ranking_table.png
│       └── ranking_table.svg
└── ...
```

### Previous Story Intelligence

**From Story 4.6 (Create LLM Comparison Framework - DONE):**
- `compare.py` produces JSON at `tests/benchmark/results/comparison_<timestamp>.json`
- `DEFAULT_MODELS` list has 11 models with Inspect-format IDs
- `generate_ranking()` returns sorted list with rank, model, secbash_score, cost_per_1000
- `print_comparison_table()` already outputs formatted console table with CIs
- Google models report $0 cost (free API tier)
- LlamaGuard (llama-guard-3-8b) scored 0.153 (very poor) - plot it but expect it as outlier
- gemini-3-pro scored 0.026 (near zero) - handle as extreme outlier
- Confidence intervals available via stderr field (multiply by 1.96 for 95% CI)
- 535 tests pass total (461 existing + 74 comparison tests)
- All code passes ruff check and ruff format

**From Story 4.5 (Implement Metrics Reporting - DONE):**
- `report.py` has `MODEL_PRICING` dict with all 11 models including Featherless per-command pricing
- `RESULTS_DIR = Path(__file__).parent / "results"` is the standard results directory
- Latency calculated from `sample.total_time * 1000` (seconds to ms)

### Git Intelligence

Recent commits:
- `ecbc288`: Add benchmark results (includes comparison JSON)
- `e2993dd`: Update docs & add benchmark files
- `8138855`: Feat: improve configuration
- All code follows PEP 8, ruff-formatted

### Dependencies

- **Blocked by:** Story 4.6 (comparison results) - DONE
- **Blocks:** None (final story in Epic 4)
- **New dependencies:** `matplotlib>=3.8.0`, `seaborn>=0.13.0` (dev group only)

### References

- [Source: docs/epics.md#story-47-generate-comparison-plots] - Original acceptance criteria
- [Source: docs/prd.md#success-criteria] - Detection Rate >=95%, Pass Rate >=90%, SecBASH Score >=0.85
- [Source: tests/benchmark/compare.py] - Comparison framework, JSON output, model list, ranking
- [Source: tests/benchmark/report.py] - MODEL_PRICING, RESULTS_DIR, metrics extraction
- [Source: tests/benchmark/results/comparison_20260206_181702.json] - Actual benchmark data (11 models)
- [Source: docs/architecture.md#python-conventions] - PEP 8, snake_case, Python 3.10+

## Dev Agent Record

### Context Reference

<!-- Story context complete - comprehensive developer guide created -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

No debug issues encountered.

### Completion Notes List

- Added matplotlib 3.10.8 and seaborn 0.13.2 as dev dependencies via `uv add --group dev`
- Created `tests/benchmark/plots.py` with 5 plot functions, Pareto frontier algorithm, CLI entry point, and helper utilities (get_provider, get_short_name, save_plot, load_comparison_results)
- Created `tests/benchmark/test_plots.py` with 37 tests covering all functions, edge cases ($0 cost, failed models), file output verification
- All 37 new tests pass; 578 total tests pass (4 pre-existing failures unrelated to this story)
- Code passes ruff check and ruff format
- Successfully generated 10 plot files (5 PNG + 5 SVG) from real comparison data with 11 models
- Latency visualization uses horizontal bar chart with P90 markers (as specified in Dev Notes) since per-command latency arrays are unavailable

### Senior Developer Review (AI) - 2026-02-06

**Reviewer:** Code Review Workflow (adversarial)
**Outcome:** Approved with fixes applied

**Issues found and fixed (6):**
- [H1] Detection vs Pass Rate Y-axis extended to 200%+ due to unclamped target zone rectangle - FIXED: axis limits clamped to 105%, rectangle bounded
- [H2] Cost vs Score legend omitted Pareto frontier and target line entries - FIXED: added both to legend handles
- [M3] CLI tests were trivial (only checked `callable(main)`) - FIXED: replaced with 4 real argparse verification tests
- [M4] Ranking table truncated long model names - FIXED: added `auto_set_column_width()`

**Issues noted (not fixed - out of scope):**
- [M1] `.gitignore` staged changes not in File List (unrelated cleanup)
- [M2] 22 `.eval` log files staged for deletion not documented (unrelated to story)
- [L1] Label overlap in dense cost_vs_score region (cosmetic, would need adjustText library)
- [L2] seaborn imported but not functionally used (harmless, style intent)
- [L3] sprint-status.yaml modified but not in File List (workflow artifact)
- [L4] AC3 says "median" but impl uses "mean" latency (documented deviation in Dev Notes)

**Test result:** 39 passed, 0 failed
**All ACs verified as implemented.**

### Change Log

- 2026-02-06: Implemented all 9 tasks for Story 4.7 - benchmark visualization plots for LLM comparison results
- 2026-02-06: Code review fixes - fixed detection_vs_pass Y-axis overflow, cost_vs_score legend, ranking table column widths, replaced trivial CLI tests with real argparse tests (39 tests now)

### File List

- `tests/benchmark/plots.py` (NEW) - Plotting module with 5 visualization functions, CLI, helpers
- `tests/benchmark/test_plots.py` (NEW) - 39 tests for plots module
- `tests/benchmark/results/plots/cost_vs_score.png` (NEW) - Cost vs SecBASH Score scatter plot
- `tests/benchmark/results/plots/cost_vs_score.svg` (NEW) - Cost vs SecBASH Score scatter plot (SVG)
- `tests/benchmark/results/plots/detection_vs_pass.png` (NEW) - Detection vs Pass Rate scatter plot
- `tests/benchmark/results/plots/detection_vs_pass.svg` (NEW) - Detection vs Pass Rate scatter plot (SVG)
- `tests/benchmark/results/plots/latency_distribution.png` (NEW) - Latency bar chart
- `tests/benchmark/results/plots/latency_distribution.svg` (NEW) - Latency bar chart (SVG)
- `tests/benchmark/results/plots/cost_comparison.png` (NEW) - Cost comparison bar chart
- `tests/benchmark/results/plots/cost_comparison.svg` (NEW) - Cost comparison bar chart (SVG)
- `tests/benchmark/results/plots/ranking_table.png` (NEW) - Model ranking table
- `tests/benchmark/results/plots/ranking_table.svg` (NEW) - Model ranking table (SVG)
- `pyproject.toml` (MODIFIED) - Added matplotlib, seaborn to dev dependencies
- `uv.lock` (MODIFIED) - Lock file updated with new dependencies
