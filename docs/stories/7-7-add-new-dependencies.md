# Story 7.7: Add New Dependencies

Status: done

## Story

As a **developer**,
I want **bashlex added as a project dependency**,
so that **the validation pipeline can parse bash ASTs for variable-in-command-position detection (Story 7.2)**.

## Acceptance Criteria

1. **Given** `bashlex` is not in pyproject.toml
   **When** `uv add bashlex` is run
   **Then** bashlex is added to the `[project] dependencies` list
   **And** `uv.lock` is updated

2. **Given** bashlex is in pyproject.toml
   **When** `uv sync` is run
   **Then** all dependencies resolve and install successfully with no conflicts

3. **Given** bashlex is installed in the virtual environment
   **When** `uv run python -c "import bashlex; print(bashlex.parse('echo hello'))"` is run
   **Then** output shows a parsed AST node list (no errors, no exceptions)

## Tasks / Subtasks

- [x] Task 1: Add bashlex to pyproject.toml (AC: 1, 2)
  - [x] 1.1: Run `uv add bashlex` in project root `/home/gbergman/YDKHHICF/SecBASH`
  - [x] 1.2: Verify `pyproject.toml` lists bashlex in `[project] dependencies`
  - [x] 1.3: Run `uv sync` and confirm clean resolution with zero conflicts
- [x] Task 2: Verify bashlex functionality (AC: 3)
  - [x] 2.1: Run `uv run python -c "import bashlex; print(bashlex.parse('echo hello'))"`
  - [x] 2.2: Confirm output is a list of AST node objects (e.g., `[CommandNode(...)]`)
  - [x] 2.3: Run `uv run python -c "import bashlex; parts = bashlex.parse('a=foo; $a'); print(parts)"` to verify compound command parsing works

## Dev Notes

### Critical Context

- **This is a prerequisite story.** bashlex is required by Story 7.2 (Detect Variable-in-Command-Position via bashlex). It must be added before Story 7.2 can begin implementation.
- **Only bashlex is a Python dependency.** The `envsubst` utility needed by Story 7.1 is a **system package** (`gettext-base` on Debian/Ubuntu), NOT a Python dependency. Do NOT add envsubst or gettext to pyproject.toml.
- **Add to `[project] dependencies`, not `[dependency-groups] dev`.** bashlex is a production runtime dependency (used in the validation pipeline at `src/aegish/validator.py`), not a dev-only dependency.

### bashlex Library Details

- **Package:** [bashlex on PyPI](https://pypi.org/project/bashlex/) / [GitHub: idank/bashlex](https://github.com/idank/bashlex)
- **Latest version:** 0.18
- **License:** GNU GPL v3+ (same as GNU bash) - compatible with this project
- **What it does:** Python port of GNU bash's internal parser; generates a complete AST without executing code
- **Key capabilities:** Parses command substitutions `$(...)`, process substitutions `<(...)`, compound commands, assignments, pipelines
- **Known limitations:**
  - No support for arithmetic expressions `$((..))`
  - Complex parameter expansions like `${parameter#word}` are treated as literals (no child nodes)
  - These limitations do NOT affect Story 7.2's use case (detecting variable expansion in command position)
- **No transitive dependencies:** bashlex is a pure Python package with no external dependencies

### Architecture Compliance

- **Package manager:** `uv` (per Architecture doc) - use `uv add bashlex`, NOT `pip install`
- **pyproject.toml location:** `/home/gbergman/YDKHHICF/SecBASH/pyproject.toml`
- **Current production dependencies:** `typer>=0.9.0`, `litellm>=1.0.0`, `adjusttext>=1.3.0`
- **Version pinning convention:** Use `>=` minimum version (matching existing deps pattern): `bashlex>=0.18`
- **Design Decision DD-09:** bashlex AST parsing chosen over regex heuristics because regex cannot distinguish variable position (command vs argument) [Source: docs/security-hardening-scope.md#DD-09]

### Related Stories in Epic 7

| Story | Dependency on 7.7 | Description |
|-------|-------------------|-------------|
| 7.1 | None (uses system `envsubst`) | Expand env vars before LLM validation |
| 7.2 | **Direct dependency** | Uses bashlex to detect variable-in-command-position |
| 7.3 | None | Command delimiters for prompt injection defense |
| 7.4 | None | Configurable fail-mode |
| 7.5 | None | Block oversized commands |
| 7.6 | None | Confidence threshold on allow |
| 7.8 | Indirect (tests 7.2) | Unit tests for validation pipeline |

### envsubst System Dependency Note

Story 7.1 requires `envsubst` which is provided by the `gettext-base` system package:
- **Debian/Ubuntu:** `sudo apt-get install gettext-base`
- **Alpine:** `apk add gettext`
- **macOS:** Pre-installed or `brew install gettext`
- This is documented here for developer awareness but is NOT part of this story's scope.

### Project Structure Notes

- No new files created by this story - only `pyproject.toml` and `uv.lock` are modified
- Alignment with unified project structure: confirmed (dependencies section of pyproject.toml)
- No conflicts or variances detected

### References

- [Source: docs/epics.md#Story 7.7] - Story definition and acceptance criteria
- [Source: docs/security-hardening-scope.md#DD-09] - Design decision for bashlex over regex
- [Source: docs/security-hardening-scope.md#BYPASS-15] - Pre-expansion vs post-expansion gap (motivation for bashlex)
- [Source: docs/architecture.md#Technology Stack] - uv package manager, Python 3.10+
- [Source: pyproject.toml] - Current dependency list

## Dev Agent Record

### Context Reference

<!-- Story context created by create-story workflow -->

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None - clean implementation with no issues.

### Completion Notes List

- Added `bashlex>=0.18` to `[project] dependencies` in pyproject.toml via `uv add bashlex`
- bashlex 0.18 (pure Python, no transitive deps) installed successfully
- `uv sync` resolved 137 packages cleanly with zero conflicts
- Verified basic parsing: `bashlex.parse('echo hello')` returns `[CommandNode(parts=[WordNode(...)])]`
- Verified compound command + variable expansion: `bashlex.parse('a=foo; $a')` returns `ListNode` with `AssignmentNode`, `OperatorNode`, and `CommandNode` containing `ParameterNode` for `$a` in command position
- Full test suite: 567 passed, 4 pre-existing failures (3 benchmark plot tests + 1 benchmark compare test, unrelated)
- No regressions introduced

### Change Log

- 2026-02-13: Added bashlex>=0.18,<1.0 as production dependency (prerequisite for Story 7.2)
- 2026-02-13: Code review fixes — added MIT LICENSE file, added license field to pyproject.toml, added version upper bound to bashlex constraint, corrected test result documentation

### File List

- pyproject.toml (modified - added bashlex>=0.18,<1.0 to dependencies, added MIT license field)
- uv.lock (modified - updated lock file with bashlex 0.18)
- LICENSE (created - MIT license for the project)
