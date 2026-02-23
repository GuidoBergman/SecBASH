# Insecure Defaults Audit -- aegish

**Auditor**: Trail of Bits insecure-defaults skill (automated)
**Date**: 2026-02-22
**Scope**: `src/aegish/` (14 Python files, ~5,100 lines)
**Excludes**: Tests, benchmarks, documentation

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 2     |
| HIGH     | 3     |
| MEDIUM   | 3     |
| LOW      | 3     |
| INFO     | 2     |

---

## [CRITICAL] Fail-Open Mode Available via Environment Variable

**File**: `/home/gbergman/YDKHHICF/SecBASH/src/aegish/constants.py`:70-71, `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py`:198-211
**Category**: Fail-Open
**Behavior**: The `AEGISH_FAIL_MODE` setting accepts the value `"open"`, which changes the system's behavior when LLM validation fails (API timeout, all models down, unparseable response). In fail-open mode, when ALL models in the chain fail, `_validation_failed_response()` returns `action="warn"` instead of `action="block"`. The user is then prompted "Proceed anyway? [y/N]:" and can type `y` to execute the unvalidated command.

In development mode, this setting is read directly from the `AEGISH_FAIL_MODE` environment variable (`config.py:592`). Any process that can set environment variables before launching aegish can downgrade the security posture.

**Impact**: An attacker who can set `AEGISH_FAIL_MODE=open` before aegish starts (e.g., via `.bashrc`, `.profile`, or a parent process) turns the security shell into a warn-only shell. Combined with an LLM outage (natural or attacker-induced by blocking API endpoints), every command would be allowed with a single `y` keystroke. This is the most critical finding for a security tool: the core security decision can be weakened by an environment variable.

**Evidence**:
```python
# constants.py:70-71
DEFAULT_FAIL_MODE = "safe"
VALID_FAIL_MODES = {"safe", "open"}

# config.py:198-211
def get_fail_mode() -> str:
    return _get_validated_setting(
        "AEGISH_FAIL_MODE", VALID_FAIL_MODES, DEFAULT_FAIL_MODE, on_invalid="debug",
    )

# llm_client.py:615-632
def _validation_failed_response(reason: str) -> dict:
    action = "block" if get_fail_mode() == "safe" else "warn"
    return {
        "action": action,
        "reason": f"Could not validate command: {reason}",
        "confidence": 0.0,
    }
```

**Mitigations already present**: (1) The default is `"safe"` (block). (2) In production mode, `AEGISH_FAIL_MODE` is read from the root-owned config file at `/etc/aegish/config`, not from env vars. (3) Invalid values silently fall back to `"safe"`.

**Classification**: Fail-Open (configurable, but SAFE by default; CRITICAL risk in development mode when env var is poisoned)

**Recommendation**:
1. Log a WARNING at startup whenever fail-open mode is active, not just in the banner -- make it impossible to miss.
2. Consider removing fail-open mode entirely, or requiring an additional confirmation mechanism (e.g., a second env var as a "yes I really mean it" guard).
3. In development mode, validate that `AEGISH_FAIL_MODE` is not set to `open` by a parent process by checking whether the variable was inherited vs. explicitly set by the user in the current shell session.

---

## [CRITICAL] Unknown LLM Action Treated as Warn (Fail-Open on Unexpected Response)

**File**: `/home/gbergman/YDKHHICF/SecBASH/src/aegish/shell.py`:182-203
**Category**: Fail-Open
**Behavior**: When the LLM returns an action that is not `"allow"`, `"block"`, or `"warn"`, the shell loop's `else` branch treats the response as a warning and allows the user to proceed by typing `y`. This means any novel/unexpected LLM response (e.g., `"skip"`, `"deny"`, `""`, `None`, or a response manipulated via prompt injection) results in the command being executable after a single confirmation.

**Impact**: If an attacker can influence the LLM response via prompt injection (e.g., crafting a command that causes the LLM to output `{"action": "proceed", "reason": "safe"}`) or if a model returns a malformed action string, the command is not blocked. The expected fail-secure behavior for unknown actions should be to BLOCK, not to WARN.

**Evidence**:
```python
# shell.py:182-203
else:
    # Unknown action from LLM - treat as warning
    action = result.get("action", "unknown")
    print(f"\nWARNING: Unexpected validation response '{action}'. Proceed with caution.")

    # Get user confirmation (same as warn flow)
    try:
        response = input("Proceed anyway? [y/N]: ").strip().lower()
        if response in ("y", "yes"):
            exec_cmd = result.get("resolved_command", command)
            last_exit_code, current_dir, previous_dir, env = (
                _execute_and_update(
                    exec_cmd, last_exit_code,
                    current_dir, previous_dir, env,
                )
            )
```

Note: `_parse_response()` in `llm_client.py:593-595` does validate that the action is one of `["allow", "warn", "block"]` and returns `None` for invalid actions, which triggers a fallback to the next model. However, if ALL models return non-standard actions and `_validation_failed_response` returns `"warn"` (in fail-open mode), or if a code path bypasses `_parse_response`, the shell.py else-branch is reachable.

**Classification**: Fail-Open (unknown states default to executable)

**Recommendation**:
1. Change the `else` branch to BLOCK unconditionally. Unknown validation states should never allow execution.
2. Log the unexpected action at WARNING level for incident investigation.
3. Add a defensive assertion or raise an error for actions not in `{"allow", "warn", "block"}` before reaching the shell loop.

---

## [HIGH] Sensitive Variable Filtering Disabled by Default

**File**: `/home/gbergman/YDKHHICF/SecBASH/src/aegish/constants.py`:104, `/home/gbergman/YDKHHICF/SecBASH/src/aegish/utils.py`:78-98
**Category**: Weak Default
**Behavior**: `DEFAULT_FILTER_SENSITIVE_VARS` is `False`. When environment variable expansion is performed via `envsubst` (in `expand_env_vars()`), ALL environment variables -- including `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, and any other secrets -- are passed to the `envsubst` subprocess and can appear in the expanded command text. This expanded text is then sent to the LLM provider in the user message.

**Impact**: If a user types a command like `echo $OPENAI_API_KEY`, the expansion will resolve the full API key value and send it to the LLM provider as part of the validation prompt. API keys are now visible in:
- LLM provider logs (third party)
- Network transit (even over TLS, the provider sees the plaintext)
- Any audit logs that capture the expanded command

This is particularly concerning because the LLM API keys used by aegish itself will be leaked to the LLM provider (which already has the key for authentication, but the key would now also appear in request content, increasing exposure surface to content logging, training data, etc.).

**Evidence**:
```python
# constants.py:104
DEFAULT_FILTER_SENSITIVE_VARS = False

# utils.py:78-98
def get_safe_env() -> dict[str, str]:
    if not get_filter_sensitive_vars():
        return dict(os.environ)  # ALL env vars, including secrets
    # ...filtering only happens when opt-in is enabled
```

**Classification**: Weak Default (security feature exists but is off by default)

**Recommendation**:
1. Change `DEFAULT_FILTER_SENSITIVE_VARS` to `True`. The current opt-in design means most users will never enable it.
2. At minimum, always filter variables matching `_API_KEY`, `_SECRET`, `_TOKEN`, `_PASSWORD` patterns from the envsubst environment, regardless of the setting.

---

## [HIGH] Development Mode Reads Security-Critical Settings from Environment Variables

**File**: `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py`:555-592
**Category**: Weak Default
**Behavior**: In development mode (the default), all security-critical settings (`AEGISH_FAIL_MODE`, `AEGISH_ROLE`, `AEGISH_ALLOWED_PROVIDERS`, `AEGISH_PRIMARY_MODEL`, `AEGISH_FALLBACK_MODELS`, `AEGISH_VAR_CMD_ACTION`) are read from environment variables via `os.environ.get()`. Any parent process, `.bashrc`, `.profile`, or `.env` file can override these settings.

While production mode correctly reads from a root-owned config file (`/etc/aegish/config`), the default operational mode is `"development"` (constants.py:66), meaning most users run with env-var-sourced security settings.

**Impact**: In the default development mode, security settings can be weakened by any process that can modify the user's environment:
- `AEGISH_FAIL_MODE=open` disables blocking on validation failure
- `AEGISH_ROLE=sysadmin` relaxes validation rules for sudo commands
- `AEGISH_ALLOWED_PROVIDERS=*` could be exploited if provider validation is bypassed
- `AEGISH_VAR_CMD_ACTION=warn` downgrades variable-in-command-position from block to warn

**Evidence**:
```python
# config.py:590-592
def _get_security_config(key: str, default: str = "") -> str:
    # ...
    # Development mode: use env var
    return os.environ.get(key, default)
```

**Classification**: Weak Default (production mode is secure; development mode trusts the environment)

**Recommendation**:
1. Document clearly that development mode is NOT suitable for security-sensitive deployments.
2. Consider adding a startup warning when security-critical env vars are detected in development mode.
3. Consider making production mode the default when running as a login shell.

---

## [HIGH] AEGISH_* Environment Variables Passed Through to Child Processes

**File**: `/home/gbergman/YDKHHICF/SecBASH/src/aegish/constants.py`:170
**Category**: Weak Default
**Behavior**: The `ALLOWED_ENV_PREFIXES` tuple includes `"AEGISH_"`, meaning ALL environment variables starting with `AEGISH_` are passed through to child processes executed by the shell. This includes `AEGISH_FAIL_MODE`, `AEGISH_ROLE`, and other security-critical settings.

**Impact**: A command executed within aegish can set `export AEGISH_FAIL_MODE=open` or `export AEGISH_ROLE=sysadmin`, and because `AEGISH_*` variables survive the `sanitize_env()` allowlist filter, these values persist in the environment for subsequent commands. In development mode, these persisted values are then read by `get_fail_mode()` and `get_role()` for future validation decisions.

While the env sanitizer (`executor.py:256-282`) re-filters on every command cycle, the AEGISH_ prefix allowlist ensures these variables survive. A user who runs `export AEGISH_FAIL_MODE=open` inside the aegish shell effectively downgrades security for all subsequent commands in that session.

**Evidence**:
```python
# constants.py:170
ALLOWED_ENV_PREFIXES = ("LC_", "XDG_", "AEGISH_")

# executor.py:274-275
for key, value in captured.items():
    if key in ALLOWED_ENV_VARS or key.startswith(ALLOWED_ENV_PREFIXES):
        env[key] = value
```

**Classification**: Weak Default (env prefix allowlist is too broad for security settings)

**Recommendation**:
1. Remove `"AEGISH_"` from `ALLOWED_ENV_PREFIXES`, or only allow specific non-security AEGISH variables.
2. In `_get_security_config()`, read security-critical values once at startup and cache them, rather than re-reading from the live environment on every call.
3. Alternatively, strip `AEGISH_FAIL_MODE`, `AEGISH_ROLE`, and other security keys from the captured environment in `sanitize_env()`.

---

## [MEDIUM] No Sandbox Enforcement in Development Mode

**File**: `/home/gbergman/YDKHHICF/SecBASH/src/aegish/executor.py`:324-338
**Category**: Weak Default
**Behavior**: In development mode (the default), `_sandbox_kwargs()` returns an empty dict. This means:
- No `preexec_fn` is set (no `NO_NEW_PRIVS`)
- No `LD_PRELOAD` sandboxer library is injected
- Child processes run with full privileges of the user

The Landlock sandbox, which prevents child processes from spawning shells (the "most critical threat" per the system prompt), is completely inactive in development mode.

**Impact**: In the default development mode, if the LLM incorrectly allows a command (false negative), the command executes with no secondary defense layer. The entire security posture depends solely on the LLM's judgment. A successful LLM bypass (via prompt injection, obfuscation, or model error) leads directly to unrestricted command execution.

**Evidence**:
```python
# executor.py:332-338
def _sandbox_kwargs() -> dict:
    if get_mode() != "production":
        return {}
    return {
        "preexec_fn": make_no_new_privs_fn(),
    }
```

**Classification**: Weak Default (sandbox exists but is off by default)

**Recommendation**:
1. Document clearly that development mode provides LLM-only security with no sandbox.
2. Consider enabling a reduced sandbox (e.g., NO_NEW_PRIVS only) in development mode for defense-in-depth.
3. Warn at startup if Landlock is available but not being used because the mode is development.

---

## [MEDIUM] Landlock Unavailability Does Not Block Startup in Production

**File**: `/home/gbergman/YDKHHICF/SecBASH/src/aegish/shell.py`:454-459
**Category**: Weak Default
**Behavior**: In production mode, if the kernel does not support Landlock, the shell prints a warning ("WARNING: Landlock not supported on this kernel. Sandbox disabled.") but continues to operate without any sandbox enforcement. This is a soft failure -- the user sees a warning but can proceed to use the shell.

**Impact**: In production mode on older kernels (Linux < 5.13), aegish operates without its primary sandbox defense. Commands that the LLM allows will execute without the Landlock shell-spawn restriction, meaning any LLM false negative leads to unrestricted execution. An attacker who knows the kernel lacks Landlock can exploit LLM bypasses with confidence.

**Evidence**:
```python
# shell.py:454-459
if mode == "production":
    ll_available, ll_version = landlock_available()
    if ll_available:
        print(f"Landlock: active (ABI v{ll_version})")
    else:
        print("WARNING: Landlock not supported on this kernel. Sandbox disabled.")
        # NOTE: No sys.exit(1) -- execution continues
```

Contrast with bash and sandboxer checks which DO call `sys.exit(1)` on failure (shell.py:441-443, 449-451).

**Classification**: Fail-Open (production sandbox silently degrades)

**Recommendation**:
1. In production mode, treat Landlock unavailability as a fatal error and call `sys.exit(1)`, consistent with the bash binary and sandboxer library checks.
2. At minimum, require explicit opt-in to run production mode without Landlock (e.g., `AEGISH_ALLOW_NO_LANDLOCK=true` in the config file).

---

## [MEDIUM] Invalid AEGISH_FAIL_MODE Values Silently Fall Back to Safe (Silent Misconfiguration)

**File**: `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py`:209-211
**Category**: Weak Default
**Behavior**: When `AEGISH_FAIL_MODE` is set to an invalid value (e.g., `"block"`, `"secure"`, or a typo like `"saef"`), the `_get_validated_setting()` function logs a DEBUG-level message and silently falls back to the default `"safe"`. The `on_invalid="debug"` parameter means this misconfiguration is invisible at normal log levels.

This contrasts with `AEGISH_MODE`, which uses `on_invalid="fatal"` and calls `sys.exit(1)` on invalid values.

**Impact**: While the fallback is to the secure default (good), the silent nature means an operator who intends a specific configuration but makes a typo will not know their setting was ignored. The inconsistency with `AEGISH_MODE` (which is fatal on invalid values) suggests this should also be more visible.

**Evidence**:
```python
# config.py:209-211
def get_fail_mode() -> str:
    return _get_validated_setting(
        "AEGISH_FAIL_MODE", VALID_FAIL_MODES, DEFAULT_FAIL_MODE, on_invalid="debug",
    )
```

**Classification**: Fail-Secure (falls back to safe default, but silently)

**Recommendation**:
1. Change `on_invalid` to `"warning"` so invalid fail mode values are visible in standard logs.
2. Consider making it `"fatal"` to match `AEGISH_MODE` behavior -- if an operator explicitly sets `AEGISH_FAIL_MODE`, they expect it to take effect.

---

## [LOW] Default Confidence of 0.5 for Missing LLM Confidence Field

**File**: `/home/gbergman/YDKHHICF/SecBASH/src/aegish/llm_client.py`:599
**Category**: Weak Default
**Behavior**: When the LLM response does not include a `"confidence"` field, `_parse_response()` defaults to `0.5`. This medium-confidence value is assigned even to responses that may have been truncated, malformed, or generated under uncertain conditions.

**Impact**: A confidence of 0.5 does not trigger any low-confidence warnings or additional scrutiny. If the confidence field was missing due to a truncated or partially-formed response, the action (allow/warn/block) is still accepted at face value with an artificial medium-confidence rating. This could mask situations where the model was uncertain but the response was malformed.

**Evidence**:
```python
# llm_client.py:599
confidence = float(data.get("confidence", 0.5))
```

**Classification**: Weak Default (not directly exploitable, but masks uncertainty)

**Recommendation**:
1. Default to `0.0` instead of `0.5` when confidence is missing, since missing confidence indicates an abnormal response.
2. Log a warning when the confidence field is absent.

---

## [LOW] Config File Permission Check Allows Non-Root-Owned Files to Be Silently Ignored

**File**: `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py`:647-653
**Category**: Weak Default
**Behavior**: When the config file at `/etc/aegish/config` fails the permission check (not root-owned, or world-writable), `_load_config_file()` logs a warning but returns an empty dict. This means all settings fall back to defaults or environment variables. In production mode, this effectively degrades to development-mode behavior for security-critical settings.

**Impact**: If an attacker can create `/etc/aegish/config` with incorrect permissions (e.g., user-owned), the permission check rejects it, and all settings revert to defaults. The `AEGISH_MODE` bootstrap key falls through to the environment variable check (`config.py:580-581`), so the system remains in production mode, but all other security settings use their defaults rather than the intended hardened values from the config file.

**Evidence**:
```python
# config.py:647-653
is_valid, err = _validate_config_file_permissions(path)
if not is_valid:
    logger.warning("Config file permission check failed: %s", err)
    if path == CONFIG_FILE_PATH:
        _config_file_cache = config  # empty dict
        _config_file_loaded = True
    return config  # empty dict -- all settings revert to defaults
```

**Classification**: Fail-Secure (reverts to defaults, which are secure), but the silent degradation is concerning.

**Recommendation**:
1. In production mode, treat a failed config file permission check as a fatal error and refuse to start, consistent with the bash hash and sandboxer checks.
2. Print the warning to stderr (not just the logger) so it is visible even without logging configuration.

---

## [LOW] Audit Log Failure Is Silent and Non-Blocking

**File**: `/home/gbergman/YDKHHICF/SecBASH/src/aegish/audit.py`:96-114, `/home/gbergman/YDKHHICF/SecBASH/src/aegish/shell.py`:92-93
**Category**: Weak Default
**Behavior**: If audit logging fails to initialize (`init_audit_log()` returns False), the shell prints a warning to stderr but continues operating. Subsequent calls to `log_validation()` and `log_warn_override()` silently return without writing, as `_audit_available` is False.

Additionally, if an individual audit write fails (line 113: `except OSError`), the failure is logged at DEBUG level and the command execution continues.

**Impact**: In an environment where audit logging is required for compliance or forensic purposes, commands can be validated and executed without any audit trail. An attacker who can cause audit logging to fail (e.g., filling the disk, changing permissions on the audit directory) can operate without leaving traces.

**Evidence**:
```python
# shell.py:92-93
if not init_audit_log():
    print("WARNING: Audit logging unavailable.", file=sys.stderr)
    # No sys.exit(1) -- continues without audit

# audit.py:96-97, 113-114
def log_validation(...):
    if not _audit_available or _audit_fd is None:
        return  # Silently skip

    except OSError:
        logger.debug("Failed to write audit log entry")  # Silent failure
```

**Classification**: Fail-Open (for audit purposes; commands still validated by LLM)

**Recommendation**:
1. In production mode, consider making audit log initialization failure a fatal error.
2. At minimum, count failed audit writes and periodically warn the user if the audit log is degraded.

---

## [INFO] No Hardcoded Credentials or Fallback Secrets Found

**File**: All files in `src/aegish/`
**Category**: Hardcoded Credential / Fallback Secret
**Behavior**: The codebase does not contain any hardcoded API keys, passwords, tokens, or fallback secret values. All API keys are read from environment variables via `os.environ.get()` with no default values -- missing keys result in `None`, which correctly prevents authentication.

The `get_api_key()` function (`config.py:254-277`) returns `None` for missing keys (not a fallback value), and `validate_credentials()` blocks startup when no keys are configured.

**Evidence**:
```python
# config.py:274-277
for env_var in names:
    key = os.environ.get(env_var)
    if key and key.strip():
        return key.strip()
return None  # No fallback -- correctly returns None
```

**Classification**: SAFE -- no hardcoded credentials.

---

## [INFO] No Weak Cryptographic Algorithms Found

**File**: `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py`:867-880
**Category**: Weak Crypto
**Behavior**: The only cryptographic operation in the codebase is SHA-256 hashing for binary integrity verification (bash and sandboxer library). SHA-256 is used via `hashlib.sha256()`, which is cryptographically strong for integrity checking. No MD5, SHA1, DES, RC4, or ECB mode usage was found anywhere in the source files.

**Evidence**:
```python
# config.py:876-877
sha256 = hashlib.sha256()
```

**Classification**: SAFE -- appropriate cryptographic algorithm for the use case.

---

## Architectural Observations

### Defense-in-Depth Assessment

The aegish architecture has two security layers:
1. **LLM validation** (always active): Classifies commands as allow/warn/block
2. **Landlock sandbox** (production only): Prevents child processes from spawning shells

In development mode (the default), only layer 1 is active. This means:
- LLM false negatives lead directly to unrestricted execution
- There is no secondary defense against prompt injection bypasses
- The security posture is entirely dependent on LLM judgment quality

### Fail-Mode Summary

| Component | Failure Behavior | Mode |
|-----------|-----------------|------|
| LLM validation (all models fail) | Block (safe) or Warn (open) | Configurable |
| Unknown LLM action | Warn + confirm | Fail-Open |
| Sandbox (Landlock unavailable) | Warning, continue | Fail-Open |
| Audit log initialization | Warning, continue | Fail-Open |
| Audit log write | Silent skip | Fail-Open |
| Config file permission check | Warning, use defaults | Fail-Secure |
| Bash binary hash mismatch | Fatal exit | Fail-Secure |
| Sandboxer library missing | Fatal exit | Fail-Secure |
| Invalid AEGISH_MODE | Fatal exit | Fail-Secure |
| Invalid AEGISH_FAIL_MODE | Silent fallback to safe | Fail-Secure |
