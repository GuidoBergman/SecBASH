# Story 8.7: Integration Tests for Bypass Verification

Status: done

## Story

As a **security engineer**,
I want **automated tests verifying that BYPASS-12, BYPASS-13, and BYPASS-18 are resolved in production mode**,
So that **bypass vectors are continuously tested against regressions**.

## Acceptance Criteria

1. BYPASS-12 (exit escape): `exit` and Ctrl+D terminate the session
2. BYPASS-13 (shell spawning): `bash`, `exec bash`, `python3 os.system('bash')`, `python3 os.execv('/bin/bash')` all blocked
3. Regression: legitimate commands work (`ls`, `echo`, `cat`, `python3`, `git`)
4. Tests skip gracefully when Docker unavailable

## Tasks / Subtasks

- [x] Task 1: Create `tests/test_production_mode.py`
  - [x] 1.1: `@pytest.mark.docker` marker, skip when Docker unavailable
  - [x] 1.2: Session-scoped `production_container` fixture (build + run + teardown)
  - [x] 1.3: `docker_exec()` helper function
- [x] Task 2: BYPASS-12 tests
  - [x] 2.1: `exit` terminates session
  - [x] 2.2: No parent shell after exit
- [x] Task 3: BYPASS-13 tests
  - [x] 3.1: `bash` blocked (exit code 126/127)
  - [x] 3.2: `python3 os.system('bash')` returns non-zero
  - [x] 3.3: `python3 os.execv('/bin/bash')` raises PermissionError
- [x] Task 4: Regression tests
  - [x] 4.1: `ls -la`, `echo hello`, `cat /etc/hostname`, `python3 -c "print('ok')"`, `git --version` all succeed
- [x] Task 5: Register `docker` marker in conftest.py/pyproject.toml

## Dev Notes

### Docker Container (Story 8.6, done)

- Image: `tests/Dockerfile.production` (ubuntu:24.04, Python 3.12)
- User: `testuser` with aegish as login shell
- Runner: `/opt/aegish/bin/runner` (hardlink)
- Env: `AEGISH_MODE=production`, `AEGISH_FAIL_MODE=safe`
- Tools: vim-tiny, less, python3, git

### Landlock on WSL2

WSL2 kernel 5.15 does NOT support Landlock. BYPASS-13 tests will only pass on hosts with kernel 5.13+ and `CONFIG_SECURITY_LANDLOCK=y`. Add secondary skip if Landlock unavailable in container.

### Testing Approach

```python
def docker_exec(container_id: str, command: str) -> tuple[int, str, str]:
    result = subprocess.run(
        ["docker", "exec", container_id, "bash", "--norc", "--noprofile", "-c", command],
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode, result.stdout, result.stderr
```

### Dependencies

All of 8-1, 8-2, 8-3, 8-4, 8-5, 8-6 must be done before this story.

### Files

- Create: `tests/test_production_mode.py`
- Modify: `pyproject.toml` or `tests/conftest.py` (register `docker` marker)
