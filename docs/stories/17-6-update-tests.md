# Story 17.6: Update Tests

**Epic:** Epic 17 - Remove Runner Binary — Use /bin/bash Directly
**Status:** done
**Priority:** High

---

## User Story

As a **developer**,
I want **all unit and integration tests updated to reflect the runner removal**,
So that **tests verify the new behavior and don't reference removed code**.

---

## Acceptance Criteria

### AC1: Config Tests Updated
**Given** `tests/test_config.py`
**When** runner-related tests are updated
**Then** tests for `get_runner_path()` and `validate_runner_binary()` are removed
**And** tests for `/bin/bash` hash verification are added

### AC2: Executor Tests Updated
**Given** `tests/test_executor.py`
**When** runner-related tests are updated
**Then** tests asserting runner path in production are updated to assert `/bin/bash`
**And** tests checking `AEGISH_RUNNER_PATH` in env are removed

### AC3: Sandbox Tests Updated
**Given** `tests/test_sandbox.py`
**When** runner references are updated
**Then** `DEFAULT_RUNNER_PATH` references are removed

### AC4: Integration Tests Updated
**Given** `tests/test_production_mode.py` (if exists)
**When** updated
**Then** Docker-based tests don't check runner binary existence
**And** tests verify `/bin/bash` is denied by Landlock for child processes

---

## Tasks / Subtasks

- [ ] Task 1: Update test_config.py (AC: #1)
  - [ ] 1.1 Remove `TestGetRunnerPath` and `TestValidateRunnerBinary` test classes
  - [ ] 1.2 Add `TestValidateBashBinary` tests (match, mismatch, missing hash)
  - [ ] 1.3 Update `SECURITY_CRITICAL_KEYS` tests for new keys

- [ ] Task 2: Update test_executor.py (AC: #2)
  - [ ] 2.1 Update `_get_shell_binary()` tests to assert `/bin/bash`
  - [ ] 2.2 Remove `AEGISH_RUNNER_PATH` env assertions

- [ ] Task 3: Update test_sandbox.py (AC: #3)
  - [ ] 3.1 Remove `DEFAULT_RUNNER_PATH` references

- [ ] Task 4: Update integration tests (AC: #4)
  - [ ] 4.1 Update test_production_mode.py if exists

---

## Files to Modify

- `tests/test_config.py`
- `tests/test_executor.py`
- `tests/test_sandbox.py`
- `tests/test_production_mode.py` (if exists)

---

## Definition of Done

- [ ] No runner-related test assertions remain
- [ ] New tests for bash hash verification
- [ ] All tests pass with no regressions

---

## Dependencies

- **Blocked by:** All code stories (17.1-17.5, 17.8-17.10)
- **Blocks:** None
