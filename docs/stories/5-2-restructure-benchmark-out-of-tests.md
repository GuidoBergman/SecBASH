# Story 5.2: Restructure Benchmark Out of Tests Directory

Status: ready-for-dev

## Story

As a **developer**,
I want **the benchmark evaluation infrastructure moved from `tests/benchmark/` to a top-level `benchmark/` directory**,
So that **the `tests/` directory contains only pytest tests, and the evaluation system has its own clear namespace**.

## Acceptance Criteria

### AC1: Directory Move Complete
**Given** the benchmark evaluation code currently lives in `tests/benchmark/`
**When** the restructure is complete
**Then** the following directory structure exists:
```
secbash/
├── src/secbash/          # Production code (unchanged)
├── tests/                # Only pytest tests
│   ├── __init__.py
│   ├── conftest.py
│   ├── utils.py
│   ├── test_validator.py
│   ├── test_llm_client.py
│   ├── test_executor.py
│   ├── test_config.py
│   ├── test_dangerous_commands.py
│   ├── test_defaults.py
│   ├── test_main.py
│   ├── test_shell.py
│   └── test_history.py
├── benchmark/            # Evaluation infrastructure (moved from tests/benchmark/)
│   ├── __init__.py
│   ├── tasks/
│   │   ├── __init__.py
│   │   └── secbash_eval.py
│   ├── scorers/
│   │   ├── __init__.py
│   │   └── security_scorer.py
│   ├── metrics/
│   │   ├── __init__.py
│   │   └── security_metrics.py
│   ├── data/
│   │   ├── .gitkeep
│   │   ├── gtfobins_commands.json
│   │   └── harmless_commands.json
│   ├── results/
│   │   ├── .gitkeep
│   │   ├── comparison_20260206_181702.json
│   │   └── plots/
│   │       └── (*.png, *.svg files)
│   ├── extract_gtfobins.py
│   ├── extract_harmless.py
│   ├── compare.py
│   ├── report.py
│   └── plots.py
```

### AC2: Test Files Relocated to tests/
**Given** the benchmark test files currently live in `tests/benchmark/test_*.py`
**When** the restructure is complete
**Then** the 6 benchmark test files are moved to `tests/`:
- `tests/benchmark/test_compare.py` → `tests/test_benchmark_compare.py`
- `tests/benchmark/test_extract_gtfobins.py` → `tests/test_benchmark_extract_gtfobins.py`
- `tests/benchmark/test_extract_harmless.py` → `tests/test_benchmark_extract_harmless.py`
- `tests/benchmark/test_plots.py` → `tests/test_benchmark_plots.py`
- `tests/benchmark/test_secbash_eval.py` → `tests/test_benchmark_secbash_eval.py`
- `tests/benchmark/test_security_scorer.py` → `tests/test_benchmark_security_scorer.py`
**And** test files are renamed with `test_benchmark_` prefix to distinguish from production tests
**And** all imports within these test files are updated from `tests.benchmark.` to `benchmark.`

### AC3: All Internal Imports Updated
**Given** the benchmark code is moved
**When** all internal imports and references are updated
**Then** every Python `from tests.benchmark.` import is changed to `from benchmark.`:
- `benchmark/scorers/security_scorer.py`: `from benchmark.metrics.security_metrics import ...`
- `benchmark/scorers/__init__.py`: `from benchmark.scorers.security_scorer import ...`
- `benchmark/tasks/secbash_eval.py`: `from benchmark.scorers import ...`
- `benchmark/tasks/__init__.py`: `from benchmark.tasks.secbash_eval import ...`
- `benchmark/metrics/__init__.py`: `from benchmark.metrics.security_metrics import ...`
- `benchmark/compare.py`: `from benchmark.report import ...` and `from benchmark.tasks.secbash_eval import ...`
- All 6 relocated test files: `from benchmark.X import ...`
**And** `python -m` docstrings/comments updated: `python -m tests.benchmark.X` → `python -m benchmark.X`
**And** `inspect eval` path references updated: `tests/benchmark/tasks/secbash_eval.py` → `benchmark/tasks/secbash_eval.py`

### AC4: CLI Entry Points Work
**Given** the move is complete and imports updated
**When** running benchmark tools
**Then** `uv run python -m benchmark.compare` works
**And** `uv run python -m benchmark.report --latest` works
**And** `uv run python -m benchmark.plots benchmark/results/comparison_20260206_181702.json` works
**And** `uv run python -m benchmark.extract_gtfobins` works
**And** `uv run python -m benchmark.extract_harmless` works
**And** `uv run inspect eval benchmark/tasks/secbash_eval.py@secbash_gtfobins --model openai/gpt-4o-mini` works (with valid API key)

### AC5: Pytest Tests Still Pass
**Given** the restructure is complete
**When** running the test suite
**Then** `uv run pytest tests/` passes with zero import errors
**And** all existing tests (production + benchmark) still pass
**And** no broken imports exist

### AC6: No Old Path References in Code
**Given** the move is complete
**When** searching for old path references in Python and config files
**Then** `grep -r "tests/benchmark" --include="*.py"` returns zero matches
**And** `grep -r "tests\.benchmark" --include="*.py"` returns zero matches
**And** `pyproject.toml` has no references to `tests/benchmark`

### AC7: Documentation Updated
**Given** the move is complete
**When** documentation is updated
**Then** `README.md` benchmark commands reference `benchmark/` paths
**And** `docs/architecture.md` project structure section is updated
**And** analysis docs that reference `tests/benchmark/` paths are updated

## Tasks / Subtasks

- [ ] Task 1: Move benchmark directory with git mv (AC: #1)
  - [ ] 1.1 `git mv tests/benchmark/ benchmark/` — move the entire directory, preserving git history
  - [ ] 1.2 Verify directory structure: `benchmark/`, `benchmark/tasks/`, `benchmark/scorers/`, `benchmark/metrics/`, `benchmark/data/`, `benchmark/results/`
  - [ ] 1.3 Remove `tests/benchmark/` if any residual files remain (e.g., `__pycache__/` — not tracked by git)

- [ ] Task 2: Move test files to tests/ with prefix (AC: #2)
  - [ ] 2.1 `git mv benchmark/test_compare.py tests/test_benchmark_compare.py`
  - [ ] 2.2 `git mv benchmark/test_extract_gtfobins.py tests/test_benchmark_extract_gtfobins.py`
  - [ ] 2.3 `git mv benchmark/test_extract_harmless.py tests/test_benchmark_extract_harmless.py`
  - [ ] 2.4 `git mv benchmark/test_plots.py tests/test_benchmark_plots.py`
  - [ ] 2.5 `git mv benchmark/test_secbash_eval.py tests/test_benchmark_secbash_eval.py`
  - [ ] 2.6 `git mv benchmark/test_security_scorer.py tests/test_benchmark_security_scorer.py`

- [ ] Task 3: Update all Python imports (AC: #3)
  - [ ] 3.1 `benchmark/__init__.py`: No import changes needed (just a docstring)
  - [ ] 3.2 `benchmark/metrics/__init__.py`: Change `from tests.benchmark.metrics.security_metrics` → `from benchmark.metrics.security_metrics`
  - [ ] 3.3 `benchmark/metrics/security_metrics.py`: No imports to change (only imports `inspect_ai`)
  - [ ] 3.4 `benchmark/scorers/__init__.py`: Change `from tests.benchmark.scorers.security_scorer` → `from benchmark.scorers.security_scorer`
  - [ ] 3.5 `benchmark/scorers/security_scorer.py`: Change `from tests.benchmark.metrics.security_metrics` → `from benchmark.metrics.security_metrics`
  - [ ] 3.6 `benchmark/tasks/__init__.py`: Change `from tests.benchmark.tasks.secbash_eval` → `from benchmark.tasks.secbash_eval`
  - [ ] 3.7 `benchmark/tasks/secbash_eval.py`: Change `from tests.benchmark.scorers` → `from benchmark.scorers`
  - [ ] 3.8 `benchmark/compare.py`: Change `from tests.benchmark.report` → `from benchmark.report`, change `from tests.benchmark.tasks.secbash_eval` → `from benchmark.tasks.secbash_eval`
  - [ ] 3.9 `benchmark/report.py`: No import changes (only imports `inspect_ai` and stdlib)
  - [ ] 3.10 `benchmark/plots.py`: No import changes (only imports `matplotlib`, `argparse`, stdlib)
  - [ ] 3.11 `benchmark/extract_gtfobins.py`: No import changes (only imports stdlib + `yaml`)
  - [ ] 3.12 `benchmark/extract_harmless.py`: No import changes (only imports stdlib + `datasets`)

- [ ] Task 4: Update docstrings and CLI path references (AC: #3)
  - [ ] 4.1 `benchmark/compare.py`: Update module docstring `python -m tests.benchmark.compare` → `python -m benchmark.compare` (4 occurrences in lines 12, 15, 18, 21)
  - [ ] 4.2 `benchmark/report.py`: Update module docstring `python -m tests.benchmark.report` → `python -m benchmark.report` (3 occurrences in lines 7, 10, 13)
  - [ ] 4.3 `benchmark/plots.py`: Update module docstring `tests.benchmark.compare` → `benchmark.compare`, update `tests/benchmark/results/` → `benchmark/results/` (lines 4, 8, 11), update default output_dir from `tests/benchmark/results/plots` → `benchmark/results/plots` (line 654, 659)
  - [ ] 4.4 `benchmark/tasks/secbash_eval.py`: Update docstring `tests/benchmark/tasks/secbash_eval.py` → `benchmark/tasks/secbash_eval.py` (3 occurrences in lines 8, 11, 14)

- [ ] Task 5: Update relocated test file imports (AC: #2, #3)
  - [ ] 5.1 `tests/test_benchmark_compare.py`: Replace all `from tests.benchmark.` → `from benchmark.` (lines 26, 39, 43, 334, 340)
  - [ ] 5.2 `tests/test_benchmark_extract_gtfobins.py`: Replace `from tests.benchmark.extract_gtfobins` → `from benchmark.extract_gtfobins` (line 8)
  - [ ] 5.3 `tests/test_benchmark_extract_harmless.py`: Replace all `from tests.benchmark.extract_harmless` → `from benchmark.extract_harmless` (lines 23, 30, 223, 241, 245, 259, 263, 386)
  - [ ] 5.4 `tests/test_benchmark_plots.py`: Replace all `from tests.benchmark.plots` → `from benchmark.plots` (lines 8, 449), update path assertion `tests/benchmark/results/plots` → `benchmark/results/plots` (lines 478, 486, 487)
  - [ ] 5.5 `tests/test_benchmark_secbash_eval.py`: Replace `from tests.benchmark.tasks.secbash_eval` → `from benchmark.tasks.secbash_eval` (line 9)
  - [ ] 5.6 `tests/test_benchmark_security_scorer.py`: Replace all `from tests.benchmark.` → `from benchmark.` (lines 20, 25, 31)

- [ ] Task 6: Update README.md (AC: #7)
  - [ ] 6.1 Update "Running a Single Evaluation" commands (lines 385, 388, 391): `tests/benchmark/tasks/secbash_eval.py` → `benchmark/tasks/secbash_eval.py`
  - [ ] 6.2 Update "Multi-Model Comparison" commands (lines 401, 404, 407): `tests.benchmark.compare` → `benchmark.compare`, `tests.benchmark.report` → `benchmark.report`

- [ ] Task 7: Update docs/architecture.md (AC: #7)
  - [ ] 7.1 Update project structure section to show `benchmark/` as top-level directory instead of under `tests/`

- [ ] Task 8: Verify and clean up (AC: #5, #6)
  - [ ] 8.1 Run `uv run pytest tests/` and verify all tests pass
  - [ ] 8.2 Run `grep -r "tests/benchmark" --include="*.py"` and confirm zero matches
  - [ ] 8.3 Run `grep -r "tests\.benchmark" --include="*.py"` and confirm zero matches
  - [ ] 8.4 Run `uv run ruff check` and `uv run ruff format --check` to verify code quality
  - [ ] 8.5 Clean up any residual `__pycache__/` directories in old location

## Dev Notes

### CRITICAL: Story 5.1 Must Be Completed First

Story 5.1 (Remove LlamaGuard from Codebase) MUST be done before this story. The reason: Story 5.1 removes LlamaGuard-specific code from `tests/benchmark/`. If you do this restructure first, you'll move dead LlamaGuard code to `benchmark/` and then have to clean it up there. Do 5.1 first to avoid moving code that will be deleted.

**Current status of 5.1:** `ready-for-dev` — verify it's `done` before starting this story.

### CRITICAL: LlamaGuard References Still Present in __init__.py Files

The `tests/benchmark/tasks/__init__.py` and `tests/benchmark/scorers/__init__.py` files still export LlamaGuard symbols:
- `tasks/__init__.py`: exports `_is_llamaguard_model`, `secbash_gtfobins_llamaguard`, `secbash_harmless_llamaguard`
- `scorers/__init__.py`: exports `extract_llamaguard_action`, `llamaguard_classification_scorer`

These should be gone after Story 5.1 completes. If they're still present when you start this story, Story 5.1 was not done — stop and complete 5.1 first.

### CRITICAL: Test File Naming Convention

The 6 test files in `tests/benchmark/` (`test_compare.py`, `test_extract_gtfobins.py`, etc.) must be moved to `tests/` root, NOT left in `benchmark/`. Benchmark test files are pytest tests and belong in `tests/`. Rename with `test_benchmark_` prefix to avoid name collisions and make it clear they test benchmark code:

| Old Path | New Path |
|----------|----------|
| `tests/benchmark/test_compare.py` | `tests/test_benchmark_compare.py` |
| `tests/benchmark/test_extract_gtfobins.py` | `tests/test_benchmark_extract_gtfobins.py` |
| `tests/benchmark/test_extract_harmless.py` | `tests/test_benchmark_extract_harmless.py` |
| `tests/benchmark/test_plots.py` | `tests/test_benchmark_plots.py` |
| `tests/benchmark/test_secbash_eval.py` | `tests/test_benchmark_secbash_eval.py` |
| `tests/benchmark/test_security_scorer.py` | `tests/test_benchmark_security_scorer.py` |

### CRITICAL: DATA_DIR Path Resolution

`benchmark/tasks/secbash_eval.py` uses relative path resolution:
```python
DATA_DIR = Path(__file__).parent.parent / "data"
```
This resolves to `benchmark/data/` after the move (since `__file__` is `benchmark/tasks/secbash_eval.py` → `parent.parent` = `benchmark/`). **No change needed** — the relative path still works.

### CRITICAL: plots.py Default Output Directory

`benchmark/plots.py` has a hardcoded default output directory at line 659:
```python
args.output_dir = Path("tests/benchmark/results/plots")
```
This MUST be updated to:
```python
args.output_dir = Path("benchmark/results/plots")
```
And the test file (`test_plots.py` → `test_benchmark_plots.py`) has assertions checking this path at lines 486-487. These MUST also be updated.

### CRITICAL: Complete Import Change Map

Every `from tests.benchmark.` import that must change to `from benchmark.`:

| File | Old Import | New Import |
|------|-----------|------------|
| `benchmark/metrics/__init__.py` | `from tests.benchmark.metrics.security_metrics` | `from benchmark.metrics.security_metrics` |
| `benchmark/scorers/__init__.py` | `from tests.benchmark.scorers.security_scorer` | `from benchmark.scorers.security_scorer` |
| `benchmark/scorers/security_scorer.py` | `from tests.benchmark.metrics.security_metrics` | `from benchmark.metrics.security_metrics` |
| `benchmark/tasks/__init__.py` | `from tests.benchmark.tasks.secbash_eval` | `from benchmark.tasks.secbash_eval` |
| `benchmark/tasks/secbash_eval.py` | `from tests.benchmark.scorers` | `from benchmark.scorers` |
| `benchmark/compare.py` | `from tests.benchmark.report` | `from benchmark.report` |
| `benchmark/compare.py` | `from tests.benchmark.tasks.secbash_eval` | `from benchmark.tasks.secbash_eval` |
| `tests/test_benchmark_compare.py` | `from tests.benchmark.compare` | `from benchmark.compare` |
| `tests/test_benchmark_compare.py` | `from tests.benchmark.scorers.security_scorer` | `from benchmark.scorers.security_scorer` |
| `tests/test_benchmark_compare.py` | `from tests.benchmark.tasks.secbash_eval` | `from benchmark.tasks.secbash_eval` |
| `tests/test_benchmark_extract_gtfobins.py` | `from tests.benchmark.extract_gtfobins` | `from benchmark.extract_gtfobins` |
| `tests/test_benchmark_extract_harmless.py` | `from tests.benchmark.extract_harmless` | `from benchmark.extract_harmless` |
| `tests/test_benchmark_plots.py` | `from tests.benchmark.plots` | `from benchmark.plots` |
| `tests/test_benchmark_secbash_eval.py` | `from tests.benchmark.tasks.secbash_eval` | `from benchmark.tasks.secbash_eval` |
| `tests/test_benchmark_security_scorer.py` | `from tests.benchmark.metrics.security_metrics` | `from benchmark.metrics.security_metrics` |
| `tests/test_benchmark_security_scorer.py` | `from tests.benchmark.report` | `from benchmark.report` |
| `tests/test_benchmark_security_scorer.py` | `from tests.benchmark.scorers.security_scorer` | `from benchmark.scorers.security_scorer` |

### CRITICAL: Docstring/Comment Path Updates

Module docstrings contain CLI usage examples with old paths. These are NOT functional code but are important for developer reference:

| File | Line(s) | Old Path | New Path |
|------|---------|----------|----------|
| `benchmark/compare.py` | 12,15,18,21 | `python -m tests.benchmark.compare` | `python -m benchmark.compare` |
| `benchmark/report.py` | 7,10,13 | `python -m tests.benchmark.report` | `python -m benchmark.report` |
| `benchmark/plots.py` | 4 | `tests.benchmark.compare` | `benchmark.compare` |
| `benchmark/plots.py` | 8 | `tests/benchmark/results/comparison_*.json` | `benchmark/results/comparison_*.json` |
| `benchmark/plots.py` | 654,659 | `tests/benchmark/results/plots/` | `benchmark/results/plots/` |
| `benchmark/tasks/secbash_eval.py` | 8,11,14 | `tests/benchmark/tasks/secbash_eval.py` | `benchmark/tasks/secbash_eval.py` |

### DO NOT Update These Documentation Files

The following docs reference `tests/benchmark/` as historical context in completed stories. Do NOT update these — they record what was true at the time of implementation:
- `docs/stories/4-2-extract-gtfobins-test-dataset.md`
- `docs/stories/4-3-create-harmless-command-baseline.md`
- `docs/stories/4-4-build-evaluation-harness-inspect.md`
- `docs/stories/4-5-implement-metrics-reporting-inspect.md`
- `docs/stories/4-6-create-llm-comparison-framework.md`
- `docs/stories/4-7-generate-comparison-plots.md`
- `docs/stories/5-1-remove-llamaguard-from-codebase.md`
- `docs/analysis/*.md` analysis files

These are historical records. Only update `README.md`, `docs/architecture.md`, and `docs/epics.md` (which has the story text saying to update imports).

### Git Intelligence

Recent commits:
- `ecbc288`: Add benchmark results
- `e2993dd`: Update docs & add benchmark files
- `8138855`: Feat: improve configuration
- All code follows PEP 8, ruff-formatted

### Execution Order

1. Verify Story 5.1 is DONE (LlamaGuard removed)
2. `git mv tests/benchmark/ benchmark/` (whole directory)
3. `git mv benchmark/test_*.py tests/test_benchmark_*.py` (6 test files)
4. Update all Python imports (use `replace_all` for `tests.benchmark` → `benchmark`)
5. Update docstrings and hardcoded paths
6. Update README.md and architecture.md
7. Run `uv run pytest tests/` to verify
8. Run `uv run ruff check` and `uv run ruff format --check`
9. Run `grep -r "tests.benchmark" --include="*.py"` and `grep -r "tests/benchmark" --include="*.py"` to confirm zero hits

### Project Structure Notes

- Production code: `src/secbash/` — NOT touched by this story
- Test code: `tests/` — gains 6 benchmark test files, loses `benchmark/` subdirectory
- Benchmark code: new `benchmark/` at repo root
- Python 3.10+ type hints, PEP 8, ruff-formatted
- No `pyproject.toml` changes needed (no tool config references `tests/benchmark`)

### Dependencies

- **Blocked by:** Story 5.1 (LlamaGuard removal must be done first)
- **Blocks:** Stories 5.3-5.7 (they reference `benchmark/` paths in their file lists)

### References

- [Source: docs/epics.md#story-52-restructure-benchmark-out-of-tests-directory] - Original acceptance criteria and file list
- [Source: docs/prd.md#FR35] - "Benchmark evaluation code lives in top-level `benchmark/` directory, not inside `tests/`"
- [Source: docs/analysis/benchmark-improvements.md] - Rationale for benchmark restructure
- [Source: tests/benchmark/__init__.py] - Root benchmark package
- [Source: tests/benchmark/tasks/secbash_eval.py] - DATA_DIR path resolution
- [Source: tests/benchmark/plots.py:654-659] - Hardcoded output directory path
- [Source: tests/benchmark/compare.py:12-21] - CLI docstring paths
- [Source: tests/benchmark/report.py:7-13] - CLI docstring paths
- [Source: README.md:381-408] - Benchmark CLI documentation
- [Source: docs/architecture.md:98-111] - Project structure section

## Dev Agent Record

### Context Reference

<!-- Story context complete - comprehensive developer guide created -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

### Change Log

### File List
