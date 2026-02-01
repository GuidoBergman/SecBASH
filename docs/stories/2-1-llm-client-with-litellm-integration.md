# Story 2.1: LLM Client with LiteLLM Integration

**Epic:** Epic 2 - LLM Security Validation
**Status:** Done
**Priority:** must-have

---

## User Story

As a **sysadmin**,
I want **SecBASH to connect to LLM providers reliably**,
So that **command validation works even if one provider is unavailable**.

---

## Acceptance Criteria

### AC1: Primary Provider Request
**Given** LiteLLM is configured with provider fallback chain
**When** a validation request is made
**Then** the request goes to OpenRouter (LlamaGuard) first

### AC2: Automatic Provider Fallback
**Given** OpenRouter fails or times out
**When** fallback providers are configured
**Then** LiteLLM automatically falls back to OpenAI, then Anthropic

### AC3: Fail-Open on Total Failure
**Given** all providers fail after LiteLLM's built-in retries
**When** retries are exhausted
**Then** the system fails open (returns allow response) with a warning logged

### AC4: Response Caching
**Given** the same or similar command was recently validated
**When** a validation request is made
**Then** LiteLLM returns cached response (faster, no API call)

### AC5: Structured Response Format
**Given** an LLM provider returns a response
**When** the response is processed
**Then** it returns a dict with: `{action: "allow"|"warn"|"block", reason: string, confidence: float}`

---

## Technical Requirements

### Implementation Location
- **Primary file:** `src/secbash/llm_client.py` (replace stub implementation)

### Dependencies
- `litellm` (already in pyproject.toml)

### Environment Variables Required
- `OPENROUTER_API_KEY` - For LlamaGuard via OpenRouter
- `OPENAI_API_KEY` - For GPT-4 fallback
- `ANTHROPIC_API_KEY` - For Claude fallback

At least one API key must be configured for the client to function.

### LiteLLM Configuration

```python
from litellm import completion

# Primary call with fallbacks
response = completion(
    model="openrouter/meta-llama/llama-guard-3-8b",
    messages=[{"role": "user", "content": prompt}],
    fallbacks=["gpt-4", "claude-3-haiku-20240307"]
)
```

### Response Format (Architecture-specified)

```python
{
    "action": "allow" | "warn" | "block",
    "reason": "Human-readable explanation of the decision",
    "confidence": 0.0 - 1.0
}
```

### Caching Configuration
- Enable LiteLLM's built-in caching
- Cache key should be based on the prompt/command
- Default cache TTL: session-based (or LiteLLM default)

---

## Implementation Notes

### From Epic 1 Retrospective

1. **Mock LLM responses in tests** - Don't depend on actual API calls for unit tests
2. **Consider integration test suite** - Separate tests that hit real LLM APIs
3. **Document fail-open behavior clearly** - Security implications must be understood

### Error Handling Strategy

Per architecture: Use standard Python exceptions
- `ConnectionError` - All providers failed
- `TimeoutError` - Request timed out
- `ValueError` - Invalid response format

**Fail-open behavior:**
```python
def validate_command(command: str) -> dict:
    try:
        return query_llm(command)
    except (ConnectionError, TimeoutError):
        logger.warning("LLM validation failed, allowing command (fail-open)")
        return {"action": "allow", "reason": "LLM unavailable - fail-open", "confidence": 0.0}
```

### Module Boundary

This story focuses ONLY on `llm_client.py`:
- Implement `query_llm()` function
- Configure LiteLLM with fallbacks and caching
- Return structured response format
- Handle errors with fail-open behavior

The integration with `validator.py` and `shell.py` is Story 2.2.

---

## Test Requirements

### Unit Tests (Mocked)
1. Test successful query returns structured response
2. Test fallback triggers when primary provider fails
3. Test fail-open returns allow response when all providers fail
4. Test cached response returns without API call
5. Test response parsing extracts action, reason, confidence

### Test Approach
- Use `unittest.mock` or `pytest-mock` to mock LiteLLM responses
- Do NOT call actual LLM APIs in unit tests
- Integration tests (optional, separate file) can hit real APIs

### Example Test Structure

```python
def test_query_llm_returns_structured_response(mocker):
    """AC5: Response has action, reason, confidence."""
    mocker.patch('litellm.completion', return_value=mock_response)
    result = query_llm("ls -la")
    assert "action" in result
    assert "reason" in result
    assert "confidence" in result
    assert result["action"] in ["allow", "warn", "block"]

def test_fail_open_on_connection_error(mocker):
    """AC3: Fail-open when all providers fail."""
    mocker.patch('litellm.completion', side_effect=ConnectionError)
    result = query_llm("ls -la")
    assert result["action"] == "allow"
    assert result["confidence"] == 0.0
```

---

## Definition of Done

- [x] `llm_client.py` implements `query_llm()` with LiteLLM
- [x] Provider fallback chain configured (OpenRouter → OpenAI → Anthropic)
- [x] Caching enabled for repeated commands
- [x] Fail-open behavior implemented and logged
- [x] Response format matches architecture spec
- [x] Unit tests with mocked LLM responses
- [x] All tests pass
- [x] No architecture violations

---

## Dependencies

- **Blocked by:** None (first story of Epic 2)
- **Blocks:** Story 2.2 (Command Validation Integration)

---

## Story Intelligence

### From Epic 1

**Patterns to follow:**
- PEP 8 naming conventions (snake_case functions)
- Standard Python logging module
- Simple, focused module boundaries

**What worked well:**
- Clear acceptance criteria enabled focused implementation
- Test-first validation approach (51 tests across Epic 1)

### Existing Code Context

**config.py** already provides:
```python
get_api_key(provider: str) -> str | None
get_available_providers() -> list[str]
```

Use these for checking which providers are available.

### Architecture Constraints

- LLM response format is fixed: `{action, reason, confidence}`
- Environment variables are the only credential source
- Fail-open on LLM failure (security trade-off documented)

---

## Estimated Complexity

**Implementation:** Medium
- New LiteLLM integration (learning curve)
- Response parsing logic
- Error handling with fail-open

**Testing:** Medium
- Requires mocking LiteLLM
- Multiple failure scenarios to test

**Risk:** Low
- Clear architecture guidance
- LiteLLM handles provider complexity

---

## Dev Agent Record

### Implementation Notes

Implemented `query_llm()` function using LiteLLM with:
- Primary model: `openrouter/meta-llama/llama-guard-3-8b`
- Fallback chain: `gpt-4` → `claude-3-haiku-20240307`
- Caching enabled via `caching=True` parameter
- Fail-open behavior on all exceptions (ConnectionError, TimeoutError, generic exceptions)
- Response parsing with validation and defaults for missing fields
- JSON parsing errors return fail-open response

Updated `pyproject.toml` to use `litellm>=1.0.0` instead of direct `openai` and `anthropic` dependencies (LiteLLM handles provider SDKs internally).

### File List

**Modified:**
- `src/secbash/llm_client.py` - Complete LiteLLM implementation
- `pyproject.toml` - Updated dependencies to use litellm

**Added:**
- `tests/test_llm_client.py` - 13 unit tests with mocked LiteLLM responses

### Change Log

- 2026-01-31: Implemented LLM client with LiteLLM integration (Story 2.1)
- 2026-01-31: Code review completed - 7 issues fixed:
  - Added config.py integration for provider availability checking
  - Added LlamaGuard-specific response parsing (safe/unsafe format)
  - Fixed fallback model names with provider prefixes
  - Added dynamic model selection based on available providers
  - Added tests for edge cases (invalid action, confidence clamping, no providers)
  - Test count increased from 13 to 28
