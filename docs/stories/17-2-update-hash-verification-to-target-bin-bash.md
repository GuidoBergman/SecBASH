# Story 17.2: Update Hash Verification to Target /bin/bash

**Epic:** Epic 17 - Remove Runner Binary — Use /bin/bash Directly
**Status:** done
**Priority:** High
**FR:** FR80

---

## User Story

As a **developer**,
I want **the SHA-256 integrity check to verify `/bin/bash` instead of the runner binary**,
So that **system bash updates are detected and the operator must acknowledge them**.

---

## Acceptance Criteria

### AC1: Hash Checks /bin/bash
**Given** production mode startup
**When** hash verification runs
**Then** it computes SHA-256 of `/bin/bash` and compares against `AEGISH_BASH_HASH` in `/etc/aegish/config`

### AC2: Hash Mismatch Message
**Given** the system bash is updated
**When** aegish starts after the update
**Then** the hash check fails with actionable guidance:
```
FATAL: /bin/bash hash mismatch.
  Expected: abc123...
  Actual:   def456...
Step 1 — Verify the binary is a legitimate package update:
  dpkg --verify bash        # Debian/Ubuntu
  rpm -V bash               # RHEL/CentOS
Step 2 — Only after verification, update the stored hash:
  sudo sed -i 's/^AEGISH_BASH_HASH=.*/AEGISH_BASH_HASH=def456.../' /etc/aegish/config
```
**And** aegish refuses to start (fail-closed)

### AC3: Dockerfile Embeds Bash Hash
**Given** the Dockerfile
**When** the image is built
**Then** `BASH_HASH=$(sha256sum /bin/bash | cut -d' ' -f1)` is used
**And** the hash is embedded as `AEGISH_BASH_HASH`

---

## Tasks / Subtasks

- [ ] Task 1: Add bash hash verification function to config.py (AC: #1, #2)
  - [ ] 1.1 Add `validate_bash_binary()` function computing SHA-256 of `/bin/bash`
  - [ ] 1.2 Read expected hash from `_get_security_config("AEGISH_BASH_HASH")`
  - [ ] 1.3 Return actionable error message on mismatch with actual hash and sed command
  - [ ] 1.4 Add `AEGISH_BASH_HASH` to `SECURITY_CRITICAL_KEYS`

- [ ] Task 2: Update Dockerfile hash computation (AC: #3)
  - [ ] 2.1 Replace runner hash line with bash hash computation

---

## Files to Modify

- `src/aegish/config.py` — Add `validate_bash_binary()`, add `AEGISH_BASH_HASH` to security keys
- `Dockerfile` — Update hash computation to target /bin/bash
- `tests/Dockerfile.production` — Same changes

---

## Definition of Done

- [ ] `validate_bash_binary()` computes SHA-256 of `/bin/bash`
- [ ] Hash compared against `AEGISH_BASH_HASH` from config
- [ ] Actionable error message on mismatch
- [ ] `AEGISH_BASH_HASH` in `SECURITY_CRITICAL_KEYS`
- [ ] Dockerfile embeds `AEGISH_BASH_HASH`

---

## Dependencies

- **Blocked by:** Story 17.8 (sandboxer hash must exist)
- **Blocks:** Stories 17.5, 17.6, 17.10
