# Story 17.10: Add AEGISH_SKIP_BASH_HASH Option for Bare-Metal Deployments

**Epic:** Epic 17 - Remove Runner Binary — Use /bin/bash Directly
**Status:** done
**Priority:** Medium

---

## User Story

As a **system administrator**,
I want **a configuration option to disable `/bin/bash` hash verification**,
So that **automated package manager updates don't cause aegish to refuse to start on bare-metal installs**.

---

## Acceptance Criteria

### AC1: Key in SECURITY_CRITICAL_KEYS
**Given** `SECURITY_CRITICAL_KEYS` in config.py
**When** updated
**Then** `"AEGISH_SKIP_BASH_HASH"` is in the set

### AC2: Skip Bash Hash When Enabled
**Given** `AEGISH_SKIP_BASH_HASH=true` in `/etc/aegish/config`
**When** aegish starts in production mode
**Then** `/bin/bash` hash check is skipped
**And** a warning is logged: "WARNING: /bin/bash hash verification disabled via AEGISH_SKIP_BASH_HASH. Binary integrity is not checked."

### AC3: Default Behavior Unchanged
**Given** `AEGISH_SKIP_BASH_HASH` is unset or not `true`
**When** aegish starts in production mode
**Then** hash check runs normally (fail-closed)

### AC4: Sandboxer Hash Not Affected
**Given** `AEGISH_SKIP_BASH_HASH=true`
**When** aegish starts
**Then** sandboxer `.so` hash check still runs regardless

---

## Tasks / Subtasks

- [ ] Task 1: Add skip key to config.py (AC: #1, #2, #3)
  - [ ] 1.1 Add `"AEGISH_SKIP_BASH_HASH"` to `SECURITY_CRITICAL_KEYS`
  - [ ] 1.2 Add `skip_bash_hash()` helper reading from `_get_security_config()`
  - [ ] 1.3 Return True only when value is exactly `"true"` (case-insensitive)

- [ ] Task 2: Gate hash check in startup (AC: #2, #4)
  - [ ] 2.1 In shell.py, check `skip_bash_hash()` before calling bash validation
  - [ ] 2.2 Log warning when skip is active
  - [ ] 2.3 Sandboxer hash check remains unconditional

---

## Files to Modify

- `src/aegish/config.py` — Add `AEGISH_SKIP_BASH_HASH` to security keys, add `skip_bash_hash()` helper
- `src/aegish/shell.py` — Gate bash hash check with skip option

---

## Definition of Done

- [ ] `AEGISH_SKIP_BASH_HASH` in `SECURITY_CRITICAL_KEYS`
- [ ] `skip_bash_hash()` helper works
- [ ] Setting `true` skips bash hash check with warning
- [ ] Sandboxer hash check always runs

---

## Dependencies

- **Blocked by:** Stories 17.2 (bash hash verification must exist first)
- **Blocks:** Story 17.6 (tests)
