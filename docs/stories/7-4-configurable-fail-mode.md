# Story 7.4: Configurable Fail-Mode (Fail-Safe / Fail-Open)

Status: done

## Story

As a **sysadmin**,
I want **to configure whether validation failures block or warn**,
so that **production deployments default to secure behavior while development allows flexibility**.

## Acceptance Criteria

1. **Given** `AEGISH_FAIL_MODE` is not set or set to `safe`
   **When** all LLM providers fail (connection error, timeout, parse error, no keys configured)
   **Then** the command is BLOCKED (action="block", confidence=0.0)
   **And** the reason message indicates validation failure

2. **Given** `AEGISH_FAIL_MODE=open`
   **When** all LLM providers fail
   **Then** the command receives a WARN (action="warn", confidence=0.0) — existing behavior
   **And** the user can confirm with "y" to proceed

3. **Given** aegish starts
   **When** the startup banner is displayed
   **Then** the current fail mode is shown:
   - `Fail mode: safe (block on validation failure)` for safe mode
   - `Fail mode: open (warn on validation failure)` for open mode

4. **Given** `AEGISH_FAIL_MODE` is set to an invalid value (e.g., "invalid", whitespace, empty)
   **When** aegish starts
   **Then** the default "safe" mode is used (same behavior as AC1)

5. **Given** `AEGISH_FAIL_MODE=open` and `AEGISH_MODE=production`
   **When** all LLM providers fail
   **Then** the command receives a WARN (fail-mode overrides production mode for this specific behavior)
   **And** the banner shows both mode and fail mode independently

## Tasks / Subtasks

- [x] Task 1: Add `get_fail_mode()` to `src/aegish/config.py` (AC: 1, 2, 4)
  - [x] 1.1: Add `DEFAULT_FAIL_MODE = "safe"` and `VALID_FAIL_MODES = {"safe", "open"}` constants
  - [x] 1.2: Implement `get_fail_mode()` following the exact pattern of existing `get_mode()` function
  - [x] 1.3: Add `AEGISH_FAIL_MODE` to the module docstring
- [x] Task 2: Update `_validation_failed_response()` in `src/aegish/llm_client.py` (AC: 1, 2)
  - [x] 2.1: Import `get_fail_mode` from `aegish.config`
  - [x] 2.2: Update `_validation_failed_response()` to return `action="block"` when fail mode is "safe", `action="warn"` when "open"
- [x] Task 3: Display fail mode in startup banner in `src/aegish/shell.py` (AC: 3)
  - [x] 3.1: Import `get_fail_mode` from `aegish.config`
  - [x] 3.2: Add fail mode display line after the existing mode display
- [x] Task 4: Update existing tests that expect "warn" for validation failures (AC: 1, 2)
  - [x] 4.1: Update `mock_providers()` in `tests/utils.py` to also mock `get_fail_mode` returning `"open"` for backward compatibility, OR update individual tests
  - [x] 4.2: Fix `TestQueryLLM` tests: `test_warns_on_connection_error`, `test_warns_on_timeout_error`, `test_warns_on_generic_exception`, `test_handles_invalid_json_response`
  - [x] 4.3: Fix `TestNoProvidersConfigured.test_warns_when_no_providers`
  - [x] 4.4: Fix `TestInvalidActionHandling.test_invalid_action_all_providers_warns`
  - [x] 4.5: Fix `TestCommandLengthValidation.test_long_command_warns`
  - [x] 4.6: Fix `TestConfigurableModels.test_single_model_no_fallbacks`
- [x] Task 5: Add new tests for fail-mode behavior (AC: 1, 2, 3, 4)
  - [x] 5.1: Add `TestGetFailMode` class to `tests/test_config.py`
  - [x] 5.2: Add `TestFailMode` class to `tests/test_llm_client.py`
  - [x] 5.3: Add `TestStartupFailModeBanner` class to `tests/test_shell.py`

## Dev Notes

### Critical Implementation Details

**Three files modified, zero new files.** This story changes:
1. `src/aegish/config.py` — add `get_fail_mode()` (new function, ~10 lines)
2. `src/aegish/llm_client.py` — update `_validation_failed_response()` (~5 line change)
3. `src/aegish/shell.py` — add fail mode to startup banner (~4 lines)

**Tests updated in existing files** — no new test files needed.

### config.py Changes

**Add constants after line 49** (after `VALID_MODES`):
```python
# Fail mode configuration (DD-05: default fail-safe)
DEFAULT_FAIL_MODE = "safe"
VALID_FAIL_MODES = {"safe", "open"}
```

**Add function** (follow the exact pattern of `get_mode()` at line 83-96):
```python
def get_fail_mode() -> str:
    """Get the fail mode for validation failures.

    Reads from AEGISH_FAIL_MODE environment variable.
    Default: safe (block on validation failure).
    Open: warn on validation failure (user can confirm to proceed).

    Returns:
        Fail mode string: "safe" or "open".
    """
    mode = os.environ.get("AEGISH_FAIL_MODE", "").strip().lower()
    if mode in VALID_FAIL_MODES:
        return mode
    return DEFAULT_FAIL_MODE
```

**Update module docstring** — add `AEGISH_FAIL_MODE` entry after the `AEGISH_MODE` block:
```
AEGISH_FAIL_MODE : str
    Behavior when validation fails: "safe" (block) or "open" (warn).
    Default: safe (block on validation failure, DD-05).
    Open: warn on validation failure (user can confirm to proceed).
```

### llm_client.py Changes

**Add import** — update the import from `aegish.config` at line 21 to include `get_fail_mode`:
```python
from aegish.config import (
    ...existing imports...,
    get_fail_mode,
)
```

**Update `_validation_failed_response()`** (lines 515-530):
```python
def _validation_failed_response(reason: str) -> dict:
    """Create a response when validation cannot be completed.

    In fail-safe mode (default): blocks the command.
    In fail-open mode: warns the user, who can decide to proceed.

    Args:
        reason: The reason validation failed.

    Returns:
        A dict with action="block" (safe) or action="warn" (open), confidence=0.0.
    """
    action = "block" if get_fail_mode() == "safe" else "warn"
    return {
        "action": action,
        "reason": f"Could not validate command: {reason}",
        "confidence": 0.0,
    }
```

### shell.py Changes

**Add import** — update line 18:
```python
from aegish.config import get_api_key, get_fail_mode, get_mode, get_model_chain, get_provider_from_model
```

**Add fail mode display** — insert after line 105 (`print("Mode: development")`), before line 106 (`print("Type 'exit'...")`):
```python
    fail_mode = get_fail_mode()
    if fail_mode == "safe":
        print("Fail mode: safe (block on validation failure)")
    else:
        print("Fail mode: open (warn on validation failure)")
```

### Existing Test Impact Analysis

**CRITICAL: The default fail mode changes from "warn" to "block".** All existing tests that assert validation failures produce `action="warn"` will break because AEGISH_FAIL_MODE is unset in the test environment (defaults to "safe" = block).

**Affected tests in `tests/test_llm_client.py`** (8 tests):

| Test | Current Assertion | Fix Strategy |
|------|-------------------|--------------|
| `TestQueryLLM.test_warns_on_connection_error` | `result["action"] == "warn"` | Set `AEGISH_FAIL_MODE=open` or expect "block" |
| `TestQueryLLM.test_warns_on_timeout_error` | `result["action"] == "warn"` | Same |
| `TestQueryLLM.test_warns_on_generic_exception` | `result["action"] == "warn"` | Same |
| `TestQueryLLM.test_handles_invalid_json_response` | `result["action"] == "warn"` | Same |
| `TestNoProvidersConfigured.test_warns_when_no_providers` | `result["action"] == "warn"` | Same |
| `TestInvalidActionHandling.test_invalid_action_all_providers_warns` | `result["action"] == "warn"` | Same |
| `TestCommandLengthValidation.test_long_command_warns` | `result["action"] == "warn"` | Same |
| `TestConfigurableModels.test_single_model_no_fallbacks` | `result["action"] == "warn"` | Same |

**Recommended fix approach:** Update `mock_providers()` in `tests/utils.py` to also mock `get_fail_mode` returning `"open"` so existing tests preserve their current behavior. Then add new dedicated tests for both fail modes.

**Alternative approach:** Add `mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": "open"})` to each affected test individually. This is more explicit but more verbose.

**Preferred approach for the dev agent:** Update `mock_providers()` to add `get_fail_mode=lambda: "open"` to the `patch.multiple` call. This preserves all existing test behavior with one change. Then write new tests that explicitly test both modes.

**In `tests/utils.py`, update the `patch.multiple` call (line 57-63):**
```python
return patch.multiple(
    "aegish.llm_client",
    get_api_key=mock_get_api_key,
    get_model_chain=lambda: model_chain,
    validate_model_provider=lambda model, allowed=None: (True, ""),
    get_allowed_providers=lambda: {"openai", "anthropic", "groq", "together_ai", "ollama"},
    get_fail_mode=lambda: "open",  # Preserve existing test behavior
)
```

### New Tests to Add

**`tests/test_config.py` — Add `TestGetFailMode` class:**
```python
class TestGetFailMode:
    """Tests for get_fail_mode function (Story 7.4)."""

    def test_default_fail_mode_is_safe(self, mocker):
        """AC1: Default is safe when AEGISH_FAIL_MODE not set."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert get_fail_mode() == "safe"

    def test_safe_mode_from_env(self, mocker):
        """AC1: Explicit safe mode."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": "safe"}, clear=True)
        assert get_fail_mode() == "safe"

    def test_open_mode_from_env(self, mocker):
        """AC2: Open mode."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": "open"}, clear=True)
        assert get_fail_mode() == "open"

    def test_invalid_value_defaults_to_safe(self, mocker):
        """AC4: Invalid value falls back to safe."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": "invalid"}, clear=True)
        assert get_fail_mode() == "safe"

    def test_whitespace_and_case_normalized(self, mocker):
        """Whitespace and mixed case are normalized."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": " Open "}, clear=True)
        assert get_fail_mode() == "open"

    def test_empty_defaults_to_safe(self, mocker):
        """Empty string defaults to safe."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": ""}, clear=True)
        assert get_fail_mode() == "safe"
```

**`tests/test_llm_client.py` — Add `TestFailMode` class:**
```python
class TestFailMode:
    """Tests for configurable fail-mode in validation failures (Story 7.4)."""

    def test_safe_mode_blocks_on_all_providers_fail(self, mocker):
        """AC1: Fail-safe mode blocks when all providers fail."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": "safe"}, clear=True)
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                with patch("aegish.llm_client.get_fail_mode", return_value="safe"):
                    mock_completion.side_effect = ConnectionError("All down")
                    result = query_llm("ls -la")
                    assert result["action"] == "block"
                    assert result["confidence"] == 0.0
                    assert "could not validate" in result["reason"].lower()

    def test_open_mode_warns_on_all_providers_fail(self, mocker):
        """AC2: Fail-open mode warns when all providers fail."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": "open"}, clear=True)
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                with patch("aegish.llm_client.get_fail_mode", return_value="open"):
                    mock_completion.side_effect = ConnectionError("All down")
                    result = query_llm("ls -la")
                    assert result["action"] == "warn"
                    assert result["confidence"] == 0.0

    def test_safe_mode_blocks_on_no_providers(self, mocker):
        """AC1: No providers configured in safe mode = block."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": "safe"}, clear=True)
        with mock_providers([]):
            with patch("aegish.llm_client.get_fail_mode", return_value="safe"):
                result = query_llm("ls -la")
                assert result["action"] == "block"

    def test_safe_mode_blocks_on_oversized_command(self, mocker):
        """AC1: Oversized command in safe mode = block."""
        from aegish.llm_client import MAX_COMMAND_LENGTH
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": "safe"}, clear=True)
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.get_fail_mode", return_value="safe"):
                result = query_llm("x" * (MAX_COMMAND_LENGTH + 1))
                assert result["action"] == "block"

    def test_default_mode_is_safe(self, mocker):
        """AC1: Default (no env var) = safe = block."""
        mocker.patch.dict(os.environ, {}, clear=True)
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                with patch("aegish.llm_client.get_fail_mode", return_value="safe"):
                    mock_completion.side_effect = TimeoutError("Timeout")
                    result = query_llm("ls -la")
                    assert result["action"] == "block"
```

**`tests/test_shell.py` — Add `TestStartupFailModeBanner` class:**
```python
class TestStartupFailModeBanner:
    """Tests for fail mode display in startup banner (Story 7.4)."""

    @pytest.fixture(autouse=True)
    def mock_banner(self):
        """Mock model chain and health check to isolate tests."""
        with patch("aegish.shell.get_model_chain", return_value=["openai/gpt-4"]):
            with patch("aegish.shell.get_api_key", return_value="test-key"):
                with patch("aegish.shell.health_check", return_value=(True, "")):
                    yield

    def test_safe_mode_displayed_in_banner(self, capsys):
        """AC3: Safe fail mode banner."""
        with patch("aegish.shell.get_mode", return_value="development"):
            with patch("aegish.shell.get_fail_mode", return_value="safe"):
                with patch("builtins.input", side_effect=["exit"]):
                    run_shell()
                    captured = capsys.readouterr()
                    assert "Fail mode: safe (block on validation failure)" in captured.out

    def test_open_mode_displayed_in_banner(self, capsys):
        """AC3: Open fail mode banner."""
        with patch("aegish.shell.get_mode", return_value="development"):
            with patch("aegish.shell.get_fail_mode", return_value="open"):
                with patch("builtins.input", side_effect=["exit"]):
                    run_shell()
                    captured = capsys.readouterr()
                    assert "Fail mode: open (warn on validation failure)" in captured.out

    def test_both_mode_and_fail_mode_displayed(self, capsys):
        """AC5: Production mode and fail mode shown independently."""
        with patch("aegish.shell.get_mode", return_value="production"):
            with patch("aegish.shell.get_fail_mode", return_value="open"):
                with patch("builtins.input", side_effect=["exit"]):
                    run_shell()
                    captured = capsys.readouterr()
                    assert "Mode: production" in captured.out
                    assert "Fail mode: open" in captured.out
```

### Why Default to "safe" (Block)

**DD-05:** A security tool should be secure by default. If aegish cannot validate a command (all providers down, no API keys, parse failures), the secure default is to block execution rather than allow the user to bypass validation.

The `AEGISH_FAIL_MODE=open` opt-in is for:
- Development environments where availability > security
- Testing scenarios
- Situations where the operator understands the risk

### How `_validation_failed_response()` Is Called

This function is the bottleneck for validation failures where the LLM cannot produce a result. It is called from two places in `query_llm()`:

1. **Line 353:** No models available (no API keys configured for any model in chain)
2. **Line 377:** All models failed (API errors, parse failures, or unparseable responses)

Note: Oversized commands (exceeding `MAX_COMMAND_LENGTH`) are handled separately at line 293-303 with a direct block response (confidence=1.0), bypassing `_validation_failed_response()` entirely.

Both paths produce the same response structure with `confidence=0.0`. The only difference this story introduces is whether `action` is `"block"` (safe) or `"warn"` (open).

### Data Flow for Fail-Mode Decision

```
User enters command
  → validator.py:validate_command()
    → llm_client.py:query_llm()
      → _try_model() for each model in chain
        → All fail
      → _validation_failed_response(reason)
        → get_fail_mode() reads AEGISH_FAIL_MODE
        → Returns {"action": "block", ...} if "safe"
        → Returns {"action": "warn", ...} if "open"
    → Returns to shell.py
  → shell.py:run_shell()
    → If "block": prints BLOCKED, sets exit_code=1
    → If "warn": prints WARNING, prompts user "Proceed anyway? [y/N]"
```

### Compatibility with Other Features

| Feature | Impact | Notes |
|---------|--------|-------|
| Health check (Story 9.2) | No impact | Health check tests primary model connectivity at startup, does not use `_validation_failed_response()` |
| Provider allowlist (Story 9.1) | Compatible | If all providers are rejected by allowlist AND defaults also fail, `_validation_failed_response()` is called — fail mode applies |
| Command delimiters (Story 7.3) | No impact | Delimiters affect user message format, not failure handling |
| envsubst expansion (Story 7.1) | No impact | Expansion happens before `_try_model()` |
| bashlex check (Story 7.2) | No impact | bashlex runs in `validator.py` before `query_llm()` |
| Oversized commands (Story 7.5) | Compatible now, replaced later | Currently, oversized commands go through `_validation_failed_response()`. Story 7.5 will change this to unconditional block with confidence=1.0, bypassing fail mode entirely |
| AEGISH_MODE (Story 8.1) | Independent | Mode controls exit behavior and Landlock. Fail mode controls validation failure behavior. They are orthogonal settings displayed separately in the banner |

### Relationship to Other Epic 7 Stories

| Story | Relationship | Notes |
|-------|-------------|-------|
| 7.1 (done) | No impact | envsubst expansion is in `_get_messages_for_model()`, not failure path |
| 7.2 (done) | No impact | bashlex is in validator.py, before LLM call |
| 7.3 (done) | No impact | Delimiters in user message, not failure path |
| 7.5 (backlog) | Will override for oversized | Story 7.5 will make oversized commands always block with confidence=1.0, bypassing `_validation_failed_response()` entirely |
| 7.7 (done) | No impact | Dependencies already added |
| 7.8 (backlog) | This story's tests will be part of 7.8 coverage | Story 7.8 is the comprehensive validation pipeline test suite |

### Project Structure Notes

- Only existing files modified (`config.py`, `llm_client.py`, `shell.py`) — no new files
- Tests updated in existing files (`test_config.py`, `test_llm_client.py`, `test_shell.py`, `utils.py`) — no new test files
- Pattern follows existing `get_mode()` in config.py exactly [Source: src/aegish/config.py:83-96]
- Data flow unchanged: `shell.py -> validator.py -> llm_client.py` [Source: docs/architecture.md#Data Flow]
- Module responsibilities preserved: config.py handles env var loading, llm_client.py handles LLM interaction [Source: docs/architecture.md#Module Responsibilities]

### References

- [Source: docs/epics.md#Story 7.4] - Story definition and acceptance criteria (FR37)
- [Source: docs/security-hardening-scope.md#BYPASS-02] - Validation fail-open design vulnerability
- [Source: docs/security-hardening-scope.md#DD-05] - Default fail-safe, configurable to fail-open
- [Source: docs/architecture.md#Module Responsibilities] - config.py, llm_client.py, shell.py responsibilities
- [Source: docs/architecture.md#Data Flow] - shell.py -> validator.py -> llm_client.py
- [Source: src/aegish/config.py:83-96] - `get_mode()` function pattern to follow
- [Source: src/aegish/llm_client.py:515-530] - Current `_validation_failed_response()` implementation
- [Source: src/aegish/shell.py:91-106] - Current startup banner code
- [Source: tests/utils.py:57-63] - `mock_providers()` patch.multiple that needs updating
- [Source: docs/stories/7-3-wrap-commands-in-delimiters-for-prompt-injection-defense.md] - Previous story, same epic

## Dev Agent Record

### Context Reference

<!-- Story context created by create-story workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

No debug issues encountered.

### Completion Notes List

- Implemented `get_fail_mode()` in config.py following the exact pattern of `get_mode()`
- Updated `_validation_failed_response()` in llm_client.py to branch on fail mode: "block" for safe (default), "warn" for open
- Added fail mode display to startup banner in shell.py after the mode line
- Fixed existing tests by adding `get_fail_mode=lambda: "open"` to `mock_providers()` in utils.py — single-line change preserving all 8 affected tests
- Added `AEGISH_FAIL_MODE=open` to `test_single_model_no_fallbacks` which sets env vars directly
- Added 14 new tests: 6 for `get_fail_mode()`, 5 for fail-mode in validation failures, 3 for banner display
- Full regression suite: 721 passed, 0 failed

### Code Review Fixes (AI)

- [H1] Added invalid value logging to `get_fail_mode()` matching `get_mode()` pattern — preserves raw value, logs debug warning for invalid values, silent for empty/unset
- [M1] Updated `llm_client.py` module docstring line 11: "Warn user" → "Block or warn user ... (configurable via AEGISH_FAIL_MODE)"
- [M2] Added `test_open_mode_warns_regardless_of_production_mode` to TestFailMode — verifies AC5 behavioral claim (fail-open + production mode)
- [M3] Fixed Dev Notes: corrected `_validation_failed_response()` call sites from 3 to 2 (oversized commands bypass it)
- Added 2 new config tests: `test_invalid_value_logs_debug_warning`, `test_empty_fail_mode_does_not_log`
- Post-fix regression: 211 passed, 0 failed

### Change Log

- 2026-02-13: Implemented configurable fail-mode (fail-safe/fail-open) for validation failures (Story 7.4)
- 2026-02-13: Code review fixes — H1 logging, M1 docstring, M2 AC5 test, M3 dev notes accuracy

### File List

- src/aegish/config.py (modified: added `DEFAULT_FAIL_MODE`, `VALID_FAIL_MODES`, `get_fail_mode()`, docstring update)
- src/aegish/llm_client.py (modified: added `get_fail_mode` import, updated `_validation_failed_response()`)
- src/aegish/shell.py (modified: added `get_fail_mode` import, added fail mode banner display)
- tests/utils.py (modified: added `get_fail_mode` mock to `mock_providers()`)
- tests/test_config.py (modified: added `TestGetFailMode` class with 6 tests)
- tests/test_llm_client.py (modified: added `TestFailMode` class with 5 tests, updated `test_single_model_no_fallbacks`)
- tests/test_shell.py (modified: added `TestStartupFailModeBanner` class with 3 tests)
- docs/stories/sprint-status.yaml (modified: story status in-progress → review)
