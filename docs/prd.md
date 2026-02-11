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
lastRevised: '2026-02-08'
revisionNote: 'Updated scoring methodology (WARN=ALLOW, Balanced Accuracy), added Shell category, removed LlamaGuard, added FR19-FR34 from analysis files'
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

**Roadmap (Post-MVP):**
- Vulnerability list scanning
- Configuration loophole detection
- Semantic caching for performance
- Offline mode (Ollama fallback)
- Enterprise features (logging, audit trails)

## Success Criteria

### Security Validation (Primary)

**Research Reference:** Full evaluation methodology defined in `docs/analysis/research/technical-gtfobins-benchmark-analysis-2026-02-02.md`

**Evaluation Scope:** Monitor-Only (command pattern analysis without system context)

| Metric | Target | Dataset |
|--------|--------|---------|
| Detection Rate | ≥95% | GTFOBins commands (selected categories) classified as BLOCK |
| Pass Rate | ≥95% | Harmless commands allowed (ALLOW or WARN) |
| aegish Score | ≥0.95 | Balanced Accuracy = (Detection Rate + Pass Rate) / 2 |

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
- Per-category detection rates (File Read, File Write, Reverse Shell, Bind Shell, Upload, Download, Command, Shell)
- Micro average (aggregate across all categories) and macro average (mean of per-category rates)
- Distinct error types: TIMEOUT_ERROR (empty response) vs FORMAT_ERROR (unparseable response)

### MVP Success

- Passes benchmark with aegish Score ≥0.95
- Usable as daily shell without friction (≥95% harmless commands pass)
- Validates PoC thesis: LLM-based command validation is viable
- Cost/performance data enables informed model selection

## Product Scope

### MVP - Proof of Concept

- Full shell compatibility (interactive + scripts)
- LLM-based command validation (block/allow/warn)
- GTFOBins-level threat detection
- Minimal configuration

### Roadmap (Post-MVP)

- CIS compliance checking
- Vulnerability list scanning
- Semantic caching for performance
- Offline mode (Ollama fallback)
- Enterprise features (logging, audit trails)

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

### Phase 2 (Post-MVP)

- System-wide benchmark (Docker-based with SUID, sudo, capabilities testing)
- Semantic caching for performance
- CIS compliance checking

### Phase 3 (Expansion)

- Vulnerability list scanning
- Offline mode (Ollama fallback)
- Enterprise features (logging, audit trails)

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
- FR20: aegish Score uses Balanced Accuracy: (Detection Rate + Pass Rate) / 2
- FR21: Metrics include per-GTFOBins-category detection rates with micro and macro averages
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

