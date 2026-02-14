# Story 6.1: Harden Subprocess Execution with Environment Sanitization

Status: done

## Story

As a **security engineer**,
I want **subprocess execution to use `bash --norc --noprofile` with a sanitized environment**,
So that **BASH_ENV injection, alias hijacking, and PAGER/EDITOR behavior hijacking are prevented**.

## Acceptance Criteria

### AC1: Hardened Bash Invocation
**Given** `executor.py` currently runs `subprocess.run(["bash", "-c", command])`
**When** the execution is hardened
**Then** commands run via `subprocess.run(["bash", "--norc", "--noprofile", "-c", command], env=safe_env)`
**And** the same hardening applies to both `execute_command()` and `run_bash_command()`

### AC2: Dangerous Environment Variables Stripped
**Given** the subprocess environment is sanitized
**When** the following variables are set in the parent process
**Then** they are NOT present in the subprocess environment:
- `BASH_ENV` (arbitrary script sourcing)
- `ENV` (sh equivalent of BASH_ENV)
- `PROMPT_COMMAND` (arbitrary code on each prompt)
- `EDITOR`, `VISUAL` (editor hijacking)
- `PAGER`, `GIT_PAGER`, `MANPAGER` (pager hijacking)
- Any variable starting with `BASH_FUNC_` (exported bash functions)

### AC3: Legitimate Environment Variables Preserved
**Given** legitimate environment variables are set
**When** the subprocess runs
**Then** the following are preserved:
- `PATH`, `HOME`, `USER`, `LOGNAME`, `TERM`, `SHELL`
- `LANG`, `LC_ALL`, `LC_CTYPE`, `TZ`, `TMPDIR`
- API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- Custom user variables: `JAVA_HOME`, `GOPATH`, `NODE_ENV`, etc.

### AC4: BASH_ENV Injection Blocked
**Given** an attacker sets `BASH_ENV=/tmp/hook.sh` before running aegish
**When** a command is executed in aegish
**Then** `/tmp/hook.sh` is NOT sourced (verified by: `echo 'echo INJECTED' > /tmp/hook.sh && BASH_ENV=/tmp/hook.sh aegish` then running any command -- "INJECTED" must not appear)

## Tasks / Subtasks

- [x] Task 1: Add `_build_safe_env()` function to `executor.py` (AC: #2, #3)
  - [x] 1.1 Define `DANGEROUS_ENV_VARS` constant set: `{"BASH_ENV", "ENV", "PROMPT_COMMAND", "EDITOR", "VISUAL", "PAGER", "GIT_PAGER", "MANPAGER"}`
  - [x] 1.2 Implement `_build_safe_env() -> dict[str, str]`: iterate `os.environ`, skip keys in `DANGEROUS_ENV_VARS` and keys starting with `BASH_FUNC_`, keep everything else
  - [x] 1.3 Add `import os` to executor.py (currently only imports `subprocess`)

- [x] Task 2: Harden `execute_command()` (AC: #1, #4)
  - [x] 2.1 Change `["bash", "-c", wrapped_command]` to `["bash", "--norc", "--noprofile", "-c", wrapped_command]`
  - [x] 2.2 Add `env=_build_safe_env()` parameter to `subprocess.run()`

- [x] Task 3: Harden `run_bash_command()` (AC: #1, #4)
  - [x] 3.1 Change `["bash", "-c", command]` to `["bash", "--norc", "--noprofile", "-c", command]`
  - [x] 3.2 Add `env=_build_safe_env()` parameter to `subprocess.run()`

## Dev Notes

### Implementation Pattern (from DD-01, DD-02)

**Denylist approach** (DD-01): Strip known dangerous vars, preserve everything else. An allowlist would break user workflows depending on custom env vars (`JAVA_HOME`, `GOPATH`, `NODE_ENV`, database connection strings).

**`--norc --noprofile` over `env -i`** (DD-02): `env -i` would strip API keys, PATH, HOME, and all user configuration, breaking both aegish's LLM calls and the user's commands.

### Reference Implementation

```python
import os

DANGEROUS_ENV_VARS = {
    "BASH_ENV", "ENV",
    "EDITOR", "VISUAL", "PAGER", "GIT_PAGER", "MANPAGER",
    "PROMPT_COMMAND",
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

### Current executor.py Structure (src/aegish/executor.py)

Two functions, both need hardening:
- `execute_command(command, last_exit_code)` -- line 10: streams output to terminal, wraps command with exit code preservation `(exit N); {command}`
- `run_bash_command(command)` -- line 35: captures output (used in tests only)

Both currently use `["bash", "-c", command]` with no env sanitization.

### What NOT to Change

- Do NOT modify the exit code wrapping logic in `execute_command()` (`(exit {last_exit_code}); {command}`)
- Do NOT change `capture_output=True, text=True` in `run_bash_command()`
- Do NOT move `_build_safe_env()` to config.py -- it's execution-specific (per security-hardening-scope.md)
- Do NOT use `env -i` -- this strips everything including PATH and API keys

### Architecture Compliance

- PEP 8: `snake_case` functions, `UPPER_SNAKE_CASE` constants [Source: docs/architecture.md#Implementation Patterns]
- Standard Python imports only (`os`, `subprocess`) -- no new dependencies needed
- Module stays focused: `executor.py` owns subprocess execution [Source: docs/architecture.md#Module Responsibilities]

### Testing Note

Unit tests for this work are covered in Story 6.2 (`tests/test_executor.py`). This story focuses on the production code changes only.

### Forward Compatibility

Epic 8 (Production Mode) will add Landlock `preexec_fn` to `subprocess.run()` in `execute_command()`. The env sanitization and `--norc --noprofile` changes in this story are additive and will not conflict with that future work.

### Project Structure Notes

- Single file modified: `src/aegish/executor.py`
- No new files created
- No new dependencies required
- Aligns with existing project structure [Source: docs/architecture.md#Complete Project Directory Structure]

### References

- [Source: docs/security-hardening-scope.md#BYPASS-14] BASH_ENV injection -- concrete solution with denylist code
- [Source: docs/security-hardening-scope.md#BYPASS-16] Alias hijacking -- solved by same fix
- [Source: docs/security-hardening-scope.md#DD-01] Denylist approach rationale
- [Source: docs/security-hardening-scope.md#DD-02] --norc --noprofile over env -i rationale
- [Source: docs/epics.md#story-61-harden-subprocess-execution-with-environment-sanitization] Original acceptance criteria and implementation notes
- [Source: docs/prd.md#FR36] Subprocess execution environment sanitized
- [Source: docs/architecture.md#Module Responsibilities] executor.py owns subprocess execution

## Dev Agent Record

### Context Reference

<!-- Story context complete - comprehensive developer guide created -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None required — clean implementation with no blockers.

### Completion Notes List

- Implemented `DANGEROUS_ENV_VARS` constant set with all 8 dangerous variable names per AC2
- Implemented `_build_safe_env()` function using denylist approach (DD-01): strips dangerous vars and `BASH_FUNC_*` prefix, preserves everything else
- Hardened `execute_command()`: added `--norc --noprofile` flags and `env=_build_safe_env()` to subprocess.run()
- Hardened `run_bash_command()`: same hardening applied
- Exit code wrapping logic (`(exit N); {command}`) preserved unchanged per Dev Notes
- `capture_output=True, text=True` in `run_bash_command()` preserved unchanged per Dev Notes
- Fixed pre-existing test `test_default_shell_is_bash` in `tests/test_defaults.py` that asserted old arg order; updated to verify `--norc`, `--noprofile`, and `-c` are all present
- All 552 passing tests remain passing; no regressions introduced (4 pre-existing failures in benchmark plots unrelated to this change)
- Unit tests for sanitization logic deferred to Story 6.2 per Dev Notes

### File List

src/aegish/executor.py
tests/test_defaults.py

## Change Log

- 2026-02-13: Implemented environment sanitization and hardened bash invocation (Tasks 1-3). Updated existing test for new bash args.
- 2026-02-13: [Code Review] Fixed test_default_shell_is_bash to verify env kwarg and exact flag ordering. Fixed Dev Notes inaccuracy about run_bash_command usage.
