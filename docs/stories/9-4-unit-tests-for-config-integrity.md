# Story 9.4: Unit Tests for Config Integrity

Status: done

## Story

As a **developer**,
I want **unit tests for provider allowlist, health check, and model warnings**,
So that **configuration integrity features are verified against regressions**.

## Acceptance Criteria

1. Provider allowlist: accepted providers pass, unknown rejected, custom allowlist via env var works
2. Health check success: mock correct response returns `(True, "")`
3. Health check failure: mock error/wrong action returns `(False, "description")`, no crash
4. Health check timeout: returns `(False, "description")`, does not block
5. Non-default model: `is_default_primary_model()` returns True for default, False for custom
6. Empty fallbacks: warning shown for single-provider mode

## Tasks / Subtasks

- [ ] Task 1: Create `tests/test_config_integrity.py`
  - [ ] 1.1: `TestProviderAllowlistIntegration` - unknown provider rejected in query_llm, custom allowlist works
  - [ ] 1.2: `TestHealthCheckIntegration` - valid config passes, no API key fails, unparseable response fails, timeout fails
  - [ ] 1.3: `TestStartupIntegration` - warnings before health check, no warnings with defaults, non-default triggers warning, empty fallbacks triggers warning
- [ ] Task 2: Run tests and verify no regressions

## Dev Notes

### Existing Unit Tests (Stories 9.1-9.3)

Individual unit tests already exist:
- `test_config.py`: `TestGetAllowedProviders` (7), `TestValidateModelProvider` (7), `TestIsDefaultPrimaryModel` (4), `TestIsDefaultFallbackModels` (3), `TestHasFallbackModels` (3)
- `test_llm_client.py`: health check tests
- `test_shell.py`: `TestStartupModelWarnings` (4)

This story adds **cross-feature integration tests** verifying features work together.

### Key Integration Scenarios

1. Allowlist -> query_llm: model from unknown provider rejected at query level
2. Health check -> startup: failure warning appears in correct position
3. Warnings -> health check ordering: warnings appear BEFORE health check
4. Full startup flow: all three features produce correct output

### Implementation Details

- `config.py`: `get_allowed_providers()` (line 261), `validate_model_provider()` (line 282), `is_default_primary_model()` (line 310)
- `llm_client.py`: `health_check()` (line 206) with 5-second timeout
- `shell.py`: warnings (lines 123-134), health check (lines 137-140)

### Mock Patterns

- `mocker.patch.dict(os.environ, {...}, clear=True)` for config
- `patch("aegish.shell.health_check", return_value=(True, ""))` for shell tests
- `patch("builtins.input", side_effect=["exit"])` for single shell iteration
- `capsys.readouterr()` for startup output

### Files

- Create: `tests/test_config_integrity.py`
- No modifications to existing files
