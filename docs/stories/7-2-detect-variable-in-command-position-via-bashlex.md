# Story 7.2: Detect Variable-in-Command-Position via bashlex

Status: Done

## Story

As a **security engineer**,
I want **commands with variable expansion in command position detected and flagged as WARN**,
so that **attacks like `a=ba; b=sh; $a$b` are caught before reaching the LLM**.

## Acceptance Criteria

1. **Given** a command like `a=ba; b=sh; $a$b`
   **When** bashlex parses the AST
   **Then** it detects: assignment nodes (`a=ba`, `b=sh`) + variable expansion in command position (`$a$b`)
   **And** returns WARN with reason "Variable expansion in command position with preceding assignment"

2. **Given** a command like `FOO=bar; echo $FOO`
   **When** bashlex parses the AST
   **Then** `$FOO` is in argument position (argument to `echo`), not command position
   **And** the command passes through to LLM validation normally

3. **Given** a command like `export PATH=$PATH:/usr/local/bin`
   **When** bashlex parses the AST
   **Then** it is recognized as a safe assignment, not a variable-in-command pattern
   **And** the command passes through to LLM validation normally

4. **Given** a command that bashlex cannot parse (syntax error or unsupported construct)
   **When** parsing fails
   **Then** the error is logged at debug level
   **And** the command passes through to LLM validation (graceful fallback)

## Tasks / Subtasks

- [x] Task 1: Implement `_check_variable_in_command_position()` in `src/aegish/validator.py` (AC: 1, 2, 3, 4)
  - [x] 1.1: Import `bashlex` and `logging` in validator.py
  - [x] 1.2: Implement AST walking logic to detect variable expansion in command position
  - [x] 1.3: Check for preceding `AssignmentNode` in the same compound command (ListNode)
  - [x] 1.4: Return WARN dict when pattern detected, `None` when safe
  - [x] 1.5: Wrap all bashlex calls in try/except for graceful fallback on parse errors
- [x] Task 2: Integrate bashlex check into `validate_command()` (AC: 1, 2, 3, 4)
  - [x] 2.1: Call `_check_variable_in_command_position(command)` before `query_llm(command)`
  - [x] 2.2: Return WARN result immediately if check triggers; otherwise proceed to LLM
- [x] Task 3: Verify edge cases pass through correctly (AC: 2, 3, 4)
  - [x] 3.1: `export PATH=$PATH:/usr/local/bin` — `export` is command, `$PATH` is in argument → safe
  - [x] 3.2: `echo hello | $CMD` — variable in command position in pipeline → should WARN
  - [x] 3.3: `$SHELL` (bare variable as command) — should pass through to LLM (no preceding assignment)
  - [x] 3.4: Unparseable syntax like `if [[ $x ==` → catch `bashlex.errors.ParsingError` → fallback

## Dev Notes

### Critical Implementation Details

**bashlex is already installed.** Story 7.7 (done) added `bashlex>=0.18,<1.0` to pyproject.toml. No dependency changes needed.

**File to modify: `src/aegish/validator.py` ONLY.** The current file is minimal (29 lines). Add the bashlex check function and integrate it before `query_llm()`. Do NOT modify `llm_client.py`, `config.py`, or `shell.py` — this story is purely a pre-LLM check in the validator.

**Current validator.py structure:**
```python
from aegish.llm_client import query_llm

def validate_command(command: str) -> dict:
    if not command or not command.strip():
        return {"action": "block", "reason": "Empty command", "confidence": 1.0}
    return query_llm(command)
```

Add the bashlex check between the empty-command check and the `query_llm()` call.

### bashlex AST Pattern Recognition

**The detection algorithm:**

1. Parse the command with `bashlex.parse(command)` → returns a list of AST nodes
2. Walk the AST tree looking for `CommandNode` where:
   - `parts[0]` is a `WordNode` that contains `ParameterNode` children
   - This means the **first word** (the command itself) involves variable expansion
3. If found AND there are `AssignmentNode` siblings in the same `ListNode` → return WARN

**Verified AST structures from bashlex 0.18:**

| Command | AST Structure | Detection |
|---------|--------------|-----------|
| `a=ba; b=sh; $a$b` | `ListNode` → `CommandNode(AssignmentNode)`, `CommandNode(AssignmentNode)`, `CommandNode(WordNode($a$b, [ParameterNode]))` | WARN: assignment + var-in-cmd-pos |
| `FOO=bar; echo $FOO` | `ListNode` → `CommandNode(AssignmentNode)`, `CommandNode(WordNode(echo), WordNode($FOO))` | Safe: `$FOO` is `parts[1]` (argument position) |
| `export PATH=$PATH:...` | `CommandNode(WordNode(export), WordNode(PATH=$PATH:...))` | Safe: `export` is the command, `$PATH` is in argument |
| `echo hello \| $CMD` | `PipelineNode` → `CommandNode(echo, hello)`, `CommandNode(WordNode($CMD))` | WARN: var-in-cmd-pos (in pipeline) |
| `$SHELL` (bare) | `CommandNode(WordNode($SHELL, [ParameterNode]))` | Pass through: no preceding assignment in same compound |

**Node kind values:** `list`, `command`, `word`, `assignment`, `parameter`, `operator`, `pipeline`, `pipe`, `compound`, `redirect`, `reservedword`

**How to check if a WordNode contains parameter expansion:**
```python
word_node = command_node.parts[0]  # First word = command position
has_param = word_node.parts and any(p.kind == 'parameter' for p in word_node.parts)
```

**How to check for preceding assignments in a ListNode:**
```python
# ListNode.parts contains CommandNodes and OperatorNodes interleaved
has_assignments = any(
    sub.kind == 'assignment'
    for part in list_node.parts if part.kind == 'command'
    for sub in part.parts
)
```

### Design Decisions

- **DD-18: WARN, not BLOCK.** False positives are possible (e.g., `VENV=.venv; $VENV/bin/python script.py` is legitimate). WARN lets the user confirm while flagging the suspicious pattern. [Source: docs/security-hardening-scope.md#DD-18]
- **DD-09: bashlex AST over regex.** Regex cannot reliably distinguish `$FOO` in command position from argument position. bashlex produces a proper AST that structurally identifies these patterns. [Source: docs/security-hardening-scope.md#DD-09]

### Error Handling

- Catch `bashlex.errors.ParsingError` for syntax errors bashlex can't handle
- Catch generic `Exception` as safety net (bashlex is a third-party library)
- Log at `debug` level (not warning) — parse failures are expected for complex bash constructs
- On ANY error, return `None` to fall through to LLM validation

### Existing Test Patterns

Tests use `pytest` with `unittest.mock.patch` and `pytest-mock`. See `tests/test_llm_client.py` for the pattern. The `tests/utils.py` provides `MockResponse` and `mock_providers()` context managers. The bashlex check can be tested without mocking LLM calls since it runs before `query_llm()`.

### Logging Convention

Use `logging.getLogger(__name__)` (consistent with `llm_client.py`). Use `logger.debug()` for parse failures. Use `logger.info()` when the bashlex check triggers a WARN.

### Project Structure Notes

- Only `src/aegish/validator.py` is modified — no new files
- Alignment with module responsibilities: validator.py is the correct location for pre-LLM command analysis [Source: docs/architecture.md#Module Responsibilities]
- Data flow unchanged: `shell.py → validator.py → llm_client.py` [Source: docs/architecture.md#Data Flow]

### Security Context

This story addresses **BYPASS-15: Pre-Expansion vs Post-Expansion Gap**. The attack vector is:
- aegish validates the raw command string `a=ba; b=sh; $a$b`
- Bash performs variable expansion → `a=ba; b=sh; bash`
- The expanded form (`bash`) would be blocked, but the raw form looks harmless

The bashlex check catches this pattern BEFORE sending to the LLM, providing a deterministic defense that doesn't rely on the LLM's ability to understand bash variable expansion.

**Relationship to Story 7.1 (envsubst):** envsubst handles environment variables (`$SHELL`, `$HOME`). bashlex handles within-command variable construction (`a=ba; b=sh; $a$b`). These are complementary — envsubst cannot expand `$a` because `a` is not an environment variable (it's set within the command itself).

### References

- [Source: docs/epics.md#Story 7.2] - Story definition and acceptance criteria
- [Source: docs/security-hardening-scope.md#BYPASS-15] - Pre-expansion vs post-expansion gap
- [Source: docs/security-hardening-scope.md#DD-09] - bashlex + envsubst over regex heuristics
- [Source: docs/security-hardening-scope.md#DD-18] - WARN for variable-in-command-position (not BLOCK)
- [Source: docs/architecture.md#Module Responsibilities] - validator.py handles LLM validation logic
- [Source: docs/architecture.md#Data Flow] - shell.py → validator.py → llm_client.py
- [Source: docs/stories/7-7-add-new-dependencies.md] - bashlex 0.18 installed, compound parsing verified
- [Source: pyproject.toml] - bashlex>=0.18,<1.0 in dependencies

## Dev Agent Record

### Context Reference

<!-- Story context created by create-story workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None required — implementation was straightforward with no debugging needed.

### Completion Notes List

- Implemented `_check_variable_in_command_position()` in validator.py using bashlex AST parsing
- Helper functions `_has_parameter_expansion()` and `_find_var_in_command_position()` walk the AST recursively
- Detection logic: finds variable expansion (`ParameterNode`) in command position (`parts[0]` of `CommandNode`) with preceding assignments
- Pipeline support: checks each segment independently — var in command position in any pipeline segment triggers WARN
- Bare variables without preceding assignment (e.g., `$SHELL`) pass through to LLM
- All bashlex calls wrapped in `try/except Exception` with `logger.debug()` on parse failure
- Integrated into `validate_command()` between empty-command check and `query_llm()` call
- 15 total new tests: 11 unit tests for `_check_variable_in_command_position()`, 4 integration tests for `validate_command()`
- All 23 validator tests pass

### File List

- `src/aegish/validator.py` — modified: added bashlex imports, `_has_parameter_expansion()`, `_find_var_in_command_position()`, `_check_variable_in_command_position()`, integrated into `validate_command()`
- `tests/test_validator.py` — modified: added `TestCheckVariableInCommandPosition` (11 tests) and `TestValidateCommandBashlex` (4 tests)

### Change Log

- 2026-02-13: Implemented bashlex-based variable-in-command-position detection (Story 7.2) — deterministic pre-LLM check for BYPASS-15 attack pattern
- 2026-02-13: [Code Review] Fixed 6 issues: CRITICAL inline-assignment bypass (`VAR=x $CMD`), HIGH uncaught exception in AST walking, MEDIUM pipeline reason string and compound test gap, LOW test consistency
