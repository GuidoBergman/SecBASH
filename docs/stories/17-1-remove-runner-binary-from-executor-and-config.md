# Story 17.1: Remove Runner Binary from Executor and Config

**Epic:** Epic 17 - Remove Runner Binary — Use /bin/bash Directly
**Status:** done
**Priority:** High
**FR:** FR80 (new), FR46 (retired)
**Design Decision:** DD-17 (retired)

---

## User Story

As a **developer**,
I want **production mode to use `/bin/bash` directly instead of the runner binary**,
So that **the deployment is simpler and the Landlock mechanism works the same way without a separate binary**.

---

## Acceptance Criteria

### AC1: Production Mode Uses /bin/bash
**Given** production mode is active
**When** `execute_command()` runs a user command
**Then** the command executes via `["/bin/bash", "--norc", "--noprofile", "-c", command]`
**And** the LD_PRELOAD sandboxer denies `/bin/bash` for child processes

### AC2: _get_shell_binary() Returns /bin/bash
**Given** `_get_shell_binary()` in executor.py
**When** called in production mode
**Then** it returns `"/bin/bash"` (not `get_runner_path()`)

### AC3: Runner Code Removed from config.py
**Given** config.py
**When** the runner-related code is removed
**Then** the following are deleted: `DEFAULT_RUNNER_PATH`, `PRODUCTION_RUNNER_PATH`, `get_runner_path()`, `validate_runner_binary()`, `AEGISH_RUNNER_PATH` env var handling

### AC4: AEGISH_RUNNER_PATH Not Injected
**Given** `_build_safe_env()` in executor.py
**When** building the production environment
**Then** `AEGISH_RUNNER_PATH` is no longer injected

### AC5: sanitize_env() Updated
**Given** `sanitize_env()` in executor.py
**When** re-injecting production variables
**Then** `AEGISH_RUNNER_PATH` is no longer re-injected

---

## Tasks / Subtasks

- [ ] Task 1: Remove runner code from config.py (AC: #3)
  - [ ] 1.1 Delete `DEFAULT_RUNNER_PATH` and `PRODUCTION_RUNNER_PATH` constants
  - [ ] 1.2 Delete `get_runner_path()` function
  - [ ] 1.3 Delete `validate_runner_binary()` function
  - [ ] 1.4 Remove `AEGISH_RUNNER_PATH` and `AEGISH_RUNNER_HASH` from `SECURITY_CRITICAL_KEYS`

- [ ] Task 2: Simplify executor.py (AC: #1, #2, #4, #5)
  - [ ] 2.1 Simplify `_get_shell_binary()` to return `"/bin/bash"` always
  - [ ] 2.2 Remove `AEGISH_RUNNER_PATH` from `_build_safe_env()`
  - [ ] 2.3 Remove `AEGISH_RUNNER_PATH` from `sanitize_env()`
  - [ ] 2.4 Update `_execute_sudo_sandboxed()` to use `/bin/bash` directly

- [ ] Task 3: Clean up sandbox.py (AC: #3)
  - [ ] 3.1 Remove `DEFAULT_RUNNER_PATH` if present in sandbox.py

---

## Files to Modify

- `src/aegish/config.py` — Remove runner constants, functions, security keys
- `src/aegish/executor.py` — Simplify `_get_shell_binary()`, remove runner env injection
- `src/aegish/sandbox.py` — Remove `DEFAULT_RUNNER_PATH` if present

---

## Definition of Done

- [ ] `_get_shell_binary()` returns `"/bin/bash"` in production mode
- [ ] `DEFAULT_RUNNER_PATH`, `PRODUCTION_RUNNER_PATH` deleted from config.py
- [ ] `get_runner_path()`, `validate_runner_binary()` deleted from config.py
- [ ] `AEGISH_RUNNER_PATH` not injected in env by executor.py
- [ ] No runner references in executor.py or sandbox.py

---

## Dependencies

- **Blocked by:** Story 17.8 (sandboxer hash verification must exist first)
- **Blocks:** Stories 17.4, 17.5, 17.6
