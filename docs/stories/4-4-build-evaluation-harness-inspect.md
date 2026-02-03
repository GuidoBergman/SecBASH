# Story 4.4: Build Evaluation Harness with Inspect Framework

**Epic:** Epic 4 - Benchmark Evaluation
**Status:** Pending
**Priority:** must-have

---

## User Story

As a **developer**,
I want **an Inspect-based evaluation harness that measures classifier performance**,
So that **I can systematically benchmark different models using industry-standard evaluation infrastructure**.

---

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

---

## Technical Requirements

### Installation
```bash
uv add inspect-ai
```

### Implementation Location
- **Task file:** `tests/benchmark/tasks/secbash_eval.py`
- **Custom solver:** `tests/benchmark/solvers/classifier_solver.py`
- **Custom scorer:** `tests/benchmark/scorers/security_scorer.py`

### Directory Structure
```
tests/benchmark/
├── tasks/
│   └── secbash_eval.py       # @task definitions
├── solvers/
│   └── classifier_solver.py  # Custom solver wrapping prompt
├── scorers/
│   └── security_scorer.py    # Custom scorer for metrics
├── datasets/
│   ├── gtfobins_commands.json
│   └── harmless_commands.json
└── results/
    └── (generated output files)
```

### Task Structure
```python
from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.solver import generate, system_message

from .solvers.classifier_solver import secbash_classifier
from .scorers.security_scorer import security_classification_scorer

# Import production prompt
import sys
sys.path.insert(0, 'src')
from secbash.llm_client import SYSTEM_PROMPT

@task
def secbash_gtfobins():
    """Evaluate classifier on malicious GTFOBins commands."""
    return Task(
        dataset=json_dataset("tests/benchmark/datasets/gtfobins_commands.json"),
        solver=[
            system_message(SYSTEM_PROMPT),
            secbash_classifier()
        ],
        scorer=security_classification_scorer()
    )

@task
def secbash_harmless():
    """Evaluate classifier on harmless baseline commands."""
    return Task(
        dataset=json_dataset("tests/benchmark/datasets/harmless_commands.json"),
        solver=[
            system_message(SYSTEM_PROMPT),
            secbash_classifier()
        ],
        scorer=security_classification_scorer()
    )
```

### Running Evaluations
```bash
# Run with specific model
inspect eval tests/benchmark/tasks/secbash_eval.py --model openai/gpt-5

# Run with different model
inspect eval tests/benchmark/tasks/secbash_eval.py --model google/gemini-3-pro

# View results in web UI
inspect view
```

---

## Implementation Notes

### Inspect vs LiteLLM
- **Production code** (`src/secbash/llm_client.py`): Continues using LiteLLM
- **Evaluation harness** (`tests/benchmark/`): Uses Inspect's native providers
- This separation is intentional - evaluation should be independent

### Prompt Consistency
Copy the exact SYSTEM_PROMPT from production to ensure evaluation matches real-world behavior. Import it directly rather than duplicating.

### Supported Models (Inspect native)
- OpenAI: `openai/gpt-5`, `openai/gpt-4o-mini`
- Anthropic: `anthropic/claude-opus-4-5-20251101`, `anthropic/claude-3-5-haiku-20241022`
- Google: `google/gemini-3-pro`, `google/gemini-3-flash`
- OpenRouter: `openrouter/meta-llama/llama-guard-3-8b`

### Environment Variables
Inspect uses standard provider environment variables:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `OPENROUTER_API_KEY`

---

## Test Requirements

### Unit Tests
1. Test task loads correctly
2. Test dataset is parsed properly
3. Test solver produces expected output format
4. Test scorer captures all required metrics

### Integration Tests
1. Test full evaluation with mock model
2. Test results export to JSON
3. Test Inspect View can load results

---

## Definition of Done

- [ ] `uv add inspect-ai` added to project
- [ ] Task file created with `@task` decorators
- [ ] Custom solver wraps production prompt
- [ ] Custom scorer captures all metrics
- [ ] Can run: `inspect eval tests/benchmark/tasks/secbash_eval.py --model openai/gpt-5`
- [ ] Results viewable in Inspect View
- [ ] Results exportable to JSON
- [ ] No commands are executed (classification only)
- [ ] Temperature uses provider defaults

---

## Dependencies

- **Blocked by:** Story 4.1 (prompt), Story 4.2 (GTFOBins dataset), Story 4.3 (harmless dataset)
- **Blocks:** Story 4.5 (metrics reporting), Story 4.6 (comparison framework)

---

## Estimated Complexity

**Implementation:** High
- Learning Inspect Framework
- Custom solver and scorer development
- Integration with production prompt

**Testing:** Medium
- Need to verify Inspect integration
- Mock model for unit tests

**Risk:** Medium
- New framework (Inspect)
- Integration with existing codebase

---

## References

- [Inspect Documentation](https://inspect.aisi.org.uk/)
- [Inspect GitHub](https://github.com/UKGovernmentBEIS/inspect_ai)
- [Inspect Evals Repository](https://ukgovernmentbeis.github.io/inspect_evals/)
