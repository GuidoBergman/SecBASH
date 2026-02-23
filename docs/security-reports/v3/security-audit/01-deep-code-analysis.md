# Deep Code Analysis: aegish Security Audit

**Scope**: All source files in `src/aegish/` (14 Python files, ~5,100 lines)
**Date**: 2026-02-22
**Method**: Ultra-granular per-function analysis with cross-function data-flow tracing
**Purpose**: Context building for subsequent security analysis phases

> **Note**: The full function-level analysis (~2,500 lines) was produced by the audit-context-building agent but exceeded the agent's write capabilities. The complete transcript is available at:
> `/tmp/claude-1000/-home-gbergman-YDKHHICF-SecBASH/tasks/a670d2a994ac5d28d.output`
>
> All 18 findings below are incorporated into the consolidated `SECURITY_REPORT.md`.

---

## Files Analyzed (Priority Order)

| File | Lines | Role | Security Criticality |
|------|-------|------|---------------------|
| executor.py | 479 | Command execution via subprocess | Highest -- sole path to OS execution |
| sandbox.py | 151 | Landlock probing, NO_NEW_PRIVS | High -- secondary defense layer |
| validator.py | 488 | Validation pipeline (static + LLM) | High -- security decision logic |
| llm_client.py | 686 | LLM API communication | High -- prompt construction, response parsing |
| shell.py | 499 | Interactive shell loop | High -- user input handling, action dispatch |
| resolver.py | 324 | Command substitution resolution | Medium -- pre-validation execution |
| canonicalizer.py | 317 | Input normalization | Medium -- transform correctness |
| config.py | 881 | Configuration management | Medium -- security settings source |
| audit.py | 143 | Audit logging | Medium -- forensic trail |
| json_utils.py | 67 | JSON extraction from LLM responses | Low -- parsing robustness |
| utils.py | 527 | Utilities (env expansion, tag escaping) | Medium -- prompt injection surface |
| main.py | 58 | CLI entry point | Low |
| constants.py | 509 | Constants, prompts, patterns | Medium -- security policy definitions |

---

## Security-Relevant Findings Summary

### Finding 1: Command Execution Relies Solely on LLM Judgment for Non-Blocklisted Commands
**Location**: `shell.py:141-152`, `executor.py:93-98`
Once `validate_command()` returns `action="allow"`, execution proceeds unconditionally. The static blocklist (8 patterns) provides a thin deterministic safety net.

### Finding 2: Bare `cd` Commands Bypass All Validation
**Location**: `shell.py:134-138`
`is_bare_cd()` fast-paths simple cd commands, skipping `validate_command()`. Compound commands with cd are not affected.

### Finding 3: Command Substitution Resolution Executes Commands Before Full Validation
**Location**: `resolver.py:122-140`
Inner `$()` commands are validated individually then executed to capture stdout BEFORE the outer command is sent to the LLM. The composed result is not re-checked against the static blocklist.

### Finding 4: Canonicalization-Execution Gap (Mitigated)
**Location**: `canonicalizer.py`, `shell.py:146`
The shell executes `result.get("resolved_command", command)` -- the canonical form. The LLM validates and executor runs the SAME text, mitigating TOCTOU.

### Finding 5: Development Mode Has No Sandbox
**Location**: `executor.py:333`, `sandbox.py:129-150`
`_sandbox_kwargs()` returns empty dict in development mode. No `preexec_fn`, no Landlock, no LD_PRELOAD.

### Finding 6: Sudo Path Skips NO_NEW_PRIVS and Environment Capture
**Location**: `executor.py:406-478`
Sudo execution skips `preexec_fn` (required for SUID). LD_PRELOAD sandboxer expected to apply Landlock post-elevation. Environment state not updated after sudo.

### Finding 7: Fail-Open Mode Allows Execution of Unvalidated Commands
**Location**: `llm_client.py:615-632`, `config.py:198-211`
`AEGISH_FAIL_MODE=open` + all models fail = `action="warn"` = user can type `y` to execute.

### Finding 8: Environment Variable Expansion May Include Sensitive Values
**Location**: `utils.py:101-144`, `llm_client.py:444-446`
`get_safe_env()` returns `dict(os.environ)` by default. API keys in `$VAR` references are sent to LLM providers.

### Finding 9: AEGISH_ Prefix Passes Through to Child Processes
**Location**: `constants.py:170`
`ALLOWED_ENV_PREFIXES = ("LC_", "XDG_", "AEGISH_")` -- all AEGISH_* vars survive env sanitization.

### Finding 10: Static Blocklist Has Limited Coverage
**Location**: `constants.py:182-191`
8 patterns covering /dev/tcp, nc -e, rm -rf /, mkfs, fork bombs. Many dangerous patterns depend on LLM.

### Finding 11: Landlock Denylist is Path-Based
**Location**: `constants.py:286-307`
DENIED_SHELLS is a set of absolute paths. Code explicitly acknowledges copy-to-unlisted-path bypass.

### Finding 12: Config File Permissions Check Does Not Verify Group Write
**Location**: `config.py:682-711`
Checks `S_IWOTH` but not `S_IWGRP`. Group-writable config files with non-root group members are accepted.

### Finding 13: Shell Binary PATH Resolution in Development Mode
**Location**: `executor.py:310-321`
Development mode returns `"bash"` (PATH-resolved). Production returns `/bin/bash` (absolute).

### Finding 14: Module-Level Side Effects at Import Time
**Location**: `llm_client.py:32-41`, `utils.py:36-40`
Importing `llm_client` modifies `os.environ` (strips API key whitespace). Importing `utils` resolves `_envsubst_path`.

### Finding 15: Scanner Fallback Escape Handling Edge Case
**Location**: `resolver.py:267`
Single-character backslash lookbehind doesn't handle double-escapes (`\\)`). Fallback path only.

### Finding 16: Audit Log Contains Full Command Text
**Location**: `audit.py:99-108`
Full command text persisted including sensitive data (passwords in arguments, keys in variable references).

### Finding 17: Rate Limiter Has No Maximum Wait Time
**Location**: `llm_client.py:660-664`
`_TokenBucket.acquire()` blocks indefinitely until a token is available.

### Finding 18: Escape Function Replaces Opening Tags Identically to Closing Tags
**Location**: `utils.py:67-69`
`<COMMAND>` is replaced with `<\/COMMAND>` (same as closing tag escape). Unusual strategy; standard would use HTML entities.

---

## Key Invariants

1. Every non-cd command passes through `validate_command()` before execution
2. Environment allowlist applied on both initial build and post-execution capture
3. Production mode reads security-critical config from file, not env vars
4. Production mode uses absolute path to bash (`/bin/bash`)
5. Production mode validates bash and sandboxer SHA-256 hashes
6. Static blocklist checked on all brace expansion variants
7. Command substitution resolution depth-limited to 2
8. Fail-safe mode blocks on total LLM failure; fail-open warns
9. NO_NEW_PRIVS set via preexec_fn in all production paths except sudo
10. LD_PRELOAD always set to sandboxer path in production env builds
