# Story 3.6: Configurable LLM Models

**Epic:** Epic 3 - User Control & Configuration
**Status:** done
**Priority:** must-have (added post-MVP based on user feedback)

---

## User Story

As a **sysadmin**,
I want **to configure which LLM models aegish uses for validation**,
So that **I can choose models based on my provider access, cost preferences, or performance needs**.

---

## Acceptance Criteria

### AC1: Primary Model Configuration via Environment Variable
**Given** environment variable `AEGISH_PRIMARY_MODEL` is set (e.g., `anthropic/claude-3-haiku-20240307`)
**When** aegish starts
**Then** the configured model is used as the primary validation model instead of the hardcoded default

### AC2: Fallback Models Configuration via Environment Variable
**Given** environment variable `AEGISH_FALLBACK_MODELS` is set (comma-separated, e.g., `openai/gpt-4,anthropic/claude-3-haiku-20240307`)
**When** aegish starts
**Then** the configured fallback models are used instead of the hardcoded defaults

### AC3: Sensible Defaults When No Configuration
**Given** no model configuration environment variables are set
**When** aegish starts
**Then** sensible defaults are used:
- Primary: `openrouter/meta-llama/llama-guard-3-8b`
- Fallbacks: `openai/gpt-4`, `anthropic/claude-3-haiku-20240307`

### AC4: Invalid Model Error Handling
**Given** an invalid model string is configured (e.g., malformed or unsupported by LiteLLM)
**When** aegish attempts to use it for validation
**Then** a clear error message is displayed
**And** fallback behavior applies (try next model in chain, or warn if all fail)

### AC5: Single Provider Configuration
**Given** I configure `AEGISH_PRIMARY_MODEL=anthropic/claude-3-haiku-20240307`
**And** I leave `AEGISH_FALLBACK_MODELS` empty or unset
**When** aegish validates commands
**Then** only that single model is used for validation (no automatic fallbacks)

---

## Technical Requirements

### Environment Variables to Add

| Variable | Format | Default | Description |
|----------|--------|---------|-------------|
| `AEGISH_PRIMARY_MODEL` | `provider/model-name` | `openrouter/meta-llama/llama-guard-3-8b` | Primary model for command validation |
| `AEGISH_FALLBACK_MODELS` | `provider/model,provider/model,...` | `openai/gpt-4,anthropic/claude-3-haiku-20240307` | Comma-separated fallback models |

### LiteLLM Model String Format

Model strings MUST follow LiteLLM format: `provider/model-name`

**Valid examples:**
- `openrouter/meta-llama/llama-guard-3-8b`
- `openai/gpt-4`
- `openai/gpt-4-turbo`
- `openai/gpt-3.5-turbo`
- `anthropic/claude-3-haiku-20240307`
- `anthropic/claude-3-sonnet-20240229`
- `anthropic/claude-3-opus-20240229`

**Important:** The model string format varies by provider. OpenRouter uses nested paths (`openrouter/provider/model`), while OpenAI and Anthropic use flat paths (`openai/model-name`).

### Files to Modify

1. **`src/aegish/config.py`** - Add model configuration loading
2. **`src/aegish/llm_client.py`** - Use configured models instead of hardcoded constants
3. **`src/aegish/shell.py`** - Update startup message to show configured models (optional enhancement)
4. **`README.md`** - Document new environment variables

---

## Tasks / Subtasks

- [x] Task 1: Add model configuration to config.py (AC: #1, #2, #3)
  - [x] 1.1 Add `get_primary_model()` function that reads `AEGISH_PRIMARY_MODEL` with default
  - [x] 1.2 Add `get_fallback_models()` function that reads `AEGISH_FALLBACK_MODELS` with defaults
  - [x] 1.3 Add `get_model_chain()` function that returns ordered list of models to try
  - [x] 1.4 Handle empty/whitespace env var values (treat as "use defaults")

- [x] Task 2: Update llm_client.py to use configurable models (AC: #1, #2, #4, #5)
  - [x] 2.1 Replace `PROVIDER_MODELS` constant with dynamic model loading from config
  - [x] 2.2 Replace `PROVIDER_PRIORITY` with dynamic model chain from config
  - [x] 2.3 Update `_try_provider()` to work with arbitrary model strings (renamed to `_try_model()`)
  - [x] 2.4 Update `_get_messages_for_model()` to detect LlamaGuard vs general models
  - [x] 2.5 Handle invalid model errors gracefully with clear error messages

- [x] Task 3: Update startup message (optional enhancement)
  - [x] 3.1 Show configured model chain in startup message instead of just provider names

- [x] Task 4: Update README.md (AC: #1, #2, #3, #4, #5)
  - [x] 4.1 Add "Model Configuration" section documenting new environment variables
  - [x] 4.2 Add examples for common configurations (single provider, custom models, etc.)

- [x] Task 5: Write tests for model configuration (all ACs)
  - [x] 5.1 Test default model behavior when no env vars set
  - [x] 5.2 Test custom primary model configuration
  - [x] 5.3 Test custom fallback models configuration
  - [x] 5.4 Test empty/whitespace env var handling
  - [x] 5.5 Test single-provider configuration (no fallbacks)
  - [x] 5.6 Test invalid model error handling

---

## Dev Notes

### Current Implementation Analysis

**Current hardcoded configuration in `llm_client.py:27-36`:**
```python
PROVIDER_MODELS = {
    "openrouter": "openrouter/meta-llama/llama-guard-3-8b",
    "openai": "openai/gpt-4",
    "anthropic": "anthropic/claude-3-haiku-20240307",
}

PROVIDER_PRIORITY = ["openrouter", "openai", "anthropic"]
```

**Current flow:**
1. `query_llm()` calls `get_available_providers()` to check which API keys are set
2. Iterates through `PROVIDER_PRIORITY` filtered by available providers
3. For each provider, looks up model from `PROVIDER_MODELS`
4. Calls `_try_provider()` with the model string

**Changes needed:**
- Replace hardcoded constants with dynamic loading from config
- Remove provider-centric approach (current: provider -> model lookup)
- Move to model-centric approach (new: ordered list of models to try)
- Still need API key validation per provider

### Architecture Compliance

Per `architecture.md`:
- **Environment variables** for configuration (matches existing pattern)
- **Fail-open behavior** when all providers fail (already implemented)
- **LiteLLM** for unified API access (already implemented)
- **PEP 8 naming** (snake_case for functions, UPPER_SNAKE_CASE for constants)

### LlamaGuard Detection Logic

The current implementation uses special prompts for LlamaGuard (OpenRouter). The new implementation must detect LlamaGuard models regardless of configuration:

**Current detection in `_get_messages_for_model()` and `_try_provider()`:**
- Checks `provider == "openrouter"` to use LlamaGuard prompt
- This must change to: check if model string contains "llama-guard"

**Update logic to:**
```python
def _is_llamaguard_model(model: str) -> bool:
    return "llama-guard" in model.lower()
```

### API Key Requirement Mapping

Even with configurable models, API keys are still required per provider:
- Models starting with `openrouter/` require `OPENROUTER_API_KEY`
- Models starting with `openai/` require `OPENAI_API_KEY`
- Models starting with `anthropic/` require `ANTHROPIC_API_KEY`

**Extract provider from model string:**
```python
def _get_provider_from_model(model: str) -> str:
    return model.split("/")[0]
```

### Edge Cases to Handle

1. **Empty env var:** `AEGISH_PRIMARY_MODEL=""` should use default
2. **Whitespace:** `AEGISH_PRIMARY_MODEL="  "` should use default
3. **Single model, no fallbacks:** Valid use case, should work
4. **Invalid model format:** Log warning, skip to next model in chain
5. **No API key for configured model:** Log warning, skip to next model

---

## Project Structure Notes

### Files to Modify

```
src/aegish/
├── config.py          # ADD: get_primary_model(), get_fallback_models(), get_model_chain()
├── llm_client.py      # MODIFY: use config functions instead of hardcoded constants
└── shell.py           # OPTIONAL: update startup message

tests/
├── test_config.py     # ADD: model configuration tests
└── test_llm_client.py # ADD: configurable model tests
```

### Existing Patterns to Follow

**From `config.py` - env var handling pattern:**
```python
def get_api_key(provider: str) -> str | None:
    env_var = env_vars.get(provider.lower())
    if env_var:
        key = os.environ.get(env_var)
        return key if key and key.strip() else None
    return None
```

**Follow same pattern for model config:**
- Return `None` or default if env var is empty/whitespace
- Use `os.environ.get()` for retrieval
- Strip whitespace before validation

---

## References

- [Source: docs/epics.md#Story 3.6]
- [Source: docs/architecture.md#LLM Provider Strategy]
- [Source: src/aegish/llm_client.py:27-36] - Current hardcoded model configuration
- [Source: src/aegish/config.py:27-46] - Existing env var handling pattern
- [LiteLLM Documentation](https://docs.litellm.ai/docs/providers) - Model string formats

---

## Previous Story Intelligence

### From Story 3.5 (Login Shell Setup Documentation)

**Relevant for this story:**
- README.md now exists and documents configuration
- Documentation section on "Configuration" → "API Keys" exists
- Provider priority documentation already in README
- Need to add new "Model Configuration" subsection

### From Story 3.1 (API Credential Configuration)

**Relevant patterns:**
- Environment variable naming: `AEGISH_*` prefix for aegish-specific config
- API keys use provider-specific names: `OPENROUTER_API_KEY`, etc.
- Error messaging pattern: Clear instructions on how to configure

### From Story 3.3 (Sensible Defaults)

**Relevant principles:**
- aegish works with minimal configuration
- Default values should be secure and functional
- Don't require configuration for basic functionality

---

## External Context (Latest Technical Information)

### LiteLLM Model Strings (2026)

LiteLLM uses provider-prefixed model strings. Current supported formats:

**OpenRouter:**
- `openrouter/meta-llama/llama-guard-3-8b` (security model)
- `openrouter/openai/gpt-4` (via OpenRouter)
- `openrouter/anthropic/claude-3-opus` (via OpenRouter)

**OpenAI:**
- `openai/gpt-4`
- `openai/gpt-4-turbo`
- `openai/gpt-3.5-turbo`

**Anthropic:**
- `anthropic/claude-3-haiku-20240307`
- `anthropic/claude-3-sonnet-20240229`
- `anthropic/claude-3-opus-20240229`
- `anthropic/claude-3-5-sonnet-20241022` (latest)

### LlamaGuard Availability

LlamaGuard 3 8B is available through:
- OpenRouter (`openrouter/meta-llama/llama-guard-3-8b`)
- Direct Meta hosting (requires separate setup)
- Local deployment via Ollama (out of scope for MVP)

For MVP, only OpenRouter access is supported for LlamaGuard.

---

## Testing Requirements

### Unit Tests

| Test | Description | AC |
|------|-------------|-----|
| `test_default_primary_model` | Verify default primary model when no env var | #3 |
| `test_default_fallback_models` | Verify default fallbacks when no env var | #3 |
| `test_custom_primary_model` | Custom primary model via env var | #1 |
| `test_custom_fallback_models` | Custom fallbacks via env var | #2 |
| `test_empty_primary_model` | Empty env var uses default | #3 |
| `test_whitespace_primary_model` | Whitespace-only env var uses default | #3 |
| `test_single_model_no_fallbacks` | Primary only, no fallbacks configured | #5 |
| `test_invalid_model_handling` | Invalid model skipped gracefully | #4 |
| `test_provider_extraction` | Correct provider extracted from model string | #1, #2 |
| `test_llamaguard_detection` | LlamaGuard detected from model string | #1 |

### Integration Tests

| Test | Description | AC |
|------|-------------|-----|
| `test_query_with_custom_model` | End-to-end validation with custom model | #1, #4 |
| `test_fallback_with_custom_chain` | Fallback works with custom model chain | #2, #4 |

---

## Definition of Done

- [x] `config.py` has `get_primary_model()`, `get_fallback_models()`, `get_model_chain()` functions
- [x] `llm_client.py` uses config functions instead of hardcoded constants
- [x] Default behavior unchanged when no env vars set (AC3)
- [x] Custom primary model works (AC1)
- [x] Custom fallback models work (AC2)
- [x] Invalid model errors handled gracefully (AC4)
- [x] Single-provider configuration works (AC5)
- [x] All existing tests pass (no regressions)
- [x] New tests for model configuration added
- [x] README.md updated with model configuration documentation

---

## Dependencies

- **Blocked by:** None (all prerequisite stories complete)
- **Blocks:** Epic 3 retrospective
- **Parallel safe:** Can work alongside any other Epic 3 work

---

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - implementation proceeded smoothly without debugging issues.

### Completion Notes List

- **Task 1:** Implemented model configuration functions in `config.py`:
  - `get_primary_model()` reads `AEGISH_PRIMARY_MODEL` env var with default
  - `get_fallback_models()` reads `AEGISH_FALLBACK_MODELS` env var with defaults
  - `get_model_chain()` returns ordered list of models with duplicate removal
  - All functions handle empty/whitespace env vars correctly

- **Task 2:** Updated `llm_client.py` to use configurable models:
  - Removed hardcoded `PROVIDER_MODELS` and `PROVIDER_PRIORITY` constants
  - Added `_is_llamaguard_model()` helper to detect LlamaGuard by model string
  - Added `_get_provider_from_model()` helper to extract provider for API key lookup
  - Renamed `_try_provider()` to `_try_model()` for model-centric approach
  - Updated `_get_messages_for_model()` to detect LlamaGuard from model string
  - Model chain filters out models without API keys automatically

- **Task 3:** Updated startup message to show model chain with availability status

- **Task 4:** Updated README.md with comprehensive Model Configuration documentation:
  - Environment variable documentation
  - Model string format examples
  - Common configuration examples (single provider, custom chain)
  - API key requirements per provider

- **Task 5:** Added comprehensive tests:
  - 14 new tests in `test_config.py` for model configuration
  - 8 new tests in `test_llm_client.py` for configurable model support
  - 3 new tests in `test_defaults.py` for default model configuration
  - Updated existing test mocks to work with new architecture

### File List

**Modified:**
- `src/aegish/config.py` - Added model configuration functions
- `src/aegish/llm_client.py` - Updated to use configurable models
- `src/aegish/shell.py` - Updated startup message to show model chain
- `tests/test_config.py` - Added model configuration tests
- `tests/test_llm_client.py` - Added configurable model tests, updated mock helper
- `tests/test_defaults.py` - Updated to test model configuration defaults
- `tests/test_dangerous_commands.py` - Updated mock helper for new architecture
- `README.md` - Added Model Configuration documentation section
- `docs/stories/sprint-status.yaml` - Updated story status
- `docs/sprint-artifacts/3-6-configurable-llm-models.md` - Updated with completion info

---

## Senior Developer Review (AI)

**Reviewed by:** Claude Opus 4.5 (Adversarial Code Review)
**Review Date:** 2026-02-02
**Outcome:** APPROVED (with fixes applied)

### Issues Found and Fixed

| Severity | Issue | Resolution |
|----------|-------|------------|
| HIGH-1 | Story file untracked in git | Noted - requires commit |
| MEDIUM-1 | Private function `_get_provider_from_model` imported cross-module | Moved to `config.py` as public `get_provider_from_model()` |
| MEDIUM-2 | Duplicate `mock_providers()` in test files | Consolidated into `tests/utils.py` |
| MEDIUM-3 | Missing comment explaining `.copy()` usage | Added explanatory comment |
| MEDIUM-4 | Redundant provider priority display | Removed redundant startup line |
| MEDIUM-5 | No validation for malformed model strings (AC4) | Added `is_valid_model_string()` and validation with warning logging |
| LOW-1 | Sprint status path mismatch | Noted - different paths in git vs story |
| LOW-2 | No test for trailing comma edge case | Added `test_fallback_models_trailing_comma_handled` |
| LOW-3 | Minor message capitalization | Verified consistent |

### Code Quality Improvements Applied

1. **Better Encapsulation**: `get_provider_from_model()` now public in `config.py` - proper module boundary
2. **DRY Compliance**: Shared test utilities in `tests/utils.py`
3. **AC4 Compliance**: Invalid model format now logs clear warning before skipping
4. **Cleaner UX**: Startup message simplified (removed redundant provider priority line)
5. **Test Coverage**: Added 12 new tests for validation and edge cases

### Test Results

- **Total Tests:** 270 passed
- **New Tests Added:** 12
- **Regressions:** None

### Files Modified During Review

- `src/aegish/config.py` - Added `get_provider_from_model()`, `is_valid_model_string()`
- `src/aegish/llm_client.py` - Updated imports, added model format validation
- `src/aegish/shell.py` - Removed redundant display, updated imports
- `tests/utils.py` - Enhanced `mock_providers()` helper
- `tests/test_config.py` - Added validation tests
- `tests/test_llm_client.py` - Added malformed model test, DRY cleanup
- `tests/test_dangerous_commands.py` - DRY cleanup
- `tests/test_defaults.py` - Updated for new startup message format
- `README.md` - Updated startup example

