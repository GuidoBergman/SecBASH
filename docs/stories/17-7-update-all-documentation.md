# Story 17.7: Update All Documentation

**Epic:** Epic 17 - Remove Runner Binary — Use /bin/bash Directly
**Status:** done
**Priority:** Medium

---

## User Story

As a **developer**,
I want **all documentation updated to reflect that aegish uses `/bin/bash` directly**,
So that **docs are accurate and don't reference the removed runner binary**.

---

## Acceptance Criteria

### AC1: PRD Updated
**Given** `docs/prd.md`
**When** updated
**Then** FR46 marked retired: "Superseded by FR80 — runner binary removed in Epic 17"
**And** FR71 updated for `/bin/bash` hash verification
**And** FR73 updated to remove runner language
**And** FR80 added

### AC2: Architecture Updated
**Given** `docs/architecture.md`
**When** runner references removed
**Then** sudo command structure uses `/bin/bash`
**And** all `/opt/aegish/bin/runner` references replaced

### AC3: Security Docs Updated
**Given** `docs/security-hardening-scope.md`
**When** DD-17 updated
**Then** DD-17 marked retired with explanation
**And** BYPASS-13 section updated

### AC4: Epics Annotated
**Given** `docs/epics.md`
**When** Epic 8 references annotated
**Then** Story 8.4 annotated "Superseded by Epic 17"
**And** FR46 in FR Coverage Map annotated as retired

### AC5: Story Files Updated
**Given** story files 8-3, 8-4, 8-5
**When** updated
**Then** 8-4 status changed to "superseded"
**And** runner references in 8-3 and 8-5 updated

---

## Tasks / Subtasks

- [ ] Task 1: Update docs/prd.md (AC: #1)
- [ ] Task 2: Update docs/architecture.md (AC: #2)
- [ ] Task 3: Update docs/security-hardening-scope.md (AC: #3)
- [ ] Task 4: Update docs/epics.md (AC: #4)
- [ ] Task 5: Update story files 8-3, 8-4, 8-5 (AC: #5)

---

## Files to Modify

- `docs/prd.md`
- `docs/architecture.md`
- `docs/security-hardening-scope.md`
- `docs/epics.md`
- `docs/stories/8-3-landlock-sandbox-implementation.md`
- `docs/stories/8-4-runner-binary-setup.md`
- `docs/stories/8-5-integrate-landlock-into-executor.md`

---

## Definition of Done

- [ ] FR46 retired, FR80 added in prd.md
- [ ] No runner references in architecture.md
- [ ] DD-17 retired in security-hardening-scope.md
- [ ] Story 8.4 marked superseded
- [ ] All runner references replaced with /bin/bash

---

## Dependencies

- **Blocked by:** All code stories (17.1-17.5, 17.8-17.10)
- **Blocks:** None
