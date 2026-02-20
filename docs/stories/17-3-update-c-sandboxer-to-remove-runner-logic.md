# Story 17.3: Update C Sandboxer to Remove Runner Logic

**Epic:** Epic 17 - Remove Runner Binary — Use /bin/bash Directly
**Status:** done
**Priority:** High

---

## User Story

As a **developer**,
I want **the C sandboxer library cleaned of runner-specific code**,
So that **the sandboxer is simpler and `/bin/bash` denial relies solely on `DENIED_SHELLS`**.

---

## Acceptance Criteria

### AC1: Runner Variables Removed
**Given** the `apply_sandbox()` constructor in `landlock_sandboxer.c`
**When** the runner logic is removed
**Then** the `AEGISH_RUNNER_PATH` env var is no longer read
**And** the `runner` and `runner_resolved` variables are removed

### AC2: is_denied() Simplified
**Given** the `is_denied()` function
**When** runner-specific comparisons removed
**Then** it only checks against `DENIED_SHELLS`

### AC3: Behavior Preserved
**Given** the sandboxer is compiled and loaded via LD_PRELOAD
**When** bash runs a user command
**Then** `/bin/bash` is denied via `DENIED_SHELLS` and non-shell binaries are allowed

---

## Tasks / Subtasks

- [ ] Task 1: Clean up landlock_sandboxer.c (AC: #1, #2, #3)
  - [ ] 1.1 Remove `runner` and `runner_resolved` variable declarations
  - [ ] 1.2 Remove `AEGISH_RUNNER_PATH` getenv call
  - [ ] 1.3 Remove runner-specific block in `is_denied()` (lines 70-77)
  - [ ] 1.4 Keep `DENIED_SHELLS` loop intact

- [ ] Task 2: Recompile sandboxer
  - [ ] 2.1 Run `make` to rebuild the .so file

---

## Files to Modify

- `src/sandboxer/landlock_sandboxer.c` — Remove runner vars, simplify `is_denied()`

---

## Definition of Done

- [ ] No `AEGISH_RUNNER_PATH` references in C code
- [ ] No `runner`/`runner_resolved` variables
- [ ] `is_denied()` only checks `DENIED_SHELLS`
- [ ] Sandboxer compiles cleanly

---

## Dependencies

- **Blocked by:** Story 17.8 (sandboxer hash must exist before removing runner)
- **Blocks:** Stories 17.4, 17.6
