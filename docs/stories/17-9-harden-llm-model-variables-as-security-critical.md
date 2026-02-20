# Story 17.9: Harden LLM Model Variables as Security-Critical

**Epic:** Epic 17 - Remove Runner Binary — Use /bin/bash Directly
**Status:** done
**Priority:** High
**NFR Assessment:** BYPASS — env var injection of malicious LLM endpoint

---

## User Story

As a **security engineer**,
I want **`AEGISH_PRIMARY_MODEL` and `AEGISH_FALLBACK_MODELS` added to `SECURITY_CRITICAL_KEYS` and routed through `_get_security_config()`**,
So that **an attacker cannot redirect validation to a malicious LLM endpoint**.

---

## Acceptance Criteria

### AC1: Keys Added to SECURITY_CRITICAL_KEYS
**Given** `SECURITY_CRITICAL_KEYS` in config.py
**When** updated
**Then** `"AEGISH_PRIMARY_MODEL"` and `"AEGISH_FALLBACK_MODELS"` are in the set

### AC2: get_primary_model() Uses Security Config
**Given** `get_primary_model()` in config.py
**When** called in production mode
**Then** it reads from `_get_security_config("AEGISH_PRIMARY_MODEL")`

### AC3: get_fallback_models() Uses Security Config
**Given** `get_fallback_models()` in config.py
**When** called in production mode
**Then** it reads from `_get_security_config("AEGISH_FALLBACK_MODELS")`

### AC4: Dockerfile Embeds Model Config
**Given** the Dockerfile
**When** built
**Then** `AEGISH_PRIMARY_MODEL` and `AEGISH_FALLBACK_MODELS` are embedded in `/etc/aegish/config`

---

## Tasks / Subtasks

- [ ] Task 1: Add model keys to SECURITY_CRITICAL_KEYS (AC: #1)
  - [ ] 1.1 Add both keys to the set

- [ ] Task 2: Refactor get_primary_model() (AC: #2)
  - [ ] 2.1 Replace `os.environ.get()` with `_get_security_config()`

- [ ] Task 3: Refactor get_fallback_models() (AC: #3)
  - [ ] 3.1 Replace `os.environ.get()` with `_get_security_config()`

- [ ] Task 4: Update Dockerfile (AC: #4)
  - [ ] 4.1 Embed model config in `/etc/aegish/config`

---

## Files to Modify

- `src/aegish/config.py` — Add keys to security set, refactor model getters
- `Dockerfile` — Embed model config
- `tests/test_config.py` — Verify keys in security set, verify production reads from config

---

## Definition of Done

- [ ] Both keys in `SECURITY_CRITICAL_KEYS`
- [ ] `get_primary_model()` uses `_get_security_config()`
- [ ] `get_fallback_models()` uses `_get_security_config()`
- [ ] Dockerfile embeds model config in `/etc/aegish/config`

---

## Dependencies

- **Blocked by:** None
- **Blocks:** Story 17.6 (tests)
