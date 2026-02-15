# Phase 5: Custom Semgrep Rules for aegish

**Date:** 2026-02-15
**Scaffolding:** `/semgrep-rule` skill (Claude Code custom rule creation skill)

## Overview

These four custom Semgrep rules detect aegish-specific security anti-patterns that generic
rulesets miss. Each rule targets a real pattern observed in the codebase during manual audit
(Phases 2-3), turning one-off findings into repeatable, CI-enforceable checks.

| Rule | Severity | What it catches |
|------|----------|-----------------|
| `aegish-allow-without-explanation` | WARNING | LLM response accepted with empty/whitespace `reason` |
| `aegish-subprocess-unsanitized-env` | ERROR | `subprocess.run()` inheriting full parent environment |
| `aegish-command-string-interpolation` | WARNING | f-string interpolation into shell command variables |
| `aegish-missing-timeout` | WARNING | `subprocess.run()` or `completion()` without `timeout=` |

---

## Running the Rules

Save the YAML blocks below into a single file (e.g., `rules/aegish-security.yaml`) and run:

```bash
semgrep scan --config rules/aegish-security.yaml src/aegish/
```

To run in CI with errors blocking the build:

```bash
semgrep scan --config rules/aegish-security.yaml --error src/aegish/
```

---

## Rule 1: ALLOW Without Explanation Detection

### Vulnerability

In `llm_client.py:504`, `_parse_response()` uses:

```python
reason = data.get("reason", "No reason provided")
```

The default `"No reason provided"` handles a *missing* key, but an *empty string* `""` passes
through unchecked. A compromised or confused LLM returning `{"action":"allow","reason":"","confidence":1.0}`
silently allows a command with no justification. Empty reasons undermine auditability and could
mask prompt-injection attacks where the model is coerced into allowing dangerous commands.

### Semgrep Rule

```yaml
rules:
  - id: aegish-allow-without-explanation
    languages: [python]
    severity: WARNING
    message: >-
      `data.get("reason", ...)` accepts empty strings as valid reasons.
      An LLM returning action=allow with reason="" silently permits commands
      without justification. Validate that reason is non-empty after retrieval:
      `reason = data.get("reason", "").strip() or "No reason provided"` and
      reject allow actions with empty reasons.
    metadata:
      cwe: "CWE-20: Improper Input Validation"
      confidence: HIGH
      category: security
      technology: [python]
      references:
        - "https://cwe.mitre.org/data/definitions/20.html"
        - "https://owasp.org/www-project-top-ten/2017/A1_2017-Injection"
    patterns:
      - pattern: |
          $REASON = $DATA.get("reason", ...)
      - pattern-not-inside: |
          $REASON = $DATA.get("reason", ...)
          ...
          if not $REASON or not $REASON.strip():
              ...
      - pattern-not-inside: |
          $REASON = $DATA.get("reason", ...).strip()
          ...
```

### Test Cases

**Positive match (vulnerable):** Should trigger the rule.

```python
# test-positive-rule1.py
def parse_llm_response(content):
    import json
    data = json.loads(content)
    action = data.get("action", "").lower()
    # BUG: empty string "" passes through as valid reason
    reason = data.get("reason", "No reason provided")
    confidence = float(data.get("confidence", 0.5))
    return {"action": action, "reason": reason, "confidence": confidence}
```

**Negative match (safe):** Should NOT trigger the rule.

```python
# test-negative-rule1.py
def parse_llm_response_safe(content):
    import json
    data = json.loads(content)
    action = data.get("action", "").lower()
    reason = data.get("reason", "").strip()
    if not reason or not reason.strip():
        reason = "No reason provided"
    if action == "allow" and reason == "No reason provided":
        return None  # Reject allow without real explanation
    confidence = float(data.get("confidence", 0.5))
    return {"action": action, "reason": reason, "confidence": confidence}
```

---

## Rule 2: Unsanitized Environment in Subprocess

### Vulnerability

`executor.py` correctly calls `subprocess.run(..., env=_build_safe_env())` and
`llm_client.py` uses `env=_get_safe_env()`. Both functions strip dangerous environment
variables (`BASH_ENV`, `PROMPT_COMMAND`, API keys, etc.). However, if a developer adds a new
`subprocess.run()` call without an explicit `env=` parameter, the child process inherits the
full parent environment -- including `BASH_ENV` (arbitrary code execution on bash startup),
`PROMPT_COMMAND` (command injection), and all API keys/secrets.

This is the highest-severity rule because a single missing `env=` parameter creates a
direct code execution vector.

### Semgrep Rule

```yaml
rules:
  - id: aegish-subprocess-unsanitized-env
    languages: [python]
    severity: ERROR
    message: >-
      `subprocess.run()` called without explicit `env=` parameter. The child
      process inherits the full parent environment including BASH_ENV (code
      execution on bash startup), PROMPT_COMMAND (command injection), and API
      keys/secrets. Always pass `env=_build_safe_env()` (executor) or
      `env=_get_safe_env()` (llm_client) to sanitize the environment.
    metadata:
      cwe: "CWE-78: Improper Neutralization of Special Elements used in an OS Command"
      confidence: HIGH
      category: security
      technology: [python]
      references:
        - "https://cwe.mitre.org/data/definitions/78.html"
        - "https://docs.python.org/3/library/subprocess.html#security-considerations"
    patterns:
      - pattern: subprocess.run(...)
      - pattern-not: subprocess.run(..., env=..., ...)
```

### Test Cases

**Positive match (vulnerable):** Should trigger the rule.

```python
# test-positive-rule2.py
import subprocess

def run_command_unsafe(cmd):
    # BUG: no env= parameter, inherits BASH_ENV, PROMPT_COMMAND, API keys
    result = subprocess.run(
        ["bash", "-c", cmd],
        capture_output=True,
        text=True,
    )
    return result

def run_piped_unsafe(cmd):
    # BUG: also missing env=
    return subprocess.run(["bash", "-c", cmd])
```

**Negative match (safe):** Should NOT trigger the rule.

```python
# test-negative-rule2.py
import subprocess
import os

DANGEROUS_ENV_VARS = {"BASH_ENV", "ENV", "PROMPT_COMMAND"}

def _build_safe_env():
    return {k: v for k, v in os.environ.items() if k not in DANGEROUS_ENV_VARS}

def run_command_safe(cmd):
    # SAFE: explicit env= strips dangerous variables
    result = subprocess.run(
        ["bash", "-c", cmd],
        capture_output=True,
        text=True,
        env=_build_safe_env(),
    )
    return result

def run_with_empty_env(cmd):
    # SAFE: explicit env={} gives minimal environment
    return subprocess.run(["bash", "-c", cmd], env={})
```

---

## Rule 3: Command String Interpolation

### Vulnerability

In `executor.py:98`:

```python
wrapped_command = f"(exit {last_exit_code}); {command}"
```

`last_exit_code` is typed as `int` (safe), and `command` is a raw user string that is
*intentionally* interpolated. However, this pattern is dangerous as a template for future
development. If a developer copies this pattern and interpolates an unsanitized string into a
variable named `*command*` or `*cmd*`, the result is a shell injection vulnerability. The
rule catches any f-string assigned to a command/cmd variable so it can be reviewed for safety.

### Semgrep Rule

```yaml
rules:
  - id: aegish-command-string-interpolation
    languages: [python]
    severity: WARNING
    message: >-
      f-string interpolation used to build a shell command string. If any
      interpolated variable contains user-controlled or unsanitized data,
      this is a shell injection vulnerability. Prefer passing command
      arguments as a list to subprocess.run() instead of string interpolation.
      If interpolation is necessary, ensure all variables are type-safe
      (e.g., strictly int) and document why.
    metadata:
      cwe: "CWE-78: Improper Neutralization of Special Elements used in an OS Command"
      confidence: MEDIUM
      category: security
      technology: [python]
      references:
        - "https://cwe.mitre.org/data/definitions/78.html"
        - "https://semgrep.dev/docs/cheat-sheets/python-command-injection/"
    pattern-either:
      - pattern: |
          $CMD = f"...{...}..."
      - pattern: |
          $CMD = f"...{...}...{...}..."
      - pattern: |
          $CMD = f"...{...}...{...}...{...}..."
    metavariable-regex:
      metavariable: $CMD
      regex: ".*(command|cmd|cmdline|commandline).*"
```

### Test Cases

**Positive match (vulnerable):** Should trigger the rule.

```python
# test-positive-rule3.py
def execute_with_interpolation(user_input, exit_code):
    # FLAGGED: f-string building a command string
    wrapped_command = f"(exit {exit_code}); {user_input}"

    # FLAGGED: building a cmd variable with interpolation
    shell_cmd = f"echo {user_input} | grep pattern"

    # FLAGGED: even with seemingly safe variables
    full_command = f"/usr/bin/timeout 30 {user_input}"

    return wrapped_command, shell_cmd, full_command
```

**Negative match (safe):** Should NOT trigger the rule.

```python
# test-negative-rule3.py
import subprocess

def execute_safe(args):
    # SAFE: no f-string interpolation, using list form
    result = subprocess.run(
        ["bash", "--norc", "--noprofile", "-c", args],
        capture_output=True,
    )
    return result

def build_message(user_input):
    # SAFE: variable name is "message", not "command" or "cmd"
    log_message = f"User ran: {user_input}"
    return log_message

def build_with_join(parts):
    # SAFE: not an f-string
    command = " ".join(parts)
    return command
```

---

## Rule 4: Missing Timeout on Subprocess/LLM Calls

### Vulnerability

In `executor.py:100-104` and `executor.py:120-125`, `subprocess.run()` is called without
`timeout=`. A malicious or buggy command (e.g., `yes`, `cat /dev/urandom`, infinite loop)
will hang the aegish shell indefinitely, creating a denial-of-service condition.

In `llm_client.py:395-399`, `completion()` is called without `timeout=`. If the LLM provider
is slow or unresponsive, the validation call blocks forever, making aegish unusable. Note that
`llm_client.py:239-242` (`health_check`) correctly uses `timeout=HEALTH_CHECK_TIMEOUT` and
`llm_client.py:439-446` (`_expand_env_vars`) correctly uses `timeout=5`.

### Semgrep Rule

```yaml
rules:
  - id: aegish-missing-timeout-subprocess
    languages: [python]
    severity: WARNING
    message: >-
      `subprocess.run()` called without `timeout=` parameter. A command that
      hangs (infinite loop, slow pipe, /dev/urandom) blocks the aegish shell
      indefinitely. Always pass an explicit timeout. For interactive commands
      (execute_command), use the configured user timeout. For internal utility
      calls (run_bash_command), use a short timeout (e.g., 30 seconds).
    metadata:
      cwe: "CWE-400: Uncontrolled Resource Consumption"
      confidence: HIGH
      category: security
      technology: [python]
      references:
        - "https://cwe.mitre.org/data/definitions/400.html"
        - "https://docs.python.org/3/library/subprocess.html#subprocess.run"
    patterns:
      - pattern: subprocess.run(...)
      - pattern-not: subprocess.run(..., timeout=..., ...)

  - id: aegish-missing-timeout-completion
    languages: [python]
    severity: WARNING
    message: >-
      `completion()` (LiteLLM) called without `timeout=` parameter. If the
      LLM provider is slow or unresponsive, this blocks the validation call
      indefinitely, making aegish unusable. Always pass an explicit timeout
      (e.g., `timeout=30`). The health_check function correctly uses
      `timeout=HEALTH_CHECK_TIMEOUT` as a reference.
    metadata:
      cwe: "CWE-400: Uncontrolled Resource Consumption"
      confidence: HIGH
      category: security
      technology: [python]
      references:
        - "https://cwe.mitre.org/data/definitions/400.html"
        - "https://litellm.vercel.app/docs/completion/input#timeout"
    patterns:
      - pattern: completion(...)
      - pattern-not: completion(..., timeout=..., ...)
```

### Test Cases

**Positive match (vulnerable):** Should trigger the rule.

```python
# test-positive-rule4.py
import subprocess
from litellm import completion

def execute_no_timeout(shell, command):
    # FLAGGED: no timeout, command could hang forever
    result = subprocess.run(
        [shell, "-c", command],
        env={},
    )
    return result.returncode

def run_bash_no_timeout(shell, command):
    # FLAGGED: no timeout on captured output either
    return subprocess.run(
        [shell, "-c", command],
        capture_output=True,
        text=True,
        env={},
    )

def validate_no_timeout(model, messages):
    # FLAGGED: completion() without timeout, LLM could hang
    response = completion(
        model=model,
        messages=messages,
        caching=True,
    )
    return response
```

**Negative match (safe):** Should NOT trigger the rule.

```python
# test-negative-rule4.py
import subprocess
from litellm import completion

HEALTH_CHECK_TIMEOUT = 5

def execute_with_timeout(shell, command):
    # SAFE: explicit timeout prevents hangs
    result = subprocess.run(
        [shell, "-c", command],
        env={},
        timeout=30,
    )
    return result.returncode

def expand_env_vars_safe(command):
    # SAFE: timeout=5 matches existing pattern in _expand_env_vars
    result = subprocess.run(
        ["envsubst"],
        input=command,
        capture_output=True,
        text=True,
        timeout=5,
        env={},
    )
    return result.stdout

def health_check_safe(model, messages):
    # SAFE: timeout matches existing health_check pattern
    response = completion(
        model=model,
        messages=messages,
        timeout=HEALTH_CHECK_TIMEOUT,
    )
    return response
```

---

## Current Findings in aegish Codebase

Running these rules against `src/aegish/` would flag the following real issues:

| Rule | File | Line(s) | Finding |
|------|------|---------|---------|
| `aegish-allow-without-explanation` | `llm_client.py` | 504 | `data.get("reason", "No reason provided")` accepts empty strings |
| `aegish-missing-timeout-subprocess` | `executor.py` | 100-104 | `subprocess.run()` in `execute_command()` has no timeout |
| `aegish-missing-timeout-subprocess` | `executor.py` | 120-125 | `subprocess.run()` in `run_bash_command()` has no timeout |
| `aegish-missing-timeout-completion` | `llm_client.py` | 395-399 | `completion()` in `_try_model()` has no timeout |
| `aegish-command-string-interpolation` | `executor.py` | 98 | `wrapped_command = f"(exit {last_exit_code}); {command}"` |

These would NOT fire (correctly):

| Rule | File | Line(s) | Why it passes |
|------|------|---------|---------------|
| `aegish-subprocess-unsanitized-env` | `executor.py` | 100-104 | Has `env=_build_safe_env()` |
| `aegish-subprocess-unsanitized-env` | `executor.py` | 120-125 | Has `env=_build_safe_env()` |
| `aegish-subprocess-unsanitized-env` | `llm_client.py` | 439-446 | Has `env=_get_safe_env()` |
| `aegish-missing-timeout-subprocess` | `llm_client.py` | 439-446 | Has `timeout=5` |
| `aegish-missing-timeout-completion` | `llm_client.py` | 239-242 | Has `timeout=HEALTH_CHECK_TIMEOUT` |

---

## Recommended Fixes

### Fix 1: Validate reason is non-empty (`llm_client.py:504`)

```python
# Before (vulnerable)
reason = data.get("reason", "No reason provided")

# After (safe)
reason = (data.get("reason") or "").strip()
if not reason:
    if action == "allow":
        logger.warning("LLM returned allow with empty reason, rejecting")
        return None
    reason = "No reason provided"
```

### Fix 2: Add timeout to `execute_command()` (`executor.py:100`)

```python
# Before (vulnerable)
result = subprocess.run(
    [_get_shell_binary(), "--norc", "--noprofile", "-c", wrapped_command],
    env=_build_safe_env(),
    **_sandbox_kwargs(),
)

# After (safe) -- use a configurable timeout
COMMAND_TIMEOUT = int(os.environ.get("AEGISH_COMMAND_TIMEOUT", "300"))

result = subprocess.run(
    [_get_shell_binary(), "--norc", "--noprofile", "-c", wrapped_command],
    env=_build_safe_env(),
    timeout=COMMAND_TIMEOUT,
    **_sandbox_kwargs(),
)
```

### Fix 3: Add timeout to `_try_model()` (`llm_client.py:395`)

```python
# Before (vulnerable)
response = completion(
    model=model,
    messages=messages,
    caching=True,
)

# After (safe)
VALIDATION_TIMEOUT = 30  # seconds

response = completion(
    model=model,
    messages=messages,
    caching=True,
    timeout=VALIDATION_TIMEOUT,
)
```

### Fix 4: Add timeout to `run_bash_command()` (`executor.py:120`)

```python
# Before (vulnerable)
return subprocess.run(
    [_get_shell_binary(), "--norc", "--noprofile", "-c", command],
    env=_build_safe_env(),
    capture_output=True,
    text=True,
    **_sandbox_kwargs(),
)

# After (safe)
INTERNAL_TIMEOUT = 30  # seconds

return subprocess.run(
    [_get_shell_binary(), "--norc", "--noprofile", "-c", command],
    env=_build_safe_env(),
    capture_output=True,
    text=True,
    timeout=INTERNAL_TIMEOUT,
    **_sandbox_kwargs(),
)
```

---

## Combined Rules File

For convenience, here is the complete `aegish-security.yaml` file containing all four rules:

```yaml
rules:
  # Rule 1: ALLOW without explanation
  - id: aegish-allow-without-explanation
    languages: [python]
    severity: WARNING
    message: >-
      `data.get("reason", ...)` accepts empty strings as valid reasons.
      An LLM returning action=allow with reason="" silently permits commands
      without justification. Validate that reason is non-empty after retrieval.
    metadata:
      cwe: "CWE-20: Improper Input Validation"
      confidence: HIGH
      category: security
      technology: [python]
      references:
        - "https://cwe.mitre.org/data/definitions/20.html"
    patterns:
      - pattern: |
          $REASON = $DATA.get("reason", ...)
      - pattern-not-inside: |
          $REASON = $DATA.get("reason", ...)
          ...
          if not $REASON or not $REASON.strip():
              ...
      - pattern-not-inside: |
          $REASON = $DATA.get("reason", ...).strip()
          ...

  # Rule 2: Unsanitized environment in subprocess
  - id: aegish-subprocess-unsanitized-env
    languages: [python]
    severity: ERROR
    message: >-
      `subprocess.run()` called without explicit `env=` parameter. The child
      process inherits BASH_ENV, PROMPT_COMMAND, and API keys. Always pass
      `env=_build_safe_env()` or `env=_get_safe_env()`.
    metadata:
      cwe: "CWE-78: Improper Neutralization of Special Elements used in an OS Command"
      confidence: HIGH
      category: security
      technology: [python]
      references:
        - "https://cwe.mitre.org/data/definitions/78.html"
    patterns:
      - pattern: subprocess.run(...)
      - pattern-not: subprocess.run(..., env=..., ...)

  # Rule 3: Command string interpolation
  - id: aegish-command-string-interpolation
    languages: [python]
    severity: WARNING
    message: >-
      f-string interpolation used to build a shell command string. If any
      interpolated variable is user-controlled, this is shell injection.
      Prefer list-form arguments or ensure all interpolated values are type-safe.
    metadata:
      cwe: "CWE-78: Improper Neutralization of Special Elements used in an OS Command"
      confidence: MEDIUM
      category: security
      technology: [python]
      references:
        - "https://cwe.mitre.org/data/definitions/78.html"
    pattern-either:
      - pattern: |
          $CMD = f"...{...}..."
      - pattern: |
          $CMD = f"...{...}...{...}..."
      - pattern: |
          $CMD = f"...{...}...{...}...{...}..."
    metavariable-regex:
      metavariable: $CMD
      regex: ".*(command|cmd|cmdline|commandline).*"

  # Rule 4a: Missing timeout on subprocess
  - id: aegish-missing-timeout-subprocess
    languages: [python]
    severity: WARNING
    message: >-
      `subprocess.run()` called without `timeout=`. A hanging command blocks
      the aegish shell indefinitely. Always pass an explicit timeout.
    metadata:
      cwe: "CWE-400: Uncontrolled Resource Consumption"
      confidence: HIGH
      category: security
      technology: [python]
      references:
        - "https://cwe.mitre.org/data/definitions/400.html"
    patterns:
      - pattern: subprocess.run(...)
      - pattern-not: subprocess.run(..., timeout=..., ...)

  # Rule 4b: Missing timeout on LLM completion
  - id: aegish-missing-timeout-completion
    languages: [python]
    severity: WARNING
    message: >-
      `completion()` called without `timeout=`. An unresponsive LLM provider
      blocks validation indefinitely. Always pass an explicit timeout.
    metadata:
      cwe: "CWE-400: Uncontrolled Resource Consumption"
      confidence: HIGH
      category: security
      technology: [python]
      references:
        - "https://cwe.mitre.org/data/definitions/400.html"
    patterns:
      - pattern: completion(...)
      - pattern-not: completion(..., timeout=..., ...)
```
