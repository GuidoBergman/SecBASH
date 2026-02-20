# Story 17.5: Update Shell Startup Validation

**Epic:** Epic 17 - Remove Runner Binary — Use /bin/bash Directly
**Status:** done
**Priority:** High

---

## User Story

As a **developer**,
I want **the shell startup sequence updated to validate `/bin/bash` instead of the runner binary**,
So that **startup checks are accurate and don't reference a nonexistent runner**.

---

## Acceptance Criteria

### AC1: No Runner Validation Call
**Given** aegish starts in production mode
**When** startup validation runs
**Then** it does NOT call `validate_runner_binary()`

### AC2: Bash Hash Verified at Startup
**Given** production mode startup
**When** validation runs
**Then** it verifies SHA-256 hash of `/bin/bash` against `AEGISH_BASH_HASH`

### AC3: Banner Updated
**Given** the startup banner
**When** displayed in production mode
**Then** it does NOT mention "runner binary"
**And** hash verification status is reported (e.g., "bash integrity: verified")

---

## Tasks / Subtasks

- [ ] Task 1: Update shell.py startup validation (AC: #1, #2)
  - [ ] 1.1 Replace `validate_runner_binary()` call with `validate_bash_binary()` call
  - [ ] 1.2 Keep fail-closed behavior (sys.exit(1) on failure)

- [ ] Task 2: Update banner (AC: #3)
  - [ ] 2.1 Remove any "runner binary" text from startup messages
  - [ ] 2.2 Report bash integrity verification status

---

## Files to Modify

- `src/aegish/shell.py` — Replace runner validation with bash validation, update banner

---

## Definition of Done

- [ ] `validate_runner_binary()` no longer called at startup
- [ ] `validate_bash_binary()` called in production mode
- [ ] Fail-closed on hash mismatch
- [ ] No "runner binary" in banner or startup messages

---

## Dependencies

- **Blocked by:** Stories 17.1, 17.2
- **Blocks:** Story 17.6
