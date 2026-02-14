# Story 7.5: Block Oversized Commands

Status: done

## Story

As a **security engineer**,
I want **commands exceeding MAX_COMMAND_LENGTH blocked instead of warned**,
so that **padding attacks cannot bypass validation by exceeding the length limit**.

## Acceptance Criteria

1. **Given** a command exceeding 4096 characters
   **When** validated
   **Then** the command is BLOCKED with confidence 1.0
   **And** the reason includes the actual length and the limit

2. **Given** a command of exactly 4096 characters
   **When** validated
   **Then** the command proceeds to LLM validation normally

## Tasks / Subtasks

- [x] Task 1: Change oversized command response from warn to block in `src/aegish/llm_client.py` (AC: 1)
  - [x] 1.1: Replace `_validation_failed_response()` call for oversized commands with a direct block response `{"action": "block", "reason": "...", "confidence": 1.0}`
  - [x] 1.2: Ensure the reason message includes both the command length and the MAX_COMMAND_LENGTH limit
- [x] Task 2: Update existing tests in `tests/test_llm_client.py` (AC: 1, 2)
  - [x] 2.1: Update `TestCommandLengthValidation.test_long_command_warns()` — rename to `test_long_command_blocked()` and assert `result["action"] == "block"` and `result["confidence"] == 1.0`
  - [x] 2.2: Verify `test_max_length_command_allowed()` still passes (no change needed — it tests the boundary at exactly 4096)
  - [x] 2.3: Add test for reason message containing both actual length and limit

## Dev Notes

### Critical Implementation Details

**File to modify: `src/aegish/llm_client.py` ONLY (production code).** One function changes: `query_llm()` at lines 288-297.

**Current code (llm_client.py:288-297):**
```python
if len(command) > MAX_COMMAND_LENGTH:
    logger.warning(
        "Command exceeds maximum length (%d > %d)",
        len(command),
        MAX_COMMAND_LENGTH,
    )
    return _validation_failed_response(
        f"Command too long ({len(command)} chars)"
    )
```

`_validation_failed_response()` returns `{"action": "warn", "reason": "Could not validate command: ...", "confidence": 0.0}`.

**Target code after this story:**
```python
if len(command) > MAX_COMMAND_LENGTH:
    logger.warning(
        "Command exceeds maximum length (%d > %d)",
        len(command),
        MAX_COMMAND_LENGTH,
    )
    return {
        "action": "block",
        "reason": f"Command too long ({len(command)} chars, limit {MAX_COMMAND_LENGTH})",
        "confidence": 1.0,
    }
```

**The change is 4 lines** — replacing the `_validation_failed_response()` call with a direct block dict. The logger.warning line stays unchanged.

### Why Block Instead of Warn

**DD-07 (Design Decision):** Block unconditionally. No legitimate use case for 4KB+ single-line interactive commands. Scripts should be run via `bash script.sh`, not pasted as one-liners. An attacker could pad a malicious command with whitespace/comments to exceed the LLM's context window, causing a validation failure that currently defaults to warn → user confirms → command executes. [Source: docs/security-hardening-scope.md#DD-07, BYPASS-05]

### Why Not Use _validation_failed_response()

`_validation_failed_response()` is designed for cases where validation **cannot be completed** (all models failed, no API keys). Oversized commands are a **deterministic security decision**, not a validation failure. They should be blocked with full confidence (1.0), not warned with zero confidence (0.0). This distinction is important:
- **warn + confidence=0.0**: "I couldn't check this, you decide"
- **block + confidence=1.0**: "This is definitely not allowed"

### Relationship to Story 7.4 (Configurable Fail-Mode)

Story 7.4 (backlog) will change `_validation_failed_response()` to use the configurable fail mode (block in safe mode, warn in open mode). Since this story removes the oversized-command path from using `_validation_failed_response()`, there is **zero interaction** between these stories. Oversized commands are always blocked regardless of fail mode.

### Compatibility with Existing Features

| Feature | Impact | Notes |
|---------|--------|-------|
| envsubst expansion (Story 7.1) | No impact | Expansion happens inside `_try_model()` → `_get_messages_for_model()`, which is never reached for oversized commands |
| bashlex check (Story 7.2) | No impact | bashlex runs in `validator.py` before `query_llm()` is called, but oversized commands would still need to pass the length check in `query_llm()` |
| Command delimiters (Story 7.3) | No impact | Delimiters are in `_get_messages_for_model()`, never reached for oversized commands |
| Provider allowlist (Story 9.1) | No impact | Provider filtering happens after the length check |
| Health check (Story 9.2) | No impact | Health check sends "echo hello" (10 chars), nowhere near 4096 |

### Existing Tests to Update

**`tests/test_llm_client.py` — `TestCommandLengthValidation` class (lines 314-348):**

1. `test_long_command_warns` (line 317) — **RENAME AND UPDATE:**
   - Rename to `test_long_command_blocked`
   - Change `assert result["action"] == "warn"` → `assert result["action"] == "block"`
   - Change `assert result["confidence"] == 0.0` → `assert result["confidence"] == 1.0`
   - The `"too long"` substring check in reason can stay (the new reason still contains "too long")
   - The `mock_completion.assert_not_called()` check stays (LLM is not called for oversized commands)

2. `test_max_length_command_allowed` (line 334) — **NO CHANGE:** Tests boundary at exactly 4096. This test already passes and verifies that exactly-max-length commands proceed to LLM.

3. **NEW TEST:** `test_long_command_reason_includes_lengths` — Verify reason includes both actual length and limit.

**Example test updates:**
```python
def test_long_command_blocked(self):
    """FR38: Commands exceeding MAX_COMMAND_LENGTH are blocked."""
    from aegish.llm_client import MAX_COMMAND_LENGTH

    long_command = "x" * (MAX_COMMAND_LENGTH + 1)
    with mock_providers(["openai"]):
        with patch("aegish.llm_client.completion") as mock_completion:
            result = query_llm(long_command)

            # Should NOT call the LLM
            mock_completion.assert_not_called()

            # Should block with full confidence
            assert result["action"] == "block"
            assert result["confidence"] == 1.0
            assert "too long" in result["reason"].lower()

def test_long_command_reason_includes_lengths(self):
    """Block reason includes actual length and limit."""
    from aegish.llm_client import MAX_COMMAND_LENGTH

    long_command = "x" * 5000
    with mock_providers(["openai"]):
        with patch("aegish.llm_client.completion") as mock_completion:
            result = query_llm(long_command)

            assert "5000" in result["reason"]
            assert str(MAX_COMMAND_LENGTH) in result["reason"]
```

### Testing Patterns

Tests follow existing patterns in `tests/test_llm_client.py`:
- Use `mock_providers()` context manager from `tests/utils.py`
- Use `unittest.mock.patch` for `aegish.llm_client.completion`
- Import `MAX_COMMAND_LENGTH` from `aegish.llm_client`

### Project Structure Notes

- Only `src/aegish/llm_client.py` is modified (production code) — no new files
- Tests updated in existing `tests/test_llm_client.py` — no new test files
- Alignment with module responsibilities: llm_client.py handles command validation including pre-checks [Source: docs/architecture.md#Module Responsibilities]
- Data flow unchanged: `shell.py -> validator.py -> llm_client.py` [Source: docs/architecture.md#Data Flow]

### Impact on Shell Behavior

When a user enters an oversized command:
- **Before (current):** `WARNING: Could not validate command: Command too long (5000 chars)` + `Proceed anyway? [y/N]:`
- **After (this story):** `BLOCKED: Command too long (5000 chars, limit 4096)` — no confirmation prompt, command does not execute

This aligns with the shell.py behavior at line 133-135 where `action == "block"` prints `BLOCKED: {reason}` and sets `last_exit_code = EXIT_BLOCKED` without any user prompt.

### Git Intelligence

Recent commits are blog post improvements and epic additions (non-code). The latest code changes are from Stories 7.1, 7.2, and 7.3 (all in llm_client.py and validator.py). The codebase is stable.

### References

- [Source: docs/epics.md#Story 7.5] - Story definition and acceptance criteria (FR38)
- [Source: docs/security-hardening-scope.md#BYPASS-05] - Command length overflow attack vector
- [Source: docs/security-hardening-scope.md#DD-07] - Block unconditionally, no legitimate 4KB+ commands
- [Source: docs/architecture.md#Module Responsibilities] - llm_client.py handles LLM validation
- [Source: docs/architecture.md#Data Flow] - shell.py -> validator.py -> llm_client.py
- [Source: src/aegish/llm_client.py:288-297] - Current oversized command handling
- [Source: src/aegish/llm_client.py:515-530] - `_validation_failed_response()` returns warn
- [Source: tests/test_llm_client.py:314-348] - `TestCommandLengthValidation` tests to update
- [Source: docs/stories/7-3-wrap-commands-in-delimiters-for-prompt-injection-defense.md] - Previous story patterns

## Dev Agent Record

### Context Reference

<!-- Story context created by create-story workflow -->

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

None — clean implementation, no debugging required.

### Completion Notes List

- Replaced `_validation_failed_response()` call in `query_llm()` with direct block dict: `{"action": "block", "reason": "Command too long ({len} chars, limit {MAX})", "confidence": 1.0}`
- Renamed `test_long_command_warns` to `test_long_command_blocked` with updated assertions (action=block, confidence=1.0)
- Added `test_long_command_reason_includes_lengths` verifying reason contains actual length (5000) and limit (4096)
- Verified `test_max_length_command_allowed` boundary test still passes unchanged
- Full test suite: 702/702 passed, 0 regressions

### File List

- `src/aegish/llm_client.py` — Modified: replaced warn response with block response for oversized commands (lines 295-298)
- `tests/test_llm_client.py` — Modified: renamed test, updated assertions, added new test for reason message content
- `docs/stories/7-5-block-oversized-commands.md` — Modified: task checkboxes, Dev Agent Record, status
- `docs/stories/sprint-status.yaml` — Modified: story status updated

## Senior Developer Review (AI)

**Reviewer:** guido (2026-02-13)
**Outcome:** Approved with minor fixes applied

### Findings

| # | Severity | Description | Resolution |
|---|----------|-------------|------------|
| H1 | HIGH | 7 tests fail in full suite (test pollution from Story 7-4's partial `_validation_failed_response` change) | NOT FIXED — belongs to Story 7-4 scope |
| M1 | MEDIUM | `query_llm()` docstring didn't document oversized→block early exit | FIXED — added docstring note |
| L1 | LOW | `test_long_command_reason_includes_lengths` missing `assert_not_called()` | FIXED — added assertion |
| L2 | LOW | Oversized tests use unnecessary `mock_providers`/`mock_completion` setup | NOT FIXED — harmless, risky during parallel changes |
| L3 | LOW | No boundary-1 test (4095 chars) | FIXED — added `test_below_max_length_command_allowed` |

### AC Verification

- AC1: IMPLEMENTED — `llm_client.py:289-299` blocks >4096 chars with confidence 1.0, reason includes both lengths
- AC2: IMPLEMENTED — strict `>` means exactly 4096 chars proceed to LLM

### Notes

- Story 7-5's 3 original tests + 1 new test all pass in isolation and full suite context
- The 7 full-suite failures are from Story 7-4 changing `_validation_failed_response()` to call `get_fail_mode()` (defaults to "safe"→"block") without updating all tests that don't use `mock_providers`
- Story 7-5's oversized path returns directly at line 295 and never reaches `_validation_failed_response()`, so 7-4's changes have zero impact on 7-5 correctness

## Change Log

- 2026-02-13: Implemented Story 7.5 — oversized commands (>4096 chars) now return block with confidence 1.0 instead of warn with confidence 0.0. Prevents padding attack bypass (BYPASS-05/DD-07).
- 2026-02-13: Code review — fixed docstring (M1), added missing assertion (L1), added boundary-1 test (L3). H1 deferred to Story 7-4.
