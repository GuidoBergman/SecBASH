# Semgrep Static Analysis Results

**Date:** 2026-02-22
**Target:** `src/aegish/` (14 Python files, ~5,100 lines)

## Scan Summary

| Ruleset | Rules Applied | Findings |
|---------|--------------|----------|
| `p/python` | 151 | 1 |
| `p/security-audit` | 225 | 0 |
| `p/owasp-top-ten` | 544 | 1 |
| `r/trailofbits.python` | 24 | 0 |
| **Total (unique rules)** | **702** | **1 (deduplicated)** |

- **Files scanned:** 14
- **Unique rules applied:** 702 (678 unique across SARIF rulesets + 24 Trail of Bits)
- **Raw findings:** 2 (1 deduplicated -- same finding detected by both `p/python` and `p/owasp-top-ten`)
- **True positives:** 0
- **False positives:** 1
- **Needs review:** 0

## Findings

### Finding 1: Logger Credential Disclosure (FALSE POSITIVE)

| Field | Value |
|-------|-------|
| **Rule** | `python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure` |
| **Rulesets** | `p/python`, `p/owasp-top-ten` |
| **File** | `src/aegish/llm_client.py` |
| **Line** | 217 |
| **Severity** | WARNING |
| **CWE** | CWE-532: Insertion of Sensitive Information into Log File |
| **OWASP** | A09:2021 - Security Logging and Monitoring Failures |
| **Classification** | **FALSE POSITIVE** |

**Flagged code:**
```python
logger.debug("Skipping model %s: no API key for provider %s", model, provider)
```

**Context (lines 213-217):**
```python
provider = get_provider_from_model(model)
if get_api_key(provider):
    models_to_try.append(model)
else:
    logger.debug("Skipping model %s: no API key for provider %s", model, provider)
```

**Why this is a false positive:**

The semgrep rule triggered on the substring "API key" appearing in the log message string, interpreting it as a potential credential being logged. However, examining the code shows:

1. **No secret is logged.** The log parameters are `model` (a model identifier string like `"openai/gpt-4"`) and `provider` (a provider name string like `"openai"`). Neither parameter contains an actual API key value.
2. **The message is informational.** It logs that a model is being skipped *because* no API key was found for its provider -- the absence of a key, not the key itself.
3. **`get_api_key()` is only called as a boolean check.** The return value of `get_api_key(provider)` is used in the `if` condition but is never passed to the logger. Only the provider name string flows into the log output.
4. **Debug level only.** This log statement uses `logger.debug()`, which is disabled by default in production.

The rule's heuristic matched on the phrase "API key" in the format string, but no actual secret or credential value is present in the logged data.

## Rulesets with Zero Findings

### `p/security-audit` (225 rules, 0 findings)
This ruleset includes rules for dangerous function usage, insecure cryptographic patterns, hardcoded secrets, SQL injection, SSRF, and other security anti-patterns. No findings indicates the codebase avoids these common vulnerability classes.

### `r/trailofbits.python` (24 rules, 0 findings)
Trail of Bits rules focus on Python-specific security issues including unsafe deserialization, command injection patterns, and cryptographic misuse. No findings.

## Notes

- SARIF output files are available at:
  - `docs/security-audit/semgrep-python.sarif`
  - `docs/security-audit/semgrep-security.sarif`
  - `docs/security-audit/semgrep-owasp.sarif`
- The Trail of Bits scan was run without SARIF output (console only).
- All scans were run with `--metrics=off` to prevent telemetry.
- Semgrep scanned only files tracked by git (14 of 14 Python source files).
