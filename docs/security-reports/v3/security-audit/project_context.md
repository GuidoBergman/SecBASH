# Project Context: aegish

## Overview
aegish is an LLM-powered interactive shell that validates commands before execution.
It intercepts user shell commands, sends them to an LLM for security analysis, and
classifies them as ALLOW/WARN/BLOCK before optionally executing them.

## Language & Framework
- **Language**: Python 3.10+
- **Package Manager**: uv (use `uv run` to execute)
- **Key Dependencies**: typer (CLI), litellm (LLM abstraction), bashlex (shell parsing), braceexpand
- **Build System**: hatchling

## Source Directory
`src/aegish/` — 14 Python files, ~5,100 lines total

## Entry Points
- **CLI**: `aegish.main:app` (typer CLI, registered as `aegish` console script)

## Source Files
| File | Likely Purpose |
|------|---------------|
| main.py | CLI entry point (typer app) |
| shell.py | Interactive shell loop |
| llm_client.py | LLM API communication via litellm |
| validator.py | Command validation logic (ALLOW/WARN/BLOCK) |
| executor.py | Command execution |
| config.py | Configuration management |
| constants.py | Constants and enums |
| sandbox.py | Sandboxed execution environment |
| canonicalizer.py | Command canonicalization/normalization |
| resolver.py | Command/path resolution |
| audit.py | Audit logging |
| json_utils.py | JSON parsing utilities |
| utils.py | General utilities |
| __init__.py | Package init |

## Security-Critical Areas (High Priority)
1. **executor.py** — Executes shell commands; most dangerous attack surface
2. **sandbox.py** — Sandboxing; bypass = full compromise
3. **validator.py** — Security decision logic; bypass = unrestricted execution
4. **llm_client.py** — LLM communication; prompt injection surface
5. **shell.py** — User input handling; injection/escape vectors
6. **resolver.py** — Path/command resolution; traversal risk
7. **canonicalizer.py** — Input normalization; bypass via inconsistency
8. **config.py** — Configuration; insecure defaults risk

## Benchmark Directory (Lower Priority)
`benchmark/` — Benchmark framework for evaluating LLMs. Not part of the runtime product.
Focus audit on `src/aegish/` only.

## Known Environment Variables
- AEGISH_PRIMARY_MODEL
- AEGISH_FALLBACK_MODELS
