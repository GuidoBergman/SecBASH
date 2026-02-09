# Story 5.7: Harden Evaluation Configuration

Status: done

## Story

As a **developer**,
I want **evaluations configured with retries and a fixed seed by default**,
so that **results are resilient to transient API failures and reproducible across runs**.

## Acceptance Criteria

1. **AC1: Task-level max_retries** - `GenerateConfig(max_retries=3)` is set in both `aegish_gtfobins()` and `aegish_harmless()` task definitions via the `Task(config=...)` parameter, so transient API failures (timeouts, rate limits) are retried up to 3 times automatically without the user needing to remember.

2. **AC2: Task-level seed** - `GenerateConfig(seed=42)` is set in both task definitions via the `Task(config=...)` parameter, so evaluations produce consistent results across identical runs (for providers that support seeded generation: OpenAI, Google, Mistral, Groq, HuggingFace, vLLM).

3. **AC3: compare.py passes seed through** - The `inspect_eval()` call in `compare.py` (line ~569) also includes `seed=42` via kwargs or GenerateConfig so comparison runs use the same seed.

4. **AC4: compare.py retries alignment** - The existing `retry_on_error=5` in `compare.py` is kept (it handles sample-level retries for the eval runner). The task-level `max_retries=3` handles API-level retries within the model provider.

5. **AC5: Reproducibility verification** - Running the same evaluation twice with the same model and dataset produces identical results (for models that support seeded generation).

6. **AC6: All existing tests pass** - No regressions. `uv run pytest tests/` passes.

## Tasks / Subtasks

- [x] Task 1: Add GenerateConfig to task definitions (AC: #1, #2)
  - [x] 1.1: Import `GenerateConfig` from `inspect_ai.model` in `aegish_eval.py`
  - [x] 1.2: Add `config=GenerateConfig(max_retries=3, seed=42)` to `aegish_gtfobins()` Task constructor
  - [x] 1.3: Add `config=GenerateConfig(max_retries=3, seed=42)` to `aegish_harmless()` Task constructor
- [x] Task 2: Update compare.py to pass seed (AC: #3, #4)
  - [x] 2.1: Verify `inspect_eval()` call supports seed kwarg or GenerateConfig passthrough
  - [x] 2.2: If seed not already passed, add it to the `inspect_eval()` call
  - [x] 2.3: Keep existing `retry_on_error=5` (sample-level) alongside task-level `max_retries=3` (API-level)
- [x] Task 3: Update task docstrings (AC: documentation)
  - [x] 3.1: Add note in `aegish_eval.py` docstrings about default retry/seed configuration
  - [x] 3.2: Add note in module docstring about reproducibility via seed=42
- [x] Task 4: Run tests and verify (AC: #5, #6)
  - [x] 4.1: Run `uv run pytest tests/` to confirm no regressions
  - [x] 4.2: Verify imports resolve correctly

## Dev Notes

### Critical Implementation Details

**Inspect AI `GenerateConfig` Usage:**
- Import: `from inspect_ai.model import GenerateConfig`
- Task-level config: `Task(dataset=..., solver=..., scorer=..., config=GenerateConfig(max_retries=3, seed=42))`
- The `config` parameter on `Task` sets the default generation configuration for that task's model
- `seed` only works with certain providers (OpenAI, Google, Mistral, Groq, HuggingFace, vLLM) - Anthropic does NOT support seed
- `max_retries` is the maximum number of times to retry a request (API-level retries within the model provider)

**Distinction: max_retries vs retry_on_error:**
- `max_retries` (in `GenerateConfig`): API-level retries within the model provider for transient failures (timeouts, rate limits). This is what we're adding.
- `retry_on_error` (in `inspect_eval()`): Sample-level retries in the eval runner. Already set to 5 in `compare.py`. This retries the entire sample evaluation if it errors out. KEEP THIS.
- Both work together: API retries happen first (3 attempts), and if all fail, the sample-level retry kicks in (up to 5 times).

**Current `compare.py` inspect_eval() call (line ~569-575):**
```python
logs = inspect_eval(
    tasks,
    model=models_to_eval,
    fail_on_error=0.5,
    retry_on_error=5,
    time_limit=time_limit,
)
```
This call does NOT currently pass `seed`. The task-level `GenerateConfig` will provide seed for individual evaluations, but for comparison runs via `inspect_eval()`, we should also ensure seed is set.

**Inspect eval() kwargs:** The `eval()` function accepts `**kwargs: Unpack[GenerateConfigArgs]` which means you can pass `seed=42` directly as a keyword argument to `inspect_eval()`.

### Files to Modify (ONLY THESE)

| File | Change |
|------|--------|
| `benchmark/tasks/aegish_eval.py` | Add `GenerateConfig` import, add `config=GenerateConfig(max_retries=3, seed=42)` to both Task constructors |
| `benchmark/compare.py` | Add `seed=42` to `inspect_eval()` call |

### What NOT to Change

- Do NOT modify `benchmark/scorers/security_scorer.py` - scoring logic is separate (Story 5.3)
- Do NOT modify `benchmark/report.py` or `benchmark/plots.py` - reporting is separate
- Do NOT change `retry_on_error=5` in compare.py - it serves a different purpose
- Do NOT change `fail_on_error=0.5` in compare.py
- Do NOT modify production code in `src/aegish/`
- Do NOT modify any test files

### Project Structure Notes

- Benchmark code lives in top-level `benchmark/` directory (moved in Story 5.2)
- Task definitions in `benchmark/tasks/aegish_eval.py` (2 tasks: `aegish_gtfobins`, `aegish_harmless`)
- Comparison framework in `benchmark/compare.py` (725 lines)
- Import convention: `from inspect_ai.model import GenerateConfig`
- Existing import block in aegish_eval.py imports from `inspect_ai`, `inspect_ai.dataset`, `inspect_ai.solver`

### Previous Story Intelligence

**From Story 5.1 (LlamaGuard removal):**
- Import changes in benchmark code are straightforward
- Test verification: run full suite with `uv run pytest tests/`
- Code quality: all code passes `ruff check` and `ruff format`

**From Story 5.2 (Benchmark restructure):**
- Benchmark code is now at `benchmark/` (not `tests/benchmark/`)
- Import convention: `from benchmark.X import Y`
- 512 tests passing as baseline

### Exact Code Changes

**`benchmark/tasks/aegish_eval.py` - Add import (after line 22):**
```python
from inspect_ai.model import GenerateConfig
```

**`benchmark/tasks/aegish_eval.py` - Update aegish_gtfobins Task (line 120-126):**
```python
    return Task(
        dataset=load_aegish_dataset(
            DATA_DIR / "gtfobins_commands.json", gtfobins_record_to_sample
        ),
        solver=solvers,
        scorer=security_classification_scorer(),
        config=GenerateConfig(max_retries=3, seed=42),
    )
```

**`benchmark/tasks/aegish_eval.py` - Update aegish_harmless Task (line 147-153):**
```python
    return Task(
        dataset=load_aegish_dataset(
            DATA_DIR / "harmless_commands.json", harmless_record_to_sample
        ),
        solver=solvers,
        scorer=security_classification_scorer(),
        config=GenerateConfig(max_retries=3, seed=42),
    )
```

**`benchmark/compare.py` - Update inspect_eval() call (line ~569):**
```python
logs = inspect_eval(
    tasks,
    model=models_to_eval,
    fail_on_error=0.5,
    retry_on_error=5,
    time_limit=time_limit,
    seed=42,
)
```

### References

- [Source: docs/analysis/benchmark-improvements.md#Section 1.4] - max_retries=3 rationale
- [Source: docs/analysis/benchmark-improvements.md#Section 1.5] - seed=42 rationale
- [Source: docs/epics.md#Story 5.7] - Story requirements (FR23, FR24)
- [Source: benchmark/tasks/aegish_eval.py] - Current task definitions (no config)
- [Source: benchmark/compare.py#L569-575] - Current inspect_eval() call
- [Inspect AI docs: GenerateConfig](https://inspect.aisi.org.uk/reference/inspect_ai.model.html) - API reference

## Dev Agent Record

### Context Reference

<!-- Story created by create-story workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- Added `GenerateConfig(max_retries=3, seed=42)` to both `aegish_gtfobins()` and `aegish_harmless()` Task constructors in `aegish_eval.py`
- Added `seed=42` kwarg to `inspect_eval()` call in `compare.py` for comparison run reproducibility
- Kept existing `retry_on_error=5` (sample-level) and `fail_on_error=0.5` unchanged in `compare.py`
- Updated module docstring and both task docstrings with retry/seed documentation
- Import verified: `from inspect_ai.model import GenerateConfig` resolves correctly
- 536 tests pass; 1 pre-existing failure from story 5-6 (unrelated to this story)

### Change Log

- 2026-02-08: Implemented evaluation hardening — added GenerateConfig with max_retries=3 and seed=42 to task definitions and compare.py

### File List

- `benchmark/tasks/aegish_eval.py` (modified) — Added GenerateConfig import and config param to both Task constructors, updated docstrings
- `benchmark/compare.py` (modified) — Added seed=42 to inspect_eval() call
- `docs/stories/sprint-status.yaml` (modified) — Status updated to in-progress → review
- `docs/stories/5-7-harden-evaluation-configuration.md` (modified) — Story file updated with completion details
