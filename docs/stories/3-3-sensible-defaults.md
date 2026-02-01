# Story 3.3: Sensible Defaults

**Epic:** Epic 3 - User Control & Configuration
**Status:** Ready for Review
**Priority:** must-have

---

## User Story

As a **sysadmin**,
I want **SecBASH to work with minimal configuration**,
So that **I can start using it quickly without complex setup**.

---

## Acceptance Criteria

### AC1: Works Without Additional Configuration Files
**Given** at least one API key is configured (OPENROUTER_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)
**When** SecBASH starts
**Then** it works without requiring additional configuration files

### AC2: Reasonable Defaults Applied
**Given** default settings are in use (no environment overrides)
**When** I use SecBASH
**Then** reasonable defaults are applied:
- Default shell is bash
- Standard prompt displays (e.g., "secbash> ")
- Default LLM providers work in priority order

---

## Technical Requirements

### Current State Analysis

The codebase already implements most of the "sensible defaults" behavior:

**config.py (lines 9-38):**
- Loads API keys from environment variables
- `get_available_providers()` returns configured providers
- `validate_credentials()` ensures at least one provider exists

**shell.py (lines 19-25):**
- `get_prompt()` returns hardcoded "secbash> " prompt
- No configurable prompt option exists

**llm_client.py (lines 23-30):**
- `PROVIDER_MODELS` dict with hardcoded model strings
- `PROVIDER_PRIORITY = ["openrouter", "openai", "anthropic"]`

**executor.py (line 29):**
- Hardcoded `["bash", "-c", ...]` for command execution

### What This Story Should Do

**AC1 is ALREADY SATISFIED** - the system works with just API keys set.

**AC2 needs verification and documentation:**
1. Verify all defaults work correctly out of the box
2. Document all defaults in code comments for maintainability
3. Consider adding a `--version` or `--info` flag to display defaults

### Recommended Scope

This story focuses on **verification, documentation, and minor UX improvements**:

1. **Add informational output** showing active configuration at startup
2. **Document all defaults** in config.py with clear comments
3. **Add --version flag** to main.py for version display
4. **Add tests** verifying default behavior works correctly

---

## Tasks / Subtasks

- [x] Task 1: Add startup info message showing active configuration (AC: #2)
  - [x] 1.1 Modify shell.py `run_shell()` to display which provider(s) are active
  - [x] 1.2 Show provider priority order being used
  - [x] 1.3 Keep info message concise (1-2 lines)

- [x] Task 2: Add --version flag to CLI (AC: #2)
  - [x] 2.1 Add `__version__` to src/secbash/__init__.py
  - [x] 2.2 Use typer's built-in version callback
  - [x] 2.3 Display version and basic info

- [x] Task 3: Document all defaults in code comments (AC: #1, #2)
  - [x] 3.1 Add docstring to config.py documenting all environment variables
  - [x] 3.2 Add comments in llm_client.py explaining default model choices
  - [x] 3.3 Add comments in shell.py explaining default prompt

- [x] Task 4: Write verification tests (AC: #1, #2)
  - [x] 4.1 test_shell_works_with_one_api_key_no_config_files
  - [x] 4.2 test_default_prompt_is_secbash
  - [x] 4.3 test_default_shell_is_bash
  - [x] 4.4 test_default_provider_priority

---

## Dev Notes

### Module Boundaries

**Modify:**
- `src/secbash/__init__.py` - Add `__version__` string
- `src/secbash/main.py` - Add version callback to Typer app
- `src/secbash/shell.py` - Add startup info message showing active providers
- `src/secbash/config.py` - Enhance module docstring with all env var documentation

**Do NOT modify:**
- `llm_client.py` - Defaults are appropriate, just add comments
- `executor.py` - Default shell (bash) is correct, no changes needed

### Architecture Compliance

Per architecture.md:
- **PEP 8:** Use snake_case for functions, UPPER_SNAKE_CASE for constants
- **Output format:** Plain text, no emojis
- **Version format:** Follow semantic versioning (e.g., "0.1.0")
- **Typer patterns:** Use `typer.Option` with callback for --version

### Testing Pattern

Follow existing patterns from tests/test_config.py:
```python
def test_shell_works_with_one_key(mocker):
    """AC1: Works without config files when one key is set."""
    mocker.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True)

    # Verify system initializes without errors
    is_valid, _ = validate_credentials()
    assert is_valid is True
```

### Default Values Reference

| Setting | Default Value | Location |
|---------|--------------|----------|
| Prompt | "secbash> " | shell.py:25 |
| Shell | bash | executor.py:29 |
| Primary LLM | openrouter/meta-llama/llama-guard-3-8b | llm_client.py:24 |
| Fallback 1 | openai/gpt-4 | llm_client.py:25 |
| Fallback 2 | anthropic/claude-3-haiku-20240307 | llm_client.py:26 |
| Max command length | 4096 chars | llm_client.py:20 |

### Project Structure Notes

**Files to Modify:**
```
src/secbash/
├── __init__.py    # Add __version__ = "0.1.0"
├── config.py      # Enhance docstring with env var docs
├── main.py        # Add --version callback
└── shell.py       # Add startup info message

tests/
└── test_defaults.py  # New file for default behavior tests
```

### Import Requirements

- `main.py` needs: No new imports (Typer callback pattern uses existing imports)
- `shell.py` needs: `from secbash.config import get_available_providers` (if not already imported)

---

## References

- [Source: docs/epics.md#Story 3.3: Sensible Defaults]
- [Source: docs/prd.md#FR18: System works with minimal configuration]
- [Source: docs/architecture.md#Technology Stack Selected]

---

## Previous Story Intelligence

### From Story 3.1 (API Credential Configuration)

**Patterns established:**
- `config.py` provides credential management functions
- `validate_credentials()` returns tuple (bool, str)
- Tests use `mocker.patch.dict(os.environ, {...})` for env var mocking
- Plain text output (no emojis)
- Functions return tuples or dicts for multi-value returns
- Comprehensive docstrings with Args/Returns
- Type hints on all function signatures

**Code locations from Story 3.1:**
- `config.py` lines 41-63: `validate_credentials()` function
- `main.py` lines 19-30: CLI entry point with credential check

### From Story 3.2 (Warning Override)

Story 3.2 was implemented as part of Story 2.3 (Security Response Actions).
- Warning override flow is in `shell.py` lines 65-81
- Uses `input("Proceed anyway? [y/N]: ")` pattern
- Standard yes/no confirmation handling

### Relevant Existing Code Patterns

**shell.py startup message pattern (lines 40-41):**
```python
print("SecBASH - LLM-powered shell with security validation")
print("Type 'exit' or press Ctrl+D to quit.\n")
```

**Typer version callback pattern (recommended approach):**
```python
from typing import Optional
import typer

def version_callback(value: bool):
    if value:
        print("SecBASH version 0.1.0")
        raise typer.Exit()

@app.command()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    )
):
    ...
```

---

## Developer Guardrails

### MUST Follow

1. **Keep startup info concise** - Maximum 2 lines showing active providers
2. **Use existing patterns** - Follow the output style from shell.py lines 40-41
3. **Semantic versioning** - Start with 0.1.0 (pre-1.0 for PoC)
4. **Test default behavior** - Verify works with just one API key set
5. **Document all env vars** - List in config.py docstring for discoverability

### MUST NOT

1. **Don't add config file support** - Environment variables only for MVP
2. **Don't change default values** - Only document and verify existing defaults
3. **Don't make prompt configurable** - Out of scope (could-have for future)
4. **Don't add excessive output** - Keep startup clean and minimal
5. **Don't modify validation logic** - Credential validation already works correctly

### Implementation Order

1. First: Add `__version__` to `__init__.py` (simple, no dependencies)
2. Second: Add version callback to `main.py` (uses `__version__`)
3. Third: Add startup info to `shell.py` (shows providers)
4. Fourth: Enhance docstrings in `config.py` (documentation)
5. Last: Write tests to verify all defaults

---

## Test Requirements

### Unit Tests for Defaults

| Test | Description | AC |
|------|-------------|-----|
| test_default_prompt_returns_secbash | get_prompt() returns "secbash> " | #2 |
| test_default_provider_priority_order | PROVIDER_PRIORITY is [openrouter, openai, anthropic] | #2 |
| test_default_shell_is_bash | execute_command uses bash -c | #2 |
| test_works_with_only_openrouter_key | System starts with just OPENROUTER_API_KEY | #1 |
| test_works_with_only_openai_key | System starts with just OPENAI_API_KEY | #1 |
| test_works_with_only_anthropic_key | System starts with just ANTHROPIC_API_KEY | #1 |
| test_version_flag_outputs_version | --version shows version string | #2 |

### Integration Tests

| Test | Description | AC |
|------|-------------|-----|
| test_startup_shows_active_providers | Startup message includes provider info | #2 |
| test_no_config_file_required | System works without any .secbash or config.yaml file | #1 |

---

## Definition of Done

- [x] `__init__.py` has `__version__ = "0.1.0"`
- [x] `main.py` has --version/-v flag that displays version
- [x] `shell.py` shows active providers at startup
- [x] `config.py` docstring documents all environment variables
- [x] All unit tests pass
- [x] All integration tests pass
- [x] No config files required for operation (only env vars)

---

## Dependencies

- **Blocked by:** Story 3.1 (API Credential Configuration) - DONE
- **Blocked by:** Story 3.2 (Warning Override) - DONE (in 2.3)
- **Blocks:** Story 3.4 (Command History), Story 3.5 (Login Shell Documentation)

---

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

No debug issues encountered.

### Completion Notes List

- Task 2.1: `__version__` already existed in `__init__.py` - no changes needed
- Task 1: Added startup info message showing active providers in `shell.py`
- Task 2.2-2.3: Added `--version/-v` flag using Typer callback pattern in `main.py`
- Task 3: Enhanced docstrings in `config.py`, `llm_client.py`, and `shell.py`
- Task 4: Created `tests/test_defaults.py` with 10 comprehensive tests covering all ACs
- All 212 tests pass (10 new tests added)
- Both acceptance criteria (AC1, AC2) verified through automated tests

### File List

- src/secbash/__init__.py (unchanged - already had `__version__`)
- src/secbash/main.py (modified - added version callback)
- src/secbash/shell.py (modified - added startup info message, import, docstring)
- src/secbash/config.py (modified - enhanced module docstring)
- src/secbash/llm_client.py (modified - added comments for model defaults)
- tests/test_defaults.py (new - 10 tests for default behavior)

### Change Log

- 2026-02-01: Implemented sensible defaults story (3.3). Added --version flag, startup provider display, and comprehensive documentation of all defaults. Created test_defaults.py with 10 tests verifying AC1 and AC2.
