# Story 3.1: API Credential Configuration

**Epic:** Epic 3 - User Control & Configuration
**Status:** done
**Priority:** must-have

---

## User Story

As a **sysadmin**,
I want **to configure LLM API credentials securely**,
So that **aegish can validate my commands**.

---

## Acceptance Criteria

### AC1: Load Credentials from Environment Variables
**Given** environment variables are set (OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY)
**When** aegish starts
**Then** credentials are loaded from environment variables

### AC2: Clear Error Message When No API Keys Configured
**Given** no API keys are configured
**When** aegish starts
**Then** a clear error message explains how to configure credentials

### AC3: Credentials Not Exposed in Logs or Error Messages
**Given** API keys are configured
**When** I inspect running processes or environment
**Then** credentials are not exposed in plain text in logs or error messages

---

## Technical Requirements

### Implementation Locations
- **Primary file:** `src/aegish/main.py` - Add startup credential check
- **Secondary file:** `src/aegish/config.py` - Enhance with validation function
- **Test file:** `tests/test_config.py` - New tests for credential validation

### Current State Analysis

**config.py already implements AC1:**
```python
def get_api_key(provider: str) -> str | None:
    """Get the API key for a provider from environment."""
    env_vars = {
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    env_var = env_vars.get(provider.lower())
    if env_var:
        return os.environ.get(env_var)
    return None

def get_available_providers() -> list[str]:
    """Get list of providers with configured API keys."""
    providers = ["openrouter", "openai", "anthropic"]
    return [p for p in providers if get_api_key(p)]
```

**What this story adds:**
1. **AC2:** Clear error message at startup when no credentials are configured
2. **AC3:** Ensure API keys are never logged or exposed in error messages

### Implementation Design

#### config.py Additions

```python
def validate_credentials() -> tuple[bool, str]:
    """Validate that at least one LLM provider credential is configured.

    Returns:
        Tuple of (is_valid, message).
        If valid: (True, "credentials configured message")
        If invalid: (False, "error message with instructions")
    """
    available = get_available_providers()

    if not available:
        return (False, """No LLM API credentials configured.

aegish requires at least one API key to validate commands.

Set one or more of these environment variables:
  export OPENROUTER_API_KEY="your-key-here"
  export OPENAI_API_KEY="your-key-here"
  export ANTHROPIC_API_KEY="your-key-here"

Recommended: Use OpenRouter for LlamaGuard (security-specific model).""")

    return (True, f"Using providers: {', '.join(available)}")
```

#### main.py Modifications

```python
from aegish.config import validate_credentials

@app.command()
def main():
    """Launch aegish interactive shell."""
    # Validate credentials before starting
    is_valid, message = validate_credentials()

    if not is_valid:
        print(f"\nError: {message}\n", file=sys.stderr)
        raise typer.Exit(1)

    exit_code = run_shell()
    raise typer.Exit(exit_code)
```

#### AC3: Credential Security (Already Implemented)

The codebase already handles AC3 correctly:
- `config.py` only returns API key values, never logs them
- `llm_client.py` uses keys via LiteLLM, never logs them
- Error messages in `llm_client.py` only show exception types, not key values

**Verification needed:** Review existing code to confirm no credential exposure.

---

## Tasks / Subtasks

- [x] Task 1: Add `validate_credentials()` function to config.py (AC: #2)
  - [x] 1.1 Create function that returns (bool, str) tuple
  - [x] 1.2 Include clear setup instructions in error message
  - [x] 1.3 Include list of available providers in success message

- [x] Task 2: Integrate credential check in main.py (AC: #2)
  - [x] 2.1 Import validate_credentials
  - [x] 2.2 Call validation before run_shell()
  - [x] 2.3 Exit with code 1 and stderr message if invalid
  - [x] 2.4 Import sys for stderr output

- [x] Task 3: Audit credential security (AC: #3)
  - [x] 3.1 Review config.py for any logging of key values
  - [x] 3.2 Review llm_client.py for any logging of key values
  - [x] 3.3 Review any exception handling that might expose keys
  - [x] 3.4 Document audit results in completion notes

- [x] Task 4: Write unit tests (AC: #1, #2, #3)
  - [x] 4.1 test_validate_credentials_no_keys_returns_false
  - [x] 4.2 test_validate_credentials_one_key_returns_true
  - [x] 4.3 test_validate_credentials_multiple_keys_returns_true
  - [x] 4.4 test_validate_credentials_error_message_includes_instructions
  - [x] 4.5 test_validate_credentials_success_message_lists_providers
  - [x] 4.6 test_main_exits_with_error_when_no_credentials
  - [x] 4.7 test_main_proceeds_when_credentials_available

---

## Dev Notes

### Module Boundaries

This story modifies two existing modules:
- `config.py`: Add validation logic (credential checking is configuration concern)
- `main.py`: Integrate startup validation (CLI entry point responsibility)

Do NOT modify:
- `llm_client.py` - Already handles missing credentials gracefully at runtime
- `shell.py` - Startup validation happens before shell loop begins
- `validator.py` - Not involved in credential management

### Architecture Compliance

- **PEP 8:** Use snake_case for functions (`validate_credentials`)
- **Standard exceptions:** No custom exceptions needed; use return tuples
- **Output format:** Error message to stderr, plain text
- **Exit codes:** 1 for configuration errors (standard Unix convention)

### Testing Pattern

Follow existing test patterns from `tests/test_llm_client.py`:
```python
def test_validate_credentials_no_keys(mocker):
    """AC2: Clear error when no credentials configured."""
    mocker.patch.dict(os.environ, {}, clear=True)

    is_valid, message = validate_credentials()

    assert is_valid is False
    assert "No LLM API credentials configured" in message
    assert "OPENROUTER_API_KEY" in message
```

### Edge Cases

1. **Partial credentials:** If only one provider is configured, that's valid
2. **Invalid key format:** Not validated at startup (API calls will fail later)
3. **Empty string keys:** `os.environ.get()` returns empty string if set but empty - should be treated as not configured

### Implementation Note on Empty Keys

The current `get_api_key()` returns `None` only if the env var is not set. An empty string `""` would be returned if the var is set but empty. This could cause issues - LiteLLM would try to use an empty key.

**Recommendation:** Update `get_api_key()` to treat empty strings as not configured:
```python
def get_api_key(provider: str) -> str | None:
    env_var = env_vars.get(provider.lower())
    if env_var:
        key = os.environ.get(env_var)
        return key if key else None  # Treat empty string as not configured
    return None
```

---

## Project Structure Notes

### Files to Modify
```
src/aegish/
├── config.py      # Add validate_credentials()
└── main.py        # Add startup credential check

tests/
└── test_config.py # Add credential validation tests
```

### Import Requirements
- `main.py` needs: `import sys` (for stderr)
- `main.py` needs: `from aegish.config import validate_credentials`

---

## References

- [Source: docs/epics.md#Story 3.1: API Credential Configuration]
- [Source: docs/architecture.md#LLM Provider Strategy - Environment variables]
- [Source: docs/prd.md#FR16: User can configure LLM API credentials]
- [Source: docs/architecture.md#NFR4: LLM API credentials stored securely]

---

## Previous Story Intelligence

### From Epic 2 Implementation

**Patterns established:**
- `config.py` provides `get_api_key()` and `get_available_providers()` - reuse these
- `llm_client.py` already checks `get_available_providers()` at validation time
- Error handling uses standard Python logging, no custom exception classes
- Tests use `mocker.patch.dict(os.environ, {...})` for env var mocking

**Code style from Epic 2:**
- Plain text output (no emojis, no fancy formatting)
- Functions return tuples or dicts for multi-value returns
- Comprehensive docstrings with Args/Returns
- Type hints on all function signatures

### Existing Credential Handling

**llm_client.py line 76-79:**
```python
available = get_available_providers()
if not available:
    logger.warning("No LLM providers configured")
    return _validation_failed_response("No API keys configured")
```

The LLM client already handles missing credentials at validation time by returning a "warn" response. Story 3.1 adds the **startup check** so users get clear feedback immediately, not after typing their first command.

---

## Developer Guardrails

### MUST Follow

1. **Return tuple from validate_credentials()** - Pattern: `(bool, str)` for valid/message
2. **Write to stderr for errors** - Use `print(..., file=sys.stderr)`
3. **Exit code 1 for credential errors** - Standard Unix convention
4. **Keep error message actionable** - Include exact env var names and example
5. **Don't log API key values** - Only log presence/absence

### MUST NOT

1. **Don't modify llm_client.py** - It already handles missing credentials at runtime
2. **Don't create config files** - Environment variables only for MVP
3. **Don't validate key format** - Let the API calls fail if keys are invalid
4. **Don't add retry logic for startup** - User must fix credentials manually
5. **Don't log which specific key is missing** - Just report "no credentials"

### Testing Requirements

All tests should:
- Mock environment variables using `mocker.patch.dict(os.environ, {...})`
- Test both positive (credentials present) and negative (no credentials) cases
- Verify error message content includes setup instructions
- Verify success message lists available providers

---

## Test Requirements

### Unit Tests for config.py

| Test | Description | AC |
|------|-------------|-----|
| test_validate_credentials_no_keys_returns_false | No env vars set, returns (False, error_message) | #2 |
| test_validate_credentials_one_key_returns_true | One provider configured, returns (True, message) | #1 |
| test_validate_credentials_all_keys_returns_true | All providers configured, returns (True, message) | #1 |
| test_validate_credentials_error_has_instructions | Error message includes env var names | #2 |
| test_validate_credentials_success_lists_providers | Success message includes provider names | #1 |
| test_get_api_key_empty_string_returns_none | Empty env var treated as not configured | #1 |

### Integration Tests for main.py

| Test | Description | AC |
|------|-------------|-----|
| test_main_exits_on_no_credentials | No credentials -> exit code 1 | #2 |
| test_main_error_to_stderr | Error message goes to stderr | #2 |
| test_main_proceeds_with_credentials | Valid credentials -> shell starts | #1 |

---

## Definition of Done

- [x] `config.py` has `validate_credentials()` function
- [x] `main.py` checks credentials before starting shell
- [x] Clear error message with setup instructions when no credentials
- [x] Exit code 1 when credentials missing
- [x] Error output goes to stderr
- [x] Empty string env vars treated as not configured
- [x] Security audit confirms no credential exposure in logs
- [x] All unit tests pass
- [x] All tests cover acceptance criteria

---

## Dependencies

- **Blocked by:** None (first story in Epic 3)
- **Blocks:** Story 3.2 (Warning Override), Story 3.3 (Sensible Defaults)

---

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No debug issues encountered.

### Completion Notes List

**Task 1 Complete:** Added `validate_credentials()` function to config.py that:
- Returns tuple (bool, str) as specified
- Error message includes all three env var names (OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY)
- Error message includes export examples for setup instructions
- Recommends OpenRouter for LlamaGuard
- Success message lists all configured providers

**Task 1 Bonus:** Fixed `get_api_key()` to treat empty/whitespace-only strings as not configured (edge case from Dev Notes).

**Task 2 Complete:** Integrated credential validation in main.py:
- Added `import sys` for stderr output
- Added `from aegish.config import validate_credentials` import
- Credential check happens before `run_shell()` is called
- Exits with code 1 and prints error to stderr if no credentials

**Task 3 Complete - Security Audit Results:**
- **config.py:** No logging. `get_api_key()` returns values but never logs them. `validate_credentials()` only returns provider names.
- **llm_client.py:** All logging statements log provider names, exception types, or sanitized messages - never API key values. Specifically checked lines 97, 109, 124, 128, 137, 205, 221, 263.
- **main.py:** Error message only contains instructions, not key values.
- **shell.py:** Only logs user-facing validation results.
- **Conclusion:** AC3 satisfied - no credential exposure in logs or error messages.

**Task 4 Complete:** Created tests/test_config.py with 12 tests:
- 5 tests for validate_credentials() covering no keys, one key, multiple keys, error message content, success message content
- 3 tests for get_api_key() empty string handling
- 1 test for empty key not counting as configured
- 3 integration tests for main.py credential validation (exit code, error message, shell proceeds)

**Full Test Suite:** 195 tests pass with no regressions.

### File List

**Modified:**
- src/aegish/config.py - Added validate_credentials(), fixed get_api_key() empty string handling
- src/aegish/main.py - Added startup credential validation with stderr error output
- tests/test_config.py - Refactored: module-level imports, added edge case tests, renamed to match spec

**Created:**
- tests/test_config.py - Credential validation tests for config.py
- tests/test_main.py - CLI entry point tests (moved from test_config.py + new stderr verification)

### Change Log

- 2026-02-01: Implemented Story 3.1 - API Credential Configuration
  - Added validate_credentials() function for startup credential check
  - Fixed get_api_key() to treat empty strings as not configured
  - Integrated credential validation in main.py CLI entry point
  - Security audit confirmed no credential exposure in logs
  - Added 12 new tests in tests/test_config.py
  - All 195 tests pass

- 2026-02-01: Code Review Fixes (Senior Developer Review)
  - **H1 Fixed:** Added subprocess-based test to properly verify stderr output separation
  - **H2 Fixed:** Added empty string tests for all three providers (openrouter, openai, anthropic)
  - **M1 Fixed:** Refactored test_config.py to use module-level imports
  - **M2 Fixed:** Renamed test to match spec (test_validate_credentials_all_keys_returns_true)
  - **M3 Fixed:** Moved main.py tests to new tests/test_main.py
  - **M4 Fixed:** Added test for get_api_key with invalid provider name
  - Added bonus tests: case-insensitivity, exit code propagation
  - All 202 tests pass (7 new tests added)
