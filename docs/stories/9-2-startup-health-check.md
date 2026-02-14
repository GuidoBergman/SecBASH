# Story 9.2: Startup Health Check

**Epic:** Epic 9 - Environment Variable Integrity
**Status:** done
**Priority:** High
**FR:** FR49
**NFR Assessment:** BYPASS-04 (Environment Variable Poisoning)
**Design Decision:** DD-10 (Provider allowlist + health check + startup warnings)

---

## User Story

As a **sysadmin**,
I want **aegish to verify that the primary model responds correctly at startup**,
So that **I know immediately if my API keys are invalid or the model is misconfigured**.

---

## Acceptance Criteria

### AC1: Successful Health Check
**Given** aegish starts with valid API keys
**When** the health check runs
**Then** a test validation call (`echo hello` -> should return "allow") is made to the primary model
**And** if it succeeds, startup continues normally with no additional output

### AC2: Failed Health Check Warns but Continues
**Given** aegish starts with an invalid API key or misconfigured model
**When** the health check fails
**Then** a visible warning is printed: `WARNING: Health check failed - primary model did not respond correctly. Operating in degraded mode.`
**And** aegish continues with fallback models (does NOT exit or crash)

### AC3: Health Check Timeout
**Given** the health check adds latency
**When** it runs at startup
**Then** it uses a short timeout (5 seconds) to avoid blocking startup for too long
**And** if the timeout is exceeded, it prints the warning from AC2 and continues

### AC4: Health Check Tests Primary Model Only
**Given** the model chain may have multiple models (primary + fallbacks)
**When** the health check runs
**Then** it tests ONLY the primary model, not the full fallback chain
**And** this ensures the check is fast and specifically validates the primary configuration

### AC5: Health Check Validates Response Content
**Given** the health check sends `echo hello`
**When** the response is received
**Then** it verifies the response contains `action: "allow"` (a correct classification)
**And** a response of "warn" or "block" for `echo hello` is treated as a health check failure

---

## Tasks / Subtasks

- [x] Task 1: Add `health_check()` function to `llm_client.py` (AC: #1, #2, #3, #4, #5)
  - [x] 1.1 Create `health_check() -> tuple[bool, str]` function
  - [x] 1.2 Send test command `echo hello` to primary model only (not full fallback chain)
  - [x] 1.3 Use `litellm.completion()` directly with a 5-second timeout
  - [x] 1.4 Verify response parses to `action: "allow"` — return `(True, "")` if so
  - [x] 1.5 On any failure (API error, timeout, wrong action, parse failure) return `(False, "reason")`
  - [x] 1.6 Catch all exceptions — never crash, always return gracefully

- [x] Task 2: Integrate health check into startup flow in `shell.py` (AC: #1, #2)
  - [x] 2.1 Import `health_check` from `llm_client`
  - [x] 2.2 Call `health_check()` after the startup banner but before the shell loop
  - [x] 2.3 On success: no output (silent pass)
  - [x] 2.4 On failure: print `WARNING: Health check failed - {reason}. Operating in degraded mode.`

- [x] Task 3: Write unit tests (AC: all)
  - [x] 3.1 Test `health_check()` returns `(True, "")` when primary model returns allow for "echo hello"
  - [x] 3.2 Test `health_check()` returns `(False, reason)` when primary model returns block/warn
  - [x] 3.3 Test `health_check()` returns `(False, reason)` on API error (ConnectionError)
  - [x] 3.4 Test `health_check()` returns `(False, reason)` on timeout
  - [x] 3.5 Test `health_check()` returns `(False, reason)` on parse failure (malformed JSON)
  - [x] 3.6 Test `health_check()` uses primary model only (not fallback chain)
  - [x] 3.7 Test `health_check()` never raises exceptions
  - [x] 3.8 Test startup displays warning on health check failure
  - [x] 3.9 Test startup continues after health check failure (shell loop still runs)

### Review Follow-ups (AI)
- [ ] [AI-Review][MEDIUM] Extract shared model validation helper to eliminate DRY violation between `health_check()` and `query_llm()` in `llm_client.py` — same 3-step validation (format, allowlist, API key) is duplicated at lines 220-233 and 301-320. Deferred from auto-fix due to `query_llm` control flow complexity (allowlist rejection tracking, different log levels). [src/aegish/llm_client.py]

---

## Dev Notes

### Current Implementation State

**`llm_client.py`** (lines 1-456) has:
- `query_llm(command)` (line 200): Full model chain with fallback — **DO NOT use this for health check** (it tries all models, adds latency, and masks primary model failures)
- `_try_model(command, model)` (line 304): Sends a command to a single model — **useful for health check** (direct model call)
- `_get_messages_for_model(command)` (line 386): Builds the message list — reusable for health check
- `_parse_response(content)` (line 405): Parses LLM JSON response — reusable for health check
- `SYSTEM_PROMPT` (line 38): System prompt constant — used by `_get_messages_for_model()`
- `completion` from litellm (line 19): The LLM API call function
- `get_allowed_providers()` and `validate_model_provider()` imported from config (lines 24-29)

**`config.py`** (lines 1-249) has:
- `get_primary_model()` (line 109): Returns primary model string — **use this in health check**
- `get_api_key(provider)` (line 46): Gets API key for provider — needed to check if key exists before calling
- `get_provider_from_model(model)` (line 170): Extracts provider from model string
- `is_valid_model_string(model)` (line 188): Validates model format
- `validate_model_provider(model)` (line 223): Checks provider against allowlist

**`shell.py`** (lines 1-167) `run_shell()` (line 72):
- Line 82: `init_history()`
- Line 87-96: Startup banner with model chain display
- Line 97: `print("Type 'exit' or press Ctrl+D to quit.\n")`
- Line 99: `while True:` shell loop begins
- **Health check should go between lines 97 and 99** (after banner, before loop)

**`main.py`** (lines 1-58):
- Line 47: `validate_credentials()` — checks API keys exist
- Line 53: `run_shell()` — launches the shell
- **No changes needed here** — health check lives in `shell.py` where it has access to the startup flow

### Implementation Strategy

**Create `health_check()` in `llm_client.py`:**
```python
def health_check() -> tuple[bool, str]:
    """Verify the primary model responds correctly at startup.

    Sends a simple test command ("echo hello") to the primary model
    and verifies it returns action="allow". Uses a 5-second timeout.

    Returns:
        Tuple of (is_healthy, error_message).
        If healthy: (True, "")
        If unhealthy: (False, "description of what went wrong")
    """
```

**Key design decisions:**
1. Call `litellm.completion()` directly with `timeout=5` — do NOT use `query_llm()` or `_try_model()` since they don't have configurable timeout
2. Use `get_primary_model()` to get only the primary model
3. Validate format and provider before calling (same checks as `query_llm()` but only for primary)
4. Parse response with `_parse_response()` and check that `action == "allow"`
5. Wrap everything in try/except — never raise

**Integration in `shell.py`:**
```python
# After startup banner, before shell loop:
from aegish.llm_client import health_check

success, reason = health_check()
if not success:
    print(f"WARNING: Health check failed - {reason}. Operating in degraded mode.")
```

### Why NOT Use `query_llm()` for Health Check

`query_llm()` tries the full model chain with fallback. If the primary model fails, `query_llm()` silently falls through to the fallback and succeeds. This defeats the purpose of the health check, which specifically wants to detect primary model misconfiguration. The health check must call the primary model directly and report its failure, not mask it with a fallback success.

### Where Health Check Goes in Startup Flow

```
main.py:
  validate_credentials()  # Are any API keys set? (existing)
  run_shell()
    ├── init_history()
    ├── print startup banner (model chain)
    ├── health_check()  ← NEW: verify primary model works
    │     └── On failure: print WARNING, continue
    └── while True: shell loop
```

### Previous Story (9.1) Intelligence

**Directly relevant patterns:**
- Provider allowlist validation in `query_llm()` uses `get_allowed_providers()` and `validate_model_provider()` — health check should also validate the primary model's provider before calling
- `mock_providers()` in `tests/utils.py` mocks `get_api_key`, `get_model_chain`, `validate_model_provider`, `get_allowed_providers` — health check tests should mock `get_primary_model`, `get_api_key`, `get_provider_from_model`, `is_valid_model_string`, `validate_model_provider` individually (since health check doesn't use `get_model_chain()`)
- Story 9.1 completion notes: "Extended `get_api_key()` for groq/together_ai/ollama" — health check benefits from this expanded provider support

**Code review lessons from 9.1:**
- Cache allowlist resolution when called in a loop (M3) — health check only calls once, no caching needed
- Test isolation: mock at the right level, ensure env vars don't leak between tests (M4)
- Provider-related functions belong in `config.py`, LLM call functions belong in `llm_client.py`

### Git Intelligence

Recent commits are documentation and epic additions (blog post, new epics). The most recent code changes are from Story 9.1 (provider allowlist). Files `config.py`, `llm_client.py`, `test_config.py`, `test_llm_client.py`, `utils.py` were modified. The codebase is stable for this story.

### Architecture Compliance

- **PEP 8:** `snake_case` function name `health_check()` [Source: docs/architecture.md#Python Conventions]
- **Standard exceptions:** No custom exceptions; health check catches all and returns tuple [Source: docs/architecture.md#Error Handling]
- **Environment variables:** Uses existing `AEGISH_PRIMARY_MODEL` — no new env vars needed [Source: src/aegish/config.py]
- **Logging:** Use `logger.warning()` for failures, `logger.info()` for success [Source: docs/architecture.md#Logging]
- **Module boundaries:** `health_check()` belongs in `llm_client.py` (LLM communication), startup call in `shell.py` (user interaction) [Source: docs/architecture.md#Module Responsibilities]

### Cross-Story Dependencies within Epic 9

- **Story 9.1 (Provider Allowlist):** DONE. Health check should validate provider before calling.
- **Story 9.3 (Non-Default Model Warnings):** Will add warnings for non-default models at startup. Should be placed AFTER health check in startup flow so warnings are grouped logically.
- **Story 9.4 (Unit Tests):** Will add integration-level tests for all Epic 9 features together. This story adds its own unit tests; 9.4 adds cross-feature tests.

### File Structure Requirements

```
src/aegish/
├── config.py          # NO CHANGES (existing functions sufficient)
├── llm_client.py      # ADD: health_check() function
└── shell.py           # MODIFY: call health_check() in run_shell() after banner

tests/
├── test_llm_client.py # ADD: TestHealthCheck class with unit tests
└── utils.py           # NO CHANGES (existing mock_providers not used by health check tests)
```

**No new files needed.** All changes extend existing modules following established patterns.

---

## Testing Requirements

### Unit Tests to Add in `test_llm_client.py`

Follow the existing class-per-function pattern:

```python
class TestHealthCheck:
    """Tests for health_check function (Story 9.2)."""

    def test_health_check_success(self, mocker):
        """AC1: Primary model returns allow for echo hello."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
            "OPENAI_API_KEY": "test-key",
        }, clear=True)
        mock_content = '{"action": "allow", "reason": "Safe echo", "confidence": 0.99}'
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse(mock_content)
            success, reason = health_check()
            assert success is True
            assert reason == ""

    def test_health_check_fails_on_block_response(self, mocker):
        """AC5: Block response for echo hello = health check failure."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
            "OPENAI_API_KEY": "test-key",
        }, clear=True)
        mock_content = '{"action": "block", "reason": "Blocked", "confidence": 0.9}'
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse(mock_content)
            success, reason = health_check()
            assert success is False
            assert "did not respond correctly" in reason.lower() or "unexpected" in reason.lower()

    def test_health_check_fails_on_api_error(self, mocker):
        """AC2: API error results in failed health check."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
            "OPENAI_API_KEY": "test-key",
        }, clear=True)
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.side_effect = ConnectionError("API unreachable")
            success, reason = health_check()
            assert success is False
            assert reason != ""

    def test_health_check_fails_on_timeout(self, mocker):
        """AC3: Timeout results in failed health check."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
            "OPENAI_API_KEY": "test-key",
        }, clear=True)
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.side_effect = TimeoutError("Health check timed out")
            success, reason = health_check()
            assert success is False

    def test_health_check_uses_primary_model_only(self, mocker):
        """AC4: Health check calls only the primary model."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
            "AEGISH_FALLBACK_MODELS": "anthropic/claude-3-haiku-20240307",
            "OPENAI_API_KEY": "test-key",
            "ANTHROPIC_API_KEY": "test-key",
        }, clear=True)
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.99}'
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse(mock_content)
            health_check()
            # Should only call once (primary model)
            assert mock_completion.call_count == 1
            assert mock_completion.call_args.kwargs["model"] == "openai/gpt-4"

    def test_health_check_never_raises(self, mocker):
        """AC2: Health check catches all exceptions, never crashes."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
            "OPENAI_API_KEY": "test-key",
        }, clear=True)
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.side_effect = RuntimeError("Unexpected catastrophic error")
            success, reason = health_check()
            assert success is False
            # Key: no exception raised

    def test_health_check_no_api_key(self, mocker):
        """AC2: No API key for primary model = failed health check."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
            # No OPENAI_API_KEY
        }, clear=True)
        success, reason = health_check()
        assert success is False
        assert "api key" in reason.lower() or "no api" in reason.lower()

    def test_health_check_malformed_json_response(self, mocker):
        """AC5: Malformed JSON response = health check failure."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
            "OPENAI_API_KEY": "test-key",
        }, clear=True)
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse("not valid json at all")
            success, reason = health_check()
            assert success is False
```

---

## Project Structure Notes

- All changes align with existing `src/aegish/` module structure
- No new modules needed
- `health_check()` in `llm_client.py` follows the module's responsibility (LLM communication) [Source: docs/architecture.md#Module Responsibilities]
- Startup integration in `shell.py` follows the module's responsibility (user interaction) [Source: docs/architecture.md#Module Responsibilities]
- Test changes follow existing class-per-function pattern in `test_llm_client.py`

---

## References

- [Source: docs/epics.md#Story 9.2] - Story requirements and acceptance criteria
- [Source: docs/security-hardening-scope.md#BYPASS-04] - Attack scenario: verify model responds correctly at startup
- [Source: docs/prd.md#FR49] - Startup health check verifies primary model responds correctly
- [Source: src/aegish/llm_client.py:200-301] - `query_llm()` full model chain (NOT to be used for health check)
- [Source: src/aegish/llm_client.py:304-327] - `_try_model()` single model call pattern
- [Source: src/aegish/llm_client.py:386-402] - `_get_messages_for_model()` message builder
- [Source: src/aegish/llm_client.py:405-437] - `_parse_response()` JSON parser
- [Source: src/aegish/config.py:109-121] - `get_primary_model()` function
- [Source: src/aegish/shell.py:72-166] - `run_shell()` startup flow
- [Source: docs/stories/9-1-provider-allowlist-validation.md] - Previous story patterns and learnings

---

## Previous Story Intelligence

### From Story 9.1 (Provider Allowlist Validation)
- **Directly relevant:** Story 9.1 added provider allowlist validation to `query_llm()`. The health check should also validate that the primary model's provider is in the allowlist before attempting the API call. Use `validate_model_provider()` and `is_valid_model_string()` from config.py.
- **Pattern:** Return `tuple[bool, str]` for pass/fail results — same pattern used by `validate_model_provider()` and `validate_credentials()`
- **Code review lesson (M4):** Test isolation is critical — use `mocker.patch.dict(os.environ, {...}, clear=True)` to prevent env var leakage between tests
- **Implementation note:** `mock_providers()` from `tests/utils.py` mocks `get_model_chain()` which health check does NOT use (it uses `get_primary_model()` directly). Health check tests should mock at a lower level or set env vars directly.

### From Epic 6 (Environment Sanitization)
- **Pattern:** Functions with security implications catch all exceptions and fail gracefully
- **Pattern:** `_build_safe_env()` in executor.py uses a denylist approach — health check uses a catch-all try/except approach

---

## Definition of Done

- [x] `llm_client.py` has `health_check()` function that tests primary model with "echo hello"
- [x] Health check uses 5-second timeout
- [x] Health check validates response is `action: "allow"`
- [x] Health check tests primary model only (not full fallback chain)
- [x] Health check catches all exceptions and returns `(False, reason)` on any failure
- [x] `shell.py` calls `health_check()` at startup after banner
- [x] Warning printed on health check failure: includes reason and "degraded mode" message
- [x] Shell continues normally after health check failure
- [x] Unit tests for all success and failure scenarios
- [x] All existing tests pass (no regressions)

---

## Dependencies

- **Blocked by:** Story 9.1 (Provider Allowlist Validation) - DONE
- **Blocks:** Story 9.4 (Unit Tests for Config Integrity - integration tests)

---

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

No debug issues encountered. All implementations succeeded on first attempt.

### Completion Notes List

- Implemented `health_check()` in `llm_client.py` following the story's design: calls `litellm.completion()` directly with `timeout=5`, uses `get_primary_model()` for primary-only check, validates model format and provider allowlist before calling, parses response with `_parse_response()` and verifies `action == "allow"`, wraps entire function in try/except to never crash.
- Integrated health check into `shell.py` `run_shell()` between startup banner and shell loop. On success: silent. On failure: prints `WARNING: Health check failed - {reason}. Operating in degraded mode.`
- Added 12 unit tests in `TestHealthCheck` class in `test_llm_client.py`: success, block response, warn response, API error, timeout, primary model only, never raises, no API key, malformed JSON, 5s timeout verification, invalid model format, provider not in allowlist.
- Added 3 integration tests in `TestStartupHealthCheck` class in `test_shell.py`: warning display on failure, silent on success, shell continues after failure.
- All 105 tests in modified files pass. Full suite: 683 passed, 4 pre-existing benchmark plot failures (unrelated).

### Change Log

- 2026-02-13: Implemented Story 9.2 - Startup Health Check. Added `health_check()` to `llm_client.py`, integrated into `shell.py` startup flow, and wrote 15 unit/integration tests.
- 2026-02-13: Code review fixes (H1, M1, M3, M4). Added structured logging to shell.py and health_check failure paths. Added "echo hello" test command assertion. Improved test isolation in TestStartupHealthCheck with mock_banner fixture. Created action item for M2 (DRY refactor).

### File List

- `src/aegish/llm_client.py` (modified) - Added `health_check()` function, `get_primary_model` import, and `logger.warning()` on all failure paths
- `src/aegish/shell.py` (modified) - Added `health_check` import, call in `run_shell()` after banner, and `logger.warning()` for structured logging
- `tests/test_llm_client.py` (modified) - Added `TestHealthCheck` class with 12 unit tests; added "echo hello" message assertion
- `tests/test_shell.py` (modified) - Added `TestStartupHealthCheck` class with 3 integration tests and `mock_banner` fixture for environment isolation
