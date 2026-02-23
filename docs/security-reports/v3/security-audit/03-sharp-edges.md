# Sharp-Edges Security Analysis: aegish

**Audit scope:** All source files in `src/aegish/` (14 files, ~5,100 lines)
**Methodology:** Trail of Bits sharp-edges framework -- error-prone APIs, dangerous configurations, and footgun designs
**Date:** 2026-02-22

---

## Table of Contents

1. [Algorithm/Mode Selection Footguns](#1-algorithmmode-selection-footguns)
2. [Dangerous Defaults](#2-dangerous-defaults)
3. [Primitive vs Semantic APIs](#3-primitive-vs-semantic-apis)
4. [Configuration Cliffs](#4-configuration-cliffs)
5. [Silent Failures](#5-silent-failures)
6. [Stringly-Typed Security](#6-stringly-typed-security)
7. [Summary Table](#7-summary-table)

---

## 1. Algorithm/Mode Selection Footguns

### SE-01: Unrestricted Model Selection Allows Security-Irrelevant LLMs

**Severity:** High
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py` (lines 106-119, 455-473)
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/constants.py` (lines 53-58)

**Description:** Any LLM model from any allowed provider can be set as the primary validation model via `AEGISH_PRIMARY_MODEL`. The provider allowlist (`AEGISH_ALLOWED_PROVIDERS`) validates the *provider* (e.g., `openai`, `ollama`) but not the *model*. A user can set `AEGISH_PRIMARY_MODEL=ollama/tinyllama` -- a model completely unsuitable for security classification -- and aegish will happily use it for all validation decisions.

The provider allowlist defaults include `ollama`, which allows any locally-hosted model, including fine-tuned models specifically trained to always return `{"action": "allow"}`.

```python
# config.py line 106-119
def get_primary_model() -> str:
    model = _get_security_config("AEGISH_PRIMARY_MODEL", "")
    if model and model.strip():
        return model.strip()  # No model capability validation whatsoever
    return DEFAULT_PRIMARY_MODEL
```

**Adversary analysis:**
- **The Scoundrel:** Deploys a local Ollama model fine-tuned to always respond with `allow`. Sets `AEGISH_PRIMARY_MODEL=ollama/always-allow`. All commands pass validation.
- **The Lazy Developer:** Sets `AEGISH_PRIMARY_MODEL=openai/gpt-5-nano` because it is cheap, unaware it has 50 ALLOW errors and 88.3% detection rate per benchmark data.
- **The Confused Developer:** Assumes the provider allowlist implies model-level security vetting.

**Recommendation:** Implement a model capability validation or a model allowlist in addition to the provider allowlist. At minimum, warn loudly when the configured model is not in the benchmark-tested set. In production mode, reject models not on an explicit approved list.

---

### SE-02: `AEGISH_FAIL_MODE=open` Degrades All Validation Failures to Warnings

**Severity:** High
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/llm_client.py` (lines 615-632)
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py` (lines 198-211)

**Description:** When `AEGISH_FAIL_MODE` is set to `open`, any LLM failure (timeout, API error, unparseable response, rate limit exhaustion, all models down) results in a `warn` action instead of `block`. The user is then prompted with `Proceed anyway? [y/N]:` and can type `y` to execute the unvalidated command.

This converts complete validation system failure into a mere speed bump. Combined with the shell's interactive flow, a user habituated to pressing `y` can bypass all security.

```python
# llm_client.py line 615-632
def _validation_failed_response(reason: str) -> dict:
    action = "block" if get_fail_mode() == "safe" else "warn"
    return {
        "action": action,
        "reason": f"Could not validate command: {reason}",
        "confidence": 0.0,
    }
```

**Adversary analysis:**
- **The Scoundrel:** Causes LLM failures (DNS poisoning, rate limit exhaustion) knowing that `open` mode degrades to a bypassable warning.
- **The Lazy Developer:** Sets `open` mode "to avoid blocking legitimate work when the API is flaky." Now all validation failures become click-through warnings.
- **The Confused Developer:** Believes `open` mode only affects edge cases; does not realize it applies to total validation system failure.

**Recommendation:** In `open` mode, still block commands that match the static blocklist even when LLM validation fails. The static blocklist should be a non-degradable backstop. Add prominent banner warnings when operating in open mode.

---

### SE-03: `AEGISH_VAR_CMD_ACTION=warn` Downgrades Variable-Injection Detection

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py` (lines 232-246)
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/validator.py` (lines 128-163)

**Description:** The variable-in-command-position detector (`_check_variable_in_command_position`) catches patterns like `a=ba; b=sh; $a$b` where variables are constructed and used as commands to evade static analysis. The action is configurable via `AEGISH_VAR_CMD_ACTION`, with `block` as default but `warn` as an option.

Setting this to `warn` allows the attacker's variable-injection technique to succeed with just a `y` confirmation.

```python
# validator.py lines 149-160
action = get_var_cmd_action()  # Could be "warn" if misconfigured
return {
    "action": action,
    "reason": reason,
    "confidence": 1.0,
}
```

**Adversary analysis:**
- **The Scoundrel:** Knows the deployment uses `warn` mode. Constructs `cmd=$'/bin/ba''sh'; $cmd` to bypass both canonicalization and the weakened AST check.
- **The Lazy Developer:** Sets `warn` because "blocking variable expansion breaks my scripts."
- **The Confused Developer:** Does not understand that variable-in-command-position is the primary shell escape evasion technique.

**Recommendation:** Document that `warn` mode for this setting significantly weakens evasion detection. Consider removing the `warn` option entirely or requiring production mode to always use `block`.

---

### SE-04: `sysadmin` Role Relaxes LLM Prompt Security Constraints

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/constants.py` (lines 490-509)
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py` (lines 214-229)

**Description:** The `sysadmin` role appends instructions to the LLM system prompt that explicitly tell the model to allow `sudo` commands and downgrade `cat /etc/shadow` from BLOCK to WARN. This role is set via `AEGISH_ROLE` environment variable (in development mode).

```python
# constants.py lines 491-498
"sysadmin": (
    "\n\n## Role Context: System Administrator\n\n"
    "The current user is a system administrator. Adjust validation:\n"
    "- `sudo` commands are expected and should NOT be blocked solely for using sudo\n"
    "- `sudo cat /etc/shadow` for a sysadmin is legitimate -> WARN (not BLOCK)\n"
),
```

**Adversary analysis:**
- **The Scoundrel:** In development mode, sets `AEGISH_ROLE=sysadmin` in the environment before launching aegish. Now `sudo cat /etc/shadow` is only warned, not blocked.
- **The Lazy Developer:** Deploys with `sysadmin` role for all users because "admins need to do admin things."
- **The Confused Developer:** Assumes the role is enforced by the system and cannot be self-assigned.

**Recommendation:** In development mode, the role should require authentication or be tied to system group membership, not just an environment variable. At minimum, display a persistent banner when a non-default role is active.

---

## 2. Dangerous Defaults

### SE-05: Development Mode Reads Security Settings from Environment Variables

**Severity:** Critical
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py` (lines 555-592)

**Description:** In development mode (the default), ALL security-critical settings are read from environment variables, which the user controls. This includes `AEGISH_FAIL_MODE`, `AEGISH_ROLE`, `AEGISH_VAR_CMD_ACTION`, `AEGISH_PRIMARY_MODEL`, `AEGISH_ALLOWED_PROVIDERS`, and `AEGISH_FALLBACK_MODELS`.

Production mode correctly reads these from a root-owned config file. But development mode is the default (`DEFAULT_MODE = "development"`), meaning the secure configuration path is opt-in, not default.

```python
# config.py lines 555-592
def _get_security_config(key: str, default: str = "") -> str:
    if _is_production_mode() and key in SECURITY_CRITICAL_KEYS:
        config = _load_config_file()
        # ...reads from root-owned file...
    # Development mode: use env var
    return os.environ.get(key, default)  # User-controlled!
```

**Adversary analysis:**
- **The Scoundrel:** Before launching aegish, sets `AEGISH_FAIL_MODE=open AEGISH_ROLE=sysadmin AEGISH_VAR_CMD_ACTION=warn` in the shell. All security controls are now maximally relaxed.
- **The Lazy Developer:** Deploys aegish in development mode to a shared server because production mode requires Landlock setup.
- **The Confused Developer:** Thinks aegish enforces security regardless of mode; does not realize development mode is "trust the user."

**Recommendation:** This is somewhat by design (development mode is for developers, production for deployment), but the threat model should be clear in documentation. Consider adding a warning at startup if security-weakening env vars are detected. In shared environments, development mode should refuse to start or require an explicit "I understand this is insecure" flag.

---

### SE-06: Default Sensitive Variable Filtering is Disabled

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/constants.py` (line 104)
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/utils.py` (lines 78-98)

**Description:** `DEFAULT_FILTER_SENSITIVE_VARS` is `False`. When a command contains `$OPENAI_API_KEY` or `$AWS_SECRET_ACCESS_KEY`, the full variable value is expanded and sent to the LLM provider for validation. This means API keys and secrets are transmitted to third-party LLM APIs in every validation request that references them.

```python
# utils.py lines 78-98
def get_safe_env() -> dict[str, str]:
    if not get_filter_sensitive_vars():
        return dict(os.environ)  # ALL env vars, including secrets
```

**Adversary analysis:**
- **The Scoundrel:** Crafts command `echo $AWS_SECRET_ACCESS_KEY` -- aegish sends the full AWS key to the LLM provider as part of the validation context.
- **The Lazy Developer:** Does not know about `AEGISH_FILTER_SENSITIVE_VARS` and never enables it.
- **The Confused Developer:** Assumes aegish would never send secrets to a third-party API.

**Recommendation:** Default `FILTER_SENSITIVE_VARS` to `True`. The risk of a slightly less accurate expansion (secrets replaced with empty strings) is far less than leaking credentials to LLM providers.

---

### SE-07: No Sandbox in Development Mode

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/executor.py` (lines 324-338)

**Description:** In development mode, `_sandbox_kwargs()` returns an empty dict. No `preexec_fn`, no `NO_NEW_PRIVS`, no Landlock, no LD_PRELOAD sandboxer. Commands validated as "allow" execute with full user privileges and no containment. The "DENIED_SHELLS" list in `constants.py` is informational only -- it is the C sandboxer library that enforces it, and that library is not loaded in development mode.

```python
# executor.py lines 324-338
def _sandbox_kwargs() -> dict:
    if get_mode() != "production":
        return {}  # No sandbox at all
    return {
        "preexec_fn": make_no_new_privs_fn(),
    }
```

**Adversary analysis:**
- **The Scoundrel:** Exploits the fact that the LLM can be tricked (no model is 100% accurate). Once a command is "allowed," there is no second line of defense.
- **The Lazy Developer:** Deploys in development mode because Landlock requires kernel support and a compiled C library.
- **The Confused Developer:** Sees the DENIED_SHELLS list in constants.py and believes shell spawning is blocked.

**Recommendation:** Document explicitly that development mode provides monitoring only, not enforcement. Consider a lighter sandbox for development mode (e.g., seccomp-bpf profile that at least blocks `execve` of shell binaries).

---

### SE-08: `AEGISH_SKIP_BASH_HASH=true` Disables Binary Integrity Checking

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py` (lines 831-845)
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/shell.py` (lines 435-445)

**Description:** When `AEGISH_SKIP_BASH_HASH=true` is set in the config file, the SHA-256 hash verification of `/bin/bash` is completely bypassed. This is intended for bare-metal deployments with automated updates, but it means a compromised `/bin/bash` would not be detected.

```python
# config.py line 845
def skip_bash_hash() -> bool:
    raw = _get_security_config("AEGISH_SKIP_BASH_HASH", "")
    return raw.strip().lower() == "true"
```

Note that the sandboxer `.so` hash check is NOT affected by this setting, which is good -- but `/bin/bash` is the actual execution environment for all commands.

**Adversary analysis:**
- **The Scoundrel:** Replaces `/bin/bash` with a trojanized version. If `SKIP_BASH_HASH` is enabled, aegish uses the trojanized binary.
- **The Lazy Developer:** Enables this flag to avoid dealing with hash updates after package upgrades.
- **The Confused Developer:** Does not realize that skipping bash hash verification eliminates the entire binary integrity guarantee.

**Recommendation:** When `SKIP_BASH_HASH` is enabled, log a persistent audit entry and require explicit acknowledgment. Consider a runtime integrity check (e.g., comparing against dpkg/rpm database) as a fallback.

---

## 3. Primitive vs Semantic APIs

### SE-09: Security Actions Are Plain Strings, Not Enums

**Severity:** High
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/validator.py` (lines 36-103)
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/shell.py` (lines 141-203)
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/llm_client.py` (lines 560-612)

**Description:** The security decision throughout the entire system is a plain string `"allow"`, `"warn"`, or `"block"` stored in a `dict`. There is no enum type, no type-checked construction, and no exhaustive match. The shell loop in `shell.py` uses string equality checks with an `else` catch-all.

The critical issue is in `shell.py` lines 182-203: the `else` branch (unknown action from LLM) treats the result as a *warning* and allows the user to confirm execution. This means any novel string value (typo, LLM hallucination, parsing error) defaults to an executable state.

```python
# shell.py lines 182-203
else:
    # Unknown action from LLM - treat as warning
    action = result.get("action", "unknown")
    print(f"\nWARNING: Unexpected validation response '{action}'.")
    # Get user confirmation (same as warn flow)
    response = input("Proceed anyway? [y/N]: ").strip().lower()
    if response in ("y", "yes"):
        # EXECUTES THE COMMAND with unknown validation state
        exec_cmd = result.get("resolved_command", command)
        last_exit_code, current_dir, previous_dir, env = (
            _execute_and_update(exec_cmd, ...)
        )
```

**Adversary analysis:**
- **The Scoundrel:** Crafts a prompt injection that causes the LLM to return `{"action": "alow"}` (typo). The shell treats this as "unknown," prompts the user, and allows execution.
- **The Lazy Developer:** Adds a new validation status without updating all switch branches.
- **The Confused Developer:** Assumes that only "allow" leads to execution; does not realize "unknown" also allows it.

**Recommendation:** Define a Python `Enum` for actions (`Action.ALLOW`, `Action.WARN`, `Action.BLOCK`). Change the unknown-action branch to default to BLOCK, not WARN. The `_parse_response` function in `llm_client.py` already validates against the three known values and returns `None` for unknowns -- but this protection is bypassed if `_parse_response` is not the only path to the shell loop.

---

### SE-10: `validate_command()` Returns Untyped Dict

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/validator.py` (lines 36-103)

**Description:** `validate_command()` returns a `dict` with no schema enforcement. Callers must manually extract `result["action"]`, `result["reason"]`, `result.get("confidence", 0.0)`, and `result.get("resolved_command", command)` with varying defaults. Missing keys are silently replaced with fallback values.

There are at least four different places where result dicts are constructed:
1. `validator.py` static blocklist results (no `resolved_command`)
2. `validator.py` bashlex results (no `resolved_command`)
3. `llm_client.py` `_parse_response` (no `resolved_command`)
4. `llm_client.py` `_validation_failed_response` (no `resolved_command`)

Each has slightly different key sets. The `resolved_command` key is only attached in `validate_command()` line 102, not in the result dicts themselves.

**Adversary analysis:**
- **The Scoundrel:** Not directly exploitable, but increases the chance of bugs that are exploitable.
- **The Lazy Developer:** Returns a dict missing the `action` key from a new code path. `result.get("action", "unknown")` in the shell loop then triggers the permissive `else` branch.
- **The Confused Developer:** Assumes all result dicts have the same shape.

**Recommendation:** Define a `@dataclass` or `TypedDict` for validation results. Ensure all construction paths produce the same schema. Use a factory function rather than ad-hoc dict construction.

---

### SE-11: `ACTION_SEVERITY` Treats Unknown Actions as `allow`

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/constants.py` (line 194)
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/validator.py` (line 487)

**Description:** The `_most_restrictive()` aggregation function uses `ACTION_SEVERITY.get(r.get("action", "allow"), 0)`. If a result has an unknown action string, it defaults to severity 0 (same as `allow`). This means an unrecognized action in a compound command would be treated as the *least* restrictive rather than the *most*.

```python
# constants.py line 194
ACTION_SEVERITY = {"allow": 0, "warn": 1, "block": 2}

# validator.py line 487
return max(results, key=lambda r: _ACTION_SEVERITY.get(r.get("action", "allow"), 0))
```

**Adversary analysis:**
- **The Scoundrel:** Crafts compound commands where one subcommand triggers an edge case returning an unrecognized action; aggregation treats it as `allow`.
- **The Lazy Developer:** Not directly relevant.
- **The Confused Developer:** Assumes `_most_restrictive` is conservative; it is actually permissive for unknown values.

**Recommendation:** Change the default from `0` (allow-severity) to `2` (block-severity) so unrecognized actions are treated as maximally restrictive: `_ACTION_SEVERITY.get(r.get("action", "block"), 2)`.

---

## 4. Configuration Cliffs

### SE-12: Env Var Typo Silently Falls Back to Insecure Defaults

**Severity:** High
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py` (lines 198-211, 500-552)

**Description:** `AEGISH_FAIL_MODE` uses `on_invalid="debug"` for invalid values. This means setting `AEGISH_FAIL_MODE=sfe` (typo of "safe") silently falls back to the default (`"safe"`, which is fortunately the secure option). However, `AEGISH_ROLE` uses `on_invalid="warning"` and falls back to `"default"`.

The real cliff is the asymmetry: `AEGISH_MODE` uses `on_invalid="fatal"` (sys.exit on invalid value), but `AEGISH_FAIL_MODE` uses `on_invalid="debug"` (silent fallback). An administrator might expect consistent behavior.

More critically, `AEGISH_FAIL_MODE=open` with `on_invalid="debug"` means if someone sets `AEGISH_FAIL_MODE=OPEN` (uppercase) and the system lowercases it, it works. But if someone sets `AEGISH_FAIL_MODE= open` (leading space in config file), the space handling in `_get_validated_setting` strips it correctly. The inconsistency in error severity across settings is the footgun.

```python
# config.py lines 209-211
def get_fail_mode() -> str:
    return _get_validated_setting(
        "AEGISH_FAIL_MODE", VALID_FAIL_MODES, DEFAULT_FAIL_MODE, on_invalid="debug",
    )  # "debug" = silently fall back
```

**Adversary analysis:**
- **The Scoundrel:** Not directly exploitable (typos fall back to secure defaults for fail_mode).
- **The Lazy Developer:** Sets `AEGISH_FAIL_MODE=sfe` (typo), doesn't notice the debug-level log, and believes they set a specific mode. When they intend `open` and type `opn`, they get `safe` silently -- this is safe-by-accident but confusing.
- **The Confused Developer:** Expects all settings to behave like `AEGISH_MODE` (fatal on invalid). Sets an invalid `AEGISH_ROLE` and does not notice the warning-level log buried in output.

**Recommendation:** Use `on_invalid="fatal"` or at minimum `on_invalid="warning"` for ALL security-critical settings, not just `AEGISH_MODE`. Silent fallback for security settings is a footgun regardless of whether the default is safe.

---

### SE-13: Config File Permission Check Silently Ignores Non-Root-Owned Files

**Severity:** High
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py` (lines 616-679, 682-711)

**Description:** When the config file at `/etc/aegish/config` fails the permission check (not owned by root, or world-writable), `_load_config_file` logs a warning and returns an empty dict. This means all `_get_security_config()` calls fall through to default values. In production mode, this causes a cascade:

1. Config file exists but is owned by the user (uid != 0)
2. Permission check fails, returns empty config
3. All SECURITY_CRITICAL_KEYS return defaults with warnings
4. System operates with default settings, which may differ from the administrator's intent

The warning is only logged at `logger.warning` level, which may not be visible in all deployments.

```python
# config.py lines 647-653
is_valid, err = _validate_config_file_permissions(path)
if not is_valid:
    logger.warning("Config file permission check failed: %s", err)
    if path == CONFIG_FILE_PATH:
        _config_file_cache = config  # Empty dict!
        _config_file_loaded = True
    return config  # Empty dict - all settings fall to defaults
```

**Adversary analysis:**
- **The Scoundrel:** Creates `/etc/aegish/config` as a non-root user with `AEGISH_FAIL_MODE=open`. The permission check rejects it, but the file's existence masks the absence of a proper config. All settings silently use defaults.
- **The Lazy Developer:** Creates the config file as their user account, not root. Production mode silently ignores all settings in it.
- **The Confused Developer:** Sees the config file exists, assumes production mode is using it.

**Recommendation:** In production mode, a config file that exists but fails permission validation should be a FATAL error, not a warning. The current behavior silently degrades to defaults.

---

### SE-14: Empty `AEGISH_ALLOWED_PROVIDERS` Restores Full Default Provider Set

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/config.py` (lines 455-473)

**Description:** If `AEGISH_ALLOWED_PROVIDERS` is set to an empty string (or all-whitespace), the system falls back to `DEFAULT_ALLOWED_PROVIDERS`, which includes 8 providers. An administrator intending to restrict to *no* providers (effectively disabling the system) instead gets *all* default providers.

```python
# config.py lines 466-473
def get_allowed_providers() -> set[str]:
    raw_value = _get_security_config("AEGISH_ALLOWED_PROVIDERS", "")
    if not raw_value or not raw_value.strip():
        return DEFAULT_ALLOWED_PROVIDERS.copy()  # Full set of 8 providers!
    providers = {p.strip().lower() for p in raw_value.split(",") if p.strip()}
    return providers if providers else DEFAULT_ALLOWED_PROVIDERS.copy()
```

**Adversary analysis:**
- **The Scoundrel:** Not directly exploitable.
- **The Lazy Developer:** Sets `AEGISH_ALLOWED_PROVIDERS=` (empty) in config, expecting to disable all providers. Gets all 8 defaults instead.
- **The Confused Developer:** Clears the variable to "reset to minimum" and gets maximum instead.

**Recommendation:** Distinguish between "not set" (use defaults) and "set to empty" (no providers allowed, which should be a fatal startup error since aegish cannot function without providers).

---

### SE-15: Fallback to Default Model Chain When All Configured Models Are Rejected

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/llm_client.py` (lines 219-232)

**Description:** When ALL user-configured models are rejected by the provider allowlist, `query_llm` silently falls back to the default model chain. This means an administrator who intentionally restricts to specific models (and has a provider allowlist misconfiguration) does not get an error -- the system silently uses models they did not configure.

```python
# llm_client.py lines 219-232
if not models_to_try and any_rejected_by_allowlist:
    logger.warning(
        "All configured models rejected by provider allowlist. "
        "Falling back to default model chain."
    )
    default_chain = [DEFAULT_PRIMARY_MODEL] + DEFAULT_FALLBACK_MODELS
    for model in default_chain:
        # ...tries default models regardless of user config...
```

**Adversary analysis:**
- **The Scoundrel:** Not directly exploitable.
- **The Lazy Developer:** Configures `AEGISH_ALLOWED_PROVIDERS=mycompany_ai` and `AEGISH_PRIMARY_MODEL=mycompany_ai/secure-model`. Provider typo causes rejection, system silently uses Gemini Flash.
- **The Confused Developer:** Believes their custom model is in use; sees no error because it fell back silently.

**Recommendation:** When all configured models are rejected, this should be a startup error, not a silent fallback. At minimum, print a visible warning (not just a logger.warning).

---

## 5. Silent Failures

### SE-16: Audit Log Failures Are Silent

**Severity:** High
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/audit.py` (lines 28-75, 96-114)

**Description:** Audit log initialization failure only produces a stderr warning in the shell loop (`shell.py` line 93: `print("WARNING: Audit logging unavailable.")`), but the shell continues operating. Individual audit write failures are logged at `logger.debug` level (line 114), which is effectively invisible.

If `/var/log/aegish/` is full, not writable, or the file descriptor is closed due to log rotation, all subsequent audit entries are silently dropped. The `_audit_available` flag is set once at init and never rechecked.

```python
# audit.py lines 110-114
try:
    _audit_fd.write(json.dumps(entry) + "\n")
    _audit_fd.flush()
except OSError:
    logger.debug("Failed to write audit log entry")  # Silent!
```

**Adversary analysis:**
- **The Scoundrel:** Fills the audit log partition before executing malicious commands. All subsequent audit entries are silently dropped.
- **The Lazy Developer:** Does not monitor audit log health. Discovers months later that audit logging has been broken since a partition filled up.
- **The Confused Developer:** Assumes "audit logging" means "forensic trail exists"; does not realize it can silently fail.

**Recommendation:** Audit write failures should escalate: after N consecutive failures, print a visible warning. In production mode, consider blocking command execution if audit logging is unavailable (audit trail is a compliance requirement).

---

### SE-17: Bashlex Parse Failures Silently Degrade Security Analysis

**Severity:** High
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/validator.py` (lines 128-163, 376-425, 428-477)

**Description:** Multiple security checks depend on bashlex parsing, and ALL of them silently fall through to the LLM-only path when bashlex fails:

1. `_check_variable_in_command_position` (line 161): Returns `{"_parse_failed": True}` which only sets `parse_unreliable = True`.
2. `_extract_subcommand_strings` (line 389): Returns `None` (no decomposition, command sent to LLM as monolithic string).
3. `_has_command_substitution_in_exec_pos` (line 440): Returns `None` (no block).

Commands that are *designed to confuse bashlex* (complex quoting, unusual syntax) bypass all AST-based security checks and rely entirely on the LLM's ability to analyze the raw text.

```python
# validator.py line 161
except Exception:
    logger.debug("bashlex analysis failed for: %s", command)
    return {"_parse_failed": True}  # Only sets a flag, doesn't block

# validator.py line 389
except Exception:
    logger.debug("bashlex decomposition failed for: %s", command)
    return None  # Falls through to single LLM pass

# validator.py line 440
except Exception:
    logger.debug("bashlex cmdsub detection failed for: %s", command)
    return None  # No block on parse failure
```

**Adversary analysis:**
- **The Scoundrel:** Uses syntax constructs known to crash bashlex (e.g., deeply nested process substitutions, unusual heredoc combinations). All structural analysis is bypassed; only the LLM sees the command.
- **The Lazy Developer:** Not directly relevant.
- **The Confused Developer:** Assumes the variable-in-command-position check and compound command decomposition always run. Does not realize bashlex failures silently disable them.

**Recommendation:** When bashlex fails, the `parse_unreliable` flag is passed to the LLM, but the LLM may not treat it with sufficient suspicion. Consider defaulting to BLOCK or WARN (not just an annotation) when bashlex fails on commands containing known risky patterns (`$`, backticks, `eval`, `exec`).

---

### SE-18: LLM Response Parsing Returns None Without Blocking

**Severity:** High
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/llm_client.py` (lines 560-612)

**Description:** `_parse_response` returns `None` when it cannot parse the LLM response. The caller (`_try_model` at line 250-252) treats `None` as "try next model." If ALL models return unparseable responses, execution falls to `_validation_failed_response` which depends on fail mode.

The multi-layer indirection (parse failure -> try next -> all failed -> fail mode check) makes it difficult to reason about what actually happens when the LLM returns garbage. In `open` mode, garbage from all models results in a bypassable warning.

```python
# llm_client.py lines 249-252
if result is not None:
    return result
# Parsing failed, try next model
last_error = f"{model}: response could not be parsed"
```

**Adversary analysis:**
- **The Scoundrel:** Crafts a prompt injection that causes the LLM to return syntactically valid JSON with an invalid action field (e.g., `{"action": "permitted", "reason": "safe"}`). `_parse_response` returns `None` (line 595: action not in valid list). This cascades through all models. In `open` mode, the command executes after a warning.
- **The Lazy Developer:** Not directly relevant.
- **The Confused Developer:** Assumes that if the LLM responded *at all*, the system will either allow or block -- does not realize "unparseable" is a distinct state that cascades.

**Recommendation:** Track the *type* of failure separately. If all models returned responses but none were parseable, this is a different situation from "all models are unreachable" and should be treated more suspiciously (possible coordinated prompt injection).

---

### SE-19: `_extract_via_scanner` Fallback Has Known Limitations

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/resolver.py` (lines 212-298, 301-323)

**Description:** When bashlex fails to parse command substitutions, the system falls back to `_extract_via_scanner`, a hand-written balanced-parenthesis scanner. This scanner has documented limitations:

1. It skips arithmetic expansions `$((` but may mishandle `$(( $(cmd) ))`.
2. Escape handling at line 248 (`text[i - 1] == "\\"`) does not handle double-escapes (`\\$(`).
3. The scanner does not handle all bash quoting contexts (e.g., `$"..."` locale strings, ANSI-C quotes inside substitutions).

Commands that bypass this scanner have their substitutions unresolved, meaning the LLM only sees the raw `$(...)` text without knowing what it expands to.

**Adversary analysis:**
- **The Scoundrel:** Uses `\\$(malicious_command)` where the double backslash is interpreted by bash as a literal backslash followed by a substitution, but the scanner sees `\$(` and skips it.
- **The Lazy Developer:** Not directly relevant.
- **The Confused Developer:** Assumes all `$(...)` patterns are resolved before LLM analysis.

**Recommendation:** Document the scanner's limitations. When the scanner fails to extract substitutions that are visibly present in the command (i.e., `$(` is in the text but scanner returns empty), set `parse_unreliable` to trigger heightened LLM scrutiny.

---

### SE-20: Health Check Failure Does Not Block Commands

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/shell.py` (lines 484-498)

**Description:** When the health check fails for all models (lines 485-494), aegish prints a warning and enters "degraded mode" but still accepts commands. In non-login-shell mode, it prints "WARNING: All models unreachable. Operating in degraded mode." and then enters the shell loop.

In degraded mode, every command will fail LLM validation and be handled by `_validation_failed_response` -- which means every command is either blocked (safe mode) or warned (open mode). In open mode, every single command becomes a click-through warning.

```python
# shell.py lines 485-494
if not success:
    logger.warning("Health check failed: %s", reason)
    print(reason)
    if login_shell:
        print("WARNING: All models unreachable. This is your login shell...")
    else:
        print("WARNING: All models unreachable. Operating in degraded mode.")
# Shell loop starts regardless
```

**Adversary analysis:**
- **The Scoundrel:** Blocks network access to LLM providers. In `open` mode, user must click through warnings for every command but all commands eventually execute.
- **The Lazy Developer:** Ignores the health check warning and uses the shell in degraded mode.
- **The Confused Developer:** Does not realize "degraded mode" means "no LLM validation at all."

**Recommendation:** In production mode with `fail_mode=safe`, health check failure should block shell entry entirely (not just print a warning). The current behavior only makes sense for login shells where blocking entry would lock out the user.

---

## 6. Stringly-Typed Security

### SE-21: Security Decisions Flow as Dict Strings Through 5+ Modules

**Severity:** High
**File:** Multiple files (validator.py, llm_client.py, shell.py, resolver.py, audit.py)

**Description:** The security decision lifecycle is:
1. LLM returns JSON string `{"action": "allow"}`
2. `_parse_response` extracts string, validates against `["allow", "warn", "block"]` list
3. Returns `dict` with `"action"` as plain string
4. `validate_command` passes dict through
5. `shell.py` compares `result["action"] == "allow"` via string equality
6. `audit.py` logs `action` as plain string
7. `resolver.py` checks `action == "block"` / `action == "warn"` via string equality

At no point is the action typed. The string literal `"allow"` appears in 6 different files. A single typo in any comparison (e.g., `result["action"] == "alow"`) would create a false-negative branch that falls to the permissive `else` clause in `shell.py`.

**Adversary analysis:**
- **The Scoundrel:** Not directly exploitable (would require a code bug, not a runtime attack).
- **The Lazy Developer:** Adds a new code path with `result["action"] == "Allow"` (capital A). The comparison fails, command falls to the `else` branch in shell.py, user can confirm execution.
- **The Confused Developer:** Searches for `"block"` to find all blocking paths, misses the `else` branch that also allows execution of unknown actions.

**Recommendation:** Define an enum:
```python
class Action(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
```
Use `Action.ALLOW` throughout. The `str` base class maintains JSON serialization compatibility.

---

### SE-22: Role Prompt Injection via Stringly-Typed Role Names

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/constants.py` (lines 489-509)
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/llm_client.py` (lines 476-479)

**Description:** Role-specific prompt additions are stored in a `dict[str, str]` keyed by role name. The role name is validated against `VALID_ROLES` in `config.py`, but the prompt lookup in `llm_client.py` uses a dict `.get()` with the role string:

```python
# llm_client.py lines 477-479
role = get_role()
if role in _ROLE_PROMPT_ADDITIONS:
    system_content += _ROLE_PROMPT_ADDITIONS[role]
```

The `ROLE_PROMPT_ADDITIONS` dict only has entries for `"sysadmin"` and `"restricted"`. The default role `"default"` has no entry, so no addition is made. This is correct but brittle -- if a new role is added to `VALID_ROLES` without a corresponding prompt addition, the LLM receives no role context and falls back to the base prompt.

More concerning: the role-specific prompts directly instruct the LLM to *weaken* its security analysis. The `sysadmin` prompt says "sudo commands...should NOT be blocked" and "cat /etc/shadow...is legitimate -> WARN (not BLOCK)". These instructions are embedded as plain strings in the system prompt, not as structured constraints.

**Adversary analysis:**
- **The Scoundrel:** In development mode, sets `AEGISH_ROLE=sysadmin` to get the weakened prompt. The weakened prompt makes the LLM more permissive for `sudo` and sensitive file access.
- **The Lazy Developer:** Not directly relevant.
- **The Confused Developer:** Adds a new role to `VALID_ROLES` but forgets to add prompt additions. The new role operates identically to `default`.

**Recommendation:** Consider making role-based constraints structural (e.g., a separate validation step that post-processes the LLM result based on role) rather than modifying the LLM prompt. Prompt-based constraints are probabilistic, not deterministic.

---

### SE-23: Static Blocklist Patterns Are Order-Dependent Regexes

**Severity:** Low
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/constants.py` (lines 182-191)

**Description:** The static blocklist is a list of `(compiled_regex, reason)` tuples. Patterns are checked in order with `pattern.search(command)`. The patterns use basic regex features and match against the canonicalized command text. However:

1. The `rm -rf /` pattern `r"\brm\s+-[^\s]*r[^\s]*f[^\s]*\s+/(?:\s|$|\*)"` matches `-rf` and `-fr` but not `-r -f` (separate flags).
2. The fork bomb pattern `r":\(\)\s*\{"` only matches the classic `:(){` form, not variants like `bomb(){ bomb|bomb& };bomb`.
3. The `nc -e` pattern `r"\bnc\b.*\s-e\s"` does not match `nc --exec` (long flag form).

```python
# constants.py lines 182-191
STATIC_BLOCK_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"/dev/tcp/"), "Reverse shell via /dev/tcp"),
    (re.compile(r"\bnc\b.*\s-e\s"), "Reverse shell via nc -e"),
    (re.compile(r"\brm\s+-[^\s]*r[^\s]*f[^\s]*\s+/(?:\s|$|\*)"), "Destructive rm -rf /"),
    # ...
]
```

**Adversary analysis:**
- **The Scoundrel:** Uses `rm -r -f /` (separate flags) to bypass the static blocklist. The LLM may still catch it, but the guaranteed-block fast path is bypassed.
- **The Lazy Developer:** Relies on the static blocklist as comprehensive protection; does not realize it only covers specific syntax forms.
- **The Confused Developer:** Sees the blocklist entries and assumes all variants are covered.

**Recommendation:** This is a known limitation of pattern-based blocklists and the LLM serves as the primary defense. However, expand the `rm` pattern to handle separated flags: `r"\brm\s+(-\S+\s+)*-\S*r\S*\s+(-\S+\s+)*-\S*f"` or similar. The static blocklist is the only defense that does not degrade in `open` fail mode.

---

### SE-24: Double-Brace Normalization May Corrupt Legitimate JSON

**Severity:** Low
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/json_utils.py` (lines 37-38)

**Description:** `find_balanced_json` normalizes `{{` to `{` and `}}` to `}` globally before parsing. This was designed to handle LLMs that double-brace their output (common with some models). However, this normalization is applied to the ENTIRE text, not just the JSON portion. If the LLM's response contains explanation text with literal double braces (e.g., `"In bash, {{var}}..."`), the normalization corrupts the text before JSON extraction.

```python
# json_utils.py lines 37-38
normalized = text.replace("{{", "{").replace("}}", "}")
```

Additionally, this normalization is destructive for JSON values that legitimately contain `{{` (e.g., template strings in a reason field). The comment acknowledges "This is safe for our expected schema (flat objects with no nesting)" but this assumption may not hold if the schema evolves.

**Adversary analysis:**
- **The Scoundrel:** Crafts a command that causes the LLM to include `{{` in its reason text. The normalization collapses `{{` to `{`, potentially corrupting the JSON parse and causing `_parse_response` to return `None`.
- **The Lazy Developer:** Not directly relevant.
- **The Confused Developer:** Evolves the schema to include nested objects; double-brace normalization corrupts them.

**Recommendation:** Apply double-brace normalization only to the outer braces (i.e., only normalize if the entire response is double-braced `{{...}}`), not globally. Alternatively, try parsing without normalization first, and only apply normalization as a fallback.

---

### SE-25: `AEGISH_` Prefix Env Vars Pass Through Allowlist to Child Processes

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/constants.py` (line 170)
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/executor.py` (lines 123-145, 256-282)

**Description:** The env allowlist includes all variables with the `AEGISH_` prefix:

```python
# constants.py line 170
ALLOWED_ENV_PREFIXES = ("LC_", "XDG_", "AEGISH_")
```

This means ALL `AEGISH_*` variables (including `AEGISH_FAIL_MODE`, `AEGISH_ROLE`, `AEGISH_PRIMARY_MODEL`) are passed to child processes. If a child process spawns another aegish instance (either directly or through a script), that inner instance inherits the potentially-attacker-controlled security settings.

More importantly, in development mode, a user can `export AEGISH_FAIL_MODE=open` and it persists across commands because the env sanitizer preserves `AEGISH_` prefixed vars.

```python
# executor.py lines 273-275 (in sanitize_env)
for key, value in captured.items():
    if key in ALLOWED_ENV_VARS or key.startswith(ALLOWED_ENV_PREFIXES):
        env[key] = value  # AEGISH_* vars pass through
```

**Adversary analysis:**
- **The Scoundrel:** Runs `export AEGISH_FAIL_MODE=open` as the first command. It passes validation (it is a simple export). All subsequent commands now operate in open fail mode because the env var persists.
- **The Lazy Developer:** Not directly relevant.
- **The Confused Developer:** Assumes security settings are read once at startup and cannot be changed during a session.

**Recommendation:** Security-critical `AEGISH_*` settings should be read once at startup and cached, NOT re-read from the (potentially modified) environment on each command. Alternatively, strip `AEGISH_FAIL_MODE`, `AEGISH_ROLE`, and other security-critical vars from the allowlist so they cannot be set from within the shell session. Note: `config.py` does re-read env vars on each call to `get_fail_mode()` etc.

---

### SE-26: Sudo Pre-flight Failure Falls Back to Running Without Sudo

**Severity:** Medium
**File:** `/home/gbergman/YDKHHICF/SecBASH/src/aegish/executor.py` (lines 406-478)

**Description:** When sudo pre-flight validation fails (invalid binary or missing sandboxer), the system falls back to running the command *without sudo* but still runs it:

```python
# executor.py lines 438-440
if not sudo_ok:
    logger.warning("sudo pre-flight failed: %s; running without sudo", sudo_err)
    return execute_command(stripped_cmd, last_exit_code, env, cwd)
```

This means `sudo rm -rf /tmp/test` with a broken sudo binary becomes `rm -rf /tmp/test` -- the command still executes but without elevated privileges. While less dangerous than running with sudo, the user typed `sudo` for a reason and the system silently drops it.

**Adversary analysis:**
- **The Scoundrel:** Replaces `/usr/bin/sudo` with a non-SUID binary. Aegish detects the SUID check failure and falls back to running without sudo. The attacker then exploits the fact that commands run under the current user without the expected sudo elevation context (e.g., commands that were validated as safe *because* they run as root).
- **The Lazy Developer:** Does not notice sudo pre-flight warnings in logs.
- **The Confused Developer:** Expects that if sudo fails, the command is blocked, not run without elevation.

**Recommendation:** When sudo pre-flight fails, block the command and inform the user rather than silently stripping `sudo`. The user should decide whether to run without elevation.

---

## 7. Summary Table

| ID | Title | Severity | Category | Primary Adversary |
|----|-------|----------|----------|-------------------|
| SE-01 | Unrestricted Model Selection | High | Algorithm/Mode | Scoundrel |
| SE-02 | open Fail Mode Degrades All Failures | High | Algorithm/Mode | Scoundrel |
| SE-03 | warn for Variable-Injection Detection | Medium | Algorithm/Mode | Scoundrel |
| SE-04 | sysadmin Role Relaxes Prompt | Medium | Algorithm/Mode | Scoundrel |
| SE-05 | Dev Mode Reads from Env Vars | Critical | Dangerous Defaults | Scoundrel |
| SE-06 | Sensitive Var Filtering Off by Default | Medium | Dangerous Defaults | Scoundrel |
| SE-07 | No Sandbox in Dev Mode | Medium | Dangerous Defaults | Scoundrel |
| SE-08 | Skip Bash Hash Disables Integrity | Medium | Dangerous Defaults | Scoundrel |
| SE-09 | Security Actions Are Plain Strings | High | Primitive vs Semantic | Scoundrel/Lazy Dev |
| SE-10 | Untyped Dict Return from validate_command | Medium | Primitive vs Semantic | Lazy Dev |
| SE-11 | ACTION_SEVERITY Treats Unknown as Allow | Medium | Primitive vs Semantic | Scoundrel |
| SE-12 | Env Var Typo Silently Falls Back | High | Configuration Cliffs | Lazy Dev |
| SE-13 | Config Permission Fail Silently Ignored | High | Configuration Cliffs | Scoundrel/Lazy Dev |
| SE-14 | Empty Providers Restores Full Default | Medium | Configuration Cliffs | Confused Dev |
| SE-15 | Fallback to Default Model Chain | Medium | Configuration Cliffs | Confused Dev |
| SE-16 | Audit Log Failures Are Silent | High | Silent Failures | Scoundrel |
| SE-17 | Bashlex Failures Degrade Analysis | High | Silent Failures | Scoundrel |
| SE-18 | LLM Parse Failure Does Not Block | High | Silent Failures | Scoundrel |
| SE-19 | Fallback Scanner Has Limitations | Medium | Silent Failures | Scoundrel |
| SE-20 | Health Check Failure Allows Shell Entry | Medium | Silent Failures | Scoundrel |
| SE-21 | String Actions Through 5+ Modules | High | Stringly-Typed | Lazy Dev |
| SE-22 | Role Prompt Injection via Strings | Medium | Stringly-Typed | Scoundrel |
| SE-23 | Regex Blocklist Order-Dependent | Low | Stringly-Typed | Scoundrel |
| SE-24 | Double-Brace Normalization Corruption | Low | Stringly-Typed | Scoundrel |
| SE-25 | AEGISH_ Vars Pass to Child Processes | Medium | Stringly-Typed | Scoundrel |
| SE-26 | Sudo Failure Falls Back to No-Sudo | Medium | Configuration Cliffs | Scoundrel |

**Severity distribution:** 1 Critical, 8 High, 13 Medium, 2 Low (26 total findings)

---

## Top 5 Priority Remediations

1. **SE-09 + SE-21 + SE-11 (Action enum):** Define a Python `Enum` for actions. Change the unknown-action fallback in `shell.py` from warn-flow to block. Change `ACTION_SEVERITY` default from allow-level to block-level. This is a structural fix that eliminates an entire class of bugs.

2. **SE-25 (Runtime config mutation):** Read all security-critical settings once at startup and cache them. Do not re-read from environment variables on each command. Strip security-critical `AEGISH_*` vars from the child process allowlist or snapshot them at startup.

3. **SE-13 (Config permission fatal):** In production mode, treat config file permission failures as fatal errors, not warnings. A non-root-owned config file in production should prevent startup.

4. **SE-16 (Audit escalation):** Implement escalating audit failure handling. After N consecutive write failures, print visible warnings. In production mode, consider halting command execution if audit integrity cannot be maintained.

5. **SE-17 + SE-18 (Parse failure handling):** When bashlex fails on commands containing `$`, backticks, `eval`, or `exec`, default to WARN or BLOCK rather than silently falling through. When all LLM models return unparseable responses (as distinct from unreachable), treat this as a potential coordinated attack and block rather than warn.
