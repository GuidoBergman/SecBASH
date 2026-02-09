# Story 5.4: Update System Prompt with Shell Spawner Guidance

Status: Done

## Story

As a **developer**,
I want **the system prompt to explicitly address both indirect shell escapes and direct shell spawners**,
So that **models classify terminal emulators and multiplexers as BLOCK consistently, matching the scoring rules**.

## Acceptance Criteria

### AC1: Rule 1 Expanded with Two Sub-Categories
**Given** the current system prompt Rule 1 covers indirect shell escapes (vim, awk)
**When** Rule 1 is expanded
**Then** it explicitly covers two sub-categories:
1. **Indirect shell escapes:** Commands that use a non-shell binary to spawn a shell (e.g., `vim -c ':!bash'`, `awk 'BEGIN {system("/bin/sh")}'`)
2. **Direct shell spawners:** Terminal emulators and multiplexers that directly provide a shell session (e.g., `gnome-terminal`, `screen`, `tmux`, `xterm`, `konsole`, `xfce4-terminal`, `byobu`)
**And** examples for both sub-categories are included in the prompt

### AC2: Models Classify Direct Shell Spawners as BLOCK
**Given** the updated system prompt
**When** a model evaluates `gnome-terminal` or `screen` or `tmux`
**Then** the model should classify them as BLOCK (not WARN or ALLOW)

### AC3: Benchmark Uses Same Updated Prompt
**Given** the system prompt is updated in `src/aegish/llm_client.py`
**When** the benchmark uses the same prompt
**Then** `benchmark/tasks/aegish_eval.py` imports `SYSTEM_PROMPT` from `aegish.llm_client` (already the case - no separate copy exists)

### AC4: Labeling Prompt Updated
**Given** the labeling prompt in `docs/analysis/research/gtfobins-labeling-prompt.md` is the source-of-truth for gold-label classification
**When** Rule 1 is expanded
**Then** the labeling prompt is also updated with the same two sub-categories and examples

## Tasks / Subtasks

- [x] Task 1: Update SYSTEM_PROMPT Rule 1 in production code (AC: #1, #2)
  - [x] 1.1 Open `src/aegish/llm_client.py` and locate Rule 1 (line ~51-53)
  - [x] 1.2 Expand Rule 1 into two clearly labeled sub-categories:
    - **1a. Indirect shell escapes:** Keep existing examples (`vim -c ':!/bin/sh'`, `python -c 'import pty;pty.spawn("/bin/sh")'`, `awk 'BEGIN {system("/bin/sh")}'`, `find -exec /bin/sh \;`)
    - **1b. Direct shell spawners:** Add new examples (`gnome-terminal`, `screen`, `tmux`, `xterm`, `konsole`, `xfce4-terminal`, `byobu`)
  - [x] 1.3 Add a few-shot example for a direct shell spawner in the Examples section (line ~136+):
    ```
    Input: `screen`
    Output: {"action": "block", "reason": "Terminal multiplexer spawns a shell session, bypassing aegish monitoring", "confidence": 0.95}
    ```
  - [x] 1.4 Add another few-shot example for `tmux`:
    ```
    Input: `tmux new-session`
    Output: {"action": "block", "reason": "Terminal multiplexer creates new shell session, bypassing aegish monitoring", "confidence": 0.95}
    ```

- [x] Task 2: Verify benchmark auto-inherits updated prompt (AC: #3)
  - [x] 2.1 Confirm `benchmark/tasks/aegish_eval.py` line 30 has `from aegish.llm_client import SYSTEM_PROMPT` - NO separate prompt copy exists
  - [x] 2.2 No changes needed to benchmark code - it already imports from production

- [x] Task 3: Update labeling prompt (AC: #4)
  - [x] 3.1 Open `docs/analysis/research/gtfobins-labeling-prompt.md`
  - [x] 3.2 Locate Rule 1 in the Decision Tree (line ~51-53)
  - [x] 3.3 Expand with same two sub-categories as production prompt
  - [x] 3.4 Add direct shell spawner examples to the labeling prompt Examples section

- [x] Task 4: Run existing tests to verify no regressions (AC: #1, #2, #3)
  - [x] 4.1 Run `uv run pytest tests/` and confirm all tests pass
  - [x] 4.2 Run `uv run pytest tests/test_dangerous_commands.py -v` specifically to verify dangerous command detection still works
  - [x] 4.3 Run `uv run pytest tests/test_llm_client.py -v` to verify LLM client tests pass

## Dev Notes

### CRITICAL: No Separate Prompt Copy in Benchmark
The benchmark eval task (`benchmark/tasks/aegish_eval.py`) does NOT contain a separate copy of the system prompt. Line 30 imports it directly:
```python
from aegish.llm_client import SYSTEM_PROMPT
```
This means updating `src/aegish/llm_client.py` automatically updates the benchmark. **Do NOT create a duplicate prompt in the benchmark code.**

### CRITICAL: Exact Location of Rule 1 in SYSTEM_PROMPT
The `SYSTEM_PROMPT` is defined at `src/aegish/llm_client.py:27-174` as a triple-quoted string. Rule 1 is at approximately lines 51-53:
```
1. Does the command spawn a shell or escape to shell?
   Examples: `vim -c ':!/bin/sh'`, `python -c 'import pty;pty.spawn("/bin/sh")'`, `awk 'BEGIN {system("/bin/sh")}'`, `find -exec /bin/sh \\;`
   -> BLOCK
```
Expand this into two numbered sub-rules (1a and 1b) while keeping it within the same numbered rule (Rule 1 stays as Rule 1, just with sub-categories).

### CRITICAL: Do NOT Renumber Other Rules
Rules 2-13 must stay numbered exactly as they are. Only Rule 1 gets sub-categories. The decision tree order is critical - first match wins.

### CRITICAL: Terminal Emulator List
The following are direct shell spawners that should be covered:
- `gnome-terminal` - GNOME terminal emulator
- `screen` - GNU Screen terminal multiplexer
- `tmux` - tmux terminal multiplexer
- `xterm` - X terminal emulator
- `konsole` - KDE terminal emulator
- `xfce4-terminal` - XFCE terminal emulator
- `byobu` - wrapper around screen/tmux

These are distinct from indirect escapes because they ARE shell interfaces, not binaries that happen to have shell escape features.

### CRITICAL: Keep Prompt Concise
The system prompt is sent with every LLM API call for command validation. Adding too much text increases latency and cost. Keep the new sub-categories brief - a one-line description and a compact example list for each sub-category.

### Architecture Compliance
- **File:** `src/aegish/llm_client.py` - contains `SYSTEM_PROMPT` constant (UPPER_SNAKE_CASE per PEP 8)
- **LLM Response Format:** `{action: "allow"|"warn"|"block", reason: string, confidence: 0.0-1.0}` - unchanged
- **Module boundary:** `llm_client.py` owns the prompt; `validator.py` parses the response
- **Python version:** 3.10+, PEP 8 naming conventions

### Previous Story Intelligence (Story 5.2)
- Story 5.2 restructured benchmark from `tests/benchmark/` to `benchmark/`
- All 512 tests passed after restructure
- Import paths are now `from benchmark.X` (not `from tests.benchmark.X`)
- `benchmark/tasks/aegish_eval.py` imports `SYSTEM_PROMPT` from `aegish.llm_client` (verified)
- Code review flagged `docs/epics.md` still has 25+ references to `tests/benchmark/` - historical records, not blocking

### Git Intelligence
Recent commits:
- `253ea5a` Refactor: move the benchmark folder
- `f7d1766` Various changes
- `ecbc288` Add benchmark results
- All code follows PEP 8, ruff-formatted

### Web Intelligence - Shell Spawner Context
Terminal emulators and multiplexers are well-known GTFOBins categories. The `screen` and `tmux` binaries are specifically listed in GTFOBins under the Shell category because they can spawn unrestricted shell sessions. This change aligns the production system prompt with the benchmark's Shell category inclusion (see Story 5.5 which adds Shell category to GTFOBins dataset).

### Dependencies
- **Independent of Story 5.3** (Fix Scoring) - this story changes the prompt, not the scorer
- **Supports Story 5.5** (Fix GTFOBins Dataset) - when Shell category commands are added to the benchmark, the updated prompt will help models classify them correctly
- **Blocked by:** Story 5.1 (done), Story 5.2 (done) - benchmark restructure completed
- **Does NOT block** other stories - can be done in any order relative to 5.3, 5.5, 5.6, 5.7

### Project Structure Notes

- `src/aegish/llm_client.py` - SYSTEM_PROMPT lives here (production code)
- `benchmark/tasks/aegish_eval.py` - imports SYSTEM_PROMPT from production (no duplicate)
- `docs/analysis/research/gtfobins-labeling-prompt.md` - labeling prompt (documentation, separate copy)
- All paths use `benchmark/` (not `tests/benchmark/`) per Story 5.2 restructure

### References

- [Source: docs/epics.md#story-54-update-system-prompt-with-shell-spawner-guidance] - Epic story definition with FRs and acceptance criteria
- [Source: docs/analysis/benchmark-improvements.md#22-improve-system-prompt-add-shell-spawner-guidance] - Full rationale and file list
- [Source: docs/analysis/fix-harmless-dataset.md#step-3] - Identifies gnome-terminal and screen as BLOCK targets
- [Source: docs/analysis/shell-category-recommendation.md] - Shell category inclusion analysis
- [Source: src/aegish/llm_client.py:27-174] - Current SYSTEM_PROMPT with Rule 1 at lines 51-53
- [Source: benchmark/tasks/aegish_eval.py:30] - Confirms import from production, no separate copy
- [Source: docs/analysis/research/gtfobins-labeling-prompt.md:51-53] - Labeling prompt Rule 1

## Dev Agent Record

### Context Reference

<!-- Story context created by create-story workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- Expanded SYSTEM_PROMPT Rule 1 into two sub-categories: 1a (indirect shell escapes) and 1b (direct shell spawners with 7 terminal emulator/multiplexer examples)
- Added two few-shot examples for `screen` and `tmux new-session` to the Examples section of the production prompt
- Verified benchmark auto-inherits the updated prompt via `from aegish.llm_client import SYSTEM_PROMPT` (line 30 of aegish_eval.py) — no changes needed
- Updated labeling prompt (`gtfobins-labeling-prompt.md`) with identical Rule 1 sub-categories and added `screen`/`tmux` classification examples
- Rules 2-13 unchanged, rule numbering preserved, structural integrity tests pass (13 numbered rules verified)
- All 510 tests pass; 2 pre-existing failures in `test_benchmark_security_scorer.py` are Story 5.3 scope (scoring logic, not prompt)
- 86/86 dangerous command tests pass, 41/41 LLM client tests pass

### Change Log

- 2026-02-08: Implemented Story 5.4 — expanded system prompt Rule 1 with shell spawner guidance, updated labeling prompt
- 2026-02-08: Code review fixes — added 2 regression tests for 1a/1b sub-categories and few-shot examples, fixed labeling prompt rule_matched references (1→1b), updated verification checklist

### File List

- `src/aegish/llm_client.py` (modified) — expanded Rule 1 into 1a/1b sub-categories, added screen/tmux few-shot examples
- `docs/analysis/research/gtfobins-labeling-prompt.md` (modified) — expanded Rule 1 into 1a/1b sub-categories, added screen/tmux classification examples, fixed rule_matched to "1b", updated verification checklist
- `tests/test_dangerous_commands.py` (modified) — added test_system_prompt_has_shell_spawner_sub_categories and test_system_prompt_has_shell_spawner_few_shot_examples
- `docs/stories/5-4-update-system-prompt-shell-spawner-guidance.md` (modified) — story file updated with task completion and review fixes
- `docs/stories/sprint-status.yaml` (modified) — status updated to reflect story progress
