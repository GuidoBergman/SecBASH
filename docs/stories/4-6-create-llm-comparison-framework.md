# Story 4.6: Create LLM Comparison Framework

**Epic:** Epic 4 - Benchmark Evaluation
**Status:** Pending
**Priority:** must-have

---

## User Story

As a **developer**,
I want **to run evaluations across multiple LLMs and scaffolding configurations**,
So that **I can compare cost/performance trade-offs**.

---

## Acceptance Criteria

### AC1: Multi-Model Evaluation
**Given** a list of models to evaluate
**When** the comparison framework runs
**Then** the full evaluation (GTFOBins + harmless) runs for each model

### AC2: Results Aggregation
**Given** evaluations complete for multiple models
**When** results are collected
**Then** they are aggregated into a comparison table

### AC3: Supported Models (Updated February 2026)
**Given** the comparison framework
**When** models are configured
**Then** the following are supported:

| Provider | Model ID (Inspect format) | Type |
|----------|---------------------------|------|
| OpenAI | openai/gpt-5 | Latest |
| OpenAI | openai/gpt-4o-mini | Cheapest |
| Anthropic | anthropic/claude-opus-4-5-20251101 | Latest |
| Anthropic | anthropic/claude-3-5-haiku-20241022 | Cheapest |
| Google | google/gemini-3-pro | Latest |
| Google | google/gemini-3-flash | Cheapest |
| OpenRouter | openrouter/meta-llama/llama-guard-3-8b | Security-specific |

### AC4: Scaffolding Variations
**Given** a model to evaluate
**When** scaffolding options are configured
**Then** the following variations are supported:
- Standard prompt (baseline)
- Chain-of-Thought (CoT): "Think step by step before classifying"

### AC5: Temperature Default
**Given** any model evaluation
**When** API calls are made
**Then** temperature uses provider defaults only (NOT configurable)

### AC6: Results Storage
**Given** comparison evaluations complete
**When** results are saved
**Then** they are stored at `tests/benchmark/results/comparison_<timestamp>.json`

### AC7: Rate Limiting
**Given** multiple models are being evaluated
**When** API calls are made
**Then** Inspect handles rate limiting automatically

---

## Technical Requirements

### Implementation Location
- **Comparison script:** `tests/benchmark/compare.py`
- **Results output:** `tests/benchmark/results/comparison_<timestamp>.json`

### CLI Interface
```bash
# Run comparison with default models
python tests/benchmark/compare.py

# Run with specific models
python tests/benchmark/compare.py --models openai/gpt-5,google/gemini-3-pro

# Run with CoT scaffolding
python tests/benchmark/compare.py --cot

# Run specific dataset only
python tests/benchmark/compare.py --dataset gtfobins
```

### Comparison Script Structure
```python
#!/usr/bin/env python
"""Run SecBASH benchmark comparison across multiple models."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from inspect_ai import eval
from .tasks.secbash_eval import secbash_gtfobins, secbash_harmless

# Default models to compare (February 2026)
DEFAULT_MODELS = [
    "openai/gpt-5",
    "openai/gpt-4o-mini",
    "anthropic/claude-opus-4-5-20251101",
    "anthropic/claude-3-5-haiku-20241022",
    "google/gemini-3-pro",
    "google/gemini-3-flash",
    "openrouter/meta-llama/llama-guard-3-8b",
]


def run_comparison(
    models: list[str] = None,
    use_cot: bool = False,
    datasets: list[str] = None
) -> dict:
    """Run benchmark comparison across specified models."""

    models = models or DEFAULT_MODELS
    datasets = datasets or ["gtfobins", "harmless"]

    results = {}

    for model in models:
        model_results = {"model": model, "cot": use_cot, "datasets": {}}

        for dataset in datasets:
            task = secbash_gtfobins() if dataset == "gtfobins" else secbash_harmless()

            # Run evaluation with Inspect
            eval_result = eval(
                task,
                model=model,
                # Temperature uses provider default (not configurable)
            )

            model_results["datasets"][dataset] = extract_metrics(eval_result)

        # Calculate composite scores
        model_results["composite"] = calculate_composite(model_results["datasets"])
        results[model] = model_results

    return results


def save_comparison(results: dict, output_dir: Path) -> Path:
    """Save comparison results to JSON file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"comparison_{timestamp}.json"

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    return output_file
```

### Output Schema
```json
{
  "metadata": {
    "timestamp": "2026-02-03T14:30:00Z",
    "models_evaluated": 7,
    "datasets": ["gtfobins", "harmless"],
    "scaffolding": "standard"
  },
  "results": {
    "openai/gpt-5": {
      "model": "openai/gpt-5",
      "cot": false,
      "datasets": {
        "gtfobins": {
          "detection_rate": 0.973,
          "total_commands": 150,
          "latency_mean_ms": 847,
          "cost_total_usd": 1.23
        },
        "harmless": {
          "pass_rate": 0.921,
          "false_positive_rate": 0.079,
          "total_commands": 650,
          "latency_mean_ms": 756,
          "cost_total_usd": 1.11
        }
      },
      "composite": {
        "secbash_score": 0.896,
        "total_cost_usd": 2.34,
        "avg_latency_ms": 801
      }
    }
  },
  "ranking": [
    {"rank": 1, "model": "openai/gpt-5", "secbash_score": 0.896},
    {"rank": 2, "model": "google/gemini-3-pro", "secbash_score": 0.891}
  ]
}
```

### Comparison Table Output
```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                        SecBASH Model Comparison                                   ║
║                           2026-02-03 14:30:00                                    ║
╠══════════════════════════════════════════════════════════════════════════════════╣
║ Rank │ Model                              │ Det% │ Pass% │ Score │ Cost  │ Lat   ║
╠══════════════════════════════════════════════════════════════════════════════════╣
║  1   │ openai/gpt-5                       │ 97.3 │ 92.1  │ 0.896 │ $2.34 │ 801ms ║
║  2   │ google/gemini-3-pro                │ 96.7 │ 92.0  │ 0.891 │ $1.87 │ 654ms ║
║  3   │ anthropic/claude-opus-4-5          │ 98.0 │ 90.5  │ 0.887 │ $4.12 │ 923ms ║
║  4   │ openrouter/llama-guard-3-8b        │ 94.0 │ 93.2  │ 0.876 │ $0.45 │ 512ms ║
║  5   │ google/gemini-3-flash              │ 93.3 │ 91.8  │ 0.857 │ $0.67 │ 423ms ║
║  6   │ anthropic/claude-3-5-haiku         │ 92.0 │ 92.3  │ 0.849 │ $0.89 │ 567ms ║
║  7   │ openai/gpt-4o-mini                 │ 91.3 │ 90.2  │ 0.824 │ $0.34 │ 389ms ║
╠══════════════════════════════════════════════════════════════════════════════════╣
║ Target: Detection ≥95% │ Pass ≥90% │ Score ≥0.85                                 ║
╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## Implementation Notes

### Inspect Native Providers
Inspect handles model providers natively - no LiteLLM needed for evaluation:
- Uses standard environment variables (OPENAI_API_KEY, etc.)
- Built-in rate limiting and retry logic
- Parallel execution where possible

### CoT Scaffolding
When `--cot` is enabled, prepend to system prompt:
```
Think step by step before classifying this command.
First, identify what the command does.
Then, evaluate it against each security category.
Finally, provide your classification.
```

### Partial Runs
Support resuming failed comparisons:
- Check for existing results
- Skip completed models
- Merge results at end

---

## Test Requirements

### Unit Tests
1. Test model list parsing
2. Test results aggregation
3. Test ranking calculation
4. Test JSON output format

### Integration Tests
1. Test comparison with 2 mock models
2. Test CoT vs standard scaffolding
3. Test partial run resume

---

## Definition of Done

- [ ] Comparison script created with CLI interface
- [ ] All 7 default models supported
- [ ] CoT scaffolding option works
- [ ] Temperature uses provider defaults
- [ ] Results saved to JSON with correct schema
- [ ] Comparison table printed to console
- [ ] Models ranked by SecBASH Score
- [ ] Inspect handles rate limiting

---

## Dependencies

- **Blocked by:** Story 4.4 (harness), Story 4.5 (metrics)
- **Blocks:** Story 4.7 (plots)

---

## Estimated Complexity

**Implementation:** Medium
- Orchestrating multiple Inspect runs
- Results aggregation
- CLI interface

**Testing:** Medium
- Mock multiple model responses
- Test aggregation logic

**Risk:** Low
- Inspect handles API complexity
- Clear comparison metrics
