# Story 1.3: Command Execution with Pipes and Redirects

## Status: done

## Story

As a **sysadmin**,
I want **to use pipes, redirects, and command chaining**,
So that **I can perform complex shell operations**.

## Epic Context

**Epic 1: Working Shell Foundation** - User can launch aegish and execute commands exactly like bash. This story validates that complex shell operations work correctly through aegish.

**FRs Addressed:** FR3 (pipes, redirects, chaining)

**Dependencies:** Story 1.2 (Basic Interactive Shell Loop) - COMPLETED

## Acceptance Criteria

### AC1: Pipe Operations
**Given** aegish is running
**When** I enter a piped command like `ls -la | grep txt`
**Then** the full pipeline executes correctly
**And** output from the final command in the pipeline is displayed

**Given** aegish is running
**When** I chain multiple pipes like `cat file | sort | uniq | head`
**Then** all stages of the pipeline execute in order

### AC2: Output Redirection
**Given** aegish is running
**When** I use output redirection like `echo "test" > file.txt`
**Then** the file is created with the content

**Given** aegish is running
**When** I use append redirection like `echo "more" >> file.txt`
**Then** content is appended to the existing file

**Given** aegish is running
**When** I redirect stderr like `ls nonexistent 2> errors.txt`
**Then** stderr is captured to the specified file

### AC3: Input Redirection
**Given** aegish is running and a file `input.txt` exists
**When** I use input redirection like `sort < input.txt`
**Then** the command reads from the specified file

### AC4: Command Chaining with &&
**Given** aegish is running
**When** I chain commands with `true && echo "success"`
**Then** the second command runs because the first succeeded

**Given** aegish is running
**When** I chain commands with `false && echo "success"`
**Then** the second command does NOT run (short-circuit)

### AC5: Command Chaining with ||
**Given** aegish is running
**When** I chain commands with `false || echo "fallback"`
**Then** the second command runs because the first failed

**Given** aegish is running
**When** I chain commands with `true || echo "fallback"`
**Then** the second command does NOT run

### AC6: Sequential Execution with ;
**Given** aegish is running
**When** I run `echo a; echo b; echo c`
**Then** all three commands execute in sequence
**And** each outputs on its own line

### AC7: Combined Operations
**Given** aegish is running
**When** I combine operations like `ls | grep txt && echo "found" || echo "none"`
**Then** the compound command executes with correct short-circuit logic

## Technical Notes

### Why This Works Already

The current implementation uses `bash -c "command"` which delegates ALL shell parsing to bash. This means:
- Pipes (`|`) are handled by bash
- Redirects (`>`, `>>`, `<`, `2>`) are handled by bash
- Command chaining (`&&`, `||`, `;`) is handled by bash
- Subshells, command substitution, etc. all work

### What This Story Adds

This story is primarily a **validation and testing story**:
1. Add comprehensive tests for pipes/redirects/chaining
2. Document that these features work
3. Verify edge cases

### Implementation Status

**No code changes required** - the feature already works. This story adds test coverage.

## Dependencies

- Story 1.2: Basic Interactive Shell Loop (COMPLETED)

## Blocked By

- None

## Test Guidance

### Manual Verification Steps
1. `ls -la | head -3` - should show first 3 lines of ls output
2. `echo "hello" > /tmp/test.txt && cat /tmp/test.txt` - should create and display file
3. `echo "more" >> /tmp/test.txt && cat /tmp/test.txt` - should append
4. `true && echo "yes"` - should print "yes"
5. `false && echo "yes"` - should print nothing
6. `false || echo "fallback"` - should print "fallback"
7. `echo a; echo b; echo c` - should print a, b, c on separate lines
8. `ls /nonexistent 2>&1 | head -1` - should show error message

### Automated Tests

Add to `tests/test_executor.py`:

```python
def test_pipe_command():
    """Test that piped commands work."""
    result = run_bash_command("echo hello | tr 'h' 'H'")
    assert result.stdout.strip() == "Hello"
    assert result.returncode == 0


def test_output_redirect(tmp_path):
    """Test output redirection."""
    test_file = tmp_path / "test.txt"
    result = run_bash_command(f'echo "content" > {test_file}')
    assert result.returncode == 0
    assert test_file.read_text().strip() == "content"


def test_append_redirect(tmp_path):
    """Test append redirection."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\n")
    result = run_bash_command(f'echo "line2" >> {test_file}')
    assert result.returncode == 0
    assert test_file.read_text() == "line1\nline2\n"


def test_chain_and_success():
    """Test && with successful first command."""
    result = run_bash_command('true && echo "success"')
    assert result.stdout.strip() == "success"


def test_chain_and_failure():
    """Test && with failed first command (short-circuit)."""
    result = run_bash_command('false && echo "success"')
    assert result.stdout.strip() == ""


def test_chain_or_success():
    """Test || with successful first command (short-circuit)."""
    result = run_bash_command('true || echo "fallback"')
    assert result.stdout.strip() == ""


def test_chain_or_failure():
    """Test || with failed first command."""
    result = run_bash_command('false || echo "fallback"')
    assert result.stdout.strip() == "fallback"


def test_sequential_semicolon():
    """Test ; for sequential execution."""
    result = run_bash_command('echo a; echo b; echo c')
    assert result.stdout.strip() == "a\nb\nc"


def test_multiple_pipes():
    """Test multiple pipes in sequence."""
    result = run_bash_command('echo "c\na\nb" | sort | head -1')
    assert result.stdout.strip() == "a"
```

## Story Points

**Estimate:** Small (1-2 points)

This is primarily a validation/testing story. The feature already works via bash delegation. The effort is in writing comprehensive tests.

## Definition of Done

- [x] Manual verification of all AC scenarios passes
- [x] Automated tests added for pipes, redirects, and chaining
- [x] All tests pass
- [x] No regressions in existing functionality
