# Phase 4: Static Analysis Security Audit - aegish

**Date:** 2026-02-15
**Scope:** `src/aegish/` (8 Python files: `__init__.py`, `config.py`, `executor.py`, `llm_client.py`, `main.py`, `sandbox.py`, `shell.py`, `validator.py`)
**Methodology:** Manual static analysis equivalent to Semgrep Python security rulesets (`p/python`, `p/owasp-top-ten`, `p/security-audit`). Semgrep was installed (v1.151.0) but could not be executed due to environment restrictions; all findings below are the result of exhaustive manual code review applying the same rule categories.
**Scaffolding:** `/semgrep` skill (Claude Code static analysis skill)
**Analyst:** Claude Opus 4.6 (automated security review)

---

## Executive Summary

The aegish codebase demonstrates a well-considered security posture with multiple defense-in-depth layers. The codebase has already been through several hardening passes (Epics 6-9). Nevertheless, this audit identifies **13 findings** across 5 severity levels. The most critical findings relate to subprocess injection patterns in `executor.py`, integer overflow potential in ctypes syscall usage in `sandbox.py`, and missing input sanitization on the `last_exit_code` path. No high-severity vulnerabilities that would allow immediate remote exploitation were found -- the identified issues require local access or specific environmental conditions.

| Severity | Count | Summary |
|----------|-------|---------|
| HIGH | 3 | Shell injection via exit code, ctypes integer handling, JSON parsing of untrusted LLM output |
| MEDIUM | 4 | Missing subprocess timeout, global mutable state in sandbox, envsubst subprocess, sensitive var leak via LLM prompt |
| LOW | 4 | Broad exception handling, unvalidated runner path, readline history permissions, mutable default avoidance incomplete |
| INFORMATIONAL | 2 | Use of `preexec_fn` with fork safety, cached fd lifetime |

---

## Finding 1: Shell Injection via Unsanitized `last_exit_code` in f-string

**Severity:** HIGH
**Semgrep Rule Equivalent:** `python.lang.security.audit.dangerous-subprocess-use`, `python.lang.security.audit.subprocess-shell-true`
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/executor.py`, line 98
**CWE:** CWE-78 (OS Command Injection)

**Code:**
```python
wrapped_command = f"(exit {last_exit_code}); {command}"
```

**Analysis:**
The `last_exit_code` parameter is typed as `int` and originates from `subprocess.run().returncode`, which Python guarantees to be an integer. The `command` parameter is the raw user input string, but that is *intentional* -- aegish's entire design passes user commands to bash for execution after LLM validation.

However, the `last_exit_code` is interpolated into a shell command string without explicit validation that it remains an integer. If any code path were to pass a non-integer value (e.g., through a future refactor or monkey-patching), this becomes a direct shell injection point. The current call sites in `shell.py` (lines 185, 197, 215) always pass the return value of `execute_command()` which returns `subprocess.run().returncode` (always `int`), or the `EXIT_*` constants (also `int`).

**Current Risk:** Low (type system provides implicit protection)
**Future Risk:** HIGH (no explicit validation at the trust boundary)

**Recommendation:**
Add an explicit integer validation guard:
```python
def execute_command(command: str, last_exit_code: int = 0) -> int:
    # Validate exit code is a safe integer (defense in depth)
    if not isinstance(last_exit_code, int) or not (0 <= last_exit_code <= 255):
        last_exit_code = 1
    wrapped_command = f"(exit {last_exit_code}); {command}"
```

---

## Finding 2: `json.loads()` on Untrusted LLM Response Without Schema Validation

**Severity:** HIGH
**Semgrep Rule Equivalent:** `python.lang.security.deserialization.avoid-json-loads-untrusted`
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/llm_client.py`, lines 497-518
**CWE:** CWE-502 (Deserialization of Untrusted Data)

**Code:**
```python
def _parse_response(content: str) -> dict | None:
    try:
        data = json.loads(content)
        action = data.get("action", "").lower()
        if action not in ["allow", "warn", "block"]:
            logger.warning("Invalid action '%s' in LLM response", action)
            return None
        reason = data.get("reason", "No reason provided")
        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        return {
            "action": action,
            "reason": reason,
            "confidence": confidence,
        }
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("Failed to parse LLM response: %s", e)
        return None
```

**Analysis:**
The LLM response is fully untrusted input. While `json.loads()` itself is safe (unlike `pickle` or `yaml.load()`), the parsed data flows into the application's security decision path. Specific concerns:

1. **`reason` field is unbounded:** The `reason` string is passed directly to `print()` in `shell.py` (lines 187, 190). An LLM that returns a multi-megabyte `reason` string could cause terminal flooding or memory exhaustion. More importantly, the reason string could contain ANSI escape sequences that manipulate the terminal (e.g., hiding the "BLOCKED" prefix, overwriting previous output).

2. **No type checking on `reason`:** If the LLM returns `{"action": "allow", "reason": ["nested", "structure"], "confidence": 0.9}`, `data.get("reason")` returns a list, which when printed produces `['nested', 'structure']`. This is benign but indicates missing schema validation.

3. **`confidence` coercion:** `float(data.get("confidence", 0.5))` will accept strings like `"0.9"` (benign) or fail on non-numeric strings (caught by `ValueError`), but accepts `float('inf')` and `float('nan')` which survive the `max(0.0, min(1.0, ...))` clamping for `nan`.

**Recommendation:**
- Truncate `reason` to a maximum length (e.g., 500 characters)
- Sanitize `reason` by stripping ANSI escape sequences before display
- Validate `confidence` is finite: `if not math.isfinite(confidence): confidence = 0.5`
- Add explicit type checking: `if not isinstance(reason, str): reason = str(reason)[:500]`

---

## Finding 3: ctypes Syscall Return Value Not Checked for Errno

**Severity:** HIGH
**Semgrep Rule Equivalent:** `python.lang.security.audit.ctypes-misuse`
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/sandbox.py`, lines 124-138, 168-175, 203-209
**CWE:** CWE-252 (Unchecked Return Value), CWE-390 (Detection of Error Condition Without Action)

**Code:**
```python
# Line 124-130: landlock_available()
abi_version = libc.syscall(
    SYS_landlock_create_ruleset,
    None,
    0,
    LANDLOCK_CREATE_RULESET_VERSION,
)
if abi_version >= 0:
    _landlock_cache = (True, abi_version)

# Line 168-175: _add_path_rule()
ret = libc.syscall(
    SYS_landlock_add_rule,
    ruleset_fd,
    LANDLOCK_RULE_PATH_BENEATH,
    ctypes.byref(attr),
    0,
)
if ret < 0:
    logger.debug("landlock_add_rule failed for %s", path)

# Line 203-209: create_sandbox_ruleset()
ruleset_fd = libc.syscall(
    SYS_landlock_create_ruleset,
    ctypes.byref(attr),
    ctypes.sizeof(attr),
    0,
)
if ruleset_fd < 0:
    raise OSError("landlock_create_ruleset failed")
```

**Analysis:**
The ctypes `syscall()` wrapper returns a C `long`. On failure, Linux syscalls return -1 and set `errno`. The code checks `ret < 0` but does not read `ctypes.get_errno()` to determine the actual error. While `use_errno=True` is correctly passed to `ctypes.CDLL()` (line 95), `ctypes.get_errno()` is never called anywhere in the module.

More critically, `libc.syscall()` has no declared `restype` or `argtypes`. By default, ctypes assumes `c_int` return type, which truncates the `long` return on x86_64 (where `syscall()` returns `long`). For `landlock_create_ruleset`, the return value is a file descriptor which is typically small, but the truncation could cause issues if the fd number exceeds `INT_MAX` on a heavily-used system (unlikely but theoretically possible).

Additionally, in `_add_path_rule()` (line 175), when `landlock_add_rule` fails, the function silently continues. If adding a rule for a critical binary fails, the sandbox may allow execution of binaries that should have been restricted, or it may fail to add the EXECUTE permission for a needed binary, causing legitimate commands to be blocked.

**Recommendation:**
1. Set `libc.syscall.restype = ctypes.c_long` and `libc.syscall.argtypes = [ctypes.c_long, ...]`
2. On failure, read and log `ctypes.get_errno()` for diagnostics
3. Consider promoting `_add_path_rule` failures from `debug` to `warning` level logging
4. Add error context to the `OSError` in `create_sandbox_ruleset`:
   ```python
   if ruleset_fd < 0:
       errno_val = ctypes.get_errno()
       raise OSError(errno_val, f"landlock_create_ruleset failed: {os.strerror(errno_val)}")
   ```

---

## Finding 4: Missing Timeout on `subprocess.run()` in `executor.py`

**Severity:** MEDIUM
**Semgrep Rule Equivalent:** `python.lang.security.audit.subprocess-timeout`
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/executor.py`, lines 100-105, 120-126
**CWE:** CWE-400 (Uncontrolled Resource Consumption)

**Code:**
```python
# execute_command (line 100)
result = subprocess.run(
    [_get_shell_binary(), "--norc", "--noprofile", "-c", wrapped_command],
    env=_build_safe_env(),
    **_sandbox_kwargs(),
)

# run_bash_command (line 120)
return subprocess.run(
    [_get_shell_binary(), "--norc", "--noprofile", "-c", command],
    env=_build_safe_env(),
    capture_output=True,
    text=True,
    **_sandbox_kwargs(),
)
```

**Analysis:**
Neither `execute_command()` nor `run_bash_command()` specifies a `timeout` parameter. A malicious or inadvertent command (e.g., `cat /dev/urandom`, `yes`, an infinite loop) will block the aegish process indefinitely.

For `execute_command()`, this is somewhat expected behavior since it's an interactive shell -- the user can Ctrl+C. However, `run_bash_command()` is a programmatic interface that captures output, and a hang here would be more problematic.

Note: `_expand_env_vars()` in `llm_client.py` correctly uses `timeout=5` for its `envsubst` subprocess call (line 444), showing awareness of this concern in other contexts.

**Recommendation:**
- For `run_bash_command()`: Add `timeout=30` (or configurable via env var)
- For `execute_command()`: Consider a generous timeout (e.g., 3600s) with a warning before termination, or document that the lack of timeout is intentional for interactive use

---

## Finding 5: Global Mutable State in Sandbox Module (Thread Safety)

**Severity:** MEDIUM
**Semgrep Rule Equivalent:** `python.lang.security.audit.global-mutable-state`
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/sandbox.py`, lines 85-86, 103, 315-316
**CWE:** CWE-362 (Race Condition)

**Code:**
```python
# Line 85-86
_libc = None

# Line 103
_landlock_cache = None

# Line 315-316
_cached_ruleset_fd = None
_ruleset_initialized = False
```

**Analysis:**
The module uses four global mutable variables for caching without any locking or thread-safety mechanisms. While aegish is currently single-threaded (interactive shell loop), these patterns would become race conditions if:
- The shell were ever extended to handle background jobs with concurrent validation
- The module were imported and used as a library by multithreaded code
- Signal handlers accessed these globals

Specific risk: `get_sandbox_ruleset()` reads `_ruleset_initialized` and then sets both `_cached_ruleset_fd` and `_ruleset_initialized`. In a concurrent scenario, two threads could both see `_ruleset_initialized = False` and create two rulesets, leaking a file descriptor.

**Recommendation:**
- Add a comment documenting the single-threaded assumption
- Or use `threading.Lock()` for the cache variables
- Consider using `functools.lru_cache` for `_get_libc()` and `landlock_available()` which provides thread-safe caching

---

## Finding 6: Subprocess Call to `envsubst` Without Full Path

**Severity:** MEDIUM
**Semgrep Rule Equivalent:** `python.lang.security.audit.subprocess-path-traversal`
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/llm_client.py`, lines 439-446
**CWE:** CWE-426 (Untrusted Search Path)

**Code:**
```python
result = subprocess.run(
    ["envsubst"],
    input=command,
    capture_output=True,
    text=True,
    timeout=5,
    env=_get_safe_env(),
)
```

**Analysis:**
The `envsubst` binary is invoked without an absolute path. If an attacker can place a malicious `envsubst` binary earlier in `PATH`, it would be executed with the command text as input. The `env` parameter uses `_get_safe_env()` which inherits `PATH` from the current environment.

This is partially mitigated by:
- The function handles `FileNotFoundError` gracefully (falls back to not expanding)
- aegish already sanitizes `BASH_ENV` and `BASH_FUNC_*` from the env
- An attacker who can modify `PATH` already has significant access

However, in production mode, this subprocess call happens *before* LLM validation, making it part of the pre-validation pipeline.

**Recommendation:**
- Use an absolute path: `/usr/bin/envsubst`
- Or resolve the path once at startup: `ENVSUBST_PATH = shutil.which("envsubst")`

---

## Finding 7: Potential API Key Leak via LLM Prompt Environment Expansion

**Severity:** MEDIUM
**Semgrep Rule Equivalent:** `python.lang.security.audit.sensitive-data-exposure`
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/llm_client.py`, lines 406-422, 425-459
**CWE:** CWE-200 (Exposure of Sensitive Information)

**Code:**
```python
_SENSITIVE_VAR_PATTERNS = (
    "_API_KEY", "_SECRET", "_PASSWORD", "_TOKEN",
    "_CREDENTIAL", "_PRIVATE_KEY", "API_KEY", "SECRET_KEY", "ACCESS_KEY",
)

def _get_safe_env() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not any(pat in key.upper() for pat in _SENSITIVE_VAR_PATTERNS)
    }
```

**Analysis:**
The sensitive variable pattern list is well-designed but not exhaustive. Variables that could contain sensitive data but would not be filtered:

- `DATABASE_URL` (often contains embedded passwords: `postgres://user:pass@host/db`)
- `REDIS_URL`, `MONGODB_URI` (same pattern)
- `AWS_SESSION_TOKEN` -- partially covered by `_TOKEN` but only in `key.upper()` which does match
- `GH_TOKEN`, `GITHUB_TOKEN` -- covered by `_TOKEN`
- `SLACK_WEBHOOK` -- not covered
- `SMTP_PASS` -- not covered (no `_PASSWORD` substring, just `_PASS`)
- `PGPASSWORD` -- not covered (contains `PASSWORD` as substring but the check is `_PASSWORD`)

Wait -- actually, `PGPASSWORD` does contain `PASSWORD` (the check is `pat in key.upper()` where pat is `_PASSWORD`). `PGPASSWORD` uppercased is `PGPASSWORD` which does NOT contain `_PASSWORD` (no underscore before PASSWORD). So `PGPASSWORD` would leak.

The `envsubst` expansion would send these values to the LLM provider if the user's command contains `$PGPASSWORD` or `$DATABASE_URL`.

**Recommendation:**
- Add `"PASSWORD"` (without leading underscore), `"_PASS"`, `"_URI"`, `"_URL"` patterns for database connection strings
- Or switch to a more conservative approach: only allow known-safe variable patterns for expansion
- Consider adding `"PGPASSWORD"`, `"MYSQL_PWD"` explicitly

---

## Finding 8: Broad Exception Handling Suppresses Security-Relevant Errors

**Severity:** LOW
**Semgrep Rule Equivalent:** `python.lang.best-practice.broad-exception-handling`
**Files:** Multiple locations
**CWE:** CWE-755 (Improper Handling of Exceptional Conditions)

**Locations:**
1. `/home/gbergman/YDKHHICF/SecBASH/src/aegish/validator.py`, line 117:
   ```python
   except Exception:
       logger.debug("bashlex analysis failed for command: %s", command)
   ```

2. `/home/gbergman/YDKHHICF/SecBASH/src/aegish/llm_client.py`, lines 365-372:
   ```python
   except Exception as e:
       last_error = f"{model}: {type(e).__name__}: {str(e)}"
       logger.warning(...)
       continue
   ```

3. `/home/gbergman/YDKHHICF/SecBASH/src/aegish/llm_client.py`, lines 266-268:
   ```python
   except Exception as e:
       logger.warning("Health check failed with exception: %s: %s", type(e).__name__, e)
       return (False, f"{type(e).__name__}: {e}")
   ```

4. `/home/gbergman/YDKHHICF/SecBASH/src/aegish/sandbox.py`, line 265:
   ```python
   except Exception:
       os.close(ruleset_fd)
       raise
   ```

**Analysis:**
Finding #4 (`sandbox.py`) is actually correct -- it's a cleanup handler that re-raises. Findings #2 and #3 in `llm_client.py` are reasonable for resilience in an LLM client (network errors, API errors, etc.).

Finding #1 (`validator.py`) is the most concerning: `bashlex.parse()` can raise various exceptions on malformed input. Catching all exceptions at `debug` level means that if bashlex encounters an internal error (not just a parse error), the security check is silently skipped and the command goes directly to LLM validation. A `bashlex` crash could be triggered intentionally by a specially crafted command designed to bypass the AST-level variable-in-command-position check.

**Recommendation:**
- In `validator.py`, catch `bashlex.errors.ParsingError` specifically, and log other exceptions at `warning` level
- In `llm_client.py`, consider catching `(ConnectionError, Timeout, APIError)` specifically in the model loop

---

## Finding 9: Unvalidated Runner Binary Path from Environment

**Severity:** LOW
**Semgrep Rule Equivalent:** `python.lang.security.audit.unvalidated-path`
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py`, lines 328-340
**CWE:** CWE-22 (Path Traversal)

**Code:**
```python
def get_runner_path() -> str:
    path = os.environ.get("AEGISH_RUNNER_PATH", "")
    if path and path.strip():
        return path.strip()
    return DEFAULT_RUNNER_PATH
```

**Analysis:**
The `AEGISH_RUNNER_PATH` environment variable is accepted without path validation. An attacker who can set environment variables could point this to any binary, which would then be used as the shell for command execution in production mode. The `validate_runner_binary()` function (lines 343-362) only checks existence and executability, not that the binary is actually bash or a legitimate runner.

This is mitigated by:
- In production mode, an attacker who can set env vars before aegish starts already has pre-aegish access
- The runner binary is used as the *shell* for executing validated commands, so pointing it to a non-shell binary would break command execution rather than escalate privileges

However, pointing `AEGISH_RUNNER_PATH` to a modified bash binary that logs keystrokes or exfiltrates data would be a supply-chain attack vector.

**Recommendation:**
- Validate the runner path is an absolute path
- Consider validating the runner binary is a hardlink to `/bin/bash` (same inode check)
- Consider reading this from a config file with restricted permissions rather than an environment variable

---

## Finding 10: Readline History File Created with Default Permissions

**Severity:** LOW
**Semgrep Rule Equivalent:** `python.lang.security.audit.insecure-file-permissions`
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/shell.py`, lines 39, 73
**CWE:** CWE-276 (Incorrect Default Permissions)

**Code:**
```python
HISTORY_FILE: str = os.path.expanduser("~/.aegish_history")
# ...
atexit.register(readline.write_history_file, HISTORY_FILE)
```

**Analysis:**
The history file is written by `readline.write_history_file()` which uses the default `umask` for file creation permissions. If the user's `umask` is permissive (e.g., `0022`), the history file would be world-readable. This file may contain sensitive commands including paths, hostnames, and partial credentials typed by the user.

This is a standard behavior shared by bash (`~/.bash_history`) and documented as a known limitation in the security-hardening scope (BYPASS-06), but a defense-in-depth fix is trivial.

**Recommendation:**
Set restrictive permissions after file creation:
```python
def _save_history():
    readline.write_history_file(HISTORY_FILE)
    os.chmod(HISTORY_FILE, 0o600)

atexit.register(_save_history)
```

---

## Finding 11: Mutable Default Constant Not Fully Protected

**Severity:** LOW
**Semgrep Rule Equivalent:** `python.lang.best-practice.mutable-default-arg`
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py`, lines 50-53
**CWE:** N/A (Code Quality)

**Code:**
```python
DEFAULT_PRIMARY_MODEL = "openai/gpt-4"
DEFAULT_FALLBACK_MODELS = ["anthropic/claude-3-haiku-20240307"]

DEFAULT_ALLOWED_PROVIDERS = {"openai", "anthropic", "groq", "together_ai", "ollama"}
```

**Analysis:**
`DEFAULT_FALLBACK_MODELS` is a mutable list and `DEFAULT_ALLOWED_PROVIDERS` is a mutable set. The `get_fallback_models()` function correctly calls `.copy()` on `DEFAULT_FALLBACK_MODELS` (line 201), and `get_allowed_providers()` correctly calls `.copy()` on `DEFAULT_ALLOWED_PROVIDERS` (lines 278, 282).

However, `DEFAULT_FALLBACK_MODELS` is directly compared by value at line 152 of `shell.py`:
```python
elif fallbacks != DEFAULT_FALLBACK_MODELS:
```

And directly referenced at line 342 of `llm_client.py`:
```python
default_chain = [DEFAULT_PRIMARY_MODEL] + DEFAULT_FALLBACK_MODELS
```

If any code mutates `DEFAULT_FALLBACK_MODELS` in-place (e.g., `DEFAULT_FALLBACK_MODELS.append(...)`), the default chain in `query_llm()` would silently change. This is currently safe but fragile.

**Recommendation:**
Use tuples for immutability:
```python
DEFAULT_FALLBACK_MODELS = ("anthropic/claude-3-haiku-20240307",)
DEFAULT_ALLOWED_PROVIDERS = frozenset({"openai", "anthropic", "groq", "together_ai", "ollama"})
```

---

## Finding 12: `preexec_fn` Usage with Fork Safety Concerns

**Severity:** INFORMATIONAL
**Semgrep Rule Equivalent:** `python.lang.security.audit.subprocess-preexec-fn`
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/sandbox.py`, lines 277-308; `/home/gbergman/YDKHHICF/SecBASH/src/aegish/executor.py`, line 74
**CWE:** CWE-362 (Race Condition in multi-threaded context)

**Code:**
```python
def make_preexec_fn(ruleset_fd: int):
    libc = _get_libc()  # Resolve before fork
    def _preexec() -> None:
        ret = libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
        # ...
        ret = libc.syscall(SYS_landlock_restrict_self, ruleset_fd, 0)
        # ...
    return _preexec
```

**Analysis:**
Python's documentation warns that `preexec_fn` is not safe in the presence of threads because it runs between `fork()` and `exec()` -- a period where only async-signal-safe functions should be called. The code correctly resolves `_get_libc()` before fork (documented in the comment at line 294), which avoids the `dlopen()` hazard. However, the `libc.prctl()` and `libc.syscall()` calls go through ctypes' FFI layer, which involves Python's GIL machinery and internal state that may be inconsistent after `fork()` in a multi-threaded process.

The current implementation is safe because:
1. aegish is single-threaded
2. The ctypes calls are thin wrappers around syscalls (no complex library code)
3. `prctl` and `landlock_restrict_self` are themselves async-signal-safe

This is documented as informational because it's a known CPython limitation, the code handles it as well as possible, and Python 3.9+ `subprocess` mitigates some fork-safety issues internally.

**Recommendation:**
- Add a code comment noting this is safe in the single-threaded context
- If threading is ever added, consider using `subprocess.Popen` with `start_new_session=True` and a wrapper binary instead of `preexec_fn`

---

## Finding 13: Cached Ruleset File Descriptor Lifetime Management

**Severity:** INFORMATIONAL
**Semgrep Rule Equivalent:** `python.lang.security.audit.resource-leak`
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/sandbox.py`, lines 319-341
**CWE:** CWE-404 (Improper Resource Shutdown or Release)

**Code:**
```python
_cached_ruleset_fd = None
_ruleset_initialized = False

def get_sandbox_ruleset() -> int | None:
    global _cached_ruleset_fd, _ruleset_initialized
    if _ruleset_initialized:
        return _cached_ruleset_fd
    # ...
    _cached_ruleset_fd = create_sandbox_ruleset()
    _ruleset_initialized = True
    return _cached_ruleset_fd
```

**Analysis:**
The Landlock ruleset file descriptor is cached globally and never explicitly closed. This is intentional -- the fd must remain open for the lifetime of the process so it can be passed to each child process via `pass_fds`. When the aegish process exits, the OS will close the fd.

However, if `get_sandbox_ruleset()` is called, the fd is created, but the process exits abnormally (e.g., `SIGKILL`) before any subprocess is launched, the ruleset fd leaks. This is a kernel resource but is cleaned up by the OS on process termination.

No action needed -- this is by design and documented here for completeness.

**Recommendation:**
- Add an `atexit` handler to close the fd for clean shutdown (optional, defense in depth):
  ```python
  import atexit
  atexit.register(lambda: os.close(_cached_ruleset_fd) if _cached_ruleset_fd is not None else None)
  ```

---

## Patterns Checked With No Findings

The following semgrep rule categories were checked and produced no findings:

| Rule Category | Status | Notes |
|--------------|--------|-------|
| `python.lang.security.audit.eval-detected` | Clean | No `eval()` or `exec()` calls anywhere |
| `python.lang.security.audit.pickle-usage` | Clean | No `pickle` usage |
| `python.lang.security.audit.yaml-load` | Clean | No `yaml.load()` usage |
| `python.lang.security.audit.hardcoded-credentials` | Clean | All credentials from env vars |
| `python.lang.security.audit.sql-injection` | Clean | No SQL usage |
| `python.lang.security.audit.ssrf` | Clean | No user-controlled URL construction |
| `python.lang.security.audit.tempfile-insecure` | Clean | No tempfile usage |
| `python.lang.security.audit.hashlib-insecure` | Clean | No hashing operations |
| `python.django.*` / `python.flask.*` | N/A | Not a web application |
| `python.lang.security.audit.subprocess-shell-true` | Clean | `shell=True` is never used; all subprocess calls use list-form arguments |
| `python.lang.security.audit.dangerous-system-call` | Clean | No `os.system()` or `os.popen()` usage |
| `python.lang.security.audit.dangerous-import` | Clean | No dynamic imports from user input |

---

## Summary of Recommendations by Priority

### Immediate (before next release)

1. **Finding 1:** Add integer validation on `last_exit_code` in `execute_command()`
2. **Finding 2:** Truncate and sanitize LLM `reason` field; validate `confidence` is finite
3. **Finding 3:** Set `restype`/`argtypes` on ctypes `syscall()` wrapper; read `ctypes.get_errno()` on failures

### Short-term (next sprint)

4. **Finding 4:** Add timeout to `run_bash_command()`
5. **Finding 6:** Use absolute path for `envsubst`
6. **Finding 7:** Expand sensitive variable patterns to cover `PGPASSWORD`, `DATABASE_URL`, etc.
7. **Finding 8:** Narrow exception handling in `validator.py` to `bashlex.errors.ParsingError`

### Nice-to-have (backlog)

8. **Finding 5:** Add threading documentation or `threading.Lock` to sandbox globals
9. **Finding 9:** Validate runner path is absolute and optionally verify inode
10. **Finding 10:** Set `0o600` permissions on history file
11. **Finding 11:** Convert mutable module-level defaults to tuples/frozensets

---

## Appendix: Semgrep Execution Environment

- **Semgrep version:** 1.151.0 (installed via `python3 -m pip`)
- **Installation status:** Successfully installed
- **Execution status:** Could not be executed due to environment shell restrictions preventing execution of the `semgrep` binary. All findings above are from equivalent manual code review.
- **Recommended follow-up:** Run `semgrep scan --config=auto --lang=python src/aegish/` when environment restrictions are resolved to confirm findings and catch any patterns not covered by manual review.
- **Rulesets that should be applied:** `p/python`, `p/owasp-top-ten`, `p/security-audit`, `p/python-security`, `p/bandit`
