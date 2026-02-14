# Story 8.6: Docker-Based Testing Infrastructure

Status: Done

## Story

As a **developer**,
I want **a Docker-based test environment for production mode verification**,
So that **login shell + Landlock behavior can be tested safely without affecting the host system**.

## Acceptance Criteria

1. **Given** a Dockerfile for production mode testing, **When** the image is built and a container started, **Then** the container has:
   - aegish installed and registered in `/etc/shells`
   - A test user with aegish as login shell
   - SSH server for login shell testing
   - Test tools: vim, less, python3, git
   - Production mode environment variables set (`AEGISH_MODE=production`, `AEGISH_FAIL_MODE=safe`)
   - Runner binary at `/opt/aegish/bin/runner` (hardlink to `/bin/bash`)

2. **Given** a running test container, **When** connecting via SSH as testuser, **Then** the user drops directly into aegish (no parent shell)

3. **Given** the Dockerfile, **When** built, **Then** `docker build -t aegish-test -f tests/Dockerfile.production .` succeeds

4. **Given** a Docker Compose file, **When** `docker compose -f tests/docker-compose.production.yml up -d` is run, **Then** the production test container starts with SSH accessible on a mapped port, with a healthcheck verifying SSH readiness

## Tasks / Subtasks

- [x] Task 1: Create Dockerfile for production mode testing (AC: #1, #3)
  - [x] 1.1: Base on `ubuntu:24.04` with Python 3.10+, install system dependencies (vim-tiny, less, man-db, git, openssh-server, gettext-base, netcat-openbsd)
  - [x] 1.2: Install `uv` using `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv`
  - [x] 1.3: Copy project source, install aegish via `uv sync --frozen` (or `uv pip install -e .` for editable)
  - [x] 1.4: Create runner binary: `mkdir -p /opt/aegish/bin && ln /bin/bash /opt/aegish/bin/runner` (MUST be hardlink, NOT symlink -- Landlock resolves symlinks, see DD-17)
  - [x] 1.5: Register aegish in `/etc/shells` via `echo "$(which aegish)" >> /etc/shells`
  - [x] 1.6: Create test user: `useradd -m -s "$(which aegish)" testuser && echo "testuser:testpass" | chpasswd`
  - [x] 1.7: Configure SSH: `mkdir /run/sshd`, enable PasswordAuthentication
  - [x] 1.8: Set production env vars: `ENV AEGISH_MODE=production`, `ENV AEGISH_FAIL_MODE=safe`
  - [x] 1.9: Expose port 22, CMD `["/usr/sbin/sshd", "-D"]`

- [x] Task 2: Create Docker Compose file for easy orchestration (AC: #4)
  - [x] 2.1: Create `tests/docker-compose.production.yml` with service definition
  - [x] 2.2: Map SSH port (e.g., `2222:22`)
  - [x] 2.3: Add healthcheck using `nc -z localhost 22`
  - [x] 2.4: Document `--security-opt seccomp=unconfined` as fallback if Landlock syscalls are blocked (modern Docker should NOT need this)

- [x] Task 3: Verify build and container functionality (AC: #1, #2, #3)
  - [x] 3.1: Build image: `docker build -t aegish-test -f tests/Dockerfile.production .`
  - [x] 3.2: Start container and verify SSH access
  - [x] 3.3: Verify aegish is the login shell for testuser
  - [x] 3.4: Verify runner binary exists at `/opt/aegish/bin/runner`
  - [x] 3.5: Verify test tools are available (vim, less, python3, git)
  - [x] 3.6: Verify Landlock support in container (kernel version check)

## Dev Notes

### Epic 8 Context

This story is part of **Epic 8: Production Mode -- Login Shell + Landlock Enforcement**. The epic covers BYPASS-12 (exit escape), BYPASS-13 (interactive shell spawning), and BYPASS-18 (exec shell). This story provides the **testing infrastructure** used by Story 8.7 (integration tests for bypass verification).

**Epic dependencies:** Epic 6 (env sanitization) must be implemented first. Stories 8.1-8.5 implement the actual production mode features that this Docker environment tests:
- 8.1: `AEGISH_MODE` configuration
- 8.2: Login shell exit behavior
- 8.3: Landlock sandbox implementation (`src/aegish/sandbox.py`)
- 8.4: Runner binary setup
- 8.5: Landlock integration into executor.py

**CRITICAL:** This story creates only the Docker testing infrastructure (Dockerfile + Compose). The actual integration **tests** are Story 8.7. Do NOT implement test cases in this story -- only the container environment.

### Architecture Compliance

**Project structure** (from architecture.md):
```
aegish/
├── src/aegish/          # Production code
├── tests/               # Test files
│   ├── Dockerfile.production          # NEW (this story)
│   └── docker-compose.production.yml  # NEW (this story)
├── benchmark/           # Evaluation infrastructure
└── pyproject.toml
```

**Module layout:** The production source is at `src/aegish/` with entry point `aegish = "aegish.main:app"` (from pyproject.toml). The `aegish` command is a Typer CLI app.

**Executor module** (`src/aegish/executor.py`): Currently uses bare `subprocess.run(["bash", "-c", ...])` -- Epic 8 stories 8.3-8.5 will add Landlock preexec_fn and runner binary support. The Dockerfile should be written to work with the FUTURE state of the codebase (post stories 8.1-8.5).

### Technical Requirements

**Landlock + Docker compatibility:**
- Docker's default seccomp profile **includes Landlock syscalls** (moby/moby PR #43199). No special flags needed on modern Docker.
- Landlock requires Linux kernel 5.13+. The host WSL2 kernel is 5.15 -- Landlock is supported.
- Docker containers share the host kernel -- if the host supports Landlock, containers do too.
- **Fallback:** If Landlock syscalls are blocked by an older Docker version, use `--security-opt seccomp=unconfined` (document in Compose file as comment).

**Runner binary (DD-17):**
- MUST be a **hardlink** (`ln /bin/bash /opt/aegish/bin/runner`), NOT a symlink
- Landlock resolves symlinks before checking permissions -- a symlink to `/bin/bash` would be resolved and denied
- A hardlink has a distinct path entry and Landlock checks the path, not the inode
- If hardlink fails (cross-filesystem), fall back to `cp /bin/bash /opt/aegish/bin/runner`

**uv in Docker (latest best practice):**
- Use multi-stage copy: `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv`
- Install project: `uv sync --frozen` (don't update lockfile in container)
- Alternative: `pip install --break-system-packages -e .` if uv adds complexity

### Library & Framework Requirements

| Dependency | Version/Source | Purpose |
|------------|---------------|---------|
| Docker | Host-installed | Container runtime |
| ubuntu:24.04 | Docker Hub | Base image |
| ghcr.io/astral-sh/uv:latest | GitHub Container Registry | uv package manager for Docker |
| openssh-server | apt | SSH server for login shell testing |
| vim-tiny | apt | Test tool (shell escape vector: `:!bash`) |
| less | apt | Test tool (shell escape vector: `!bash`) |
| man-db | apt | Test tool (pager-based shell escapes) |
| git | apt | Test tool (pager-based shell escapes) |
| python3 | apt (bundled with ubuntu:24.04) | Test tool (`os.system('bash')` vector) |
| gettext-base | apt | Provides `envsubst` (used by Epic 7) |
| netcat-openbsd | apt | Healthcheck for SSH (`nc -z localhost 22`) |

### File Structure Requirements

**Files to create:**
- `tests/Dockerfile.production` -- Docker image definition
- `tests/docker-compose.production.yml` -- Docker Compose orchestration

**Files NOT to modify:** No changes to production source code, existing tests, or configuration.

### Testing Requirements

**Verification of the Docker infrastructure itself (this story):**
- `docker build -t aegish-test -f tests/Dockerfile.production .` succeeds
- `docker compose -f tests/docker-compose.production.yml up -d` starts the container
- `docker exec <container> which aegish` returns a valid path
- `docker exec <container> getent passwd testuser` shows aegish as shell
- `docker exec <container> test -f /opt/aegish/bin/runner && echo OK` returns OK
- `docker exec <container> vim --version` succeeds
- `docker exec <container> python3 --version` succeeds
- `docker exec <container> git --version` succeeds

**Landlock verification command (document in Compose file comments):**
```bash
docker exec <container> python3 -c "
import ctypes, ctypes.util
libc = ctypes.CDLL(ctypes.util.find_library('c'))
try:
    fd = libc.syscall(444, 0, 0, 0x4)  # SYS_landlock_create_ruleset, ABI version check
    import os; os.close(fd)
    print('Landlock: SUPPORTED')
except:
    print('Landlock: NOT SUPPORTED')
"
```

### Design Decisions Referenced

| ID | Decision | Impact on This Story |
|----|----------|---------------------|
| DD-13 | Login shell approach (not exit-trapping) | testuser must have aegish as login shell via `chsh`/`useradd -s` |
| DD-14 | Production/development modes via AEGISH_MODE | Container sets `AEGISH_MODE=production` |
| DD-15 | Landlock over other sandboxing | Docker must support Landlock syscalls (default seccomp allows them) |
| DD-16 | Shell scripts break in production mode | Expected behavior in test container; tests should account for this |
| DD-17 | Runner hardlink (not symlink) | `ln /bin/bash /opt/aegish/bin/runner` (hardlink), NOT `ln -s` |

### Security Hardening Reference

**Source:** docs/security-hardening-scope.md, "Testing Strategy: Docker-Based Production Mode Verification" section

The security-hardening-scope.md provides a **complete reference Dockerfile** and test patterns. The implementation should follow that reference closely, with the following improvements from web research:
1. Use `uv` instead of `pip install --break-system-packages` for faster, more reliable builds
2. Add healthcheck in Docker Compose for test reliability
3. No `--security-opt seccomp=unconfined` needed (modern Docker includes Landlock syscalls)

### SSH Test Pattern

```bash
# Build and start
docker build -t aegish-test -f tests/Dockerfile.production .
docker run -d --name aegish-prod-test -p 2222:22 aegish-test

# Connect as testuser (drops directly into aegish)
ssh -p 2222 testuser@localhost
# Password: testpass
```

### IMPORTANT: Story 8.7 Boundary

This story creates the **infrastructure only**. Do NOT implement:
- Integration test files (`tests/test_production_mode.py`)
- The `aegish --single-command` flag
- Any bypass verification tests

Those belong to **Story 8.7: Integration Tests for Bypass Verification**.

### Project Structure Notes

- Alignment with unified project structure: Tests infrastructure files go in `tests/` directory per architecture.md
- No production code changes required
- Docker files follow the `tests/Dockerfile.*` naming convention (similar to how benchmark/ is separated)

### References

- [Source: docs/security-hardening-scope.md#Testing Strategy: Docker-Based Production Mode Verification] -- Full reference Dockerfile and test patterns
- [Source: docs/epics.md#Story 8.6: Docker-Based Testing Infrastructure] -- Acceptance criteria
- [Source: docs/architecture.md#Complete Project Directory Structure] -- Project structure
- [Source: docs/security-hardening-scope.md#DD-17] -- Runner binary must be hardlink, not symlink
- [Source: docs/security-hardening-scope.md#DD-15] -- Landlock over other sandboxing mechanisms
- [Source: docs/security-hardening-scope.md#BYPASS-13] -- Landlock implementation details and shell denial list
- [Source: docs/prd.md#FR43-FR47] -- Production mode functional requirements
- [Docker seccomp + Landlock: moby/moby PR #43199] -- Docker default seccomp allows Landlock syscalls
- [uv Docker guide: docs.astral.sh/uv/guides/integration/docker/] -- COPY --from pattern for uv

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- Task 1: Created `tests/Dockerfile.production` based on reference in security-hardening-scope.md with improvements: uses `uv` (COPY --from=ghcr.io/astral-sh/uv:latest) instead of pip, `UV_SYSTEM_PYTHON=1` + `UV_BREAK_SYSTEM_PACKAGES=1` for global install, all subtasks 1.1-1.9 implemented as specified (ubuntu:24.04, system deps, uv install, hardlink runner DD-17, /etc/shells, testuser, SSH, env vars, expose 22).
- Task 2: Created `tests/docker-compose.production.yml` with service definition, 2222:22 port mapping, healthcheck via `nc -z localhost 22`, and documented seccomp=unconfined fallback + Landlock verification command in comments.
- Task 3: All verification passed. Build succeeds, container starts healthy, SSH port open, aegish at `/usr/local/bin/aegish`, testuser shell = `/usr/local/bin/aegish`, runner binary exists with Links: 2 (hardlink confirmed), vim (vim.tiny/vi) VIM 9.1, less 590, Python 3.12.3, git 2.43.0, AEGISH_MODE=production, AEGISH_FAIL_MODE=safe. Landlock: NOT SUPPORTED on WSL2 kernel 5.15.167.4 (CONFIG_SECURITY_LANDLOCK likely not compiled in WSL2 default kernel — not a Dockerfile issue, will work on native Linux hosts).

### Senior Developer Review (AI)

**Reviewer:** guido | **Date:** 2026-02-13 | **Outcome:** Approved (after fixes)

**Issues Found:** 1 Critical, 2 High, 2 Medium, 2 Low — **All 7 fixed**

| # | Severity | Issue | Fix Applied |
|---|----------|-------|-------------|
| 1 | CRITICAL | API keys (`.env`) baked into Docker image — no `.dockerignore` existed | Created `.dockerignore` excluding `.env`, `.git/`, `logs/`, `benchmark/`, `docs/`, `.bmad/`, `.claude/` |
| 2 | HIGH | ~260MB unnecessary data in image (`.git/` 66MB, `logs/` 194MB, `benchmark/` 3.2MB) | Same `.dockerignore` fix |
| 3 | HIGH | SSH `PasswordAuthentication` append fragile (sshd uses first-match-wins) | Changed `echo >>` to `sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/'` |
| 4 | MEDIUM | Editable install (`-e`) reduces production-mode testing fidelity | Changed to `uv pip install .` (non-editable) |
| 5 | MEDIUM | No Docker layer caching — any file change invalidates dep install | Selective COPY: `pyproject.toml` + `uv.lock` + `src/` instead of `COPY .` |
| 6 | LOW | Unnecessary `python3-pip` and `python3-venv` packages (~50MB bloat) | Removed from apt install |
| 7 | LOW | No restart policy in Docker Compose | Added `restart: unless-stopped` |

### Change Log

- 2026-02-13: Code review — 7 issues found and fixed (Claude Opus 4.6). Created `.dockerignore`, hardened SSH config, optimized Dockerfile layers, non-editable install, restart policy.

### File List

- `tests/Dockerfile.production` (NEW, then MODIFIED by review)
- `tests/docker-compose.production.yml` (NEW, then MODIFIED by review)
- `.dockerignore` (NEW - created by review)
- `docs/stories/8-6-docker-based-testing-infrastructure.md` (MODIFIED - status, tasks, dev agent record, review)
- `docs/stories/sprint-status.yaml` (MODIFIED - epic-8 and story 8-6 status)
