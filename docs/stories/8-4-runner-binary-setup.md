# Story 8.4: Runner Binary Setup

Status: done

## Story

As a **developer**,
I want **a runner binary (hardlink or copy of bash) for production mode command execution**,
So that **aegish can run commands via bash while Landlock denies execution of the original bash binary**.

## Acceptance Criteria

1. `/opt/aegish/bin/runner` exists and is executable (hardlink/copy of bash, NOT symlink)
2. Missing runner in production mode: print error with setup instructions, fall back to development mode
3. Production mode: commands execute via `["/opt/aegish/bin/runner", "--norc", "--noprofile", "-c", command]`
4. `AEGISH_RUNNER_PATH` env var overrides default path
5. Development mode: unchanged behavior (`["bash", ...]`)

## Tasks / Subtasks

- [ ] Task 1: Add to `src/aegish/config.py`
  - [ ] 1.1: `DEFAULT_RUNNER_PATH = "/opt/aegish/bin/runner"`
  - [ ] 1.2: `get_runner_path() -> str` reads `AEGISH_RUNNER_PATH` env var
  - [ ] 1.3: `validate_runner_binary() -> tuple[bool, str]` checks existence + executable
- [ ] Task 2: Update `src/aegish/executor.py`
  - [ ] 2.1: Add `_get_shell_binary() -> str` helper (production=runner, dev=bash)
  - [ ] 2.2: Use in `execute_command()` and `run_bash_command()`
- [ ] Task 3: Update `src/aegish/shell.py` startup
  - [ ] 3.1: If production mode, call `validate_runner_binary()`, fall back if missing
- [ ] Task 4: Add tests
  - [ ] 4.1: `get_runner_path()` default and custom
  - [ ] 4.2: `validate_runner_binary()` success and failure
  - [ ] 4.3: `execute_command()` uses runner in production, bash in development
  - [ ] 4.4: Startup fallback when runner missing

## Dev Notes

### Why Runner Binary (DD-17)

Landlock blocks `execve("/bin/bash")`. aegish needs bash to run commands. Solution: hardlink at `/opt/aegish/bin/runner` (same inode, different path). Landlock checks paths, not inodes. Symlinks don't work (Landlock resolves them).

### Current executor.py

Two subprocess sites:
1. `execute_command()`: `subprocess.run(["bash", "--norc", "--noprofile", "-c", wrapped_command], env=_build_safe_env())`
2. `run_bash_command()`: `subprocess.run(["bash", "--norc", "--noprofile", "-c", command], env=_build_safe_env(), capture_output=True, text=True)`

Both switch binary via `_get_shell_binary()`.

### sandbox.py already has DEFAULT_RUNNER_PATH

`sandbox.py` (Story 8.3) already defines `DEFAULT_RUNNER_PATH` for Landlock enumeration. `config.py` adds the config-level access.

### Files

- Modify: `src/aegish/config.py`, `src/aegish/executor.py`, `src/aegish/shell.py`
- Modify: `tests/test_config.py`, `tests/test_executor.py`
