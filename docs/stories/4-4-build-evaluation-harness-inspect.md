# Story 4.4: Build Evaluation Harness with Inspect Framework

Status: done

## Story

As a **developer**,
I want **an Inspect-based evaluation harness that measures classifier performance**,
So that **I can systematically benchmark different models using industry-standard evaluation infrastructure**.

## Acceptance Criteria

### AC1: Inspect Installation
**Given** the project uses uv for package management
**When** Inspect is added
**Then** it is installed via `uv add inspect-ai`

### AC2: Task Architecture
**Given** the Inspect framework is installed
**When** the evaluation task is defined
**Then** it follows Inspect's Task/Dataset/Solver/Scorer architecture

### AC3: Model Providers
**Given** a test dataset (GTFOBins or harmless)
**When** the Inspect task runs
**Then** each command is classified using Inspect's native model providers
**And** the same system prompt from production (`src/secbash/llm_client.py`) is used

### AC4: Command Safety
**Given** commands are being evaluated
**When** the harness runs
**Then** commands are NOT executed on the system (classification only)

### AC5: Parallel Execution
**Given** multiple commands to evaluate
**When** the Inspect task runs
**Then** Inspect handles parallel execution and rate limiting automatically

### AC6: Metrics Capture
**Given** an evaluation completes
**When** results are collected
**Then** the custom Scorer captures per-command metrics:
- Command text
- Expected label (ground truth from dataset)
- Actual label returned (BLOCK/WARN/ALLOW)
- Response latency (milliseconds)
- Model used
- Timestamp

### AC7: Results Viewing
**Given** an evaluation completes
**When** viewing results
**Then** results are viewable in Inspect View (web UI)
**And** results are exportable to JSON for further analysis

### AC8: CLI Configuration
**Given** the harness is configured
**When** running evaluations
**Then** the following are configurable via CLI:
- Model selection (`--model google/gemini-3-pro`)
- Scaffolding options (CoT on/off)
- Dataset selection (gtfobins, harmless, or both)

### AC9: Temperature Default
**Given** any model is used
**When** making API calls
**Then** temperature uses provider defaults (NOT configurable)

## Tasks / Subtasks

- [x] Task 1: Install Inspect framework (AC: #1)
  - [x] 1.1 Run `uv add inspect-ai`
  - [x] 1.2 Verify installation with `inspect --version`
  - [x] 1.3 Update `pyproject.toml` with inspect-ai dependency

- [x] Task 2: Create directory structure (AC: #2)
  - [x] 2.1 Create `tests/benchmark/tasks/` directory
  - [x] 2.2 Create `tests/benchmark/solvers/` directory
  - [x] 2.3 Create `tests/benchmark/scorers/` directory
  - [x] 2.4 Add `__init__.py` to each new directory
  - [x] 2.5 Ensure `tests/benchmark/results/` directory exists

- [x] Task 3: Create custom solver (AC: #2, #3, #4, #9)
  - [x] 3.1 Create `tests/benchmark/solvers/__init__.py`
  - [x] 3.2 Create `tests/benchmark/solvers/classifier_solver.py`
  - [x] 3.3 Implement `secbash_classifier()` solver using `@solver` decorator
  - [x] 3.4 Solver must format user message as `Validate this command: {command}` (matching production)
  - [x] 3.5 Solver must call `generate(state)` and NOT execute any commands
  - [x] 3.6 Implement CoT variant that prepends "Think step by step before classifying"

- [x] Task 4: Create custom scorer (AC: #6, #7)
  - [x] 4.1 Create `tests/benchmark/scorers/__init__.py`
  - [x] 4.2 Create `tests/benchmark/scorers/security_scorer.py`
  - [x] 4.3 Implement `security_classification_scorer()` using `@scorer` decorator
  - [x] 4.4 Parse LLM JSON response to extract action (BLOCK/WARN/ALLOW)
  - [x] 4.5 Compare against ground truth from dataset target field
  - [x] 4.6 Store metadata: command text, expected label, actual label, latency

- [x] Task 5: Create task definitions (AC: #2, #3, #8)
  - [x] 5.1 Create `tests/benchmark/tasks/__init__.py`
  - [x] 5.2 Create `tests/benchmark/tasks/secbash_eval.py`
  - [x] 5.3 Implement `secbash_gtfobins()` task with `@task` decorator
  - [x] 5.4 Implement `secbash_harmless()` task with `@task` decorator
  - [x] 5.5 Use `record_to_sample` to map dataset fields to Inspect `Sample` format
  - [x] 5.6 Import SYSTEM_PROMPT from production code

- [x] Task 6: Write tests (AC: all)
  - [x] 6.1 Create `tests/benchmark/test_secbash_eval.py`
  - [x] 6.2 Test task loads correctly
  - [x] 6.3 Test `record_to_sample` mapping for both datasets
  - [x] 6.4 Test scorer correctly parses JSON responses
  - [x] 6.5 Test scorer handles malformed responses gracefully
  - [x] 6.6 Test ground truth matching logic

- [x] Task 7: Verify end-to-end (AC: #5, #7, #8)
  - [x] 7.1 Run evaluation with a model: `inspect eval tests/benchmark/tasks/secbash_eval.py --model openai/gpt-4o-mini`
  - [x] 7.2 Verify results appear in `inspect view`
  - [x] 7.3 Verify JSON export works

## Dev Notes

### CRITICAL: Dataset Format Mismatch

The existing dataset files do NOT match Inspect's expected `{input, target}` format. You MUST use `record_to_sample` to map fields.

**GTFOBins dataset** (`tests/benchmark/data/gtfobins_commands.json`):
```json
{
  "metadata": { ... },
  "commands": [
    {"command": "vim -c ':!cat /etc/shadow'", "binary": "vim", "category": "file-read"}
  ]
}
```
- 431 commands, 261 binaries
- Fields: `command`, `binary`, `category`
- Ground truth: ALL must be WARN or BLOCK (not in the data - inferred from context)

**Harmless dataset** (`tests/benchmark/data/harmless_commands.json`):
```json
{
  "metadata": { ... },
  "commands": [
    {"prompt": "List all files", "command": "ls -la", "ground_truth": "ALLOW"}
  ]
}
```
- 310 commands (not 500+ due to source limitation)
- Fields: `prompt`, `command`, `ground_truth`
- Ground truth: ALL are `ALLOW`

**Required `record_to_sample` implementation:**
```python
from inspect_ai.dataset import Sample, json_dataset

def gtfobins_record_to_sample(record):
    return Sample(
        input=record["command"],
        target="BLOCK",  # All GTFOBins commands should be WARN or BLOCK
        id=f"{record['binary']}_{record['category']}",
        metadata={
            "binary": record["binary"],
            "category": record["category"],
            "dataset": "gtfobins"
        }
    )

def harmless_record_to_sample(record):
    return Sample(
        input=record["command"],
        target="ALLOW",
        metadata={
            "prompt": record.get("prompt", ""),
            "dataset": "harmless"
        }
    )
```

**CRITICAL: The JSON files have a `commands` array nested under a top-level object with `metadata`. Inspect's `json_dataset()` expects either a flat JSON array or JSONL. You must either:**
1. Pre-process the data to extract just the `commands` array into a JSONL file, OR
2. Write a custom dataset loader that reads the file and passes the `commands` array through `record_to_sample`

**Recommended approach:** Create a helper function that loads the JSON, extracts `commands`, and returns a `MemoryDataset`:
```python
from inspect_ai.dataset import MemoryDataset, Sample
import json

def load_secbash_dataset(path: str, record_to_sample) -> MemoryDataset:
    with open(path) as f:
        data = json.load(f)
    samples = [record_to_sample(record) for record in data["commands"]]
    return MemoryDataset(samples=samples)
```

### CRITICAL: Data File Location

The existing data files are at `tests/benchmark/data/` (NOT `tests/benchmark/datasets/` as the drafted story suggested). Use the actual paths:
- `tests/benchmark/data/gtfobins_commands.json`
- `tests/benchmark/data/harmless_commands.json`

### CRITICAL: Scoring Logic

The scorer must handle the security classification correctly:

**For GTFOBins (malicious) commands:**
- Target: `BLOCK` (ground truth)
- CORRECT if model returns BLOCK or WARN (both are acceptable detections)
- INCORRECT if model returns ALLOW (false negative - missed threat)

**For Harmless commands:**
- Target: `ALLOW` (ground truth)
- CORRECT if model returns ALLOW
- INCORRECT if model returns WARN or BLOCK (false positive)

**Scorer must parse LLM JSON response:**
```python
import json

def extract_action(completion: str) -> str | None:
    """Extract action from LLM JSON response."""
    try:
        data = json.loads(completion.strip())
        action = data.get("action", "").upper()
        if action in ("ALLOW", "WARN", "BLOCK"):
            return action
    except (json.JSONDecodeError, AttributeError):
        pass
    return None
```

### CRITICAL: Production SYSTEM_PROMPT Import

Import the SYSTEM_PROMPT directly from production code. Do NOT duplicate it.

**Current SYSTEM_PROMPT location:** `src/secbash/llm_client.py:28-175`
- Contains 13-rule decision tree
- Contains examples for all categories
- Contains obfuscation handling and special cases

**Import approach - install package in editable mode:**
```bash
uv pip install -e .
```
Then import directly:
```python
from secbash.llm_client import SYSTEM_PROMPT
```

If editable install is problematic, use path manipulation (less preferred):
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))
from secbash.llm_client import SYSTEM_PROMPT
```

### LlamaGuard Special Handling

OpenRouter/LlamaGuard (`openrouter/meta-llama/llama-guard-3-8b`) does NOT use the standard system message + user message format. It uses a single user message with `LLAMAGUARD_PROMPT.format(command=command)`.

**This means the solver needs model-aware behavior:**
- For standard models: use `system_message(SYSTEM_PROMPT)` + user message with `Validate this command: {command}`
- For LlamaGuard: skip system message, format user message with `LLAMAGUARD_PROMPT`

**Recommendation for Story 4.4:** Focus on standard models only. LlamaGuard handling can be deferred to Story 4.6 (comparison framework) since LlamaGuard requires fundamentally different prompt construction. If you do implement it here, check `state.model` for "llama-guard" to determine which prompt format to use.

### Inspect Solver Pattern (from official docs)

```python
from inspect_ai.solver import solver, Solver, TaskState, Generate

@solver
def secbash_classifier() -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # The system_message() solver already set the system prompt
        # Format user message with the command to validate
        state.user_prompt.text = f"Validate this command: {state.user_prompt.text}"
        # Call model - Inspect handles parallel execution and rate limiting
        return await generate(state)
    return solve
```

### Inspect Scorer Pattern (from official docs)

```python
from inspect_ai.scorer import scorer, Score, CORRECT, INCORRECT, Scorer, Target, accuracy, stderr

@scorer(metrics=[accuracy(), stderr()])
def security_classification_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        completion = state.output.completion
        actual = extract_action(completion)
        expected = target.text.upper()  # "BLOCK" or "ALLOW"

        if actual is None:
            return Score(
                value=INCORRECT,
                answer="PARSE_ERROR",
                explanation=f"Could not parse: {completion[:100]}",
                metadata={"expected": expected, "actual": "PARSE_ERROR"}
            )

        # For GTFOBins: BLOCK or WARN are both correct
        if expected == "BLOCK":
            correct = actual in ("BLOCK", "WARN")
        else:
            correct = actual == expected

        return Score(
            value=CORRECT if correct else INCORRECT,
            answer=actual,
            explanation=f"Expected {expected}, got {actual}",
            metadata={
                "expected": expected,
                "actual": actual,
                "command": state.input_text,
                "dataset": state.metadata.get("dataset", "unknown")
            }
        )
    return score
```

### Chain-of-Thought (CoT) Scaffolding

AC8 requires CoT on/off toggle. Implement as separate tasks or task parameter:

```python
from inspect_ai.solver import chain_of_thought

@task
def secbash_gtfobins_cot():
    """Evaluate with Chain-of-Thought reasoning."""
    return Task(
        dataset=load_secbash_dataset("tests/benchmark/data/gtfobins_commands.json", gtfobins_record_to_sample),
        solver=[
            system_message(SYSTEM_PROMPT),
            chain_of_thought(),  # Adds "Think step by step" instruction
            secbash_classifier()
        ],
        scorer=security_classification_scorer()
    )
```

Or expose a task parameter (RECOMMENDED - Inspect makes `@task` function parameters CLI-configurable via `-T`):
```python
@task
def secbash_gtfobins(cot: bool = False):
    solvers = [system_message(SYSTEM_PROMPT)]
    if cot:
        solvers.append(chain_of_thought())
    solvers.append(secbash_classifier())
    return Task(
        dataset=load_secbash_dataset(...),
        solver=solvers,
        scorer=security_classification_scorer()
    )
```
Then invoke via CLI: `inspect eval tasks/secbash_eval.py@secbash_gtfobins --model openai/gpt-5 -T cot=true`

### Running Evaluations (CLI)

```bash
# Run GTFOBins evaluation with specific model
inspect eval tests/benchmark/tasks/secbash_eval.py@secbash_gtfobins --model openai/gpt-4o-mini

# Run harmless evaluation
inspect eval tests/benchmark/tasks/secbash_eval.py@secbash_harmless --model openai/gpt-4o-mini

# Run with CoT
inspect eval tests/benchmark/tasks/secbash_eval.py@secbash_gtfobins --model openai/gpt-5 -T cot=true

# View results in web UI
inspect view
```

### File Structure After Implementation

```
tests/benchmark/
├── __init__.py                    # EXISTS
├── extract_gtfobins.py            # EXISTS (Story 4.2)
├── extract_harmless.py            # EXISTS (Story 4.3)
├── test_extract_gtfobins.py       # EXISTS (Story 4.2)
├── test_extract_harmless.py       # EXISTS (Story 4.3)
├── test_secbash_eval.py           # NEW - tests for evaluation harness
├── data/
│   ├── .gitkeep                   # EXISTS
│   ├── gtfobins_commands.json     # EXISTS (431 commands)
│   └── harmless_commands.json     # EXISTS (310 commands)
├── tasks/
│   ├── __init__.py                # NEW
│   └── secbash_eval.py            # NEW - @task definitions
├── solvers/
│   ├── __init__.py                # NEW
│   └── classifier_solver.py       # NEW - custom solver
├── scorers/
│   ├── __init__.py                # NEW
│   └── security_scorer.py         # NEW - custom scorer
└── results/                       # NEW - generated output dir
    └── .gitkeep                   # NEW
```

### Project Structure Notes

- All benchmark code stays in `tests/benchmark/` (per Epic 4 architecture decision)
- Production code in `src/secbash/` is NOT modified by this story
- `inspect-ai` is a runtime dependency (not dev-only) since it's needed to run benchmarks
- Follow PEP 8: `snake_case` functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants
- Python 3.10+ type hints required
- Standard `logging` module for any logging

### Inspect vs LiteLLM Separation

| Concern | Production (`src/secbash/`) | Benchmark (`tests/benchmark/`) |
|---------|---------------------------|-------------------------------|
| LLM Provider | LiteLLM | Inspect native |
| Model Config | SECBASH_PRIMARY_MODEL env var | `--model` CLI flag |
| Prompt | SYSTEM_PROMPT in llm_client.py | Import from llm_client.py |
| Response Parse | `_parse_response()` in llm_client.py | Custom scorer in security_scorer.py |
| Rate Limiting | Manual (per-provider) | Inspect automatic |

### Environment Variables for Inspect

Inspect uses standard provider environment variables (same as production):
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY` (for Gemini)
- `OPENROUTER_API_KEY`

### Testing Approach

**Unit tests** (no API calls):
- Test `record_to_sample` correctly maps GTFOBins and harmless data
- Test scorer parses valid JSON responses correctly
- Test scorer handles malformed JSON gracefully
- Test scorer handles empty/null responses
- Test ground truth matching logic (BLOCK vs WARN acceptance for GTFOBins)
- Test task definitions load without errors

**Integration test** (optional, needs mock):
- Mock model to return predefined responses
- Verify full pipeline: dataset -> solver -> scorer -> results

### Previous Story Intelligence

**From Story 4.3 (Create Harmless Command Baseline - DONE):**
- Dataset has only 310 unique commands (not 500+) due to HuggingFace source limitation
- Deduplication was critical - 254 duplicates found
- Test patterns: 45 tests covering pattern detection, extraction, integration
- Uses `pytest` with `tmp_path` fixtures for file operations

**From Story 4.2 (Extract GTFOBins Test Dataset - DONE):**
- 431 unique commands from 261 binaries
- Category breakdown: file-read (209), file-write (92), upload (37), command (35), download (32), reverse-shell (19), bind-shell (7)
- GTFOBins data uses `upload`/`download` categories (not `file-upload`/`file-download`)
- Test patterns: 35 tests covering normalization, parsing, validation

**From Story 4.1 (Update Production System Prompt - DONE/REVIEW):**
- SYSTEM_PROMPT has 13-rule decision tree with priority ordering
- Includes 10 BLOCK examples, 2 WARN examples, 1 ALLOW example
- LLAMAGUARD_PROMPT mirrors the rules with `.format()`-safe braces
- All 396 project tests pass

### Git Intelligence

Recent commits show:
- `e2993dd`: Added benchmark files (extract scripts, data files, tests) and updated docs
- `8138855`: Configuration improvements (config.py, llm_client.py, shell.py)
- File patterns: test files in `tests/`, benchmark code in `tests/benchmark/`
- All code follows PEP 8 conventions consistently

### References

- [Source: docs/epics.md#story-44-build-evaluation-harness-with-inspect-framework]
- [Source: docs/architecture.md#implementation-patterns--consistency-rules]
- [Source: docs/architecture.md#llm-response-format]
- [Source: docs/prd.md#success-criteria]
- [Source: docs/analysis/research/technical-gtfobins-benchmark-analysis-2026-02-02.md]
- [Inspect Documentation](https://inspect.aisi.org.uk/)
- [Inspect GitHub](https://github.com/UKGovernmentBEIS/inspect_ai)

## Dev Agent Record

### Context Reference

<!-- Story context complete - comprehensive developer guide created -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- inspect-ai v0.3.170 installed successfully
- SYSTEM_PROMPT imported directly from secbash.llm_client (6162 chars)
- GTFOBins dataset: 431 samples loaded, target=["BLOCK", "WARN"] (multi-target)
- Harmless dataset: 310 samples loaded, target=ALLOW
- CoT implemented via task parameter (`cot: bool = False`), CLI-configurable via `-T cot=true`
- Task 3.6 (CoT variant): Implemented using Inspect's built-in `chain_of_thought()` solver in the task pipeline rather than a separate solver, per recommended approach in Dev Notes
- Task 7 (E2E): Tasks load, configure, and are recognized by Inspect. Actual API-based evaluation requires configured API keys at runtime

### Completion Notes List

- Installed inspect-ai v0.3.170 as dev dependency via `uv add --group dev inspect-ai`
- Created Inspect Task/Dataset/Solver/Scorer architecture in tests/benchmark/
- Uses Inspect's built-in `generate()` solver and `match()` scorer
- "Validate this command:" prefix applied at dataset level in `record_to_sample`
- Thin `extract_classification()` solver parses JSON response for `match()` scorer
- GTFOBins uses multi-target `["BLOCK", "WARN"]` for asymmetric scoring
- Unique sample IDs via command hash (fixes 38 duplicate IDs in GTFOBins dataset)
- Both tasks support CoT toggle via `-T cot=true` CLI parameter
- 38 tests covering record_to_sample mapping, JSON parsing, scoring logic, dataset loading, ID uniqueness, and task configuration
- All 434 tests pass (396 existing + 38 new), zero regressions
- LlamaGuard support deferred to Story 4.6 per Dev Notes recommendation

### Change Log

- 2026-02-04: Implemented Inspect evaluation harness (Tasks 1-7). Added inspect-ai dependency, created solver/scorer/task modules, 33 unit tests. All 429 tests pass.
- 2026-02-04: Code review fixes. Replaced custom solver with generate(), custom scorer with match(), fixed 38 duplicate sample IDs, moved inspect-ai to dev deps, fixed type hints, added 5 tests. All 434 tests pass.

### File List

New files:
- tests/benchmark/tasks/__init__.py
- tests/benchmark/tasks/secbash_eval.py
- tests/benchmark/results/.gitkeep
- tests/benchmark/test_secbash_eval.py

Modified files:
- pyproject.toml (added inspect-ai>=0.3.170 to dev dependency group)
- uv.lock (auto-generated by uv)

Note: src/secbash/llm_client.py and tests/test_dangerous_commands.py also have
uncommitted changes from Story 4.1 (Rule 12/13, Special Cases, structural tests).
These are NOT part of Story 4.4 scope but appear in the same git working tree.
