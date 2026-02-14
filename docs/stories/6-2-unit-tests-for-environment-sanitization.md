# Story 6.2: Unit Tests for Environment Sanitization

Status: Done

## Story

As a **developer**,
I want **unit tests verifying environment sanitization works correctly**,
So that **regressions in subprocess security are caught immediately**.

## Acceptance Criteria

### AC1: Dangerous Variables Stripped
**Given** test fixtures with controlled environment variables
**When** `_build_safe_env()` is called
**Then** tests verify:
- `BASH_ENV` is stripped
- `ENV` is stripped
- `PROMPT_COMMAND` is stripped
- `EDITOR`, `VISUAL` are stripped
- `PAGER`, `GIT_PAGER`, `MANPAGER` are stripped

### AC2: BASH_FUNC_* Variables Stripped
**Given** the environment contains variables starting with `BASH_FUNC_`
**When** `_build_safe_env()` is called
**Then** all `BASH_FUNC_*` variables are stripped (e.g., `BASH_FUNC_myfunc%%`)

### AC3: Legitimate Variables Preserved
**Given** legitimate environment variables are set
**When** `_build_safe_env()` is called
**Then** the following are preserved:
- `PATH`, `HOME`, `USER` (system essentials)
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (API keys)
- `JAVA_HOME`, `GOPATH`, `NODE_ENV` (custom user variables)

### AC4: Hardened Bash Invocation Verified
**Given** a mock subprocess
**When** `execute_command("echo test")` is called
**Then** the subprocess receives `["bash", "--norc", "--noprofile", "-c", ...]`
**And** the `env` parameter excludes dangerous variables

### AC5: Both Functions Hardened
**Given** a mock subprocess
**When** `run_bash_command("echo test")` is called
**Then** the subprocess receives `["bash", "--norc", "--noprofile", "-c", ...]`
**And** the `env` parameter excludes dangerous variables

## Tasks / Subtasks

- [x] Task 1: Add `_build_safe_env()` unit tests to `tests/test_executor.py` (AC: #1, #2, #3)
  - [x] 1.1 Test each of the 8 `DANGEROUS_ENV_VARS` is stripped individually
  - [x] 1.2 Test `BASH_FUNC_*` prefix variables are stripped (use `BASH_FUNC_myfunc%%` as example)
  - [x] 1.3 Test `PATH`, `HOME`, `USER` are preserved
  - [x] 1.4 Test `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` are preserved
  - [x] 1.5 Test custom variables like `JAVA_HOME` are preserved
  - [x] 1.6 Test combined scenario: dangerous + safe vars in same env, only dangerous stripped
- [x] Task 2: Add `execute_command()` hardening tests (AC: #4)
  - [x] 2.1 Test subprocess.run receives `--norc` and `--noprofile` flags
  - [x] 2.2 Test subprocess.run receives `env` kwarg with sanitized dict
  - [x] 2.3 Test env dict in subprocess call does NOT contain `BASH_ENV`
- [x] Task 3: Add `run_bash_command()` hardening tests (AC: #5)
  - [x] 3.1 Test subprocess.run receives `--norc` and `--noprofile` flags
  - [x] 3.2 Test subprocess.run receives `env` kwarg with sanitized dict

## Dev Notes

### Key Implementation Details

**Target file:** `tests/test_executor.py` (EXISTING file -- append new test class, do NOT create a new file)

The file already contains 40+ tests for Stories 1.3-1.5 (pipes, redirects, script execution, exit codes). Add a new section at the bottom:

```python
# =============================================================================
# Story 6.2: Environment Sanitization Tests
# =============================================================================
```

**Function under test:** `aegish.executor._build_safe_env()` -- note the leading underscore (private function, but testable via direct import).

**Constants under test:** `aegish.executor.DANGEROUS_ENV_VARS` -- the set of 8 variable names to strip.

### Testing Approach

Use `mocker.patch.dict(os.environ, {...}, clear=True)` to set up controlled environments for `_build_safe_env()` tests. This ensures tests don't depend on the actual host environment.

Use `mocker.patch("subprocess.run")` for verifying subprocess invocation args in `execute_command()` and `run_bash_command()` tests.

### Current Implementation (src/aegish/executor.py)

```python
DANGEROUS_ENV_VARS = {
    "BASH_ENV", "ENV", "PROMPT_COMMAND",
    "EDITOR", "VISUAL", "PAGER", "GIT_PAGER", "MANPAGER",
}

def _build_safe_env() -> dict[str, str]:
    env = {}
    for key, value in os.environ.items():
        if key in DANGEROUS_ENV_VARS:
            continue
        if key.startswith("BASH_FUNC_"):
            continue
        env[key] = value
    return env
```

Both `execute_command()` and `run_bash_command()` call `subprocess.run()` with:
- `["bash", "--norc", "--noprofile", "-c", command]`
- `env=_build_safe_env()`

### Existing Test That Already Covers Partial AC4

`tests/test_defaults.py::TestDefaultShell::test_default_shell_is_bash` already verifies:
- `execute_command()` uses `["bash", "--norc", "--noprofile", "-c", ...]`
- `env` kwarg is present and is a dict

Your tests in `test_executor.py` should focus on the **content** of the env dict (what's stripped, what's preserved) and verify `run_bash_command()` gets the same treatment.

### What NOT to Do

- Do NOT create a new test file -- add to existing `tests/test_executor.py`
- Do NOT test the actual command execution with dangerous env vars set (that would be an integration test, not a unit test)
- Do NOT modify `src/aegish/executor.py` -- this is a test-only story
- Do NOT add pytest-mock to dependencies -- it's already installed (used via `mocker` fixture)
- Do NOT use `monkeypatch` for env vars -- use `mocker.patch.dict(os.environ, ...)` for consistency with existing test patterns (see `tests/test_defaults.py` for examples)

### Test Pattern Example

```python
import os
from unittest.mock import patch

from aegish.executor import _build_safe_env, DANGEROUS_ENV_VARS

class TestBuildSafeEnv:
    def test_bash_env_stripped(self, mocker):
        mocker.patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "BASH_ENV": "/tmp/hook.sh",
        }, clear=True)
        env = _build_safe_env()
        assert "BASH_ENV" not in env
        assert env["PATH"] == "/usr/bin"
```

### Architecture Compliance

- PEP 8: `snake_case` test functions, `PascalCase` test classes [Source: docs/architecture.md#Implementation Patterns]
- pytest with `mocker` fixture (pytest-mock) -- consistent with existing tests
- No new dependencies required
- Tests go in `tests/test_executor.py` [Source: docs/architecture.md#Complete Project Directory Structure]

### References

- [Source: docs/security-hardening-scope.md#BYPASS-14] BASH_ENV injection -- defines DANGEROUS_ENV_VARS
- [Source: docs/security-hardening-scope.md#DD-01] Denylist approach rationale
- [Source: docs/security-hardening-scope.md#DD-02] --norc --noprofile rationale
- [Source: docs/epics.md#story-62-unit-tests-for-environment-sanitization] Original acceptance criteria
- [Source: docs/stories/6-1-harden-subprocess-execution-with-environment-sanitization.md] Implementation details and completion notes
- [Source: docs/prd.md#FR36] Subprocess execution environment sanitized
- [Source: docs/architecture.md#Module Responsibilities] executor.py owns subprocess execution

### Previous Story Intelligence (6.1)

- `_build_safe_env()` uses a denylist approach per DD-01
- `DANGEROUS_ENV_VARS` has exactly 8 entries: BASH_ENV, ENV, PROMPT_COMMAND, EDITOR, VISUAL, PAGER, GIT_PAGER, MANPAGER
- `BASH_FUNC_*` prefix check is separate from the set lookup
- Story 6.1 updated `test_default_shell_is_bash` in `tests/test_defaults.py` to verify `--norc`, `--noprofile`, and `env` kwarg
- All 552 tests passing after 6.1; 4 pre-existing benchmark plot failures unrelated

### Project Structure Notes

- Single file modified: `tests/test_executor.py` (existing)
- No new files created
- No new dependencies required
- Aligns with `docs/architecture.md#Complete Project Directory Structure`

## Dev Agent Record

### Context Reference

<!-- Story context complete - comprehensive developer guide created -->

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

None required — all tests passed on first run.

### Completion Notes List

- Added 25 new unit tests across 3 test classes in `tests/test_executor.py`:
  - `TestBuildSafeEnv` (20 tests): Verifies all 8 DANGEROUS_ENV_VARS are stripped individually, BASH_FUNC_* prefix stripping, preservation of system essentials (PATH/HOME/USER), API keys, and custom user variables, plus a combined scenario test and a constant validation test.
  - `TestExecuteCommandHardening` (3 tests): Verifies execute_command() passes --norc/--noprofile flags, sanitized env dict, and BASH_ENV exclusion via mocked subprocess.
  - `TestRunBashCommandHardening` (2 tests): Verifies run_bash_command() passes --norc/--noprofile flags and sanitized env dict via mocked subprocess.
- All 25 new tests pass. Full regression suite: 612 passed, 4 failed (pre-existing benchmark plot failures, unrelated).
- Used `mocker.patch.dict(os.environ, {...}, clear=True)` pattern consistent with existing tests in `test_defaults.py`.
- No source code modified — test-only story as specified.

### Code Review Fixes (2026-02-13)

- [M1] Expanded `test_combined_dangerous_and_safe_vars` to include all 8 DANGEROUS_ENV_VARS (was only 4) + added `len(env)` assertion
- [M2] Added `test_bash_func_without_percent_suffix_stripped` — verifies BASH_FUNC_ prefix match works without %% suffix
- [M3] Added `test_empty_environment_returns_empty_dict` — boundary condition for empty os.environ
- Test count: 25 → 27 after review fixes

### Change Log

- 2026-02-13: Added 25 environment sanitization unit tests to tests/test_executor.py covering AC1-AC5
- 2026-02-13: Code review — fixed 3 MEDIUM issues: expanded combined test to all 8 dangerous vars, added BASH_FUNC_ no-%% edge case, added empty env boundary test (25 → 27 tests)

### File List

- `tests/test_executor.py` (modified) — added Story 6.2 test section with 3 test classes and 27 tests
