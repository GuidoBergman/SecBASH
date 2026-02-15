# Phase 3: Insecure Defaults Security Audit

**Project:** aegish (LLM-powered interactive shell with security validation)
**Audit Date:** 2026-02-15
**Scope:** Entire aegish repository
**Methodology:** Trail of Bits Insecure Defaults framework
**Scaffolding:** `/insecure-defaults` skill (Claude Code security audit skill)

---

## Executive Summary

14 findings across 5 severity levels. The project demonstrates strong security defaults (fail-safe mode, provider allowlisting, Landlock sandboxing), but has gaps in environment variable filtering, subprocess sanitization, and Docker infrastructure.

| Severity | Count |
|----------|-------|
| CRITICAL | 1     |
| HIGH     | 4     |
| MEDIUM   | 5     |
| LOW      | 3     |
| INFO     | 1     |

---

## CRITICAL-01: Live API Keys in `.env` File on Disk

**File:** `.env`
**Severity:** CRITICAL

The `.env` file contains five live API keys in plaintext (OpenAI, Anthropic, OpenRouter, Google, HuggingFace). While `.env` is in `.gitignore` and `.dockerignore` (never committed to git), the file exists on disk with default permissions (world-readable via umask).

**Recommendation:** Rotate all five API keys. Use a secrets manager. Set `chmod 600 .env`.

---

## HIGH-01: Incomplete Sensitive Variable Filter (_SENSITIVE_VAR_PATTERNS)

**File:** `src/aegish/llm_client.py:406-409`
**Severity:** HIGH

Variables like `DATABASE_URL`, `REDIS_URL`, `MONGODB_URI`, `DSN`, `CONNECTION_STRING`, `KUBECONFIG`, `DOCKER_AUTH_CONFIG` pass through unfiltered and could leak via envsubst into LLM prompts. Also: `PGPASSWORD` does NOT match `_PASSWORD` (no underscore prefix).

**Recommendation:** Add `_URL`, `_URI`, `_DSN`, `PASSWORD` (without underscore), `_PASS` patterns. Consider allowlist approach.

---

## HIGH-02: Missing Library Injection Variables in DANGEROUS_ENV_VARS

**File:** `src/aegish/executor.py:16-25`
**Severity:** HIGH

Missing: `LD_PRELOAD`, `LD_LIBRARY_PATH`, `PYTHONPATH`, `PYTHONSTARTUP`, `PERL5LIB`, `NODE_PATH`, `RUBYLIB`, `CLASSPATH`, `LD_AUDIT`.

**Recommendation:** Add at minimum `LD_PRELOAD`, `LD_LIBRARY_PATH`, `PYTHONPATH`, `PYTHONSTARTUP`. Consider stripping all `LD_*`.

---

## HIGH-03: Hardcoded Credentials in Docker Test Infrastructure

**File:** `tests/Dockerfile.production:36`
**Severity:** HIGH

- Hardcoded `testuser:testpass` password
- SSH with `PasswordAuthentication yes`
- Port 2222 on all interfaces (not localhost-only)
- No `PermitRootLogin no` / `AllowUsers` restriction
- `netcat-openbsd` installed (post-exploitation tool)

**Recommendation:** Bind `127.0.0.1:2222:22`, disable root login, consider key-based auth.

---

## HIGH-04: No Timeout on Production LLM Queries

**File:** `src/aegish/llm_client.py:393-399`
**Severity:** HIGH

`_try_model()` calls `completion()` without timeout. Health check uses `timeout=5` but production path has none.

**Recommendation:** Add `timeout=30` (or `AEGISH_QUERY_TIMEOUT` env var).

---

## MEDIUM-01: Default Mode is Development (No Sandboxing)

**File:** `src/aegish/config.py:56`
**Severity:** MEDIUM

`DEFAULT_MODE = "development"` -- Landlock disabled, no sandbox, exit returns to parent shell.

**Recommendation:** Print explicit warning about inactive sandbox in development mode.

---

## MEDIUM-02: History File World-Readable

**File:** `src/aegish/shell.py:39,73`
**Severity:** MEDIUM

`~/.aegish_history` created with default umask (typically 0022 = world-readable). May contain inline credentials.

**Recommendation:** Set `os.chmod(HISTORY_FILE, 0o600)` after creation.

---

## MEDIUM-03: envsubst Expansion Could Leak Secrets

**File:** `src/aegish/llm_client.py:425-459`
**Severity:** MEDIUM

Non-filtered variables are expanded and sent to third-party LLM APIs.

**Recommendation:** Switch to allowlist of known-safe variables for expansion.

---

## MEDIUM-04: No Rate Limiting on LLM Queries

**File:** `src/aegish/llm_client.py`
**Severity:** MEDIUM

No client-side rate limiting. Denial-of-wallet attack possible.

**Recommendation:** Implement token bucket with configurable `AEGISH_MAX_QUERIES_PER_MINUTE`.

---

## MEDIUM-05: LiteLLM Caching Without Explicit Configuration

**File:** `src/aegish/llm_client.py:398`
**Severity:** MEDIUM

`caching=True` uses in-memory cache with no TTL/size bounds.

**Recommendation:** Configure explicit TTL and maximum cache size.

---

## LOW-01: .env.example References OpenRouter Without Allowlisting

**File:** `.env.example:24`
**Severity:** LOW

`OPENROUTER_API_KEY` referenced but `openrouter` not in `DEFAULT_ALLOWED_PROVIDERS`.

---

## LOW-02: Docker Compose SSH on All Interfaces

**File:** `tests/docker-compose.production.yml:33`
**Severity:** LOW

`"2222:22"` binds on `0.0.0.0`. Should be `"127.0.0.1:2222:22"`.

---

## LOW-03: No Type Assertion on last_exit_code

**File:** `src/aegish/executor.py:98`
**Severity:** LOW

`f"(exit {last_exit_code})"` -- safe due to type system but fragile.

**Recommendation:** Add `assert isinstance(last_exit_code, int)`.

---

## INFO-01: Secure Defaults Working Correctly

| Default | Assessment |
|---------|-----------|
| `DEFAULT_FAIL_MODE = "safe"` | Correct: blocks on failure |
| Provider allowlist | Correct: rejects unknown providers |
| `--norc --noprofile` flags | Correct: prevents rc injection |
| `BASH_FUNC_` filtering | Correct: blocks Shellshock |
| Landlock in production | Correct: comprehensive |
| Command length limit (4096) | Correct: prevents token abuse |
| COMMAND tag wrapping | Correct: prompt injection defense |
| Empty command blocking | Correct |
| `.env` in `.gitignore`/`.dockerignore` | Correct |
