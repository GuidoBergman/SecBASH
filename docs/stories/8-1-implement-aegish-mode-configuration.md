# Story 8.1: Implement AEGISH_MODE Configuration

Status: Done

## Story

As a **sysadmin**,
I want **to configure aegish in production or development mode**,
So that **production deployments have login shell + Landlock enforcement while development allows normal exit behavior**.

## Acceptance Criteria

1. **Given** `AEGISH_MODE` is not set, **When** aegish starts, **Then** development mode is used (default)

2. **Given** `AEGISH_MODE=production`, **When** aegish starts, **Then** production mode is active, **And** the startup banner shows: `Mode: production (login shell + Landlock enforcement)`

3. **Given** `AEGISH_MODE=development`, **When** aegish starts, **Then** the startup banner shows: `Mode: development`

4. **Given** `AEGISH_MODE` is set to an invalid value (e.g., `AEGISH_MODE=staging`), **When** aegish starts, **Then** development mode is used as fallback, **And** a warning is logged at debug level

5. **Given** `AEGISH_MODE` has leading/trailing whitespace or mixed case (e.g., `AEGISH_MODE=" Production "`), **When** aegish starts, **Then** the value is normalized (stripped and lowercased) and `production` mode is active

## Tasks / Subtasks

- [x] Task 1: Add mode configuration to `src/aegish/config.py` (AC: #1, #4, #5)
  - [x] 1.1: Add constants: `DEFAULT_MODE = "development"` and `VALID_MODES = {"production", "development"}`
  - [x] 1.2: Add `AEGISH_MODE` to module docstring with description
  - [x] 1.3: Implement `get_mode() -> str` function that reads `AEGISH_MODE` env var, normalizes (strip + lower), validates against `VALID_MODES`, returns default if unset or invalid

- [x] Task 2: Display mode in startup banner in `src/aegish/shell.py` (AC: #2, #3)
  - [x] 2.1: Import `get_mode` from `aegish.config`
  - [x] 2.2: Add mode line to startup banner after model chain display: production shows `Mode: production (login shell + Landlock enforcement)`, development shows `Mode: development`

- [x] Task 3: Add unit tests (AC: #1, #2, #3, #4, #5)
  - [x] 3.1: Test `get_mode()` returns "development" when env var not set
  - [x] 3.2: Test `get_mode()` returns "production" when `AEGISH_MODE=production`
  - [x] 3.3: Test `get_mode()` returns "development" when `AEGISH_MODE=development`
  - [x] 3.4: Test `get_mode()` returns "development" for invalid values (e.g., "staging", "test")
  - [x] 3.5: Test `get_mode()` normalizes whitespace and case (e.g., " Production " -> "production")
  - [x] 3.6: Test `get_mode()` returns "development" for empty string
  - [x] 3.7: Test startup banner includes "Mode: production" when in production mode
  - [x] 3.8: Test startup banner includes "Mode: development" when in development mode

## Dev Notes

### Epic 8 Context

This story is the **first story** in **Epic 8: Production Mode -- Login Shell + Landlock Enforcement**. The epic addresses three critical bypass vectors from the NFR assessment:
- **BYPASS-12:** Exit escape (Story 8.2 -- login shell behavior)
- **BYPASS-13:** Interactive shell spawning (Stories 8.3 + 8.5 -- Landlock)
- **BYPASS-18:** `exec` replaces subprocess with shell (Stories 8.3 + 8.5 -- Landlock)

**Story dependency chain within Epic 8:**
- **8.1: `AEGISH_MODE` configuration (config.py + shell.py) -- THIS STORY**
- 8.2: Login shell exit behavior (shell.py) -- depends on 8.1
- 8.3: Landlock sandbox implementation (sandbox.py) -- **done, in review**
- 8.4: Runner binary setup (executor.py + config.py) -- depends on 8.1
- 8.5: Integrate Landlock into executor.py (executor.py) -- depends on 8.1, 8.3, 8.4
- 8.6: Docker-based testing infrastructure -- **done**
- 8.7: Integration tests for bypass verification -- depends on all above

This story is foundational -- it introduces the mode concept that ALL other Epic 8 stories depend on. Stories 8.2, 8.4, and 8.5 all call `get_mode()` to determine behavior.

### Architecture Compliance

**Project structure** (from architecture.md):
```
aegish/
├── src/aegish/
│   ├── __init__.py
│   ├── main.py          # Typer CLI entry
│   ├── shell.py          # readline loop, user interaction, startup banner
│   ├── validator.py      # LLM validation logic + bashlex
│   ├── llm_client.py     # LLM clients with fallback
│   ├── executor.py       # subprocess.run wrapper (sanitized env)
│   └── config.py          # Environment variable loading, model config
├── tests/
│   ├── test_config.py     # Config module tests (ADD tests here)
│   └── test_shell.py      # Shell module tests (ADD tests here)
└── pyproject.toml
```

**Naming conventions (PEP 8):**
- Functions: `snake_case` (e.g., `get_mode`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_MODE`, `VALID_MODES`)
- No new classes needed for this story

**Error handling:** Use standard Python conventions. Invalid `AEGISH_MODE` values silently fall back to development mode (no exception, no crash). This follows the existing pattern in `config.py` where `get_primary_model()` silently falls back to default on empty/whitespace values.

[Source: docs/architecture.md#Implementation Patterns & Consistency Rules]

### Technical Requirements

**Implementation in config.py:**

Follow the established pattern from `get_primary_model()`, `get_fail_mode()` style:

```python
# Mode configuration (DD-14: production/development modes)
DEFAULT_MODE = "development"
VALID_MODES = {"production", "development"}


def get_mode() -> str:
    """Get the operational mode for aegish.

    Reads from AEGISH_MODE environment variable.
    Default: development (normal shell behavior).
    Production: login shell + Landlock enforcement.

    Returns:
        Mode string: "production" or "development".
    """
    mode = os.environ.get("AEGISH_MODE", "").strip().lower()
    if mode in VALID_MODES:
        return mode
    return DEFAULT_MODE
```

**Implementation in shell.py:**

Add mode display after the model chain display (line 97) and before "Type 'exit'" (line 98):

```python
from aegish.config import get_api_key, get_mode, get_model_chain, get_provider_from_model

# In run_shell(), after model chain display:
mode = get_mode()
if mode == "production":
    print("Mode: production (login shell + Landlock enforcement)")
else:
    print("Mode: development")
```

**IMPORTANT boundary -- do NOT implement in this story:**
- Exit behavior changes (Story 8.2)
- Landlock integration (Story 8.5)
- Runner binary setup (Story 8.4)

This story ONLY adds `get_mode()` and displays the mode in the banner. All behavioral changes based on the mode are in subsequent stories.

### Library & Framework Requirements

| Dependency | Version/Source | Purpose |
|------------|---------------|---------|
| `os` | Python stdlib | `os.environ.get()` for reading AEGISH_MODE |

**No new PyPI dependencies needed.** This story uses only the `os` module already imported in `config.py`.

### File Structure Requirements

**Files to modify:**
- `src/aegish/config.py` -- Add `DEFAULT_MODE`, `VALID_MODES`, `get_mode()`, update module docstring
- `src/aegish/shell.py` -- Add mode display in startup banner, import `get_mode`
- `tests/test_config.py` -- Add `TestGetMode` test class
- `tests/test_shell.py` -- Add mode banner tests

**Files NOT to modify:**
- `src/aegish/executor.py` -- Story 8.5 handles Landlock integration
- `src/aegish/sandbox.py` -- Story 8.3 (already done)
- `src/aegish/main.py` -- No changes needed
- `pyproject.toml` -- No new dependencies

### Testing Requirements

**Unit tests for `get_mode()` in `tests/test_config.py`:**

Add a new `TestGetMode` class following the existing pattern (e.g., `TestGetPrimaryModel`):

```python
class TestGetMode:
    """Tests for get_mode function."""

    def test_default_mode_when_no_env_var(self, mocker):
        mocker.patch.dict(os.environ, {}, clear=True)
        assert get_mode() == "development"

    def test_production_mode_from_env_var(self, mocker):
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        assert get_mode() == "production"

    def test_development_mode_from_env_var(self, mocker):
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "development"}, clear=True)
        assert get_mode() == "development"

    def test_invalid_mode_falls_back_to_development(self, mocker):
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "staging"}, clear=True)
        assert get_mode() == "development"

    def test_mode_normalized_whitespace_and_case(self, mocker):
        mocker.patch.dict(os.environ, {"AEGISH_MODE": " Production "}, clear=True)
        assert get_mode() == "production"

    def test_empty_mode_returns_development(self, mocker):
        mocker.patch.dict(os.environ, {"AEGISH_MODE": ""}, clear=True)
        assert get_mode() == "development"
```

**Startup banner tests in `tests/test_shell.py`:**

Add tests following existing `TestStartupHealthCheck` pattern:

```python
class TestStartupModeBanner:
    """Tests for mode display in startup banner."""

    def test_production_mode_displayed_in_banner(self, capsys):
        with patch("aegish.shell.get_mode", return_value="production"):
            with patch("aegish.shell.health_check", return_value=(True, "")):
                with patch("builtins.input", side_effect=["exit"]):
                    run_shell()
                    captured = capsys.readouterr()
                    assert "Mode: production" in captured.out

    def test_development_mode_displayed_in_banner(self, capsys):
        with patch("aegish.shell.get_mode", return_value="development"):
            with patch("aegish.shell.health_check", return_value=(True, "")):
                with patch("builtins.input", side_effect=["exit"]):
                    run_shell()
                    captured = capsys.readouterr()
                    assert "Mode: development" in captured.out
```

**Test patterns to follow:**
- Use `mocker.patch.dict(os.environ, {...}, clear=True)` for config tests (existing pattern)
- Use `unittest.mock.patch` for shell tests (existing pattern)
- Class-based test grouping with descriptive docstrings

### Previous Story Intelligence

**Story 8.3 (Landlock sandbox) learnings:**
- Uses `get_mode()` from config to determine whether to apply Landlock -- this is the function we're implementing
- sandbox.py calls `get_sandbox_preexec()` which returns `None` when Landlock unavailable -- graceful fallback pattern
- WSL2 kernel 5.15 doesn't support Landlock (not relevant to this config story, but good to know)

**Story 8.6 (Docker infrastructure) learnings:**
- Dockerfile sets `ENV AEGISH_MODE=production` and `ENV AEGISH_FAIL_MODE=safe`
- The Docker container is already configured to expect `AEGISH_MODE` to work
- Runner binary at `/opt/aegish/bin/runner` (hardlink) is already set up

**Epic 6 (env sanitization) pattern:**
- `executor.py` already uses `_build_safe_env()` with `DANGEROUS_ENV_VARS` denylist
- `AEGISH_MODE` is NOT in the denylist (it's a config var, not a dangerous injection var)
- This means `AEGISH_MODE` will be preserved in subprocess environments (correct)

### Git Intelligence

Recent commits:
- `4c1dd9d` Add new epics (most recent)
- Epic 8 stories 8.3 and 8.6 already implemented
- `config.py` was modified in last 5 commits (Story 9.1: provider allowlist)
- `shell.py` was modified in last 5 commits (Story 9.2: health check)

**Current `config.py` state:** Has `get_allowed_providers()`, `validate_model_provider()`, `get_primary_model()`, `get_fallback_models()`, `get_model_chain()`. The new `get_mode()` follows the same pattern.

**Current `shell.py` state:** Startup banner at lines 88-98 shows title, model chain, and "Type 'exit'" message. Health check at lines 101-103. The mode line should be inserted between the model chain display and the "Type 'exit'" line.

### Design Decisions Referenced

| ID | Decision | Impact on This Story |
|----|----------|---------------------|
| DD-13 | Login shell over exit-trapping | Context: production mode uses login shell approach (Story 8.2 implements behavior) |
| DD-14 | Production/development modes via `AEGISH_MODE` | **Primary decision** -- this story implements the mode configuration |

[Source: docs/security-hardening-scope.md#DD-14]
[Source: docs/security-hardening-scope.md#BYPASS-12]

### Project Structure Notes

- No new files created; only modifications to existing `config.py`, `shell.py`, `test_config.py`, `test_shell.py`
- Follows existing import pattern: `from aegish.config import get_mode`
- Constants placed at module level following existing pattern (`DEFAULT_PRIMARY_MODEL`, `DEFAULT_ALLOWED_PROVIDERS`)

### References

- [Source: docs/security-hardening-scope.md#BYPASS-12] -- Exit escape problem and login shell solution
- [Source: docs/security-hardening-scope.md#DD-14] -- Production/development modes via AEGISH_MODE
- [Source: docs/epics.md#Story 8.1: Implement AEGISH_MODE Configuration] -- Acceptance criteria, FRs covered (FR43, FR44)
- [Source: docs/prd.md#FR43] -- Production mode: exit terminates session, Landlock enforces shell execution denial
- [Source: docs/prd.md#FR44] -- Development mode: exit works normally with warning, no Landlock enforcement
- [Source: docs/architecture.md#Implementation Patterns & Consistency Rules] -- PEP 8, standard exceptions, module responsibilities
- [Source: src/aegish/config.py] -- Existing env var reading patterns (get_primary_model, get_allowed_providers)
- [Source: src/aegish/shell.py] -- Existing startup banner pattern (lines 88-98)
- [Source: docs/stories/8-3-landlock-sandbox-implementation.md] -- Sister story, references get_mode()
- [Source: docs/stories/8-6-docker-based-testing-infrastructure.md] -- Docker sets AEGISH_MODE=production

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

No debug issues encountered.

### Completion Notes List

- Implemented `DEFAULT_MODE` and `VALID_MODES` constants in config.py following existing pattern (e.g., `DEFAULT_ALLOWED_PROVIDERS`)
- Added `get_mode()` function following the established `get_primary_model()` pattern: reads env var, normalizes (strip + lower), validates against allowed set, falls back to default
- Added `AEGISH_MODE` documentation to config.py module docstring
- Updated shell.py import to include `get_mode`, added mode display line in startup banner between model chain and "Type 'exit'" message
- Production mode shows: `Mode: production (login shell + Landlock enforcement)`; development shows: `Mode: development`
- Added 11 unit tests in `TestGetMode` class (test_config.py) covering all ACs: default, production, development, invalid (parametrized x4), normalization, empty, debug logging, no-log-on-empty
- Added 2 banner tests in `TestStartupModeBanner` class (test_shell.py) covering production and development mode display

### Change Log

- 2026-02-13: Implemented AEGISH_MODE configuration (Story 8.1) - added get_mode() to config.py, mode banner to shell.py, 8 new tests
- 2026-02-13: [Code Review] Fixed H1: AC4 debug logging for invalid AEGISH_MODE (added logging import + logger.debug call). Fixed M1: added caplog test for debug log + negative test for empty mode. Fixed M2: parametrized invalid value test with 4 values. Fixed L1: consolidated health_check mock into shared fixture.

### File List

- src/aegish/config.py (modified: added DEFAULT_MODE, VALID_MODES constants, get_mode() function with debug logging, logging import, updated module docstring)
- src/aegish/shell.py (modified: imported get_mode, added mode display in startup banner)
- tests/test_config.py (modified: added TestGetMode class with 11 tests including parametrized invalid values and caplog assertions)
- tests/test_shell.py (modified: added TestStartupModeBanner class with 2 tests, health_check mock in shared fixture)
