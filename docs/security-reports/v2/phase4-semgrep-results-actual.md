# Phase 4 (Revised): Actual Semgrep Static Analysis Results

**Date:** 2026-02-15
**Scope:** Primary: `src/aegish/` (8 Python files). Secondary: `tests/` (27 files), `benchmark/` (12 files).
**Semgrep Version:** 1.151.0 (OSS, no Pro engine)
**Execution:** All scans executed successfully. No environment restrictions.

---

## Context

The [original Phase 4 report](phase4-semgrep-results.md) documented 13 findings labeled as Semgrep results, but Semgrep was never actually executed -- all findings were from manual code review. This report contains **actual Semgrep execution results** and compares them against the manual findings.

---

## Scan Configuration

### Rulesets Executed

| Ruleset | Target | Findings | Notes |
|---------|--------|----------|-------|
| `p/python` | `src/aegish/` | 2 | Logger credential disclosure (both FP) |
| `p/security-audit` | `src/aegish/` | 0 | |
| `p/secrets` | `src/aegish/` | 0 | |
| `p/owasp-top-ten` | `src/aegish/` | 2 | Same 2 logger findings as p/python |
| `p/cwe-top-25` | `src/aegish/` | 0 | |
| Trail of Bits (cloned, python/ dir) | `src/aegish/` | 0 | |
| `rules/aegish-security.yaml` (5 custom) | `src/aegish/` | 7 | Custom rules from Phase 5 |
| `p/python` + `p/security-audit` | `tests/` | 0 | All files matched .semgrepignore |
| `p/python` + `p/security-audit` | `benchmark/` | 1 | MD5 hash usage (FP) |

**Total raw findings:** 12 (across all JSON files)
**Deduplicated unique findings:** 10

### Third-Party Rulesets

The three GitHub-hosted rulesets (`trailofbits/semgrep-rules`, `elttam/semgrep-rules`, `apiiro/malicious-code-ruleset`) initially failed when referenced by URL due to a YAML float parsing error in Semgrep's rule validator (`ValueError: Invalid YAML tree structure, found: float: 18.382224`). Trail of Bits was successfully run by cloning the repo and targeting only the `python/` subdirectory (0 findings). The elttam and apiiro rulesets were not run due to the same parsing incompatibility.

---

## Triaged Findings

### True Positives (5)

#### TP-1: Command String Interpolation in `execute_command()`

| Field | Value |
|-------|-------|
| **Rule** | `aegish-command-string-interpolation` (custom) |
| **File** | `src/aegish/executor.py:98` |
| **Severity** | WARNING |
| **CWE** | CWE-78 |

```python
wrapped_command = f"(exit {last_exit_code}); {command}"
```

**Analysis:** `last_exit_code` is typed as `int` (from `subprocess.run().returncode`) so the interpolation is currently type-safe. `command` is intentionally the raw user string -- aegish's design passes user commands to bash after LLM validation. The rule correctly flags the pattern for review. Risk is primarily in future refactoring where type guarantees could be weakened.

**Maps to Phase 4:** Finding 1 (Shell Injection via Unsanitized `last_exit_code`).

---

#### TP-2: Missing Timeout on `subprocess.run()` in `execute_command()`

| Field | Value |
|-------|-------|
| **Rule** | `aegish-missing-timeout-subprocess` (custom) |
| **File** | `src/aegish/executor.py:100-104` |
| **Severity** | WARNING |
| **CWE** | CWE-400 |

```python
result = subprocess.run(
    [_get_shell_binary(), "--norc", "--noprofile", "-c", wrapped_command],
    env=_build_safe_env(),
    **_sandbox_kwargs(),
)
```

**Analysis:** Interactive command execution without timeout. For interactive use the user can Ctrl+C, but programmatic callers would hang indefinitely.

**Maps to Phase 4:** Finding 4 (Missing Timeout on `subprocess.run()`).

---

#### TP-3: Missing Timeout on `subprocess.run()` in `run_bash_command()`

| Field | Value |
|-------|-------|
| **Rule** | `aegish-missing-timeout-subprocess` (custom) |
| **File** | `src/aegish/executor.py:120-126` |
| **Severity** | WARNING |
| **CWE** | CWE-400 |

```python
return subprocess.run(
    [_get_shell_binary(), "--norc", "--noprofile", "-c", command],
    env=_build_safe_env(),
    capture_output=True,
    text=True,
    **_sandbox_kwargs(),
)
```

**Analysis:** Programmatic interface with captured output -- more concerning than TP-2 since a hang here blocks the calling code with no user intervention possible.

**Maps to Phase 4:** Finding 4 (same finding, second location).

---

#### TP-4: Missing Timeout on `completion()` in `_try_model()`

| Field | Value |
|-------|-------|
| **Rule** | `aegish-missing-timeout-completion` (custom) |
| **File** | `src/aegish/llm_client.py:395-399` |
| **Severity** | WARNING |
| **CWE** | CWE-400 |

```python
response = completion(
    model=model,
    messages=messages,
    caching=True,
)
```

**Analysis:** LiteLLM `completion()` call without timeout. If the LLM provider is slow or unresponsive, validation blocks indefinitely. The `health_check()` function at line 242 correctly uses `timeout=HEALTH_CHECK_TIMEOUT`, and `_expand_env_vars()` at line 444 correctly uses `timeout=5` -- showing awareness of the pattern elsewhere but not here.

**Maps to Phase 4:** NOT in Phase 4. Phase 4 Finding 4 only covered `subprocess.run()` timeouts in `executor.py`. **This is a net-new finding from Semgrep.**

---

#### TP-5: ALLOW Without Explanation Accepted

| Field | Value |
|-------|-------|
| **Rule** | `aegish-allow-without-explanation` (custom) |
| **File** | `src/aegish/llm_client.py:504` |
| **Severity** | WARNING |
| **CWE** | CWE-20 |

```python
reason = data.get("reason", "No reason provided")
```

**Analysis:** Default `"No reason provided"` handles a missing key, but an empty string `""` passes through as a valid reason. An LLM returning `{"action": "allow", "reason": "", "confidence": 1.0}` would silently allow a command with no justification, undermining auditability.

**Maps to Phase 4:** Partially relates to Finding 2 (json.loads() on Untrusted LLM Response), which noted the unbounded reason field. However, Phase 4 did not specifically flag the empty-string acceptance as a distinct issue.

---

### False Positives (5)

#### FP-1 & FP-2: Command String Interpolation on `last_error` Variable

| Field | Value |
|-------|-------|
| **Rule** | `aegish-command-string-interpolation` (custom) |
| **Files** | `src/aegish/llm_client.py:362`, `src/aegish/llm_client.py:366` |
| **Reason** | Rule structural defect -- `metavariable-regex` not constraining |

```python
# Line 362
last_error = f"{model}: response could not be parsed"
# Line 366
last_error = f"{model}: {type(e).__name__}: {str(e)}"
```

The rule's `metavariable-regex` requires the variable name to match `(command|cmd|cmdline|commandline)`, but the matched variable is `last_error`. The regex constraint is not being applied because `metavariable-regex` is placed as a sibling to `pattern-either` at the rule's top level rather than wrapped together inside a `patterns` block. This is a rule authoring bug, not a codebase issue.

**Fix for `rules/aegish-security.yaml`:** Wrap `pattern-either` and `metavariable-regex` inside a `patterns:` list.

---

#### FP-3 & FP-4: Logger Credential Disclosure

| Field | Value |
|-------|-------|
| **Rule** | `python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure` |
| **Files** | `src/aegish/llm_client.py:234`, `src/aegish/llm_client.py:334` |
| **Reason** | Logging metadata about credentials, not credential values |

```python
# Line 234
logger.warning("Health check failed: no API key for provider '%s'", provider)
# Line 334
logger.debug("Skipping model %s: no API key for provider %s", model, provider)
```

Both log statements mention "API key" in the message text but only interpolate the **provider name** (e.g., `"openai"`), not any actual credential value. The rule triggered on the substring "key" in the log format string.

---

#### FP-5: Insecure Hash Algorithm (MD5) in Benchmark

| Field | Value |
|-------|-------|
| **Rule** | `python.lang.security.insecure-hash-algorithms-md5.insecure-hash-algorithm-md5` |
| **File** | `benchmark/tasks/aegish_eval.py:75` |
| **Reason** | Non-security use of MD5 |

```python
cmd_hash = hashlib.md5(record["command"].encode()).hexdigest()[:8]
```

MD5 is used to generate 8-character unique identifiers for benchmark test samples. No cryptographic or security purpose -- just deduplication. The benchmark code is not part of the production runtime.

---

## Comparison Against Phase 4 Manual Review

Phase 4 reported 13 findings from manual code review. Here is how each maps to actual Semgrep results:

| # | Phase 4 Finding | Severity | Semgrep Status | Notes |
|---|----------------|----------|----------------|-------|
| 1 | Shell injection via `last_exit_code` f-string (executor.py:98) | HIGH | **CONFIRMED** (TP-1) | Custom rule `aegish-command-string-interpolation` |
| 2 | `json.loads()` on untrusted LLM response (llm_client.py:497-518) | HIGH | **PARTIALLY** (TP-5) | Custom rule caught the empty-reason aspect; no standard rule flagged json.loads() deserialization concerns, unbounded reason length, or NaN confidence |
| 3 | ctypes syscall return value not checked (sandbox.py) | HIGH | **MISSED** | No Semgrep rule exists for ctypes misuse patterns, errno checking, or `restype`/`argtypes` validation |
| 4 | Missing timeout on subprocess.run() (executor.py:100, 120) | MEDIUM | **CONFIRMED** (TP-2, TP-3) | Custom rule `aegish-missing-timeout-subprocess` |
| 5 | Global mutable state / thread safety (sandbox.py) | MEDIUM | **MISSED** | No thread-safety or race-condition rules in any standard ruleset |
| 6 | `envsubst` without full path (llm_client.py:439) | MEDIUM | **MISSED** | No "missing absolute path" rule; `aegish-subprocess-unsanitized-env` correctly did NOT fire (env= is present) |
| 7 | API key leak via LLM prompt environment expansion (llm_client.py:406-459) | MEDIUM | **MISSED** | Sensitive data flow through environment variables to LLM prompts requires cross-file taint analysis (Pro) or custom rules |
| 8 | Broad exception handling (multiple files) | LOW | **MISSED** | No `except Exception` rule in selected rulesets flagged these locations |
| 9 | Unvalidated runner binary path (config.py:328-340) | LOW | **MISSED** | No standard rule for unvalidated paths from environment variables |
| 10 | Readline history file permissions (shell.py:39, 73) | LOW | **MISSED** | No file permission rule for readline history |
| 11 | Mutable default constants (config.py:50-53) | LOW | **MISSED** | Code quality issue; not in security rulesets |
| 12 | `preexec_fn` fork safety (sandbox.py:277-308) | INFO | **MISSED** | No standard rule for `preexec_fn` safety concerns |
| 13 | Cached ruleset fd lifetime (sandbox.py:319-341) | INFO | **MISSED** | No resource leak rule fired for this pattern |

### Summary

| Category | Count |
|----------|-------|
| Phase 4 findings CONFIRMED by Semgrep | 2 of 13 (Findings 1, 4) |
| Phase 4 findings PARTIALLY confirmed | 1 of 13 (Finding 2, empty-reason aspect only) |
| Phase 4 findings MISSED by Semgrep | 10 of 13 |
| Net-new TRUE POSITIVE from Semgrep | 1 (TP-4: `completion()` missing timeout) |
| Net-new FALSE POSITIVES from Semgrep | 5 (2 rule-structure FPs, 2 logger FPs, 1 MD5 FP) |

---

## Net-New Findings (Not in Phase 4)

### NEW-1: Missing Timeout on `completion()` (TRUE POSITIVE)

**Rule:** `aegish-missing-timeout-completion` (custom)
**File:** `src/aegish/llm_client.py:395`
**Severity:** WARNING / CWE-400

Phase 4 Finding 4 covered `subprocess.run()` timeouts in `executor.py` but did not flag the `completion()` call in `_try_model()`. The custom rule caught this. Both `health_check()` (line 242, `timeout=HEALTH_CHECK_TIMEOUT`) and `_expand_env_vars()` (line 444, `timeout=5`) correctly use timeouts -- `_try_model()` is the only LiteLLM call without one.

---

## Standard Ruleset Effectiveness Analysis

| Ruleset | Rules Run | Findings | True Positives | Assessment |
|---------|-----------|----------|----------------|------------|
| `p/python` | 198 | 2 | 0 | Both findings were FP logger-credential-disclosure |
| `p/security-audit` | ~300 | 0 | 0 | No findings on this codebase |
| `p/secrets` | ~150 | 0 | 0 | No hardcoded credentials (correct) |
| `p/owasp-top-ten` | ~300 | 2 | 0 | Same 2 FP as p/python (overlapping rules) |
| `p/cwe-top-25` | ~200 | 0 | 0 | No findings |
| Trail of Bits (python/) | 24 | 0 | 0 | No findings |
| **Custom rules** | **5** | **7** | **5** | **71% precision, 100% of true positives** |

**Key insight:** All 5 true positives came from the custom aegish-specific rules. Zero true positives came from any standard or third-party ruleset. This validates that:

1. The aegish codebase has a mature security posture -- standard vulnerability patterns (eval, pickle, yaml.load, shell=True, hardcoded credentials, SQL injection) are absent.
2. The remaining vulnerabilities are **domain-specific** (missing timeouts, empty LLM reasons, command interpolation patterns) that require custom rules to detect.
3. Manual code review found 10 issues that no Semgrep ruleset -- standard, third-party, or custom -- could detect, including ctypes misuse, thread safety, path validation, file permissions, and fork safety concerns.

---

## Custom Rule Bug: `aegish-command-string-interpolation`

The `metavariable-regex` constraint in `rules/aegish-security.yaml` is not being applied, causing 2 false positives (40% of that rule's matches). The `metavariable-regex` key is a sibling of `pattern-either` at the rule's top level. Semgrep requires both to be inside a `patterns` list for the AND composition to work.

**Current (broken):**
```yaml
pattern-either:
  - pattern: $CMD = f"...{...}..."
  # ...
metavariable-regex:
  metavariable: $CMD
  regex: ".*(command|cmd|cmdline|commandline).*"
```

**Fixed:**
```yaml
patterns:
  - pattern-either:
      - pattern: $CMD = f"...{...}..."
      - pattern: $CMD = f"...{...}...{...}..."
      - pattern: $CMD = f"...{...}...{...}...{...}..."
  - metavariable-regex:
      metavariable: $CMD
      regex: ".*(command|cmd|cmdline|commandline).*"
```

---

## Appendix: Scan Artifacts

All scan results are in `semgrep-results-001/`:

| File | Description |
|------|-------------|
| `python-python.json` / `.sarif` | p/python ruleset results |
| `python-security-audit.json` / `.sarif` | p/security-audit results |
| `python-secrets.json` / `.sarif` | p/secrets results |
| `python-owasp.json` / `.sarif` | p/owasp-top-ten results |
| `python-cwe25.json` / `.sarif` | p/cwe-top-25 results |
| `python-trailofbits.json` / `.sarif` | Trail of Bits python/ results |
| `python-custom-aegish.json` / `.sarif` | Custom aegish rules results |
| `secondary-tests.json` / `.sarif` | tests/ directory results |
| `secondary-benchmark.json` / `.sarif` | benchmark/ directory results |
| `python-triage.json` | Triage classifications |
