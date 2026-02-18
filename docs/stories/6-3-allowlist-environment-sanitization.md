# Story 6.3: Switch Environment Sanitization from Blocklist to Allowlist

Status: draft

Supersedes: CV-05 (Incomplete DANGEROUS_ENV_VARS Blocklist)

## Story

As a **security engineer**,
I want **subprocess environment sanitization to use an allowlist instead of a blocklist**,
So that **unknown or future dangerous environment variables are blocked by default**.

## Context

The current blocklist (`DANGEROUS_ENV_VARS`) contains 8 entries. Fuzzing proved that 39 dangerous env vars leak through it, including 4 CRITICAL (`LD_PRELOAD`, `LD_LIBRARY_PATH`, `LD_AUDIT`, `BASH_LOADABLES_PATH`). An allowlist is secure by default: new attack vectors are blocked without code changes.

## Acceptance Criteria

### AC1: Allowlist Replaces Blocklist
**Given** `executor.py` currently uses `DANGEROUS_ENV_VARS` blocklist
**When** the allowlist is implemented
**Then** `_build_safe_env()` only passes through variables matching `ALLOWED_ENV_VARS` or `ALLOWED_ENV_PREFIXES`
**And** `DANGEROUS_ENV_VARS` is removed

### AC2: Standard Variables Preserved
**Given** a user runs a command inside aegish
**When** the subprocess environment is built
**Then** these variables are present (if set in parent): `PATH`, `HOME`, `USER`, `LOGNAME`, `SHELL`, `PWD`, `OLDPWD`, `SHLVL`, `TERM`, `COLORTERM`, `TERM_PROGRAM`, `LANG`, `LANGUAGE`, `TZ`, `TMPDIR`, `DISPLAY`, `WAYLAND_DISPLAY`, `SSH_AUTH_SOCK`, `SSH_AGENT_PID`, `GPG_AGENT_INFO`, `DBUS_SESSION_BUS_ADDRESS`, `HOSTNAME`

### AC3: Safe Prefixes Preserved
**Given** variables with known-safe prefixes exist
**When** the subprocess environment is built
**Then** variables starting with these prefixes are preserved: `LC_`, `XDG_`, `AEGISH_`

### AC4: Dangerous Variables Blocked
**Given** `LD_PRELOAD`, `BASH_ENV`, `SHELLOPTS`, `PS4`, `PYTHONPATH`, or any variable not on the allowlist is set
**When** a command is executed in aegish
**Then** none of these appear in the subprocess environment

## Tasks

- [ ] Task 1: Replace blocklist with allowlist in `executor.py`
  - [ ] 1.1 Remove `DANGEROUS_ENV_VARS`
  - [ ] 1.2 Add `ALLOWED_ENV_VARS` set (exact names from AC2)
  - [ ] 1.3 Add `ALLOWED_ENV_PREFIXES` tuple (prefixes from AC3)
  - [ ] 1.4 Rewrite `_build_safe_env()` (see reference implementation below)
- [ ] Task 2: Update tests in `tests/test_executor.py`
  - [ ] 2.1 Update existing blocklist tests to verify allowlist behavior
  - [ ] 2.2 Add test: `LD_PRELOAD` set in parent is absent in subprocess env
  - [ ] 2.3 Add test: `PATH`, `HOME`, `TERM` are preserved
  - [ ] 2.4 Add test: `LC_ALL`, `XDG_RUNTIME_DIR`, `AEGISH_MODE` are preserved via prefix matching

## Reference Implementation

```python
ALLOWED_ENV_VARS = {
    "PATH", "HOME", "USER", "LOGNAME", "SHELL",
    "PWD", "OLDPWD", "SHLVL",
    "TERM", "COLORTERM", "TERM_PROGRAM",
    "LANG", "LANGUAGE", "TZ", "TMPDIR",
    "DISPLAY", "WAYLAND_DISPLAY",
    "SSH_AUTH_SOCK", "SSH_AGENT_PID", "GPG_AGENT_INFO",
    "DBUS_SESSION_BUS_ADDRESS", "HOSTNAME",
}

ALLOWED_ENV_PREFIXES = ("LC_", "XDG_", "AEGISH_")


def _build_safe_env() -> dict[str, str]:
    """Build a sanitized environment for subprocess execution.

    Uses an allowlist approach: only known-safe variables are passed
    to child processes. Unknown variables are stripped by default.
    """
    env = {}
    for key, value in os.environ.items():
        if key in ALLOWED_ENV_VARS or key.startswith(ALLOWED_ENV_PREFIXES):
            env[key] = value
    return env
```

## File List

- `src/aegish/executor.py` (modify)
- `tests/test_executor.py` (modify)
