# Story 9.3: Non-Default Model Warnings

**Epic:** Epic 9 - Environment Variable Integrity
**Status:** Done
**Priority:** Medium
**FR:** FR50
**NFR Assessment:** BYPASS-04 (Environment Variable Poisoning)
**Design Decision:** DD-10 (Provider allowlist + health check + startup warnings)

---

## User Story

As a **security engineer**,
I want **visible warnings when non-default models are configured**,
So that **intentional or accidental model changes are immediately visible to the operator**.

---

## Acceptance Criteria

### AC1: Non-Default Primary Model Warning
**Given** `AEGISH_PRIMARY_MODEL` is set to a non-default value (anything other than `openai/gpt-4`)
**When** aegish starts
**Then** the startup banner includes:
```
WARNING: Using non-default primary model: <configured-model>
         Default is: openai/gpt-4
```

### AC2: No Fallback Models Warning
**Given** `AEGISH_FALLBACK_MODELS` is set to empty string (no fallbacks)
**When** aegish starts
**Then** the startup banner includes:
```
WARNING: No fallback models configured. Single-provider mode.
```

### AC3: Default Models — No Warnings
**Given** default models are used (no `AEGISH_PRIMARY_MODEL` or `AEGISH_FALLBACK_MODELS` env vars set)
**When** aegish starts
**Then** no model warnings are shown

### AC4: Non-Default Fallback Models Warning
**Given** `AEGISH_FALLBACK_MODELS` is set to a value different from the default (not `anthropic/claude-3-haiku-20240307`)
**When** aegish starts
**Then** the startup banner includes:
```
WARNING: Using non-default fallback models: <configured-models>
         Default is: anthropic/claude-3-haiku-20240307
```

### AC5: Warnings Display Before Health Check
**Given** non-default models are configured
**When** aegish starts
**Then** model warnings appear AFTER the startup banner (model chain, mode, fail mode) and BEFORE the health check runs

---

## Tasks / Subtasks

- [x] Task 1: Add default-model detection helpers to config.py (AC: #1, #2, #3, #4)
  - [x] 1.1 Add `is_default_primary_model() -> bool` — returns True if `get_primary_model()` equals `DEFAULT_PRIMARY_MODEL`
  - [x] 1.2 Add `is_default_fallback_models() -> bool` — returns True if `get_fallback_models()` equals `DEFAULT_FALLBACK_MODELS`
  - [x] 1.3 Add `has_fallback_models() -> bool` — returns True if `get_fallback_models()` is non-empty

- [x] Task 2: Add non-default model warnings to shell.py startup banner (AC: #1, #2, #4, #5)
  - [x] 2.1 Import `is_default_primary_model`, `is_default_fallback_models`, `has_fallback_models`, `DEFAULT_PRIMARY_MODEL`, `DEFAULT_FALLBACK_MODELS` from config
  - [x] 2.2 After the existing startup banner lines (after `print("Type 'exit' ...")`) and BEFORE the health check call, add model warnings
  - [x] 2.3 If primary model is non-default: print `WARNING: Using non-default primary model: {primary_model}` and `         Default is: {DEFAULT_PRIMARY_MODEL}`
  - [x] 2.4 If fallback models list is empty: print `WARNING: No fallback models configured. Single-provider mode.`
  - [x] 2.5 If fallback models are non-default and non-empty: print `WARNING: Using non-default fallback models: {fallback_list}` and `         Default is: {DEFAULT_FALLBACK_MODELS[0]}`

- [x] Task 3: Write unit tests (AC: all)
  - [x] 3.1 Test `is_default_primary_model()` returns True when env var not set
  - [x] 3.2 Test `is_default_primary_model()` returns False when env var set to non-default
  - [x] 3.3 Test `is_default_fallback_models()` returns True when env var not set
  - [x] 3.4 Test `is_default_fallback_models()` returns False when env var set to non-default
  - [x] 3.5 Test `has_fallback_models()` returns True with defaults
  - [x] 3.6 Test `has_fallback_models()` returns False when env var set to empty string
  - [x] 3.7 Test shell startup shows non-default primary model warning
  - [x] 3.8 Test shell startup shows no-fallback warning
  - [x] 3.9 Test shell startup shows non-default fallback warning
  - [x] 3.10 Test shell startup shows NO warnings with default models

---

## Dev Notes

### Current Implementation State

**`config.py` (lines 1-305)** already has:
- `DEFAULT_PRIMARY_MODEL = "openai/gpt-4"` (line 49)
- `DEFAULT_FALLBACK_MODELS = ["anthropic/claude-3-haiku-20240307"]` (line 50)
- `get_primary_model()` (line 165) — reads `AEGISH_PRIMARY_MODEL`, falls back to `DEFAULT_PRIMARY_MODEL`
- `get_fallback_models()` (line 180) — reads `AEGISH_FALLBACK_MODELS`, `None` → defaults, `""` → empty list
- `get_model_chain()` (line 206) — returns `[primary] + fallbacks` deduplicated

**`shell.py` (lines 1-187)** `run_shell()` (line 76):
- Lines 91-100: Startup banner showing model chain with availability status
- Lines 101-110: Mode and fail mode display
- Line 111: `print("Type 'exit' or press Ctrl+D to quit.\n")`
- Lines 113-117: Health check call (after banner, before shell loop)
- Line 119: `while True:` shell loop begins

**Non-default model warnings should go between lines 111 and 113** — after the full startup banner and before the health check. This keeps the information hierarchy clean:
1. Model chain display (what models are configured)
2. Mode/fail-mode display
3. **Model warnings (NEW)** — flag anything unusual about the configuration
4. Health check — verify the primary model actually works

### Implementation Strategy

**config.py — Three simple comparison helpers:**

```python
def is_default_primary_model() -> bool:
    """Check if the primary model is the default."""
    return get_primary_model() == DEFAULT_PRIMARY_MODEL


def is_default_fallback_models() -> bool:
    """Check if fallback models match the defaults."""
    return get_fallback_models() == DEFAULT_FALLBACK_MODELS


def has_fallback_models() -> bool:
    """Check if any fallback models are configured."""
    return len(get_fallback_models()) > 0
```

**shell.py — Warning block after banner:**

```python
# Non-default model warnings (Story 9.3, FR50)
if not is_default_primary_model():
    primary = get_primary_model()
    print(f"WARNING: Using non-default primary model: {primary}")
    print(f"         Default is: {DEFAULT_PRIMARY_MODEL}")

fallbacks = get_fallback_models()
if not fallbacks:
    print("WARNING: No fallback models configured. Single-provider mode.")
elif not is_default_fallback_models():
    print(f"WARNING: Using non-default fallback models: {', '.join(fallbacks)}")
    print(f"         Default is: {DEFAULT_FALLBACK_MODELS[0]}")
```

### Where to Insert in shell.py

Insert between the existing `print("Type 'exit' ...")` (line 111) and the health check (line 113):

```
Line 111:  print("Type 'exit' or press Ctrl+D to quit.\n")
           ← INSERT MODEL WARNINGS HERE (new lines)
Line 113:  success, reason = health_check()
```

### Import Changes in shell.py

Add to the existing imports from config (line 18):
```python
from aegish.config import (
    DEFAULT_FALLBACK_MODELS,
    DEFAULT_PRIMARY_MODEL,
    get_api_key,
    get_fail_mode,
    get_fallback_models,
    get_mode,
    get_model_chain,
    get_primary_model,
    get_provider_from_model,
    has_fallback_models,
    is_default_fallback_models,
    is_default_primary_model,
)
```

### Edge Cases

1. **`AEGISH_PRIMARY_MODEL` set to empty string** — `get_primary_model()` returns the default → `is_default_primary_model()` returns True → no warning. Correct behavior.
2. **`AEGISH_FALLBACK_MODELS` set to empty string** — `get_fallback_models()` returns `[]` → `has_fallback_models()` returns False → "No fallback models" warning. Correct.
3. **`AEGISH_FALLBACK_MODELS` not set at all** — `get_fallback_models()` returns default list → `is_default_fallback_models()` returns True → no warning. Correct.
4. **Primary model set to exact default value** — `is_default_primary_model()` returns True → no warning. Correct (intentional override to default is fine).

### Architecture Compliance

- **PEP 8:** `snake_case` functions, `UPPER_SNAKE_CASE` constants [Source: docs/architecture.md#Python Conventions]
- **Standard exceptions:** No exceptions needed — pure comparison functions [Source: docs/architecture.md#Error Handling]
- **Environment variables:** Uses existing `AEGISH_PRIMARY_MODEL` and `AEGISH_FALLBACK_MODELS` — no new env vars [Source: src/aegish/config.py]
- **Module boundaries:** Config comparison helpers in `config.py`, startup display in `shell.py` [Source: docs/architecture.md#Module Responsibilities]
- **Logging:** No logger calls needed in helpers (they are pure comparisons). Shell.py can optionally log at debug level.

### Cross-Story Dependencies within Epic 9

- **Story 9.1 (Provider Allowlist):** DONE. No interaction with model warnings.
- **Story 9.2 (Startup Health Check):** DONE. Warnings appear BEFORE health check in startup flow. Health check tests may need `mock_banner` pattern extended if they assert startup output.
- **Story 9.4 (Unit Tests for Config Integrity):** Will add integration-level tests for all Epic 9 features. This story adds its own unit tests.

### Previous Story (9.2) Intelligence

**Directly relevant patterns:**
- Story 9.2 added health check integration at shell.py lines 113-117. Model warnings go just above this, maintaining the information hierarchy.
- Story 9.2's `TestStartupHealthCheck` in test_shell.py uses a `mock_banner` fixture that mocks `get_model_chain`, `get_provider_from_model`, `get_api_key`, `get_mode`, `get_fail_mode`. This story's shell tests should extend this fixture to also mock the new config imports (`is_default_primary_model`, `is_default_fallback_models`, `has_fallback_models`, `get_primary_model`, `get_fallback_models`, `DEFAULT_PRIMARY_MODEL`, `DEFAULT_FALLBACK_MODELS`).
- Story 9.2 completion notes: "All 105 tests pass" — ensure no regressions from new code.

**Code review lessons from 9.1 and 9.2:**
- Test isolation: `mocker.patch.dict(os.environ, {...}, clear=True)` to prevent leakage
- Provider-related functions in `config.py`, display in `shell.py`
- Functions should be simple — comparison helpers don't need error handling

### Git Intelligence

Recent commits are documentation (blog post, epics). Most recent code changes from Stories 9.1 and 9.2 (provider allowlist, health check). The modified but uncommitted files include `config.py`, `shell.py`, `test_config.py`, `test_shell.py` — these contain the 9.1 and 9.2 work that this story builds on. The codebase is stable for this story.

---

## Testing Requirements

### Unit Tests to Add in `test_config.py`

Follow the existing class-per-function pattern:

```python
class TestIsDefaultPrimaryModel:
    """Tests for is_default_primary_model function."""

    def test_default_when_env_not_set(self, mocker):
        """Returns True when AEGISH_PRIMARY_MODEL not set."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert is_default_primary_model() is True

    def test_non_default_when_env_set(self, mocker):
        """Returns False when env var is a different model."""
        mocker.patch.dict(os.environ, {"AEGISH_PRIMARY_MODEL": "anthropic/claude-sonnet-4-5-20250929"}, clear=True)
        assert is_default_primary_model() is False

    def test_default_when_env_set_to_default(self, mocker):
        """Returns True when env var matches default."""
        mocker.patch.dict(os.environ, {"AEGISH_PRIMARY_MODEL": "openai/gpt-4"}, clear=True)
        assert is_default_primary_model() is True

    def test_default_when_env_empty(self, mocker):
        """Returns True when env var is empty (falls back to default)."""
        mocker.patch.dict(os.environ, {"AEGISH_PRIMARY_MODEL": ""}, clear=True)
        assert is_default_primary_model() is True


class TestIsDefaultFallbackModels:
    """Tests for is_default_fallback_models function."""

    def test_default_when_env_not_set(self, mocker):
        """Returns True when AEGISH_FALLBACK_MODELS not set."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert is_default_fallback_models() is True

    def test_non_default_when_env_set(self, mocker):
        """Returns False when env var is a different model list."""
        mocker.patch.dict(os.environ, {"AEGISH_FALLBACK_MODELS": "openai/gpt-3.5-turbo"}, clear=True)
        assert is_default_fallback_models() is False

    def test_non_default_when_env_empty(self, mocker):
        """Returns False when env var is empty (single-provider mode)."""
        mocker.patch.dict(os.environ, {"AEGISH_FALLBACK_MODELS": ""}, clear=True)
        assert is_default_fallback_models() is False


class TestHasFallbackModels:
    """Tests for has_fallback_models function."""

    def test_has_fallbacks_with_defaults(self, mocker):
        """Returns True with default fallback models."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert has_fallback_models() is True

    def test_no_fallbacks_when_empty(self, mocker):
        """Returns False when AEGISH_FALLBACK_MODELS is empty string."""
        mocker.patch.dict(os.environ, {"AEGISH_FALLBACK_MODELS": ""}, clear=True)
        assert has_fallback_models() is False

    def test_has_fallbacks_when_custom(self, mocker):
        """Returns True with custom fallback models."""
        mocker.patch.dict(os.environ, {"AEGISH_FALLBACK_MODELS": "openai/gpt-3.5-turbo"}, clear=True)
        assert has_fallback_models() is True
```

### Integration Tests to Add in `test_shell.py`

Extend the existing `TestStartupHealthCheck` pattern or add a new class:

```python
class TestStartupModelWarnings:
    """Tests for non-default model warnings at startup (Story 9.3)."""

    def test_non_default_primary_model_warning(self, mocker, capsys):
        """AC1: Warning shown for non-default primary model."""
        # Mock to make shell run one iteration then exit
        mocker.patch("aegish.shell.input", side_effect=EOFError)
        mocker.patch("aegish.shell.health_check", return_value=(True, ""))
        mocker.patch("aegish.shell.get_model_chain", return_value=["anthropic/claude-sonnet-4-5-20250929"])
        mocker.patch("aegish.shell.get_provider_from_model", return_value="anthropic")
        mocker.patch("aegish.shell.get_api_key", return_value="test-key")
        mocker.patch("aegish.shell.get_mode", return_value="development")
        mocker.patch("aegish.shell.get_fail_mode", return_value="safe")
        mocker.patch("aegish.shell.is_default_primary_model", return_value=False)
        mocker.patch("aegish.shell.get_primary_model", return_value="anthropic/claude-sonnet-4-5-20250929")
        mocker.patch("aegish.shell.has_fallback_models", return_value=True)
        mocker.patch("aegish.shell.is_default_fallback_models", return_value=True)
        run_shell()
        captured = capsys.readouterr()
        assert "WARNING: Using non-default primary model: anthropic/claude-sonnet-4-5-20250929" in captured.out
        assert "Default is: openai/gpt-4" in captured.out

    def test_no_fallback_warning(self, mocker, capsys):
        """AC2: Warning shown when no fallbacks configured."""
        mocker.patch("aegish.shell.input", side_effect=EOFError)
        mocker.patch("aegish.shell.health_check", return_value=(True, ""))
        mocker.patch("aegish.shell.get_model_chain", return_value=["openai/gpt-4"])
        mocker.patch("aegish.shell.get_provider_from_model", return_value="openai")
        mocker.patch("aegish.shell.get_api_key", return_value="test-key")
        mocker.patch("aegish.shell.get_mode", return_value="development")
        mocker.patch("aegish.shell.get_fail_mode", return_value="safe")
        mocker.patch("aegish.shell.is_default_primary_model", return_value=True)
        mocker.patch("aegish.shell.has_fallback_models", return_value=False)
        mocker.patch("aegish.shell.get_fallback_models", return_value=[])
        run_shell()
        captured = capsys.readouterr()
        assert "WARNING: No fallback models configured. Single-provider mode." in captured.out

    def test_no_warnings_with_defaults(self, mocker, capsys):
        """AC3: No warnings when defaults are used."""
        mocker.patch("aegish.shell.input", side_effect=EOFError)
        mocker.patch("aegish.shell.health_check", return_value=(True, ""))
        mocker.patch("aegish.shell.get_model_chain", return_value=["openai/gpt-4"])
        mocker.patch("aegish.shell.get_provider_from_model", return_value="openai")
        mocker.patch("aegish.shell.get_api_key", return_value="test-key")
        mocker.patch("aegish.shell.get_mode", return_value="development")
        mocker.patch("aegish.shell.get_fail_mode", return_value="safe")
        mocker.patch("aegish.shell.is_default_primary_model", return_value=True)
        mocker.patch("aegish.shell.has_fallback_models", return_value=True)
        mocker.patch("aegish.shell.is_default_fallback_models", return_value=True)
        run_shell()
        captured = capsys.readouterr()
        assert "WARNING: Using non-default" not in captured.out
        assert "WARNING: No fallback" not in captured.out
```

---

## Project Structure Notes

- All changes align with existing `src/aegish/` module structure
- No new modules needed
- Config helpers in `config.py` follow the module's responsibility (configuration) [Source: docs/architecture.md#Module Responsibilities]
- Display logic in `shell.py` follows the module's responsibility (user interaction) [Source: docs/architecture.md#Module Responsibilities]
- Test changes follow existing class-per-function pattern in `test_config.py` and `test_shell.py`

### File Structure Requirements

```
src/aegish/
├── config.py          # ADD: is_default_primary_model(), is_default_fallback_models(), has_fallback_models()
└── shell.py           # MODIFY: add model warning block in run_shell() after banner, before health check

tests/
├── test_config.py     # ADD: TestIsDefaultPrimaryModel, TestIsDefaultFallbackModels, TestHasFallbackModels
└── test_shell.py      # ADD: TestStartupModelWarnings class with 3-4 tests
```

**No new files needed.** All changes extend existing modules following established patterns.

---

## References

- [Source: docs/epics.md#Story 9.3] - Story requirements and acceptance criteria
- [Source: docs/security-hardening-scope.md#BYPASS-04] - Attack scenario: model configuration poisoning
- [Source: docs/prd.md#FR50] - Non-default model configuration triggers visible warning
- [Source: src/aegish/config.py:49-50] - `DEFAULT_PRIMARY_MODEL` and `DEFAULT_FALLBACK_MODELS` constants
- [Source: src/aegish/config.py:165-203] - `get_primary_model()` and `get_fallback_models()` functions
- [Source: src/aegish/shell.py:91-117] - Current startup banner and health check flow
- [Source: docs/stories/9-1-provider-allowlist-validation.md] - Previous story patterns
- [Source: docs/stories/9-2-startup-health-check.md] - Previous story patterns and startup flow integration

---

## Definition of Done

- [x] `config.py` has `is_default_primary_model()` function
- [x] `config.py` has `is_default_fallback_models()` function
- [x] `config.py` has `has_fallback_models()` function
- [x] `shell.py` shows warning for non-default primary model
- [x] `shell.py` shows warning for no fallback models (single-provider mode)
- [x] `shell.py` shows warning for non-default fallback models
- [x] `shell.py` shows NO warnings when defaults are used
- [x] Warnings appear after banner but before health check
- [x] Unit tests for all new config functions
- [x] Integration tests for startup warning display
- [x] All existing tests pass (no regressions)

---

## Dependencies

- **Blocked by:** Story 9.2 (Startup Health Check) - DONE (warnings integrate into the same startup flow)
- **Blocks:** Story 9.4 (Unit Tests for Config Integrity - integration tests for all Epic 9 features)

---

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None required — clean implementation with no debugging needed.

### Completion Notes List

- Added three config helper functions: `is_default_primary_model()`, `is_default_fallback_models()`, `has_fallback_models()` — simple comparison functions with no error handling needed.
- Added non-default model warning block to `shell.py` `run_shell()` between the startup banner and health check, covering all three warning cases (non-default primary, no fallbacks, non-default fallbacks).
- Added 10 unit tests in `test_config.py` (TestIsDefaultPrimaryModel: 4, TestIsDefaultFallbackModels: 3, TestHasFallbackModels: 3).
- Added 4 integration tests in `test_shell.py` (TestStartupModelWarnings: AC1-AC4 coverage plus default no-warning verification).
- Full test suite: 739 passed, 0 failures, 0 regressions.

### Change Log

- 2026-02-14: Implemented Story 9.3 — non-default model warnings (FR50, BYPASS-04)
- 2026-02-14: Code review fixes — removed unused `has_fallback_models` import from shell.py, replaced boolean helper calls with inline comparisons to eliminate redundant env lookups, simplified TestStartupModelWarnings (removed misleading mock of unused `has_fallback_models`, reduced nesting via fixture defaults)

### File List

- `src/aegish/config.py` — Added `is_default_primary_model()`, `is_default_fallback_models()`, `has_fallback_models()`
- `src/aegish/shell.py` — Added non-default model warning block in `run_shell()` using inline comparisons against DEFAULT_PRIMARY_MODEL/DEFAULT_FALLBACK_MODELS
- `tests/test_config.py` — Added TestIsDefaultPrimaryModel, TestIsDefaultFallbackModels, TestHasFallbackModels classes (10 tests)
- `tests/test_shell.py` — Added TestStartupModelWarnings class (4 tests) with fixture-provided default config mocks
