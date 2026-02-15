# Story 7.8: Unit Tests for Validation Pipeline Hardening

Status: done

## Story

As a **developer**,
I want **comprehensive integration tests for all validation pipeline hardening changes**,
so that **regressions in security hardening are caught immediately**.

## Acceptance Criteria

1. envsubst expansion: `exec $SHELL` produces expanded form with real `$SHELL` value
2. envsubst graceful fallback: expansion skipped if envsubst unavailable (returns None)
3. bashlex detection: `a=ba; b=sh; $a$b` returns WARN with "Variable expansion in command position"
4. bashlex safe: `FOO=bar; echo $FOO` passes through (returns None)
5. bashlex fallback: unparseable command passes through to LLM
6. Command delimiters: user message contains `<COMMAND>` and `</COMMAND>` tags
7. Fail-safe mode: `AEGISH_FAIL_MODE=safe` validation failure returns block
8. Fail-open mode: `AEGISH_FAIL_MODE=open` validation failure returns warn
9. Oversized command: 5000-char command returns BLOCK with confidence 1.0

## Tasks / Subtasks

- [x] Task 1: Create `tests/test_validation_pipeline.py`
  - [x] 1.1: `TestEnvSubstExpansion` - expansion, fallback, no-dollar short-circuit
  - [x] 1.2: `TestBashlexDetection` - var-in-command WARN, argument passthrough, parse-error fallback
  - [x] 1.3: `TestCommandDelimiters` - COMMAND tag wrapping, expansion placement
  - [x] 1.4: `TestFailMode` - safe-mode block, open-mode warn, default-is-safe
  - [x] 1.5: `TestOversizedCommand` - blocking >4096-char, reason with lengths
- [x] Task 2: Run `uv run pytest tests/test_validation_pipeline.py -v` and full suite

## Dev Notes

### Existing Test Coverage

Tests already exist scattered across files. This story creates a **unified integration test file** focusing on cross-feature paths:

| Feature | Existing Tests | File |
|---------|---------------|------|
| envsubst | `TestExpandEnvVars` (8), `TestGetSafeEnv` (6), `TestGetMessagesEnvExpansion` (5) | `test_llm_client.py` |
| bashlex | `TestCheckVariableInCommandPosition` (11), `TestValidateCommandBashlex` (4) | `test_validator.py` |
| Delimiters | `TestCommandDelimiters` (6) | `test_llm_client.py` |
| Fail-mode | `TestFailMode` (6) | `test_llm_client.py` |
| Oversized | `TestCommandLengthValidation` (4) | `test_llm_client.py` |

### Integration Test Priorities

Focus on **cross-feature integration paths**:
1. envsubst + delimiters + LLM flow: command with `$VAR` gets expanded, wrapped in tags, sent to LLM
2. bashlex short-circuit before envsubst: `validate_command("a=ba; b=sh; $a$b")` returns WARN without invoking envsubst/LLM
3. Oversized short-circuit: `validate_command("x" * 5000)` returns block without bashlex/envsubst
4. Fail-mode + provider failure end-to-end: `validate_command("ls")` with providers down returns block/warn
5. Sensitive variable filtering: `_get_safe_env()` strips API keys

### Key Implementation Details

- `MAX_COMMAND_LENGTH = 4096` in `src/aegish/llm_client.py`
- `_expand_env_vars()` returns None when envsubst unavailable
- `_check_variable_in_command_position()` returns WARN dict or None
- `_validation_failed_response()` checks `get_fail_mode()` for block vs warn
- `_get_messages_for_model()` wraps command in `<COMMAND>` tags
- Use mocking patterns from `tests/utils.py`: `MockResponse`, `mock_providers`
- No actual LLM calls - all mocked

### Files

- Create: `tests/test_validation_pipeline.py`
- No modifications to existing files
