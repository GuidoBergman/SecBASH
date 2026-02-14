# Story 9.1: Provider Allowlist Validation

**Epic:** Epic 9 - Environment Variable Integrity
**Status:** done
**Priority:** High
**FR:** FR48
**NFR Assessment:** BYPASS-04 (Environment Variable Poisoning)
**Design Decision:** DD-10 (Provider allowlist, not model allowlist)

---

## User Story

As a **security engineer**,
I want **configured models validated against a provider allowlist**,
So that **an attacker cannot redirect validation to a model they control by poisoning AEGISH_PRIMARY_MODEL**.

---

## Acceptance Criteria

### AC1: Default Allowlist Accepts Known Providers
**Given** the default allowed providers are: `openai`, `anthropic`, `groq`, `together_ai`, `ollama`
**When** `AEGISH_PRIMARY_MODEL=openai/gpt-4` is configured
**Then** the model is accepted (provider is in the allowlist)

### AC2: Unknown Provider Rejected with Clear Error
**Given** `AEGISH_PRIMARY_MODEL=evil-corp/permissive-model` is configured
**When** aegish starts
**Then** the model is rejected with a clear error:
```
ERROR: Provider 'evil-corp' is not in the allowed providers list.
Allowed: openai, anthropic, groq, together_ai, ollama
```
**And** aegish falls back to the default model (`openai/gpt-4`)

### AC3: Custom Allowlist via Environment Variable
**Given** `AEGISH_ALLOWED_PROVIDERS=openai,anthropic,custom-corp` is set
**When** aegish starts
**Then** the custom allowlist is used instead of the default
**And** `AEGISH_PRIMARY_MODEL=custom-corp/my-model` is accepted

### AC4: Fallback Models Also Validated
**Given** `AEGISH_FALLBACK_MODELS=evil-corp/bad-model,anthropic/claude-3-haiku-20240307` is configured
**When** aegish builds the model chain
**Then** `evil-corp/bad-model` is rejected (not in allowlist)
**And** `anthropic/claude-3-haiku-20240307` is kept
**And** a warning is logged for the rejected model

### AC5: All Models Rejected Falls Back to Default
**Given** `AEGISH_PRIMARY_MODEL=evil-corp/bad` and `AEGISH_FALLBACK_MODELS=evil-corp/worse`
**When** aegish builds the model chain
**Then** both are rejected
**And** aegish falls back to the default model chain (`openai/gpt-4` + `anthropic/claude-3-haiku-20240307`)
**And** a visible warning is printed

### AC6: Ollama (Local) Provider Accepted by Default
**Given** `AEGISH_PRIMARY_MODEL=ollama/llama3` is configured
**When** aegish validates the provider
**Then** it is accepted (ollama is in the default allowlist)

---

## Tasks / Subtasks

- [x] Task 1: Add provider allowlist to config.py (AC: #1, #3)
  - [x] 1.1 Add `DEFAULT_ALLOWED_PROVIDERS` constant: `{"openai", "anthropic", "groq", "together_ai", "ollama"}`
  - [x] 1.2 Add `get_allowed_providers()` function reading from `AEGISH_ALLOWED_PROVIDERS` env var
  - [x] 1.3 Handle comma-separated parsing with whitespace trimming (same pattern as `get_fallback_models()`)

- [x] Task 2: Add provider validation function to config.py (AC: #1, #2)
  - [x] 2.1 Add `validate_model_provider(model: str) -> tuple[bool, str]` function
  - [x] 2.2 Extract provider via existing `get_provider_from_model()`, check against allowlist
  - [x] 2.3 Return `(True, "")` if valid, `(False, "error message with allowed list")` if not

- [x] Task 3: Integrate allowlist into llm_client.py model chain filtering (AC: #2, #4, #5)
  - [x] 3.1 In `query_llm()`, add provider validation before the existing format/API-key checks
  - [x] 3.2 Log warning for each rejected model with provider name and allowed list
  - [x] 3.3 If ALL models rejected after allowlist filtering, fall back to default chain with warning
  - [x] 3.4 The rejection message must include the model string and the allowed providers list

- [x] Task 4: Write unit tests (AC: all)
  - [x] 4.1 Test `get_allowed_providers()` returns default when no env var
  - [x] 4.2 Test `get_allowed_providers()` parses custom env var
  - [x] 4.3 Test `validate_model_provider()` accepts known providers
  - [x] 4.4 Test `validate_model_provider()` rejects unknown providers
  - [x] 4.5 Test `query_llm()` skips models with unknown providers
  - [x] 4.6 Test `query_llm()` falls back to defaults when all rejected
  - [x] 4.7 Test custom allowlist via env var works end-to-end

---

## Dev Notes

### Current Implementation State

**`config.py` (lines 1-182)** already has:
- `DEFAULT_PRIMARY_MODEL = "openai/gpt-4"` (line 31)
- `DEFAULT_FALLBACK_MODELS = ["anthropic/claude-3-haiku-20240307"]` (line 32)
- `get_primary_model()` (line 91) - reads `AEGISH_PRIMARY_MODEL`
- `get_fallback_models()` (line 106) - reads `AEGISH_FALLBACK_MODELS`
- `get_model_chain()` (line 132) - returns ordered list [primary, ...fallbacks]
- `get_provider_from_model(model)` (line 152) - extracts provider from `provider/model-name`
- `is_valid_model_string(model)` (line 170) - checks for `/` in format

**`llm_client.py` `query_llm()` (lines 189-264)** already:
1. Gets model chain via `get_model_chain()`
2. Filters models: validates format via `is_valid_model_string()`, checks API key via `get_api_key(provider)`
3. Iterates through `models_to_try`, calling `_try_model()` for each
4. Returns `_validation_failed_response()` if all fail

### Where to Insert Allowlist Check

The allowlist validation should be added to the existing filtering loop in `query_llm()` at **line 222-236**, between the format check and the API key check:

```python
# Current (llm_client.py:222-236):
models_to_try = []
for model in model_chain:
    if not is_valid_model_string(model):
        logger.warning("Invalid model format '%s'...", model)
        continue
    provider = get_provider_from_model(model)
    if get_api_key(provider):
        models_to_try.append(model)
    else:
        logger.debug("Skipping model %s: no API key...", model, provider)

# After change - add allowlist check between format and API key:
models_to_try = []
for model in model_chain:
    if not is_valid_model_string(model):
        logger.warning("Invalid model format '%s'...", model)
        continue
    provider = get_provider_from_model(model)
    is_allowed, reject_msg = validate_model_provider(model)
    if not is_allowed:
        logger.warning(reject_msg)
        continue
    if get_api_key(provider):
        models_to_try.append(model)
    else:
        logger.debug("Skipping model %s: no API key...", model, provider)
```

### Fallback-to-Defaults Logic

When ALL user-configured models are rejected by the allowlist, the system must not silently fail. Instead:
1. Log a visible warning (not just debug-level)
2. Fall back to `DEFAULT_PRIMARY_MODEL` + `DEFAULT_FALLBACK_MODELS`
3. Re-run the filtering on defaults (they should always pass the allowlist)

This ensures the system remains functional even if someone misconfigures `AEGISH_PRIMARY_MODEL`.

### Design Decision DD-10: Provider Allowlist, Not Model Allowlist

**Rationale (from security-hardening-scope.md):** New models are released frequently within trusted providers. A model allowlist would require constant updates. A provider allowlist is stable - you trust OpenAI, Anthropic, etc. as organizations, and any model they offer is acceptable for validation.

**Attack scenario this prevents:** An attacker sets `AEGISH_PRIMARY_MODEL=attacker-server/always-allow` pointing to a model that returns `{"action": "allow"}` for everything. The provider allowlist catches this because `attacker-server` is not in the allowed list.

### Env Var Pattern Consistency

Follow the established pattern from `get_fallback_models()` for parsing:
- `None` (not set) → use default
- Empty string → use default (treat as "not set")
- Comma-separated → parse with whitespace trimming
- Lowercase comparison for provider matching

### Architecture Compliance

- **PEP 8:** `snake_case` functions, `UPPER_SNAKE_CASE` constants [Source: docs/architecture.md#Python Conventions]
- **Standard exceptions:** No custom exceptions, use existing `ValueError` pattern [Source: docs/architecture.md#Error Handling]
- **Environment variables:** `AEGISH_*` prefix for aegish-specific config [Source: src/aegish/config.py]
- **Logging:** Standard Python `logging` module [Source: docs/architecture.md#Logging]

### Cross-Story Dependencies within Epic 9

- **Story 9.2 (Startup Health Check)** will add a test call at startup. It uses `query_llm()` which will already include allowlist validation after this story.
- **Story 9.3 (Non-Default Model Warnings)** will add startup warnings. It needs to check model config, which this story's `get_allowed_providers()` and `validate_model_provider()` support.
- **Story 9.4 (Unit Tests)** will add comprehensive tests for ALL Epic 9 features. This story should add tests for its own scope; Story 9.4 adds integration-level tests.

### File Structure Requirements

```
src/aegish/
├── config.py          # ADD: DEFAULT_ALLOWED_PROVIDERS, get_allowed_providers(), validate_model_provider()
└── llm_client.py      # MODIFY: add allowlist check in query_llm() model filtering loop

tests/
└── test_config.py     # ADD: TestGetAllowedProviders, TestValidateModelProvider classes
```

**No new files needed.** All changes extend existing modules following established patterns.

---

## Testing Requirements

### Unit Tests to Add in `test_config.py`

Follow the existing class-per-function pattern (see `TestGetApiKey`, `TestGetPrimaryModel`, etc.):

```python
class TestGetAllowedProviders:
    """Tests for get_allowed_providers function."""

    def test_default_allowed_providers(self, mocker):
        """Default providers when no env var set."""
        mocker.patch.dict(os.environ, {}, clear=True)
        result = get_allowed_providers()
        assert "openai" in result
        assert "anthropic" in result
        assert "ollama" in result

    def test_custom_allowed_providers(self, mocker):
        """Custom providers from env var."""
        mocker.patch.dict(os.environ, {"AEGISH_ALLOWED_PROVIDERS": "openai,custom"}, clear=True)
        result = get_allowed_providers()
        assert result == {"openai", "custom"}

    def test_empty_env_var_uses_default(self, mocker):
        """Empty env var uses default allowlist."""
        mocker.patch.dict(os.environ, {"AEGISH_ALLOWED_PROVIDERS": ""}, clear=True)
        result = get_allowed_providers()
        assert "openai" in result  # defaults


class TestValidateModelProvider:
    """Tests for validate_model_provider function."""

    def test_known_provider_accepted(self, mocker):
        mocker.patch.dict(os.environ, {}, clear=True)
        is_valid, msg = validate_model_provider("openai/gpt-4")
        assert is_valid is True

    def test_unknown_provider_rejected(self, mocker):
        mocker.patch.dict(os.environ, {}, clear=True)
        is_valid, msg = validate_model_provider("evil-corp/bad-model")
        assert is_valid is False
        assert "evil-corp" in msg
        assert "openai" in msg  # shows allowed list

    def test_custom_allowlist_provider_accepted(self, mocker):
        mocker.patch.dict(os.environ, {"AEGISH_ALLOWED_PROVIDERS": "openai,custom"}, clear=True)
        is_valid, msg = validate_model_provider("custom/my-model")
        assert is_valid is True
```

### Integration-Level Tests for `query_llm()` Allowlist Behavior

Add to existing `test_llm_client.py`:

```python
def test_query_llm_rejects_unknown_provider(self, mocker):
    """Models from unknown providers are skipped."""
    mocker.patch.dict(os.environ, {
        "AEGISH_PRIMARY_MODEL": "evil-corp/bad",
        "AEGISH_FALLBACK_MODELS": "",
        "OPENAI_API_KEY": "test-key",
    }, clear=True)
    # Should fall back to default chain since evil-corp is rejected
    # ...
```

---

## Project Structure Notes

- All changes align with existing `src/aegish/` module structure
- No new modules needed
- Test changes follow existing class-per-function pattern in `test_config.py`
- The `validate_model_provider()` function belongs in `config.py` (not `llm_client.py`) because it's configuration validation, matching the module's responsibility [Source: docs/architecture.md#Module Responsibilities]

---

## References

- [Source: docs/epics.md#Story 9.1] - Story requirements and acceptance criteria
- [Source: docs/security-hardening-scope.md#BYPASS-04] - Attack scenario and design decision DD-10
- [Source: src/aegish/config.py:152-167] - Existing `get_provider_from_model()` function
- [Source: src/aegish/llm_client.py:218-264] - Current model chain filtering in `query_llm()`
- [Source: src/aegish/config.py:106-129] - Pattern for parsing comma-separated env vars (`get_fallback_models()`)
- [Source: tests/test_config.py] - Existing test patterns (class-per-function, mocker.patch.dict)

---

## Previous Story Intelligence

### From Story 3.6 (Configurable LLM Models)
- **Directly relevant:** Story 3.6 established the entire model configuration system that this story validates against
- **Key patterns:** `get_model_chain()` returns ordered list, `get_provider_from_model()` extracts provider, `is_valid_model_string()` validates format
- **Code review lesson (MEDIUM-1):** Provider-related functions belong in `config.py`, not `llm_client.py` - `get_provider_from_model()` was moved from llm_client to config during review
- **Code review lesson (MEDIUM-5):** Model string validation was missing initially and added during review - similar pattern needed for provider validation

### From Epic 5 Implementation
- **Pattern:** New constants (`DEFAULT_ALLOWED_PROVIDERS`) follow `UPPER_SNAKE_CASE` convention
- **Pattern:** Config functions return defaults when env vars empty/unset
- **Test pattern:** `mocker.patch.dict(os.environ, {...}, clear=True)` for isolated env var testing

---

## Git Intelligence

Recent commits show documentation and epic work (blog post improvements, new epics). No recent code changes to `config.py` or `llm_client.py`. The codebase is stable for this story's modifications.

---

## Definition of Done

- [x] `config.py` has `DEFAULT_ALLOWED_PROVIDERS` constant
- [x] `config.py` has `get_allowed_providers()` function
- [x] `config.py` has `validate_model_provider()` function
- [x] `llm_client.py` validates providers against allowlist before API key check
- [x] Unknown providers are rejected with clear error message including allowed list
- [x] Fallback to default chain when all configured models rejected
- [x] Custom allowlist via `AEGISH_ALLOWED_PROVIDERS` works
- [x] Unit tests for all new functions
- [x] All existing tests pass (no regressions)

---

## Dependencies

- **Blocked by:** None (Epic 9 has no dependencies on other epics)
- **Blocks:** Story 9.2 (health check uses `query_llm()` which gains allowlist after this)
- **Blocks:** Story 9.4 (integration tests cover all Epic 9 features)

---

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None - clean implementation with no debug issues.

### Completion Notes List

- Added `DEFAULT_ALLOWED_PROVIDERS` set constant with 5 providers: openai, anthropic, groq, together_ai, ollama
- Added `get_allowed_providers()` with env var override via `AEGISH_ALLOWED_PROVIDERS`, follows same parsing pattern as `get_fallback_models()`
- Added `validate_model_provider()` returning `(bool, str)` tuple with clear rejection messages including allowed providers list
- Integrated allowlist check into `query_llm()` model filtering loop, positioned between format validation and API key check
- Added fallback-to-defaults logic when all user-configured models are rejected by allowlist
- Added 7 unit tests for `get_allowed_providers()` in `TestGetAllowedProviders`
- Added 7 unit tests for `validate_model_provider()` in `TestValidateModelProvider`
- Added 5 integration tests for `query_llm()` allowlist behavior in `TestProviderAllowlist`
- All 96 config + llm_client tests pass; 4 pre-existing benchmark plot test failures unrelated to this story

### Change Log

- 2026-02-13: Implemented provider allowlist validation (Story 9.1, all 4 tasks complete)
- 2026-02-13: Code review fixes (H1, M1-M4): Extended `get_api_key()` for groq/together_ai/ollama, documented AEGISH_ALLOWED_PROVIDERS in module docstring, cached allowlist resolution in query_llm(), fixed test isolation in mock_providers(), rewrote misleading custom allowlist test

### File List

- `src/aegish/config.py` — MODIFIED: Added `DEFAULT_ALLOWED_PROVIDERS`, `LOCAL_PROVIDERS`, `get_allowed_providers()`, `validate_model_provider()`; extended `get_api_key()` with groq/together_ai/ollama support; added AEGISH_ALLOWED_PROVIDERS to module docstring
- `src/aegish/llm_client.py` — MODIFIED: Added allowlist check in `query_llm()` model filtering with cached resolution, added fallback-to-defaults logic
- `tests/test_config.py` — MODIFIED: Added `TestGetAllowedProviders` (7 tests), `TestValidateModelProvider` (7 tests), `TestGetApiKeyExtendedProviders` (4 tests)
- `tests/test_llm_client.py` — MODIFIED: Added `TestProviderAllowlist` (5 tests), rewrote `test_custom_allowlist_via_env_var` for true end-to-end coverage
- `tests/utils.py` — MODIFIED: Updated `mock_providers()` to mock `validate_model_provider` and `get_allowed_providers` for test isolation
- `docs/stories/sprint-status.yaml` — MODIFIED: Story status updated
- `docs/stories/9-1-provider-allowlist-validation.md` — MODIFIED: Task checkboxes, Dev Agent Record, File List, Status
