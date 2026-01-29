# Story 1.2: Basic Interactive Shell Loop

## Status: done

## Story

As a **sysadmin**,
I want **to launch SecBASH and run simple commands interactively**,
So that **I can use it as my command-line interface**.

## Epic Context

**Epic 1: Working Shell Foundation** - User can launch SecBASH and execute commands exactly like bash. This story delivers the core interactive shell experience, building on the project structure from Story 1.1.

**FRs Addressed:** FR1 (interactive commands like bash), partially FR3 (basic shell features), FR5 (exit codes)

**Dependencies:** Story 1.1 (project structure) - COMPLETED

## Acceptance Criteria

### AC1: Shell Launch and Basic Commands
**Given** SecBASH is installed and launched via `uv run secbash`
**When** I type a command like `ls` or `pwd`
**Then** the command executes and output is displayed
**And** a new prompt appears for the next command

### AC2: Exit Commands
**Given** SecBASH is running
**When** I type `exit` or press Ctrl+D (EOF)
**Then** the shell exits gracefully with exit code 0

### AC3: Interrupt Handling
**Given** SecBASH is running
**When** I press Ctrl+C
**Then** the current input is cancelled without exiting the shell
**And** a new prompt appears

### AC4: Exit Code Preservation
**Given** a command that succeeds (e.g., `true` or `ls`)
**When** the command completes
**Then** exit code 0 is available via `$?` in subsequent commands

**Given** a command that fails (e.g., `false` or `ls nonexistent`)
**When** the command completes
**Then** the appropriate non-zero exit code is available

### AC5: Output Streams
**Given** SecBASH is running
**When** a command produces stdout output
**Then** stdout is displayed to the terminal

**Given** SecBASH is running
**When** a command produces stderr output
**Then** stderr is displayed to the terminal (on stderr)

## Technical Requirements

### Module Implementation: shell.py

The `shell.py` module must implement the readline-based interactive loop:

```python
"""Shell interaction module.

Handles the readline loop, prompt display, and user interaction.
"""

import readline
import sys
from secbash.executor import execute_command


def get_prompt() -> str:
    """Return the shell prompt string.

    Returns:
        Prompt string, default is "secbash> "
    """
    return "secbash> "


def run_shell() -> int:
    """Run the interactive shell loop.

    Returns:
        Exit code (0 for normal exit).
    """
    # Implementation here
```

### Module Implementation: executor.py

The `executor.py` module must implement command execution:

```python
"""Command execution module.

Runs shell commands via subprocess and captures output.
"""

import subprocess
import sys


def execute_command(command: str) -> int:
    """Execute a shell command via bash.

    Args:
        command: The command string to execute.

    Returns:
        Exit code from the command.
    """
    # Use subprocess.run with bash -c
    # Stream output directly to terminal (no capture)
    # Return the exit code
```

### Integration: main.py

Update `main.py` to call the shell loop:

```python
@app.command()
def main():
    """Launch SecBASH interactive shell."""
    from secbash.shell import run_shell
    exit_code = run_shell()
    raise typer.Exit(exit_code)
```

### Key Implementation Details

1. **Use readline for input**: Provides line editing, but history is deferred to Story 3.4
2. **Use subprocess.run with shell=False**: Pass command to `bash -c "command"` for execution
3. **Stream output directly**: Don't capture stdout/stderr, let them flow to terminal
4. **Handle signals properly**: Ctrl+C should interrupt input, not exit shell
5. **Track last exit code**: Store in a variable for `$?` expansion in future commands

### Subprocess Execution Pattern

```python
result = subprocess.run(
    ["bash", "-c", command],
    # Don't capture - stream directly to terminal
)
return result.returncode
```

### Signal Handling

```python
import signal

# In run_shell():
# Ctrl+C should cancel current input line, not exit
# Ctrl+D (EOF) should exit the shell
```

## Implementation Notes

### Developer Workflow
1. Implement `execute_command()` in `executor.py` first
2. Implement `run_shell()` in `shell.py` with basic loop
3. Add Ctrl+C handling (KeyboardInterrupt)
4. Add Ctrl+D handling (EOFError from input())
5. Update `main.py` to call `run_shell()`
6. Test manually with various commands

### Edge Cases to Handle
- Empty input (just press Enter) - show new prompt
- Whitespace-only input - show new prompt
- Very long commands - should work (bash handles it)
- Commands with quotes and special characters - pass through to bash

### What This Story Does NOT Include
- Command validation (Epic 2)
- History navigation with arrow keys (Story 3.4)
- Tab completion (out of scope for MVP)
- Pipes and redirects (Story 1.3 - but bash handles this, so basic support works)
- Shell script execution (Story 1.4 - but single-line scripts work)

## Dependencies

- Story 1.1: Initialize Project Structure (COMPLETED)

## Blocked By

- None (Story 1.1 is complete)

## Test Guidance

### Manual Verification Steps
1. Run `uv run secbash` - shell should launch with prompt
2. Type `pwd` - should show current directory
3. Type `ls` - should list files
4. Type `echo hello` - should print "hello"
5. Press Enter with empty input - should show new prompt
6. Type `false` then `echo $?` - should show "1"
7. Type `true` then `echo $?` - should show "0"
8. Press Ctrl+C - should cancel input, show new prompt
9. Press Ctrl+D - should exit shell
10. Type `exit` - should exit shell

### Automated Tests

Create `tests/test_executor.py`:

```python
"""Tests for command execution."""

import subprocess
from secbash.executor import execute_command


def test_execute_simple_command():
    """Test executing a simple command."""
    # This would need to capture output for testing
    # Consider adding a capture mode for tests
    pass


def test_execute_command_exit_code_success():
    """Test that successful commands return 0."""
    exit_code = execute_command("true")
    assert exit_code == 0


def test_execute_command_exit_code_failure():
    """Test that failed commands return non-zero."""
    exit_code = execute_command("false")
    assert exit_code == 1
```

Create `tests/test_shell.py`:

```python
"""Tests for shell module."""

from secbash.shell import get_prompt


def test_get_prompt():
    """Test default prompt string."""
    prompt = get_prompt()
    assert "secbash" in prompt.lower()
```

## Story Points

**Estimate:** Medium (3-5 points)

This story requires implementing two modules with proper signal handling and subprocess management. The core logic is straightforward but edge cases and proper terminal behavior require attention.

## Definition of Done

- [x] `uv run secbash` launches interactive shell with prompt
- [x] Simple commands (`ls`, `pwd`, `echo`) execute and display output
- [x] `exit` command exits the shell
- [x] Ctrl+D (EOF) exits the shell
- [x] Ctrl+C cancels current input without exiting
- [x] Exit codes are preserved (testable via `echo $?`)
- [x] stderr is displayed on stderr, stdout on stdout
- [x] Empty input shows new prompt (no error)
- [x] Code follows PEP 8 naming conventions
- [x] Basic tests pass (11 tests passing)
