# Story 17.8: SHA-256 Hash Verification for Sandboxer Library

**Epic:** Epic 17 - Remove Runner Binary — Use /bin/bash Directly
**Status:** done
**Priority:** Critical
**NFR Assessment:** Integrity verification gap — sandboxer .so has no hash check

---

## User Story

As a **security engineer**,
I want **the sandboxer shared library verified via SHA-256 hash at startup, with its path hardcoded in production mode**,
So that **a tampered or substituted `.so` cannot bypass Landlock enforcement**.

---

## Acceptance Criteria

### AC1: AEGISH_SANDBOXER_HASH in Security Keys
**Given** `SECURITY_CRITICAL_KEYS` in config.py
**When** updated
**Then** `"AEGISH_SANDBOXER_HASH"` is in the set

### AC2: get_sandboxer_path() Hardened
**Given** `get_sandboxer_path()` in config.py
**When** called in production mode
**Then** it returns hardcoded `DEFAULT_SANDBOXER_PATH` (ignores env vars)
**And** in non-production mode, reads from `_get_security_config("AEGISH_SANDBOXER_PATH")`

### AC3: validate_sandboxer_library() Hash Check
**Given** `validate_sandboxer_library()` in config.py
**When** called in production mode
**Then** it computes SHA-256 hash and compares against `AEGISH_SANDBOXER_HASH`
**And** returns failure on mismatch with actionable error message
**And** returns failure if no hash is configured

### AC4: Dockerfile Embeds Hash
**Given** the Dockerfile
**When** built
**Then** sandboxer hash computed after `make install` and appended to `/etc/aegish/config`

### AC5: Shell Startup Fatal on Failure
**Given** shell.py startup validation
**When** `validate_sandboxer_library()` fails in production
**Then** aegish exits with `sys.exit(1)` (NOT fallback to dev mode)

---

## Tasks / Subtasks

- [ ] Task 1: Add sandboxer hash to security keys (AC: #1)
  - [ ] 1.1 Add `"AEGISH_SANDBOXER_HASH"` to `SECURITY_CRITICAL_KEYS`

- [ ] Task 2: Harden get_sandboxer_path() (AC: #2)
  - [ ] 2.1 Return hardcoded path in production mode
  - [ ] 2.2 Use `_get_security_config()` in non-production mode

- [ ] Task 3: Add hash verification to validate_sandboxer_library() (AC: #3)
  - [ ] 3.1 Read expected hash from `_get_security_config("AEGISH_SANDBOXER_HASH")`
  - [ ] 3.2 Compute actual hash with `_compute_file_sha256()`
  - [ ] 3.3 Return actionable error on mismatch
  - [ ] 3.4 Return error if no hash configured in production

- [ ] Task 4: Update Dockerfiles (AC: #4)
  - [ ] 4.1 Add sandboxer hash computation step after `make install`

- [ ] Task 5: Update shell.py (AC: #5)
  - [ ] 5.1 Change sandboxer failure from fallback to `sys.exit(1)`

---

## Files to Modify

- `src/aegish/config.py` — Security keys, get_sandboxer_path(), validate_sandboxer_library()
- `Dockerfile` — Add sandboxer hash embed step
- `tests/Dockerfile.production` — Same
- `src/aegish/shell.py` — Fatal exit on sandboxer failure

---

## Definition of Done

- [ ] `AEGISH_SANDBOXER_HASH` in `SECURITY_CRITICAL_KEYS`
- [ ] `get_sandboxer_path()` hardcoded in production
- [ ] `validate_sandboxer_library()` verifies SHA-256 hash
- [ ] Actionable error message on mismatch
- [ ] Dockerfile embeds sandboxer hash
- [ ] Shell exits fatally on sandboxer validation failure

---

## Dependencies

- **Blocked by:** None
- **Blocks:** Stories 17.1, 17.2, 17.3 (CRITICAL — must be done first)
