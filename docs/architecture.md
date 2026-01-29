---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - docs/prd.md
  - docs/analysis/research/technical-secbash-llm-command-validation-2026-01-23.md
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-01-28'
project_name: 'SecBASH'
user_name: 'guido'
date: '2026-01-28'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
- Shell compatibility (interactive + scripts, pipes, history)
- LLM-based command validation before execution
- Three-tier response: allow, warn (with override), block

**Non-Functional Requirements:**
- Must not break existing bash scripts
- Secure credential storage

**Scale & Complexity:**
- Primary domain: CLI tool
- Complexity level: Low (PoC)
- Core components: Interceptor, Validator, LLM Client, Decision Enforcer

### Technical Constraints

- Must maintain bash exit code compatibility
- API dependency for LLM

### Cross-Cutting Concerns

- Error handling: Exponential backoff with max retries, then fail-open (allow execution)

### MVP Scope Boundaries

**In Scope:**
- Basic LLM command validation (block/allow/warn)
- Full bash shell compatibility
- Simple retry logic with exponential backoff
- Fail-open on LLM unavailability

**Deferred (TODO):**
- Latency optimization
- Local model fallback (Ollama)
- GTFOBins benchmark targeting
- Semantic caching
- Enterprise features

## Starter Template Evaluation

### Primary Technology Domain

CLI tool - Python-based shell security wrapper

### Technology Stack Selected

**Language & Runtime:**
- Python 3.10+
- uv for package management (fast, modern)

**CLI Framework:**
- Typer (type-hint based, minimal boilerplate)

**Project Initialization:**

```bash
mkdir secbash && cd secbash
uv init
uv add typer openai anthropic
```

### Architectural Decisions from Stack

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Package manager | uv | Fast, resolves dependencies well |
| CLI framework | Typer | Clean syntax, auto --help |
| LLM clients | openai + anthropic SDKs | Official, maintained |
| Project structure | Single package | Simple for PoC |

### Basic Project Structure

```
secbash/
├── pyproject.toml
├── src/
│   └── secbash/
│       ├── __init__.py
│       ├── main.py          # Typer CLI entry
│       ├── validator.py     # LLM validation logic
│       └── config.py        # Settings/credentials
└── tests/
```

## Core Architectural Decisions

### Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Command interception | Interactive wrapper + subprocess | Simple, feels like shell, bash handles complexity |
| LLM providers | OpenRouter (LlamaGuard) → OpenAI → Anthropic | Security-specific model first, fallbacks for resilience |
| Credential storage | Environment variables | Industry standard, simple |
| Subprocess shell | bash -c (configurable) | Can swap for zsh if needed |

### Command Interception Architecture

```
┌─────────────────────────────────────────┐
│  SecBASH                                │
│  ┌─────────────────────────────────┐    │
│  │  readline/prompt_toolkit loop   │    │
│  │  (history, tab completion)      │    │
│  └─────────────────────────────────┘    │
│              ↓                          │
│  Validate command with LLM              │
│              ↓                          │
│  subprocess.run("bash -c '...'")        │
└─────────────────────────────────────────┘
```

### LLM Provider Strategy

**Fallback chain:**
1. OpenRouter → LlamaGuard (security-specific)
2. OpenAI GPT-4
3. Anthropic Claude
4. Exponential backoff → fail-open (allow)

**Environment variables:**
- `OPENROUTER_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

### Deferred (Out of Scope for MVP)

**Production Deployment Configs:**
- SSH ForceCommand configuration
- Login shell setup (/etc/shells, chsh)
- authorized_keys restrictions

**Shell Escape Pattern Detection:**
- GTFOBins escape patterns (vim :!bash, less !, etc.)
- Blacklist of shell-spawning binaries
- rbash or container isolation
- Defense-in-depth bypass resistance

## Implementation Patterns & Consistency Rules

### Python Conventions

Follow PEP 8:
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Files/modules: `snake_case.py`

### LLM Response Format

```python
{
    "action": "allow" | "warn" | "block",
    "reason": "Human-readable explanation",
    "confidence": 0.0 - 1.0
}
```

### Error Handling

Use standard Python exceptions for MVP:
- `ValueError` for invalid input
- `ConnectionError` for LLM API failures
- `TimeoutError` for LLM timeouts

### Logging

Standard Python `logging` module with default configuration.

### All AI Agents MUST

- Follow PEP 8 naming conventions
- Return LLM responses in the specified format (action, reason, confidence)
- Use standard exceptions, no custom exception classes for MVP

## Project Structure & Boundaries

### Complete Project Directory Structure

```
secbash/
├── pyproject.toml              # uv/pip config, dependencies
├── README.md
├── .env.example                # Template for API keys
├── .gitignore
│
├── src/
│   └── secbash/
│       ├── __init__.py         # Version, package info
│       ├── main.py             # Typer CLI entry point
│       ├── shell.py            # readline loop, user interaction
│       ├── validator.py        # LLM validation logic
│       ├── llm_client.py       # OpenRouter/OpenAI/Anthropic clients
│       ├── executor.py         # subprocess.run wrapper
│       └── config.py           # Environment variable loading
│
└── tests/
    ├── __init__.py
    ├── test_validator.py       # Validation logic tests
    ├── test_llm_client.py      # Mock LLM response tests
    └── test_executor.py        # Subprocess execution tests
```

### Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `main.py` | Typer CLI, `secbash` command entry |
| `shell.py` | readline loop, prompt, history |
| `validator.py` | Parse LLM response, decide action |
| `llm_client.py` | API calls with fallback chain |
| `executor.py` | Run `bash -c "..."`, capture output |
| `config.py` | Load `*_API_KEY` from env |

### Data Flow

```
User input → shell.py → validator.py → llm_client.py → LLM API
                ↓
         Decision (allow/warn/block)
                ↓
         executor.py → bash -c "command"
                ↓
         Output displayed
```

### Requirements Mapping

| PRD Requirement | Module |
|-----------------|--------|
| FR1-5 (Shell execution) | `shell.py`, `executor.py` |
| FR6-10 (Command validation) | `validator.py`, `llm_client.py` |
| FR11-15 (Security response) | `validator.py`, `shell.py` |
| FR16-18 (Configuration) | `config.py` |

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
- Python 3.10+ + uv + Typer + LLM SDKs: All compatible
- OpenRouter/OpenAI/Anthropic fallback chain: Works together
- subprocess approach with readline: Compatible

**Pattern Consistency:**
- PEP 8 naming applies consistently across all modules
- LLM response format used uniformly in validator
- Standard exceptions throughout

**Structure Alignment:**
- 6 focused modules, each with single responsibility
- Clear data flow from shell → validator → llm_client → executor

### Requirements Coverage ✅

| Requirement | Covered By | Status |
|-------------|------------|--------|
| FR1-5 (Shell execution) | `shell.py`, `executor.py` | ✅ |
| FR6-10 (Command validation) | `validator.py`, `llm_client.py` | ✅ |
| FR11-15 (Security response) | `validator.py`, `shell.py` | ✅ |
| FR16-18 (Configuration) | `config.py` | ✅ |
| NFR: Bash compatibility | `executor.py` (subprocess) | ✅ |
| NFR: Secure credentials | Environment variables | ✅ |

### Implementation Readiness ✅

- All modules defined with clear boundaries
- Data flow documented
- LLM response format specified (action, reason, confidence)
- Error handling: standard exceptions + exponential backoff

### Gap Analysis

**No Critical Gaps** for MVP scope.

**Nice-to-Have (Future):**
- Detailed LLM prompt template documentation
- Test fixtures for mocking LLM responses
- Logging configuration examples

### Architecture Completeness Checklist

- [x] Project context analyzed
- [x] Technology stack specified (Python, uv, Typer)
- [x] Core decisions documented (interception, LLM providers, credentials)
- [x] Implementation patterns defined (PEP 8, response format)
- [x] Project structure complete (6 modules + tests)
- [x] Requirements mapped to modules

**Overall Status:** ✅ READY FOR IMPLEMENTATION

## Architecture Completion Summary

**Architecture Decision Workflow:** COMPLETED ✅
**Date Completed:** 2026-01-28
**Document Location:** `docs/architecture.md`

### Final Deliverables

- 4 core architectural decisions documented
- 6 modules with clear responsibilities
- All 18 functional requirements mapped
- Implementation patterns for AI agent consistency

### First Implementation Priority

```bash
mkdir secbash && cd secbash
uv init
uv add typer openai anthropic
```

### Development Sequence

1. Initialize project using commands above
2. Create module files per project structure
3. Implement `config.py` (environment loading)
4. Implement `llm_client.py` (API calls with fallback)
5. Implement `validator.py` (parse LLM response)
6. Implement `executor.py` (subprocess wrapper)
7. Implement `shell.py` (readline loop)
8. Implement `main.py` (Typer entry point)

---

**Architecture Status:** READY FOR IMPLEMENTATION ✅

