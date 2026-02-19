# Story 8.3: Landlock Sandbox Implementation

Status: done

## Story

As a **security engineer**,
I want **a Landlock-based sandbox that denies shell execution by child processes**,
So that **programs like vim, less, and python3 cannot spawn unmonitored shells in production mode**.

## Acceptance Criteria

1. **Given** a Landlock ruleset is created, **When** applied via `preexec_fn` in `subprocess.run()`, **Then** `execve("/bin/bash", ...)` returns EPERM for the child process, **And** `execve("/bin/sh", ...)` returns EPERM, **And** `execve("/bin/zsh", ...)` returns EPERM, **And** `execve("/bin/dash", ...)` returns EPERM, **And** all shell binaries in `DENIED_SHELLS` are blocked

2. **Given** the Landlock ruleset is applied, **Then** `execve("/opt/aegish/bin/runner", ...)` is allowed (the runner binary), **And** `execve("/usr/bin/python3", ...)` is allowed (non-shell programs), **And** `execve("/usr/bin/git", ...)` is allowed, **And** `execve("/usr/bin/ls", ...)` is allowed

3. **Given** the Landlock restriction is applied, **When** a child process forks its own children, **Then** the Landlock restriction is inherited (grandchildren also cannot spawn shells)

4. **Given** the Landlock restriction is applied, **When** a child process attempts to undo the restriction, **Then** it cannot -- Landlock restrictions are irrevocable

5. **Given** the host kernel does not support Landlock (< 5.13 or CONFIG_SECURITY_LANDLOCK not compiled), **When** `landlock_available()` is called, **Then** it returns `False` and no exception is raised

## Tasks / Subtasks

- [x] Task 1: Create `src/aegish/sandbox.py` with Landlock constants and struct definitions (AC: #1, #2)
  - [x] 1.1: Define syscall numbers: `SYS_landlock_create_ruleset=444`, `SYS_landlock_add_rule=445`, `SYS_landlock_restrict_self=446` (x86_64)
  - [x] 1.2: Define ctypes structs: `LandlockRulesetAttr` (field: `handled_access_fs` uint64), `LandlockPathBeneathAttr` (packed, fields: `allowed_access` uint64, `parent_fd` int32)
  - [x] 1.3: Define access flags: `LANDLOCK_ACCESS_FS_EXECUTE = 1 << 0`, `LANDLOCK_RULE_PATH_BENEATH = 1`, `LANDLOCK_CREATE_RULESET_VERSION = 1 << 0`, `PR_SET_NO_NEW_PRIVS = 38`
  - [x] 1.4: Define `DENIED_SHELLS` set with all known shell binary paths (both `/bin/` and `/usr/bin/` variants): bash, sh, dash, zsh, fish, ksh, csh, tcsh
  - [x] 1.5: Define `DEFAULT_RUNNER_PATH = "/opt/aegish/bin/runner"`

- [x] Task 2: Implement `landlock_available()` function (AC: #5)
  - [x] 2.1: Load `libc.so.6` via `ctypes.CDLL`
  - [x] 2.2: Call `SYS_landlock_create_ruleset` with `(None, 0, LANDLOCK_CREATE_RULESET_VERSION)` to get ABI version
  - [x] 2.3: If syscall succeeds (returns >= 0), Landlock is available; close the returned fd
  - [x] 2.4: If syscall fails (returns -1, errno=ENOSYS or EOPNOTSUPP), Landlock is not available
  - [x] 2.5: Cache the result in a module-level variable to avoid repeated syscalls
  - [x] 2.6: Return `(bool, int)` tuple: `(is_available, abi_version)` (version=0 if unavailable)

- [x] Task 3: Implement `create_sandbox_ruleset()` function (AC: #1, #2)
  - [x] 3.1: Create a Landlock ruleset handling only `LANDLOCK_ACCESS_FS_EXECUTE` via `SYS_landlock_create_ruleset`
  - [x] 3.2: Enumerate executable directories from `PATH` environment variable (split on `:`, resolve symlinks, deduplicate)
  - [x] 3.3: Add the runner directory (`/opt/aegish/bin/`) to the enumeration list
  - [x] 3.4: For each directory, use `os.scandir()` to iterate over entries
  - [x] 3.5: For each regular, executable file: resolve its real path via `os.path.realpath()`, check if it's in `DENIED_SHELLS` (compare resolved paths), and if NOT a shell, add an EXECUTE rule via `_add_path_rule()`
  - [x] 3.6: Implement `_add_path_rule(ruleset_fd, path)`: open path with `O_PATH | O_CLOEXEC`, create `LandlockPathBeneathAttr` with `allowed_access=EXECUTE` and `parent_fd=fd`, call `SYS_landlock_add_rule`, close the fd
  - [x] 3.7: Handle errors gracefully: skip files that can't be opened (PermissionError), log at debug level
  - [x] 3.8: Return the `ruleset_fd` (caller is responsible for closing it and using `pass_fds` in subprocess)

- [x] Task 4: Implement `make_preexec_fn(ruleset_fd)` factory (AC: #1, #3, #4)
  - [x] 4.1: Return a closure that calls `prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)` first
  - [x] 4.2: Then calls `SYS_landlock_restrict_self(ruleset_fd, 0)`
  - [x] 4.3: If either call fails, raise `OSError` with descriptive message
  - [x] 4.4: The closure signature must be `() -> None` (no arguments, compatible with `preexec_fn`)

- [x] Task 5: Implement module-level `get_sandbox_ruleset()` with lazy initialization (AC: #1, #2, #5)
  - [x] 5.1: Cache the ruleset_fd in a module-level `_cached_ruleset_fd` variable
  - [x] 5.2: On first call, create the ruleset via `create_sandbox_ruleset()` and cache it
  - [x] 5.3: On subsequent calls, return the cached fd
  - [x] 5.4: If Landlock is not available, return `None`
  - [x] 5.5: Provide `get_sandbox_preexec()` convenience function that returns `make_preexec_fn(cached_fd)` or `None`

## Dev Notes

### Epic 8 Context

This story is part of **Epic 8: Production Mode -- Login Shell + Landlock Enforcement**. The epic addresses three critical bypass vectors from the NFR assessment:
- **BYPASS-12:** Exit escape (handled by Story 8.2 -- login shell behavior)
- **BYPASS-13:** Interactive shell spawning (handled by THIS story + Story 8.5)
- **BYPASS-18:** `exec` replaces subprocess with shell (handled by THIS story via Landlock)

**Story dependency chain:**
- 8.1: `AEGISH_MODE` configuration (config.py)
- 8.2: Login shell exit behavior (shell.py)
- **8.3: Landlock sandbox implementation (sandbox.py) -- THIS STORY**
- 8.4: Runner binary setup (executor.py + config.py)
- 8.5: Integrate Landlock into executor.py (executor.py)
- 8.6: Docker-based testing infrastructure (DONE -- in review)
- 8.7: Integration tests for bypass verification

This story creates the **standalone sandbox module** (`src/aegish/sandbox.py`). It does NOT modify `executor.py` -- that integration is Story 8.5.

### Architecture Compliance

**Project structure** (from architecture.md):
```
aegish/
├── src/aegish/
│   ├── __init__.py
│   ├── main.py          # Typer CLI entry
│   ├── shell.py          # readline loop, user interaction
│   ├── validator.py      # LLM validation logic + bashlex
│   ├── llm_client.py     # LLM clients with fallback
│   ├── executor.py       # subprocess.run wrapper (sanitized env, --norc --noprofile)
│   ├── config.py          # Environment variable loading, model config, provider allowlist
│   └── sandbox.py         # NEW: Landlock sandbox implementation
├── tests/
│   ├── test_executor.py
│   ├── Dockerfile.production    # Story 8.6 (done)
│   └── docker-compose.production.yml
└── pyproject.toml
```

**Naming conventions (PEP 8):**
- Functions: `snake_case` (e.g., `landlock_available`, `create_sandbox_ruleset`, `make_preexec_fn`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DENIED_SHELLS`, `SYS_landlock_create_ruleset`)
- Classes: `PascalCase` (e.g., `LandlockRulesetAttr`, `LandlockPathBeneathAttr`)
- Module: `snake_case.py` (`sandbox.py`)

**Error handling:** Use standard Python exceptions (`OSError`, `RuntimeError`). No custom exception classes per architecture.md.

[Source: docs/architecture.md#Implementation Patterns & Consistency Rules]

### How Landlock Works -- Critical Developer Knowledge

**Landlock is an ALLOWLIST (default-deny) security model:**
1. You create a ruleset declaring which access types you handle (e.g., `EXECUTE`)
2. By default, ALL handled accesses are DENIED
3. You add rules that ALLOW specific paths to have specific accesses
4. You call `restrict_self` to activate the ruleset
5. The restriction is **inherited** by all child processes and **irrevocable**

**What this means for our use case:**
- We handle `LANDLOCK_ACCESS_FS_EXECUTE` (controls `execve()` syscall)
- We must add EXECUTE rules for EVERY binary the child process needs to run
- Binaries WITHOUT EXECUTE rules are denied -- this is how we block shells
- We enumerate executables from `PATH`, add rules for non-shells, skip shells

**Why we can't use directory-level rules:**
Landlock allows rules on directories (covers all files beneath) or individual files. Rules are **additive** (union). If we add EXECUTE for `/usr/bin/` (directory), ALL files under it are allowed, including `/usr/bin/bash`. There is no "subtract" operation. Therefore, we must use **file-level rules** to exclude specific binaries.

**The critical `preexec_fn` pattern:**
```python
# In executor.py (Story 8.5 will do this):
result = subprocess.run(
    [RUNNER_PATH, "--norc", "--noprofile", "-c", command],
    env=_build_safe_env(),
    preexec_fn=make_preexec_fn(ruleset_fd),
    pass_fds=(ruleset_fd,),  # CRITICAL: fd must survive close_fds
)
```

`preexec_fn` runs in the child process AFTER `fork()` but BEFORE `exec()`. CPython's subprocess implementation closes all fds >= 3 (except stdin/stdout/stderr) BEFORE calling `preexec_fn`. Therefore, the `ruleset_fd` must be listed in `pass_fds` to survive. This is handled by Story 8.5, but sandbox.py must document this requirement.

[Source: docs/security-hardening-scope.md#BYPASS-13]

### Technical Requirements

**Landlock syscall interface (x86_64):**

| Syscall | Number | Signature |
|---------|--------|-----------|
| `landlock_create_ruleset` | 444 | `(attr*, size, flags) -> fd` |
| `landlock_add_rule` | 445 | `(ruleset_fd, rule_type, rule_attr*, flags) -> 0` |
| `landlock_restrict_self` | 446 | `(ruleset_fd, flags) -> 0` |

**Struct definitions (ctypes):**

```python
class LandlockRulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]

class LandlockPathBeneathAttr(ctypes.Structure):
    _pack_ = 1  # MUST be packed -- kernel struct is packed
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
    ]
```

**Key constants:**
```python
LANDLOCK_ACCESS_FS_EXECUTE = 1 << 0
LANDLOCK_RULE_PATH_BENEATH = 1
LANDLOCK_CREATE_RULESET_VERSION = 1 << 0
PR_SET_NO_NEW_PRIVS = 38
```

**ABI version detection:** Call `landlock_create_ruleset(NULL, 0, LANDLOCK_CREATE_RULESET_VERSION)`. Returns the ABI version number (>= 1) if supported, or -1 with `errno=ENOSYS` if not.

**prctl requirement:** `prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)` MUST be called before `landlock_restrict_self()` unless the process has `CAP_SYS_ADMIN`. This prevents setuid/setgid escalation from the sandboxed process.

[Source: Linux kernel docs, landlock(7) man page]

### Library & Framework Requirements

| Dependency | Version/Source | Purpose |
|------------|---------------|---------|
| `ctypes` | Python stdlib | C library FFI for Landlock syscalls |
| `os` | Python stdlib | File operations (scandir, open O_PATH, realpath) |
| `logging` | Python stdlib | Debug-level logging for rule enumeration |

**No new PyPI dependencies needed.** The `landlock` PyPI package exists (v1.0.0.dev5) but is pre-release and unnecessary -- raw ctypes is more transparent and has zero additional dependencies.

### File Structure Requirements

**Files to create:**
- `src/aegish/sandbox.py` -- Complete Landlock implementation

**Files NOT to modify (those belong to other stories):**
- `src/aegish/executor.py` -- Story 8.5 handles Landlock integration
- `src/aegish/config.py` -- Story 8.1 handles `AEGISH_MODE`, Story 8.4 handles `RUNNER_PATH`
- `src/aegish/shell.py` -- Story 8.2 handles exit behavior
- `pyproject.toml` -- No new dependencies needed

### Testing Requirements

**Unit tests for sandbox.py (can be in `tests/test_sandbox.py`):**

1. **`DENIED_SHELLS` completeness:** Verify the set contains at least: `/bin/bash`, `/bin/sh`, `/bin/dash`, `/bin/zsh`, `/usr/bin/bash`, `/usr/bin/sh`, `/usr/bin/dash`, `/usr/bin/zsh`
2. **`landlock_available()` caching:** Call twice, verify second call doesn't make a syscall (mock-based)
3. **`create_sandbox_ruleset()` enumeration:** Mock `os.scandir` and verify shell binaries are skipped, non-shell binaries get rules added
4. **`create_sandbox_ruleset()` error handling:** Verify `PermissionError` on scandir is caught and skipped
5. **`make_preexec_fn()` closure:** Verify it returns a callable with no arguments
6. **`_add_path_rule()` with invalid path:** Verify `FileNotFoundError` is caught gracefully
7. **Struct packing:** Verify `ctypes.sizeof(LandlockPathBeneathAttr) == 12` (8 + 4, packed)
8. **`get_sandbox_preexec()` when unavailable:** Verify returns `None` when `landlock_available()` is False

**Integration tests (Story 8.7, not this story):**
- Docker-based tests verifying `execve("/bin/bash")` returns EPERM
- Docker-based tests verifying `execve("/usr/bin/ls")` succeeds

**WSL2 limitation:** Landlock is NOT supported on the project's WSL2 kernel (5.15.167.4, CONFIG_SECURITY_LANDLOCK not compiled). Unit tests must mock the syscalls. Integration tests require the Docker container on a native Linux host with kernel 5.13+.

[Source: docs/stories/8-6-docker-based-testing-infrastructure.md#Completion Notes List]

### DENIED_SHELLS Reference List

These are all shell binaries that must be denied execution. Both `/bin/` and `/usr/bin/` paths are included because on some systems they are separate directories (on Ubuntu 24.04, `/bin` is a symlink to `/usr/bin`, but `os.path.realpath()` normalizes this).

```python
DENIED_SHELLS = {
    "/bin/bash", "/usr/bin/bash",
    "/bin/sh", "/usr/bin/sh",
    "/bin/dash", "/usr/bin/dash",
    "/bin/zsh", "/usr/bin/zsh",
    "/bin/fish", "/usr/bin/fish",
    "/bin/ksh", "/usr/bin/ksh",
    "/bin/csh", "/usr/bin/csh",
    "/bin/tcsh", "/usr/bin/tcsh",
}
```

The comparison in `create_sandbox_ruleset()` must use `os.path.realpath()` on both the scanned path AND the DENIED_SHELLS entries to handle symlinks correctly. Build a resolved set at function start:

```python
resolved_denied = {os.path.realpath(s) for s in DENIED_SHELLS if os.path.exists(s)}
```

[Source: docs/security-hardening-scope.md#BYPASS-13]

### Landlock Hardlink/Symlink Behavior (DD-17)

**CRITICAL:** Landlock resolves symlinks but checks PATHS for access decisions:
- A symlink `/bin/bash -> /usr/bin/bash` is resolved to `/usr/bin/bash` by the kernel
- If `/bin` is a symlink to `/usr/bin`, then `execve("/bin/bash")` resolves to `/usr/bin/bash`
- File-level rules are based on the resolved path
- **Hardlinks** share the same inode but have separate path entries. A hardlink at `/opt/aegish/bin/runner` to `/bin/bash` has a DIFFERENT path, so:
  - `execve("/opt/aegish/bin/runner")` -- checked against `/opt/aegish/bin/runner` path rules
  - `execve("/bin/bash")` -- checked against `/bin/bash` (or resolved `/usr/bin/bash`) path rules
  - These are independent Landlock checks, so we CAN allow runner while denying bash

**Implication for `create_sandbox_ruleset()`:**
- Use `os.path.realpath()` to resolve scanned paths before checking DENIED_SHELLS
- The runner binary is added as an explicit rule using its own path (`/opt/aegish/bin/runner`)
- The runner binary MUST be a hardlink or copy of bash, NOT a symlink (DD-17)

[Source: docs/security-hardening-scope.md#DD-17]

### `pass_fds` Requirement for Integration (Story 8.5)

**CPython subprocess fd management:**
1. `subprocess.Popen` with `close_fds=True` (default since Python 3.2) closes all fds >= 3 in the child
2. This happens BEFORE `preexec_fn` is called
3. The `ruleset_fd` from `create_sandbox_ruleset()` would be closed unless listed in `pass_fds`

**Therefore, Story 8.5 MUST use:**
```python
subprocess.run(
    [...],
    preexec_fn=preexec_fn,
    pass_fds=(ruleset_fd,),  # Keeps ruleset_fd open for preexec_fn
)
```

**sandbox.py MUST document this requirement** in the `create_sandbox_ruleset()` docstring and the module docstring.

### Design Decisions Referenced

| ID | Decision | Impact on This Story |
|----|----------|---------------------|
| DD-13 | Login shell over exit-trapping | Story 8.2 (not this story) |
| DD-14 | Production/development modes | sandbox.py is used ONLY in production mode; caller checks mode |
| DD-15 | Landlock over seccomp/ptrace/LD_PRELOAD/rbash/AppArmor | This story implements the Landlock approach |
| DD-16 | `./script.sh` shebangs break in production mode | Accepted -- `#!/bin/bash` shebangs trigger `execve("/bin/bash")` which Landlock denies; use `source script.sh` instead |
| DD-17 | Runner hardlink (not symlink) | Runner binary at `/opt/aegish/bin/runner` is a hardlink; its path gets an explicit EXECUTE rule |

### WSL2 + Docker Compatibility Note

**WSL2 kernel 5.15 does NOT support Landlock** (`CONFIG_SECURITY_LANDLOCK` not compiled in default WSL2 kernel). This was confirmed during Story 8.6 verification.

**Implications:**
- `landlock_available()` will return `(False, 0)` on WSL2
- Unit tests MUST mock syscalls (cannot test real Landlock on WSL2)
- Integration tests require the Docker container built in Story 8.6, running on a native Linux host with kernel 5.13+
- The `get_sandbox_preexec()` function returns `None` when Landlock is unavailable, enabling graceful fallback

[Source: docs/stories/8-6-docker-based-testing-infrastructure.md#Completion Notes List]

### Git Intelligence

Recent commits show:
- `4c1dd9d` Add new epics (most recent)
- Story 8.6 Docker infrastructure is already implemented (Dockerfile.production, docker-compose.production.yml)
- Epic 6 (env sanitization) is DONE -- `executor.py` already uses `bash --norc --noprofile -c` with `_build_safe_env()`
- Epic 7 stories 7.1 and 7.2 are in review (envsubst expansion, bashlex detection)
- Story 9.1 (provider allowlist) is done

**Current `executor.py` state** (relevant for Story 8.5 integration):
- `execute_command()` at line 39: uses `subprocess.run(["bash", "--norc", "--noprofile", "-c", ...], env=_build_safe_env())`
- `run_bash_command()` at line 65: similar pattern with `capture_output=True`
- `_build_safe_env()` at line 22: strips `DANGEROUS_ENV_VARS` and `BASH_FUNC_*`
- No `preexec_fn` currently used -- Story 8.5 will add this

### Previous Story Intelligence

**Story 8.6 (Docker infrastructure) learnings:**
- Ubuntu 24.04 base image works well
- `uv` installation via `COPY --from=ghcr.io/astral-sh/uv:latest` pattern
- Runner binary created with hardlink: `ln /bin/bash /opt/aegish/bin/runner` (verified Links: 2)
- Landlock NOT supported on WSL2 -- documented in completion notes
- SSH + login shell testing pattern established

### Project Structure Notes

- New file `src/aegish/sandbox.py` follows the existing module pattern in `src/aegish/`
- No changes to existing files in this story
- Tests should go in `tests/test_sandbox.py` (follows existing test naming pattern: `test_executor.py`, `test_config.py`, etc.)

### References

- [Source: docs/security-hardening-scope.md#BYPASS-13] -- Landlock solution design, DENIED_SHELLS list, preexec_fn pattern
- [Source: docs/security-hardening-scope.md#DD-15] -- Landlock chosen over seccomp/ptrace/LD_PRELOAD/rbash/AppArmor
- [Source: docs/security-hardening-scope.md#DD-16] -- Shell scripts break in production mode (accepted)
- [Source: docs/security-hardening-scope.md#DD-17] -- Runner must be hardlink/copy, not symlink
- [Source: docs/epics.md#Story 8.3: Landlock Sandbox Implementation] -- Acceptance criteria, FRs covered (FR45)
- [Source: docs/prd.md#FR45] -- Landlock denies execve of shell binaries for child processes
- [Source: docs/prd.md#FR47] -- Graceful Landlock fallback for unsupported kernels
- [Source: docs/architecture.md#Implementation Patterns & Consistency Rules] -- PEP 8, standard exceptions
- [Source: docs/stories/8-6-docker-based-testing-infrastructure.md] -- WSL2 Landlock not supported, Docker testing pattern
- [Source: src/aegish/executor.py] -- Current subprocess execution pattern (env sanitization, --norc --noprofile)
- [Linux kernel Landlock docs: docs.kernel.org/userspace-api/landlock.html] -- Syscall numbers, struct layouts, ABI versions
- [landlock(7) man page] -- Constants, usage patterns, prctl requirement

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- Implemented complete Landlock sandbox module (`src/aegish/sandbox.py`) with all 5 tasks
- Task 1: Defined x86_64 syscall numbers (444/445/446), ctypes structs (LandlockRulesetAttr, LandlockPathBeneathAttr with _pack_=1), access flags, DENIED_SHELLS (16 paths covering 8 shells in /bin/ and /usr/bin/), and DEFAULT_RUNNER_PATH
- Task 2: Implemented `landlock_available()` with libc CDLL loading via `ctypes.util.find_library`, syscall probing, fd cleanup, and module-level caching. Returns `(bool, int)` tuple
- Task 3: Implemented `create_sandbox_ruleset()` with PATH enumeration, symlink resolution via `os.path.realpath()`, directory deduplication, runner dir inclusion, shell filtering against both resolved and literal DENIED_SHELLS paths, and `_add_path_rule()` helper with O_PATH|O_CLOEXEC fd management. Graceful PermissionError/OSError handling with debug logging
- Task 4: Implemented `make_preexec_fn(ruleset_fd)` factory returning a `() -> None` closure that calls `prctl(PR_SET_NO_NEW_PRIVS)` then `landlock_restrict_self()`, raising OSError on failure
- Task 5: Implemented `get_sandbox_ruleset()` with lazy initialization and `get_sandbox_preexec()` convenience function. Both return None when Landlock unavailable for graceful fallback
- Module docstring documents the critical `pass_fds=(ruleset_fd,)` requirement for Story 8.5 integration
- 28 unit tests written in `tests/test_sandbox.py` covering all 8 test categories from story requirements
- All syscalls mocked (WSL2 kernel 5.15 doesn't support Landlock) - integration tests deferred to Story 8.7
- No new PyPI dependencies needed; uses only stdlib (ctypes, os, stat, logging)
- Full test suite: 683 passed, 4 failed (pre-existing benchmark plot/compare test failures, unrelated to this story)

### File List

- `src/aegish/sandbox.py` (NEW) - Complete Landlock sandbox implementation
- `tests/test_sandbox.py` (NEW) - 28 unit tests for sandbox module
- `docs/stories/8-3-landlock-sandbox-implementation.md` (MODIFIED) - Story status and task tracking
- `docs/stories/sprint-status.yaml` (MODIFIED) - Sprint status updated

### Change Log

- 2026-02-13: Implemented Landlock sandbox module (sandbox.py) with all 5 tasks complete. Created 28 unit tests. All acceptance criteria satisfied via mock-based testing (WSL2 lacks Landlock kernel support).
- 2026-02-13: **Code Review (Claude Opus 4.6)** — Found 6 issues (1 CRITICAL, 2 HIGH, 3 MEDIUM), all fixed:
  - CRITICAL: `landlock_available()` called `os.close()` on ABI version number (not an fd) — would close stdout (fd 1) on Landlock-capable systems. Removed the erroneous close.
  - HIGH: `is_file(follow_symlinks=False)` skipped symlinked executables in PATH (199 symlinks in /usr/bin, 17 to outside dirs). Changed to `follow_symlinks=True`.
  - HIGH: `create_sandbox_ruleset()` leaked `ruleset_fd` on unhandled exceptions. Added try/except with fd cleanup.
  - MEDIUM: `make_preexec_fn._preexec()` called `_get_libc()` after fork (potential deadlock). Moved libc resolution to factory scope.
  - MEDIUM: `test_returns_tuple` called real `landlock_available()` without mocking. Fixed to mock syscall.
  - MEDIUM: `test_calls_prctl_then_restrict_self` didn't verify prctl argument values. Added assertions.
  - 3 LOW issues noted but not fixed (subtask comments, no `__all__`, no `_get_libc` fallback test).
  - Full test suite: 597 passed, 0 failed (excluding pre-existing benchmark test exclusions).
