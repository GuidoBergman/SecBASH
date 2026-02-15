# Story 8.5: Integrate Landlock into Executor

Status: done

## Story

As a **security engineer**,
I want **Landlock applied automatically in production mode for every command execution**,
So that **shell spawning is kernel-enforced without manual configuration per command**.

## Acceptance Criteria

1. Production mode + Landlock available: `preexec_fn` activates sandbox, child cannot execve shells
2. Development mode: no Landlock restrictions (unchanged)
3. Kernel < 5.13: warning printed, falls back to development behavior
4. `run_bash_command()` also applies Landlock in production mode
5. Production mode uses runner binary path

## Tasks / Subtasks

- [x] Task 1: Integrate Landlock into `execute_command()` in `src/aegish/executor.py`
  - [x] 1.1: Import `get_sandbox_ruleset`, `make_preexec_fn` from `aegish.sandbox`
  - [x] 1.2: Production mode: get `ruleset_fd`, use `preexec_fn=make_preexec_fn(fd)`, `pass_fds=(fd,)`
  - [x] 1.3: Landlock unavailable or runner missing: fall back to bash, no preexec_fn
- [x] Task 2: Integrate into `run_bash_command()`
  - [x] 2.1: Same production/development branching
- [x] Task 3: Add Landlock availability warning at startup in `src/aegish/shell.py`
  - [x] 3.1: If production mode, check `landlock_available()`, print warning if not supported
- [x] Task 4: Unit tests in `tests/test_executor.py`
  - [x] 4.1: Production + Landlock + runner: subprocess with runner path, preexec_fn, pass_fds
  - [x] 4.2: Production + no Landlock: fallback to bash
  - [x] 4.3: Development: bash, no preexec_fn

## Dev Notes

### Critical: pass_fds Required

CPython closes all fds >= 3 BEFORE calling `preexec_fn`. Without `pass_fds=(ruleset_fd,)`, `landlock_restrict_self()` fails with EBADF.

```python
fd = get_sandbox_ruleset()
if fd is not None:
    subprocess.run(
        [runner_path, "--norc", "--noprofile", "-c", command],
        env=_build_safe_env(),
        preexec_fn=make_preexec_fn(fd),
        pass_fds=(fd,),
    )
```

### sandbox.py API (Story 8.3, done)

- `landlock_available() -> tuple[bool, int]` - cached
- `get_sandbox_ruleset() -> int | None` - lazily creates ruleset fd; None if unavailable
- `make_preexec_fn(ruleset_fd: int) -> Callable` - returns closure for preexec_fn

**Important:** Don't use `get_sandbox_preexec()` - it hides the fd needed for `pass_fds`. Use `get_sandbox_ruleset()` + `make_preexec_fn()` separately.

### Dependencies

- Story 8.4 (runner binary) must be done first - this story uses `get_runner_path()` and `_get_shell_binary()`
- Story 8.3 (Landlock sandbox) is done - sandbox.py exists

### WSL2 Limitation

Landlock NOT supported on WSL2 kernel 5.15. All tests must mock sandbox functions.

### Files

- Modify: `src/aegish/executor.py`, `src/aegish/shell.py`
- Modify: `tests/test_executor.py`
