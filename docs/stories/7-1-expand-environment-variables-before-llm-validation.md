# Story 7.1: Expand Environment Variables Before LLM Validation

Status: Done

## Story

As a **security engineer**,
I want **environment variables in commands expanded via `envsubst` before sending to the LLM**,
so that **the LLM sees what `$SHELL`, `$HOME`, etc. actually resolve to and can detect threats hidden by variable indirection**.

## Acceptance Criteria

1. **Given** a command containing environment variable references (e.g., `exec $SHELL`)
   **When** the command is prepared for LLM validation
   **Then** `envsubst` is used to produce an expanded version (e.g., `exec /bin/bash`)
   **And** the LLM receives both the raw command and the expanded version in the user message

2. **Given** a command with no variable references (e.g., `ls -la`)
   **When** the command is prepared for LLM validation
   **Then** no expansion note is added (raw and expanded are identical)

3. **Given** `envsubst` is not available on the system
   **When** the command is prepared
   **Then** expansion is skipped gracefully and the raw command is sent to the LLM
   **And** a debug-level log message notes that envsubst is unavailable

4. **Given** a command with command substitution (e.g., `$(rm -rf /)`)
   **When** `envsubst` processes it
   **Then** the command substitution is NOT executed (envsubst only expands `$VAR` and `${VAR}`, nothing else)

## Tasks / Subtasks

- [x] Task 1: Implement `_expand_env_vars()` in `src/aegish/llm_client.py` (AC: 1, 2, 3, 4)
  - [x] 1.1: Add `import subprocess` to llm_client.py
  - [x] 1.2: Implement `_expand_env_vars(command: str) -> str | None` that calls `subprocess.run(["envsubst"], input=command, capture_output=True, text=True)`
  - [x] 1.3: Return expanded stdout on success, `None` on `FileNotFoundError` or other subprocess errors
  - [x] 1.4: Log at `debug` level when envsubst is unavailable; do NOT log at warning (it's an expected condition on some systems)
- [x] Task 2: Update `_get_messages_for_model()` to include expanded version (AC: 1, 2)
  - [x] 2.1: Call `_expand_env_vars(command)` inside `_get_messages_for_model()`
  - [x] 2.2: If expanded is not None AND differs from raw command, append `\n\nAfter environment expansion: {expanded}` to the user message content
  - [x] 2.3: If expanded is None (envsubst unavailable) or identical to raw, send just the raw command (no expansion note)
- [x] Task 3: Write unit tests in `tests/test_llm_client.py` (AC: 1, 2, 3, 4)
  - [x] 3.1: Test `_expand_env_vars()` returns expanded string when envsubst succeeds
  - [x] 3.2: Test `_expand_env_vars()` returns `None` when envsubst not found (`FileNotFoundError`)
  - [x] 3.3: Test `_get_messages_for_model()` includes expansion note when variables are present
  - [x] 3.4: Test `_get_messages_for_model()` omits expansion note when no variables present
  - [x] 3.5: Test `_get_messages_for_model()` omits expansion note when envsubst unavailable
  - [x] 3.6: Test that command substitution syntax is NOT executed by envsubst

## Dev Notes

### Critical Implementation Details

**File to modify: `src/aegish/llm_client.py` ONLY.** This story adds environment variable expansion to the LLM message construction. No changes to `validator.py`, `config.py`, `executor.py`, or `shell.py`.

**Current `_get_messages_for_model()` (line 328-340):**
```python
def _get_messages_for_model(command: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Validate this command: {command}"},
    ]
```

**Target `_get_messages_for_model()` after this story:**
```python
def _get_messages_for_model(command: str) -> list[dict]:
    content = f"Validate this command: {command}"
    expanded = _expand_env_vars(command)
    if expanded is not None and expanded != command:
        content += f"\n\nAfter environment expansion: {expanded}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]
```

**New `_expand_env_vars()` function:**
```python
def _expand_env_vars(command: str) -> str | None:
    """Expand environment variables in a command using envsubst.

    Only expands $VAR and ${VAR} patterns. Does NOT execute command
    substitutions like $(...) or backticks.

    Returns:
        Expanded command string, or None if envsubst is unavailable.
    """
    try:
        result = subprocess.run(
            ["envsubst"],
            input=command,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.rstrip("\n")
        logger.debug("envsubst returned non-zero exit code: %d", result.returncode)
        return None
    except FileNotFoundError:
        logger.debug("envsubst not available on this system")
        return None
    except subprocess.TimeoutExpired:
        logger.debug("envsubst timed out")
        return None
    except Exception as e:
        logger.debug("envsubst failed: %s", e)
        return None
```

### Why This Goes in llm_client.py, Not validator.py

The envsubst expansion enriches the LLM's context — it does NOT make a security decision. The expanded version is included in the user message so the LLM can see the resolved values. This is fundamentally different from the bashlex check (in validator.py) which short-circuits with a WARN before the LLM is consulted. The expansion belongs in the message-construction function `_get_messages_for_model()`.

### Relationship to Other Epic 7 Stories

| Story | Relationship | Notes |
|-------|-------------|-------|
| 7.2 (in review) | Complementary | bashlex catches within-command variable construction (`a=ba; b=sh; $a$b`). envsubst expands environment variables (`$SHELL` → `/bin/bash`). envsubst CANNOT expand `$a` when `a` is set within the command — it only knows environment variables. |
| 7.3 (backlog) | Compatible | Story 7.3 will wrap commands in `<COMMAND>` tags. The expansion note should be placed AFTER the command block, not inside it. The current implementation (`content += "\n\nAfter environment expansion: ..."`) is compatible — Story 7.3 will restructure the content but the expansion note pattern stays the same. |
| 7.7 (done) | Noted | Story 7.7 confirmed: envsubst is a **system package** (`gettext-base`), NOT a Python dependency. Do NOT add anything to pyproject.toml. |

### envsubst System Dependency

`envsubst` is provided by the `gettext-base` package:
- **Debian/Ubuntu:** `sudo apt-get install gettext-base` (often pre-installed)
- **Alpine:** `apk add gettext`
- **macOS:** Pre-installed with Xcode or `brew install gettext`
- **This is NOT a Python dependency** — do not modify pyproject.toml

### How envsubst Works

envsubst reads from stdin, replaces `$VAR` and `${VAR}` with values from the process environment, and writes to stdout. It does NOT:
- Execute command substitutions `$(...)`
- Execute backtick substitutions `` `...` ``
- Perform arithmetic expansion `$((..))`
- Evaluate any code — it is purely a string substitution tool

**Example:**
```bash
$ echo 'exec $SHELL' | envsubst
exec /bin/bash

$ echo 'a=ba; b=sh; $a$b' | envsubst
a=ba; b=sh;              # $a and $b are empty (not in environment)

$ echo '$(rm -rf /)' | envsubst
$(rm -rf /)              # Command substitution is NOT executed
```

### Security Context

This story addresses **BYPASS-01 (Prompt Injection)** and **BYPASS-15 (Pre-Expansion vs Post-Expansion Gap)**:

- **BYPASS-15:** Commands like `exec $SHELL` look harmless as raw strings, but `$SHELL` typically resolves to `/bin/bash`. Without expansion, the LLM might allow the command. With expansion, the LLM sees `exec /bin/bash` and correctly blocks it.
- **BYPASS-01:** The envsubst expansion provides additional context that helps the LLM make better decisions, complementing the `<COMMAND>` delimiters added by Story 7.3.

**Key constraint: SYSTEM_PROMPT is frozen.** The benchmark has been run against the current system prompt. Only the user message is modified (DD-03). [Source: docs/security-hardening-scope.md#DD-03]

### Subprocess Import Note

`subprocess` is NOT currently imported in llm_client.py. It IS imported in executor.py. Add `import subprocess` at the top of llm_client.py alongside the existing imports.

### Testing Patterns

Tests follow the existing patterns in `tests/test_llm_client.py`:
- Use `unittest.mock.patch` to mock `subprocess.run` for envsubst calls
- Use `MockResponse` and `mock_providers()` from `tests/utils.py` for LLM calls
- Add new tests to existing test file — do NOT create a separate test file

**Key test scenarios:**

1. **envsubst succeeds with expansion:** Mock `subprocess.run` to return expanded output. Verify user message includes expansion note.
2. **envsubst succeeds, no change:** Mock `subprocess.run` to return same string. Verify user message does NOT include expansion note.
3. **envsubst not found:** Mock `subprocess.run` to raise `FileNotFoundError`. Verify user message has no expansion note, no errors raised.
4. **envsubst timeout:** Mock `subprocess.run` to raise `subprocess.TimeoutExpired`. Verify graceful fallback.
5. **Command substitution safety:** Use REAL envsubst (if available) to verify `$(rm -rf /)` is not executed. This can be a conditional test that skips if envsubst is not installed.

**Example test for expansion in user message:**
```python
def test_user_message_includes_expansion(self):
    """AC1: Expanded version included when variables are present."""
    with patch("aegish.llm_client.subprocess") as mock_subprocess:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "exec /bin/bash"
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

        messages = _get_messages_for_model("exec $SHELL")
        user_content = messages[1]["content"]
        assert "exec $SHELL" in user_content
        assert "After environment expansion: exec /bin/bash" in user_content
```

### Project Structure Notes

- Only `src/aegish/llm_client.py` is modified — no new files
- Tests added to existing `tests/test_llm_client.py`
- Alignment with module responsibilities: llm_client.py handles LLM message construction [Source: docs/architecture.md#Module Responsibilities]
- Data flow unchanged: `shell.py → validator.py → llm_client.py` [Source: docs/architecture.md#Data Flow]

### Git Intelligence

Recent commits are blog post improvements and epic additions (non-code). The latest code changes are from Story 7.7 (bashlex dependency) and Story 7.2 (bashlex integration in validator.py). The codebase is stable — no conflicting changes expected.

### References

- [Source: docs/epics.md#Story 7.1] - Story definition and acceptance criteria (FR40)
- [Source: docs/security-hardening-scope.md#BYPASS-01] - Prompt injection via command input
- [Source: docs/security-hardening-scope.md#BYPASS-15] - Pre-expansion vs post-expansion gap
- [Source: docs/security-hardening-scope.md#DD-03] - Command delimiters in user message, not system prompt
- [Source: docs/security-hardening-scope.md#DD-09] - envsubst + bashlex over regex heuristics
- [Source: docs/architecture.md#Module Responsibilities] - llm_client.py handles LLM API interaction
- [Source: docs/architecture.md#Data Flow] - shell.py → validator.py → llm_client.py
- [Source: docs/stories/7-7-add-new-dependencies.md] - Confirmed envsubst is system package, not Python dependency
- [Source: docs/stories/7-2-detect-variable-in-command-position-via-bashlex.md] - Complementary bashlex check in validator.py
- [Source: src/aegish/llm_client.py:328-340] - Current `_get_messages_for_model()` implementation
- [Source: src/aegish/llm_client.py:14] - Existing imports (json, logging, litellm) — add subprocess

## Dev Agent Record

### Context Reference

<!-- Story context created by create-story workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

No debug issues encountered.

### Completion Notes List

- Implemented `_expand_env_vars()` function that calls `envsubst` via subprocess to expand `$VAR` and `${VAR}` patterns without executing command substitutions
- Updated `_get_messages_for_model()` to include expanded version in user message when expansion differs from raw command
- All error paths (FileNotFoundError, TimeoutExpired, non-zero exit, generic exceptions) return None gracefully with debug-level logging
- Added 12 new tests: 7 for `_expand_env_vars()` (success, not found, non-zero exit, timeout, generic error, trailing newline strip, real envsubst command substitution safety) and 5 for `_get_messages_for_model()` env expansion (includes expansion, omits when identical, omits when unavailable, system message unchanged, structure preserved)
- All 4 acceptance criteria verified: AC1 (expansion in user message), AC2 (no note when identical), AC3 (graceful skip when envsubst missing), AC4 (command substitution not executed)
- Full test suite: 626 passed, 4 failed (pre-existing benchmark plot tests unrelated to this story)
- **Review fixes (2026-02-13):** Added `$` pre-check to skip subprocess for commands without variables (M1), added `_get_safe_env()` to filter sensitive env vars from envsubst (M2), added 10 new tests (subprocess arg verification, empty string, safe env filtering x6, no-dollar-sign skip, integration test)

### Change Log

- 2026-02-13: Implemented environment variable expansion before LLM validation (Story 7.1)
- 2026-02-13: Code review fixes — added `$` pre-check (M1), sensitive env var filtering via `_get_safe_env()` (M2), 10 new tests, fixed doc test count (L1)

### File List

- src/aegish/llm_client.py (modified: added `import subprocess`, `import os`, `_expand_env_vars()`, `_get_safe_env()`, `_SENSITIVE_VAR_PATTERNS`, updated `_get_messages_for_model()`)
- tests/test_llm_client.py (modified: added `TestExpandEnvVars`, `TestGetSafeEnv`, `TestGetMessagesEnvExpansion`, `TestQueryLLMEnvExpansionIntegration` test classes, 22 total new tests)
- docs/stories/sprint-status.yaml (modified: story status updated)
- docs/stories/7-1-expand-environment-variables-before-llm-validation.md (modified: tasks marked complete, dev agent record updated, review fixes applied)
