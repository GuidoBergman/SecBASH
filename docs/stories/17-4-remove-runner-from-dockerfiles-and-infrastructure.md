# Story 17.4: Remove Runner from Dockerfiles and Infrastructure

**Epic:** Epic 17 - Remove Runner Binary — Use /bin/bash Directly
**Status:** done
**Priority:** Medium

---

## User Story

As a **developer**,
I want **all Docker and infrastructure files updated to remove runner binary creation**,
So that **the deployment pipeline is simpler and doesn't create unnecessary artifacts**.

---

## Acceptance Criteria

### AC1: Production Dockerfile Cleaned
**Given** the production Dockerfile
**When** runner steps are removed
**Then** `mkdir -p /opt/aegish/bin && ln /bin/bash /opt/aegish/bin/runner` is deleted
**And** hash computation uses `/bin/bash` directly
**And** `AEGISH_RUNNER_HASH` becomes `AEGISH_BASH_HASH`
**And** `/opt/aegish/bin/` directory is no longer created

### AC2: Test Dockerfile Cleaned
**Given** `tests/Dockerfile.production`
**When** updated
**Then** same changes as the production Dockerfile

### AC3: Docker Compose Cleaned
**Given** `docker-compose.yml` and `tests/docker-compose.production.yml`
**When** checked for runner references
**Then** any runner-related environment variables or volume mounts are removed

---

## Tasks / Subtasks

- [ ] Task 1: Update production Dockerfile (AC: #1)
  - [ ] 1.1 Remove hardlink creation step
  - [ ] 1.2 Update hash computation to `/bin/bash` → `AEGISH_BASH_HASH`
  - [ ] 1.3 Remove `/opt/aegish/bin/` directory creation

- [ ] Task 2: Update tests/Dockerfile.production (AC: #2)
  - [ ] 2.1 Same changes as production Dockerfile

- [ ] Task 3: Check compose files (AC: #3)
  - [ ] 3.1 Remove any runner env vars/mounts from compose files

---

## Files to Modify

- `Dockerfile` — Remove runner hardlink, update hash
- `tests/Dockerfile.production` — Same changes
- `docker-compose.yml` — Remove runner refs if present
- `tests/docker-compose.production.yml` — Same

---

## Definition of Done

- [ ] No runner hardlink creation in any Dockerfile
- [ ] Hash computation targets `/bin/bash` with key `AEGISH_BASH_HASH`
- [ ] No runner references in compose files
- [ ] `/opt/aegish/bin/` no longer created

---

## Dependencies

- **Blocked by:** Stories 17.1, 17.2, 17.3
- **Blocks:** Story 17.6
