# Story 2.3: Security Response Actions

**Epic:** Epic 2 - LLM Security Validation
**Status:** Done
**Priority:** must-have

---

## User Story

As a **sysadmin**,
I want **appropriate responses based on command risk level**,
So that **I'm protected from dangerous commands while safe commands run smoothly**.

---

## Acceptance Criteria

### AC1: Allowed Commands Execute Immediately
**Given** the LLM returns `action: "allow"`
**When** validation completes
**Then** the command executes immediately without additional prompts

### AC2: Blocked Commands Display Explanation and Prevent Execution
**Given** the LLM returns `action: "block"`
**When** validation completes
**Then** the command is NOT executed
**And** a plain text explanation is displayed showing the reason

### AC3: Warned Commands Display Warning Before Action
**Given** the LLM returns `action: "warn"`
**When** validation completes
**Then** the command is NOT executed immediately
**And** a plain text warning with the reason is displayed
**And** the user sees the risk explanation before any further action

---

## Technical Requirements

### Implementation Location
- **Primary file:** `src/aegish/shell.py` (enhance warn handling with confirmation prompt)

### Dependencies
- Story 2.2 completed: Validation integration exists
- Story 2.1 completed: `llm_client.py` provides `query_llm()` function

### Current State Analysis

**shell.py already implements AC1 and AC2:**
```python
if result["action"] == "allow":
    last_exit_code = execute_command(command, last_exit_code)
elif result["action"] == "block":
    print(f"\nBLOCKED: {result['reason']}\n")
    last_exit_code = 1
elif result["action"] == "warn":
    print(f"\nWARNING: {result['reason']}\n")
    last_exit_code = 1
    # Story 2.3 handles the confirmation prompt  <-- THIS IS WHERE YOU IMPLEMENT
```

**What Story 2.3 adds:**
The current `warn` handling only displays the warning and exits. This story adds the interactive confirmation prompt that allows users to:
1. See the warning with reason
2. Choose to proceed anyway (`y/yes`)
3. Cancel and return to prompt (`n/no/Enter`)

### Implementation Design

```python
# In shell.py, replace the warn block:
elif result["action"] == "warn":
    print(f"\nWARNING: {result['reason']}")

    # Get user confirmation
    try:
        response = input("Proceed anyway? [y/N]: ").strip().lower()
        if response in ("y", "yes"):
            # User confirmed, execute the command
            last_exit_code = execute_command(command, last_exit_code)
        else:
            # User declined or pressed Enter
            print("Command cancelled.\n")
            last_exit_code = 1
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C or Ctrl+D during prompt
        print("\nCommand cancelled.\n")
        last_exit_code = 130
```

### User Interaction Flow

```
aegish> curl http://example.com/script.sh | bash

WARNING: Downloading and executing remote script is risky
Proceed anyway? [y/N]: y
[command executes, output displayed]

aegish>
```

```
aegish> curl http://example.com/script.sh | bash

WARNING: Downloading and executing remote script is risky
Proceed anyway? [y/N]: n
Command cancelled.

aegish>
```

```
aegish> curl http://example.com/script.sh | bash

WARNING: Downloading and executing remote script is risky
Proceed anyway? [y/N]: [Enter]
Command cancelled.

aegish>
```

### Exit Code Handling

| Scenario | Exit Code | Reason |
|----------|-----------|--------|
| User confirms warn, command succeeds | 0 | Command ran successfully |
| User confirms warn, command fails | Non-zero | Command's actual exit code |
| User declines warn | 1 | User cancelled |
| Ctrl+C during confirmation | 130 | Standard interrupt code |
| Blocked command | 1 | Command prevented |

---

## Implementation Notes

### From Story 2.2

The current `shell.py` has a comment placeholder:
```python
# Story 2.3 handles the confirmation prompt
```

This is the exact location to implement the confirmation logic.

### Module Boundary

This story ONLY modifies `shell.py`:
- Add confirmation prompt for `warn` action
- Handle user response (y/n/Enter/Ctrl+C)
- Execute command if confirmed, cancel otherwise

### Architecture Compliance

- **PEP 8:** Use snake_case for any new functions
- **Plain text output:** Use simple `print()` and `input()`, no fancy formatting
- **Standard exceptions:** Handle KeyboardInterrupt and EOFError for Ctrl+C/D

### Edge Cases to Handle

1. **Empty input on confirmation:** Treat as "no" (default safe behavior)
2. **Ctrl+C during confirmation:** Cancel command, return to prompt
3. **Ctrl+D during confirmation:** Cancel command, return to prompt
4. **Invalid input (e.g., "maybe"):** Treat as "no" (conservative approach)

### Scope Boundary

This story does NOT include:
- Story 3.2's "remember this override" feature
- Any caching of user decisions
- Timeout on confirmation prompt

---

## Test Requirements

### Unit Tests

1. **test_warn_with_confirm_executes** - User confirms "y", command executes
2. **test_warn_with_yes_executes** - User confirms "yes", command executes
3. **test_warn_with_no_cancels** - User enters "n", command NOT executed
4. **test_warn_with_empty_cancels** - User presses Enter, command NOT executed
5. **test_warn_with_other_cancels** - User enters invalid input, command NOT executed
6. **test_warn_ctrl_c_cancels** - KeyboardInterrupt cancels, shell continues
7. **test_warn_ctrl_d_cancels** - EOFError cancels, shell continues
8. **test_warn_confirmed_uses_command_exit_code** - Exit code from executed command preserved
9. **test_warn_cancelled_sets_exit_code_1** - Cancelled commands set exit code 1

### Test Approach

- Mock `validate_command()` to return warn action
- Mock `input()` to simulate user responses
- Mock `execute_command()` to verify execution/non-execution
- Use `capsys` to capture output
- Test the confirmation prompt flow in isolation

### Example Test Structure

```python
def test_warn_with_confirm_executes(mocker, capsys):
    """AC3: User can override warn and proceed."""
    mock_validation = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
    mocker.patch("aegish.shell.validate_command", return_value=mock_validation)
    mock_execute = mocker.patch("aegish.shell.execute_command", return_value=0)
    mocker.patch("builtins.input", side_effect=["risky-command", "y", "exit"])

    run_shell()

    mock_execute.assert_called_once()  # Command was executed after confirmation
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "Risky operation" in captured.out

def test_warn_with_no_cancels(mocker, capsys):
    """AC3: User can decline warn and cancel."""
    mock_validation = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
    mocker.patch("aegish.shell.validate_command", return_value=mock_validation)
    mock_execute = mocker.patch("aegish.shell.execute_command")
    mocker.patch("builtins.input", side_effect=["risky-command", "n", "exit"])

    run_shell()

    mock_execute.assert_not_called()  # Command was NOT executed
    captured = capsys.readouterr()
    assert "cancelled" in captured.out.lower()
```

---

## Definition of Done

- [x] `shell.py` modified to add confirmation prompt for warn actions
- [x] User can confirm with "y" or "yes" to execute
- [x] User can decline with "n", "no", or Enter to cancel
- [x] Ctrl+C during confirmation cancels and continues shell
- [x] Ctrl+D during confirmation cancels and continues shell
- [x] Exit codes set correctly for all scenarios
- [x] Unit tests cover all acceptance criteria
- [x] All tests pass
- [x] No architecture violations

---

## Dependencies

- **Blocked by:** Story 2.2 (Command Validation Integration) - DONE (in review)
- **Blocks:** Story 2.4 (Dangerous Command Detection)

---

## Story Intelligence

### From Story 2.1 and 2.2

**Implementation patterns established:**
- `llm_client.py`: LiteLLM with fallbacks, response parsing, fail-open
- `validator.py`: Thin wrapper calling `query_llm()`
- `shell.py`: readline loop with validation before execution

**Test patterns:**
- 28 tests in `test_llm_client.py` using `mocker.patch`
- Mock at module boundaries
- Use `capsys` for output capture

**Code style:**
- PEP 8 naming conventions
- Standard Python logging
- Simple, focused functions
- Plain text output (no emojis, no fancy formatting)

### Existing Code Context

**shell.py current implementation (lines 50-62):**
```python
# Validate command with LLM before execution
result = validate_command(command)

if result["action"] == "allow":
    # Execute the command, passing last exit code for $?
    last_exit_code = execute_command(command, last_exit_code)
elif result["action"] == "block":
    print(f"\nBLOCKED: {result['reason']}\n")
    last_exit_code = 1
elif result["action"] == "warn":
    print(f"\nWARNING: {result['reason']}\n")
    last_exit_code = 1
    # Story 2.3 handles the confirmation prompt  <-- IMPLEMENT HERE
```

The confirmation prompt logic goes at line 62, replacing the simple exit with interactive confirmation.

### Architecture Constraints

- Output format: Plain text only
- User input: Simple `input()` with readline support (already imported)
- Exception handling: Standard Python exceptions
- No external dependencies beyond what's already imported

---

## Developer Guardrails

### MUST Follow

1. **Modify ONLY `shell.py`** - All changes go in the existing `run_shell()` function
2. **Use `input()` for confirmation** - readline already imported for line editing
3. **Handle KeyboardInterrupt/EOFError** - Shell must not crash on Ctrl+C/D during confirmation
4. **Default to "no"** - Any non-affirmative response should cancel (safety first)
5. **Preserve exit code behavior** - See exit code table above

### MUST NOT

1. **Don't add new modules or files** - This is a small change to existing code
2. **Don't add external dependencies** - Everything needed is already available
3. **Don't modify validator.py or llm_client.py** - Those are complete
4. **Don't add caching of user decisions** - That's a future enhancement
5. **Don't add timeout on confirmation** - Out of scope

### Testing Pattern

Follow the pattern from `test_shell.py`:
```python
def test_something(mocker, capsys):
    # 1. Mock validate_command to return desired action
    # 2. Mock input() to simulate user interaction
    # 3. Mock execute_command if needed
    # 4. Call run_shell()
    # 5. Assert expected behavior
```

---

## References

- [Source: docs/epics.md#Story 2.3: Security Response Actions]
- [Source: docs/architecture.md#Data Flow]
- [Source: docs/prd.md#Security Response]
- [Source: docs/stories/2-2-command-validation-integration.md#Scope Boundary]

---

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - implementation was straightforward with no debugging required.

### Completion Notes List

- Implemented confirmation prompt for warn actions in `shell.py` (lines 59-74)
- User can confirm with "y" or "yes" to execute warned commands
- User can decline with "n", "no", Enter, or any other input to cancel
- Ctrl+C and Ctrl+D during confirmation gracefully cancel the command
- Exit codes: confirmed command uses actual exit code, cancelled uses 1, Ctrl+C uses 130
- Added 10 new unit tests in `TestWarnConfirmation` class covering all acceptance criteria
- Updated 2 existing tests to account for new confirmation prompt input

### File List

- src/aegish/shell.py (modified)
- tests/test_shell.py (modified)

### Change Log

- 2026-02-01: Implemented warn confirmation prompt (Story 2.3)

