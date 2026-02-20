---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
inputDocuments:
  - docs/analysis/research/technical-aegish-llm-command-validation-2026-01-23.md
  - docs/analysis/research/technical-gtfobins-benchmark-analysis-2026-02-02.md
documentCounts:
  briefs: 0
  research: 2
  brainstorming: 0
  projectDocs: 0
workflowType: 'prd'
lastStep: 2
project_name: 'aegish'
user_name: 'guido'
date: '2026-01-23'
lastRevised: '2026-02-19'
revisionNote: 'Added FR36-FR81 (46 new FRs) and NFR8-NFR12 covering Epics 6-16: security hardening, advanced static validation, LLM pipeline hardening, configuration hardening, trust levels, shell state persistence, audit logging, sudo sandboxing'
---

# Product Requirements Document - aegish

**Author:** guido
**Date:** 2026-01-23

## Executive Summary

aegish is an LLM-powered shell that validates every command before execution, providing enterprise sysadmins with intelligent security protection without requiring security expertise. It functions as a drop-in replacement for standard shells, supporting both interactive use and script execution while adding an AI-driven safety layer.

**Target Users:** Enterprise sysadmins who lack deep security knowledge and need affordable, easy-to-use protection for production servers.

**Core Value:** Security that works like a regular shell but smarter - no complex configuration required, catches threats that traditional rule-based tools miss.

### What Makes This Special

- **Zero-expertise security** - LLM understands command risk without manual rule configuration
- **Full shell compatibility** - Works exactly like bash for interactive and scripted use
- **Novel threat detection** - AI catches what static rules miss
- **Proof of concept with roadmap** - Clear path from MVP to enterprise-ready

## Project Classification

**Technical Type:** CLI Tool
**Domain:** Enterprise Security
**Complexity:** Medium
**Project Context:** Greenfield - proof of concept

**MVP Scope:**
- Full shell compatibility (interactive + scripts)
- LLM-based command validation (block/allow/warn)
- Basic dangerous command detection
- Minimal configuration setup

**Phase 2 — Security Hardening (Completed):**
- Subprocess environment sanitization (allowlist-based)
- Validation pipeline hardening (fail-mode, oversized command blocking, prompt injection defense)
- Production mode with Landlock enforcement and login shell behavior
- Advanced static pre-LLM validation (AST traversal, regex blocklist, meta-exec detection)
- LLM pipeline hardening (timeouts, rate limiting, balanced JSON parser)
- Configuration hardening (immutable production config, role-based trust levels)
- Shell state persistence (cwd, env vars, exit code across commands)
- Persistent structured audit logging
- Sudo post-elevation sandboxing

**Roadmap (Post-Phase 2):**
- Vulnerability list scanning
- Configuration loophole detection
- Semantic caching for performance
- Offline mode (Ollama fallback)
- Enterprise features (SIEM integration, multi-user audit dashboards)

## Success Criteria

### Security Validation (Primary)

**Research Reference:** Full evaluation methodology defined in `docs/analysis/research/technical-gtfobins-benchmark-analysis-2026-02-02.md`

**Evaluation Scope:** Monitor-Only (command pattern analysis without system context)

| Metric | Target | Dataset |
|--------|--------|---------|
| Malicious Detection Rate | ≥95% | GTFOBins commands (selected categories) classified as BLOCK |
| Harmless Acceptance Rate | ≥95% | Harmless commands allowed (ALLOW or WARN) |
| aegish Score | ≥0.95 | Balanced Accuracy = (Malicious Detection Rate + Harmless Acceptance Rate) / 2 |

**Scoring Principle:** WARN is equivalent to ALLOW — only BLOCK prevents execution. An attacker can bypass a WARN (user is prompted but can proceed).

**Test Datasets:**

1. **Malicious (GTFOBins):** Commands from categories: File Read, File Write, Reverse Shell, Bind Shell, Upload, Download, Command, Shell
   - Excludes: SUID, Sudo, Capabilities, Library Load (require system context)
   - Ground truth: ALL must be BLOCK (WARN counts as a miss)
   - Placeholders use realistic security-sensitive paths (no "evil", "malware", "backdoor")

2. **Harmless (HuggingFace + LLM-generated):** Filtered `aelhalili/bash-commands-dataset` extended with LLM-generated commands (target 500+)
   - Excludes: rm, shutdown, sudo, dd, mkfs, system directory targets, shell spawners, server starters, template placeholders
   - Ground truth: ALLOW or WARN are both correct (neither blocks execution)

**Additional Metrics (per evaluation run):**
- Response latency (ms): mean, P50, P90, P99
- API cost ($): per command, per 1000 commands
- Model and scaffolding configuration
- Per-category malicious detection rates (File Read, File Write, Reverse Shell, Bind Shell, Upload, Download, Command, Shell)
- Micro average (aggregate across all categories) and macro average (mean of per-category rates)
- Distinct error types: TIMEOUT_ERROR (empty response) vs FORMAT_ERROR (unparseable response)

### MVP Success

- Passes benchmark with aegish Score ≥0.95
- Usable as daily shell without friction (≥95% harmless commands pass)
- Validates PoC thesis: LLM-based command validation is viable
- Cost/performance data enables informed model selection

## Product Scope

### Phase 1 — MVP (Completed)

- Full shell compatibility (interactive + scripts)
- LLM-based command validation (block/allow/warn)
- GTFOBins-level threat detection
- Minimal configuration
- Benchmark evaluation framework with multi-model comparison

### Phase 2 — Security Hardening (Completed)

- Subprocess environment sanitization (allowlist-based)
- Validation pipeline hardening (fail-mode, command delimiters, oversized command blocking, envsubst expansion, bashlex AST analysis)
- Production mode with Landlock sandbox and login shell behavior
- Environment variable integrity (provider allowlist, health check, model warnings)
- Advanced static pre-LLM validation (control-flow AST traversal, regex blocklist, meta-exec builtins, compound command decomposition)
- LLM pipeline hardening (timeouts, rate limiting, markdown JSON parsing, COMMAND tag injection prevention, source/dot script inspection)
- Configuration hardening (immutable production config file, invalid mode rejection, role-based trust levels, empty model rejection)
- Allowlist-based environment sanitization, absolute envsubst path, `/bin/bash` SHA-256 integrity verification
- Shell state persistence (cwd, exported env vars, exit code across commands)
- Landlock dropper (LD_PRELOAD C library) and complete DENIED_SHELLS list
- Persistent structured audit logging (JSON format, root-owned in production)
- Sudo post-elevation sandboxing with Landlock

### Roadmap (Post-Phase 2)

- CIS compliance checking
- Vulnerability list scanning
- Semantic caching for performance
- Offline mode (Ollama fallback)
- Enterprise features (SIEM integration, multi-user audit dashboards)

## User Journeys

**Primary User:** Enterprise sysadmin using aegish on production server

*Detailed user journeys deferred for PoC phase - focus is on technical validation.*

## CLI Tool Specific Requirements

### Command Interface

| Aspect | Requirement |
|--------|-------------|
| Mode | Interactive + Scriptable (full bash compatibility) |
| Output format | Plain text messages for block/allow/warn |
| Configuration | Minimal setup (environment variables or single config file) |
| Shell completion | Out of scope for MVP |

### Command Structure

- **Entry point:** `aegish` or set as login shell
- **Validation response:** Block, Allow, or Warn with plain text explanation
- **Script support:** Must execute .sh scripts transparently

### Technical Constraints

- Must not break existing bash scripts
- Validation latency must be acceptable for interactive use
- Exit codes must match bash behavior for script compatibility

## Project Scoping & Phased Development

### MVP Strategy

**Approach:** Problem-Solving MVP (PoC to validate LLM-based command validation)

### MVP Feature Set (Phase 1)

| Feature | Priority |
|---------|----------|
| Full bash shell compatibility | Must-have |
| LLM command validation (block/allow/warn) | Must-have |
| Basic dangerous command detection | Must-have |
| Plain text output | Must-have |
| Minimal config (env vars or single file) | Must-have |
| GTFOBins-level threat detection | Should-have |
| Shell completion | Out of scope |
| JSON logging | Out of scope |

### Phase 2 — Security Hardening (Completed)

- Subprocess environment sanitization (allowlist-based)
- Validation pipeline hardening (fail-mode, command delimiters, oversized command blocking)
- Production mode with Landlock sandbox and login shell behavior
- Environment variable integrity (provider allowlist, health check, model warnings)
- Advanced static pre-LLM validation (AST traversal, regex blocklist, meta-exec builtins, compound command decomposition)
- LLM pipeline hardening (timeouts, rate limiting, markdown JSON parsing, COMMAND tag injection prevention, source/dot script inspection)
- Configuration hardening (immutable production config, invalid mode rejection, role-based trust levels)
- Environment & subprocess security (allowlist sanitization, absolute envsubst path, `/bin/bash` integrity verification)
- Shell state persistence (cwd, exported env vars, exit code across commands)
- Landlock dropper and complete DENIED_SHELLS list
- Persistent structured audit logging
- Sudo post-elevation sandboxing with Landlock

### Phase 3 (Roadmap)

- System-wide benchmark (Docker-based with SUID, sudo, capabilities testing)
- Semantic caching for performance
- CIS compliance checking

### Phase 4 (Expansion)

- Vulnerability list scanning
- Offline mode (Ollama fallback)
- Enterprise features (SIEM integration, multi-user audit dashboards)

### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM latency too slow | Caching, prompt optimization |
| False positives frustrate users | Tune prompts, add whitelist |
| LLM costs too high | Caching, smaller models |

## Functional Requirements

### Shell Execution

- FR1: User can run interactive commands exactly as in bash
- FR2: User can execute shell scripts (.sh files) transparently
- FR3: User can use pipes, redirects, and command chaining
- FR4: User can access command history and recall previous commands (should-have)
- FR5: System preserves bash exit codes for script compatibility

### Command Validation

- FR6: System intercepts every command before execution
- FR7: System sends command to LLM for security analysis
- FR8: System receives risk assessment from LLM (safe/warn/block)
- FR9: System can detect basic dangerous commands (rm -rf /, fork bombs)
- FR10: System can detect GTFOBins patterns (should-have)

### Security Response

- FR11: System blocks commands classified as dangerous
- FR12: System warns user about risky commands with explanation
- FR13: System allows safe commands to execute immediately
- FR14: User receives plain text explanation when command is blocked/warned
- FR15: User can override warnings and proceed (with confirmation)

### Configuration

- FR16: User can configure LLM API credentials
- FR17: User can set aegish as login shell
- FR18: System works with minimal configuration (sensible defaults)

### Scoring & Evaluation Methodology

- FR19: Scoring treats WARN as equivalent to ALLOW — only BLOCK prevents execution
- FR20: aegish Score uses Balanced Accuracy: (Malicious Detection Rate + Harmless Acceptance Rate) / 2
- FR21: Metrics include per-GTFOBins-category malicious detection rates with micro and macro averages
- FR22: Parse errors distinguish TIMEOUT_ERROR (empty response) from FORMAT_ERROR (unparseable)
- FR23: All evaluations use max_retries=3 for transient API failure resilience
- FR24: All evaluations use a fixed seed (seed=42) for reproducibility

### Production Improvements

- FR25: All LlamaGuard-related code, config, prompts, and documentation removed from codebase
- FR26: System prompt Rule 1 covers both indirect shell escapes and direct shell spawners

### Dataset Quality

- FR27: GTFOBins placeholders use realistic security-sensitive paths (no "evil", "malware", "backdoor")
- FR28: Extraction script includes banned-name validation to prevent future regressions
- FR29: GTFOBins Shell category included in benchmark (~265 additional commands)
- FR30: Harmless dataset has genuinely dangerous commands removed
- FR31: Harmless dataset has commands that should be BLOCKed removed (shell spawners, servers)
- FR32: Harmless dataset has commands with unresolved template placeholders removed
- FR33: Harmless extraction filter tightened with new DANGEROUS_PATTERNS
- FR34: Harmless dataset extended to 500+ commands via LLM-generated commands
- FR35: Benchmark evaluation code lives in top-level `benchmark/` directory, not inside `tests/`

### Subprocess & Environment Hardening

- FR36: Subprocess execution environment sanitized (BASH_ENV, ENV, BASH_FUNC_* stripped; bash runs with --norc --noprofile)
- FR37: Validation failure behavior configurable: fail-safe (block) or fail-open (warn) via AEGISH_FAIL_MODE
- FR38: Commands exceeding MAX_COMMAND_LENGTH are blocked (not warned)
- FR39: ~~Low-confidence "allow" responses treated as "warn"~~ *(deferred)*
- FR40: Environment variables expanded via envsubst before LLM validation so LLM sees resolved values
- FR41: bashlex AST parsing detects variable expansion in command position and returns configurable action (default: BLOCK)
- FR42: User commands wrapped in `<COMMAND>` delimiters in LLM user message to resist prompt injection

### Production Mode & Landlock

- FR43: Production mode (AEGISH_MODE=production): exit terminates session (login shell), Landlock enforces shell execution denial
- FR44: Development mode (AEGISH_MODE=development): exit works normally with warning, no Landlock enforcement
- FR45: Landlock sandbox denies execve of shell binaries for child processes in production mode
- FR46: ~~Runner binary (hardlink/copy of bash) at /opt/aegish/bin/runner used for command execution in production mode~~ [RETIRED -- Superseded by FR80 in Epic 17. Runner binary removed; aegish uses /bin/bash directly.]
- FR47: Graceful Landlock fallback: if kernel < 5.13, production mode warns and falls back to development behavior

### Environment Variable Integrity

- FR48: Provider allowlist validates configured models against known-good providers
- FR49: Startup health check verifies primary model responds correctly before entering shell loop
- FR50: Non-default model configuration triggers visible warning at startup

### Advanced Static Pre-LLM Validation

- FR51: Variable-in-command-position detection action is configurable via AEGISH_VAR_CMD_ACTION (default: BLOCK)
- FR52: Meta-execution builtins (eval, source, .) with variable arguments are detected and blocked by default (configurable via AEGISH_VAR_CMD_ACTION)
- FR53: AST walker traverses control-flow nodes (for, if, while, until, function) to detect variable-in-command patterns
- FR54: Compound commands are recursively decomposed and each subcommand validated independently; command substitutions in execution position (e.g., `$(cat file)`) are detected and blocked
- FR55: Static regex blocklist catches known-dangerous patterns (reverse shells, rm -rf /, fork bombs) before LLM validation

### LLM Pipeline Hardening

- FR56: Health check timeout triggers automatic fallback: iterates through the full fallback chain, pins the first responsive model as the active session model
- FR57: LLM validation queries have a configurable timeout via AEGISH_LLM_TIMEOUT (default: 30 seconds)
- FR58: Client-side rate limiting prevents denial-of-wallet attacks on LLM API via AEGISH_MAX_QUERIES_PER_MINUTE (default: 30)
- FR59: JSON response parser handles markdown-wrapped LLM output (code fences, double braces)
- FR60: User commands are delimited to prevent COMMAND tag injection in LLM prompts (escaping `</COMMAND>` in user input)
- FR61: Source/dot commands trigger script content inspection before LLM validation (with size limits, sensitive path blocking, symlink resolution)

### Configuration Hardening & Trust Levels

- FR62: Security-critical configuration values cannot be overridden via environment variables in production mode (read from /etc/aegish/config)
- FR63: Invalid AEGISH_MODE value prevents aegish from starting (no silent fallback to development mode)
- FR64: Default production models match benchmark-recommended models (Gemini Flash primary, full 8-model fallback chain)
- FR65: Role-based trust level configuration adjusts validation rules (sysadmin, restricted, default) via AEGISH_ROLE
- FR66: Empty model names are rejected during validation (e.g., `openai/` is invalid)
- FR67: Login shell mode prints lockout warning at startup and clear error when health check fails

### Environment & Subprocess Security (Phase 2)

- FR68: Environment sanitization uses an allowlist instead of blocklist (unknown variables blocked by default)
- FR69: Full variable expansion to LLM by default; sensitive variable filter is opt-in via AEGISH_FILTER_SENSITIVE_VARS
- FR70: envsubst is invoked via absolute path resolved at startup (prevents PATH poisoning)
- FR71: `/bin/bash` path is used directly in production mode and verified via SHA-256 hash at startup

### Production Infrastructure & Shell State

- FR72: Shell state (cwd, exported env vars, exit code) persists across commands via pipe-based environment capture
- FR73: Landlock dropper (LD_PRELOAD C library) prevents `/bin/bash` from being executed as interactive shell by denying future execve() calls after the process is already running
- FR74: DENIED_SHELLS list includes all common shell binaries (bash, sh, zsh, fish, dash, csh, tcsh, ksh, ash, busybox, mksh, rbash, elvish, nu, pwsh, xonsh)
- FR75: ctypes syscall() uses correct c_long return type for 64-bit compatibility

### Audit Trail & Project Hygiene

- FR76: All validation decisions are logged to a persistent structured audit trail (JSON format with timestamp, command, user, action, confidence, model, source)
- FR77: litellm dependency has a version ceiling to prevent untested major upgrades (>=1.81.0,<2.0.0)
- FR78: Benchmark-only dependencies (adjusttext) are not in runtime dependencies
- FR79: Benchmark metadata counts are computed dynamically from actual datasets (not hardcoded)
- FR80: Production mode uses `/bin/bash` directly. SHA-256 hash verification applies to `/bin/bash` and the sandboxer library (`landlock_sandboxer.so`). The runner binary concept is retired.
- FR81: .gitignore and .env.example reflect current project structure and providers

### Sudo Post-Elevation Sandboxing

- FR82: Sudo commands in production mode with sysadmin role are sandboxed: Landlock dropper via LD_PRELOAD blocks shell escapes even after privilege elevation

## Non-Functional Requirements

### Performance

- NFR1: Command validation completes within 2 seconds for interactive use
- NFR2: Cached command decisions return within 100ms
- NFR3: Shell startup time adds no more than 5 seconds to bash startup

### Security

- NFR4: LLM API credentials stored securely (not in plain text)
- NFR5: No command data sent to external services beyond configured LLM API
- NFR6: Tool should not be easily bypassed to run commands directly (should-have)
- NFR7: LLM prompt should resist jailbreak attempts (out of scope for MVP)

### Reliability

*Out of scope for MVP - fail-safe mode and graceful degradation deferred to post-MVP.*

### Static Safety Floor (Phase 2)

- NFR8: Static pre-LLM checks provide a deterministic safety floor independent of LLM availability

### Audit & Observability (Phase 2)

- NFR9: Audit log entries use structured JSON format with timestamp, command, user, action, confidence, model, source
- NFR10: Rate limiting is configurable via AEGISH_MAX_QUERIES_PER_MINUTE (default: 30)
- NFR11: LLM query timeout is configurable via AEGISH_LLM_TIMEOUT (default: 30 seconds)

### Trust & Access Control (Phase 2)

- NFR12: Role/trust level configuration is deny-by-default (unknown roles get strictest rules)

