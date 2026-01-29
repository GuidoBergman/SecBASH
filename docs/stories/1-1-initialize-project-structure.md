# Story 1.1: Initialize Project Structure

## Status: done

## Story

As a **developer**,
I want **the SecBASH project initialized with proper Python structure**,
So that **I have a foundation to build the shell functionality**.

## Epic Context

**Epic 1: Working Shell Foundation** - User can launch SecBASH and execute commands exactly like bash. This story establishes the project foundation that all subsequent stories build upon.

**FRs Addressed:** Project initialization from Architecture (Python/uv/Typer setup)

## Acceptance Criteria

### AC1: Project Directory Structure
**Given** a fresh directory
**When** the project is initialized
**Then** the following structure exists:
- `pyproject.toml` with project metadata
- `src/secbash/` directory with `__init__.py`
- Module files: `main.py`, `shell.py`, `validator.py`, `llm_client.py`, `executor.py`, `config.py`
- `tests/` directory with `__init__.py`
- `.env.example` with API key placeholders
- `.gitignore` with Python defaults

### AC2: Dependencies Installable
**Given** the project structure exists
**When** a developer runs `uv sync`
**Then** all dependencies are installed successfully
**And** the virtual environment is created

### AC3: Entry Point Functional
**Given** dependencies are installed
**When** a developer runs `uv run secbash --help`
**Then** the CLI shows help output (even if minimal)
**And** no import errors occur

### AC4: Architecture Compliance
**Given** the project structure
**When** reviewed against the Architecture document
**Then** the structure matches the specification:
- Python 3.10+ required in pyproject.toml
- uv as package manager
- Typer, openai, anthropic as dependencies
- Module responsibilities align with architecture

## Technical Requirements

### pyproject.toml Configuration
```toml
[project]
name = "secbash"
version = "0.1.0"
description = "LLM-powered shell with security validation"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.9.0",
    "openai>=1.0.0",
    "anthropic>=0.18.0",
]

[project.scripts]
secbash = "secbash.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Module Stubs
Each module should have a minimal stub with:
- Module docstring explaining its responsibility (from Architecture)
- Any necessary imports
- Placeholder functions with `pass` or `raise NotImplementedError`

**Module Responsibilities (from Architecture):**
| Module | Responsibility |
|--------|----------------|
| `main.py` | Typer CLI, `secbash` command entry |
| `shell.py` | readline loop, prompt, history |
| `validator.py` | Parse LLM response, decide action |
| `llm_client.py` | API calls with fallback chain |
| `executor.py` | Run `bash -c "..."`, capture output |
| `config.py` | Load `*_API_KEY` from env |

### .env.example Template
```
# SecBASH API Configuration
# At least one API key is required

# OpenRouter (preferred - uses LlamaGuard)
OPENROUTER_API_KEY=

# OpenAI (fallback)
OPENAI_API_KEY=

# Anthropic (second fallback)
ANTHROPIC_API_KEY=
```

### .gitignore Essentials
- `.venv/`
- `__pycache__/`
- `*.pyc`
- `.env` (but NOT `.env.example`)
- `dist/`
- `*.egg-info/`

## Implementation Notes

### Developer Workflow
1. Create project root directory structure
2. Initialize with `uv init` or create `pyproject.toml` manually
3. Create `src/secbash/` package structure
4. Add dependencies via `uv add typer openai anthropic`
5. Create module stubs with docstrings
6. Verify with `uv sync` and `uv run secbash --help`

### main.py Entry Point
Should contain minimal Typer app setup:
```python
"""SecBASH CLI entry point."""
import typer

app = typer.Typer(
    name="secbash",
    help="LLM-powered shell with security validation"
)

@app.command()
def main():
    """Launch SecBASH interactive shell."""
    typer.echo("SecBASH - Not yet implemented")
    raise typer.Exit(0)

if __name__ == "__main__":
    app()
```

## Dependencies

- None (this is the foundation story)

## Blocked By

- None

## Test Guidance

### Manual Verification Steps
1. Run `uv sync` - should complete without errors
2. Run `uv run secbash --help` - should show help
3. Run `uv run secbash` - should show "Not yet implemented" message
4. Verify all 6 module files exist in `src/secbash/`
5. Verify `tests/` directory exists with `__init__.py`

### Automated Tests (Optional for this story)
Since this is a scaffolding story, automated tests are optional. If added:
- Test that all modules are importable
- Test that `app` is a valid Typer application

## Story Points

**Estimate:** Small (1-2 points)

This is a scaffolding story with minimal complexity. The primary value is establishing the correct structure for subsequent development.

## Definition of Done

- [x] Project directory matches Architecture specification
- [x] `pyproject.toml` properly configured with all dependencies
- [x] All 6 module files created with appropriate stubs
- [x] `uv sync` completes successfully
- [x] `uv run secbash --help` works
- [x] `.env.example` and `.gitignore` in place
- [x] Code follows PEP 8 naming conventions
