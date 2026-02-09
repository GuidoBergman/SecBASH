# Story 1.5: Exit Code Preservation

## Status: Done

## Story

As a **sysadmin**,
I want **aegish to preserve bash exit codes**,
So that **my scripts and conditional logic work correctly**.

## Epic Context

**Epic 1: Working Shell Foundation** - User can launch aegish and execute commands exactly like bash. This is the final story in Epic 1, completing bash compatibility for the shell foundation.

**FRs Addressed:** FR5 (System preserves bash exit codes for script compatibility)

**Dependencies:** Stories 1.1-1.4 (all COMPLETED)

## Acceptance Criteria

### AC1: Successful Command Returns Zero
**Given** a command that succeeds (e.g., `true`)
**When** I check `$?` or use `&&`
**Then** exit code 0 is returned

### AC2: Failed Command Returns Non-Zero
**Given** a command that fails (e.g., `false` or `ls nonexistent`)
**When** I check `$?`
**Then** the appropriate non-zero exit code is returned

### AC3: Specific Exit Codes Preserved
**Given** a command that exits with a specific code (e.g., `exit 42`)
**When** I check `$?`
**Then** that exact exit code is available

### AC4: Exit Code Available Across Commands
**Given** a command has executed
**When** I run a subsequent command that references `$?`
**Then** the previous command's exit code is correctly available

### AC5: Script Compatibility with set -e
**Given** aegish is used to run a script with `set -e`
**When** a command in the script fails
**Then** the script exits as expected (bash-compatible behavior)

### AC6: Chained Commands Use Exit Codes
**Given** commands are chained with `&&` or `||`
**When** the chain executes
**Then** short-circuit behavior works based on exit codes (0 = success, non-zero = failure)

## Technical Notes

### Current Implementation Analysis

The current `executor.py` implementation:

```python
def execute_command(command: str, last_exit_code: int = 0) -> int:
    wrapped_command = f"(exit {last_exit_code}); {command}"
    result = subprocess.run(["bash", "-c", wrapped_command])
    return result.returncode
```

And in `shell.py`:

```python
last_exit_code = 0
# ...
last_exit_code = execute_command(command, last_exit_code)
```

**What already works:**
- Exit codes are captured from commands
- Exit codes are passed to next command via `(exit N);` prefix
- The `$?` variable is set correctly for each command

**What this story validates:**
- Comprehensive test coverage for exit code scenarios
- Edge cases work correctly
- Script-level compatibility

### Why This Likely Already Works

The `bash -c` delegation pattern handles exit codes naturally:
1. `subprocess.run()` captures the exit code in `result.returncode`
2. `shell.py` tracks `last_exit_code` between commands
3. The `(exit N);` prefix ensures `$?` is correct at command start

This story is primarily **validation and testing**.

## Dependencies

- Story 1.2: Basic Interactive Shell Loop (COMPLETED)
- Story 1.3: Command Execution with Pipes and Redirects (COMPLETED)
- Story 1.4: Shell Script Execution (COMPLETED)

## Architecture Compliance

### Module Boundaries
| Module | Responsibility |
|--------|----------------|
| `executor.py` | Capture exit code from subprocess - **NO CHANGES EXPECTED** |
| `shell.py` | Track and pass last_exit_code - **NO CHANGES EXPECTED** |

### Code Patterns (from Architecture)
- PEP 8 naming: `snake_case` functions
- Standard Python exceptions
- Docstrings on all public functions

### Current Implementation Reference

**executor.py** (lines 10-32) - already captures exit codes
**shell.py** (lines 30-50) - already tracks last_exit_code

## Test Guidance

### Test File Structure

Add to `tests/test_executor.py`:

```python
# =============================================================================
# Story 1.5: Exit Code Preservation Tests
# =============================================================================


def test_exit_code_success_is_zero():
    """Test successful command returns exit code 0 (AC1)."""
    exit_code = execute_command("true")
    assert exit_code == 0


def test_exit_code_true_command():
    """Test 'true' returns 0 (AC1)."""
    result = run_bash_command("true; echo $?")
    assert result.stdout.strip() == "0"


def test_exit_code_false_is_one():
    """Test 'false' returns exit code 1 (AC2)."""
    exit_code = execute_command("false")
    assert exit_code == 1


def test_exit_code_nonexistent_file():
    """Test ls on nonexistent file returns non-zero (AC2)."""
    result = run_bash_command("ls /nonexistent_file_12345 2>/dev/null")
    assert result.returncode != 0


def test_exit_code_specific_value():
    """Test specific exit code is preserved (AC3)."""
    exit_code = execute_command("exit 42")
    assert exit_code == 42


def test_exit_code_range():
    """Test various exit codes in valid range (AC3)."""
    for code in [0, 1, 2, 127, 128, 255]:
        exit_code = execute_command(f"exit {code}")
        assert exit_code == code


def test_exit_code_available_in_next_command():
    """Test $? is available in subsequent command (AC4)."""
    # Run a command that fails, then check $? in next command
    result = run_bash_command("(exit 5); echo $?")
    assert result.stdout.strip() == "5"


def test_exit_code_chained_and_success():
    """Test && executes second command on success (AC6)."""
    result = run_bash_command('true && echo "ran"')
    assert result.stdout.strip() == "ran"


def test_exit_code_chained_and_failure():
    """Test && skips second command on failure (AC6)."""
    result = run_bash_command('false && echo "ran"')
    assert result.stdout.strip() == ""


def test_exit_code_chained_or_success():
    """Test || skips second command on success (AC6)."""
    result = run_bash_command('true || echo "ran"')
    assert result.stdout.strip() == ""


def test_exit_code_chained_or_failure():
    """Test || executes second command on failure (AC6)."""
    result = run_bash_command('false || echo "ran"')
    assert result.stdout.strip() == "ran"


def test_exit_code_pipeline_last_command():
    """Test pipeline returns exit code of last command."""
    # grep with no match returns 1
    result = run_bash_command("echo hello | grep goodbye")
    assert result.returncode == 1

    # grep with match returns 0
    result = run_bash_command("echo hello | grep hello")
    assert result.returncode == 0


def test_exit_code_script_set_e(tmp_path):
    """Test script with set -e exits on first failure (AC5)."""
    script = tmp_path / "set_e.sh"
    script.write_text("""#!/bin/bash
set -e
echo "before"
false
echo "after"
""")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    # Should print "before" but not "after" due to set -e
    assert "before" in result.stdout
    assert "after" not in result.stdout
    assert result.returncode != 0


def test_exit_code_script_no_set_e(tmp_path):
    """Test script without set -e continues after failure."""
    script = tmp_path / "no_set_e.sh"
    script.write_text("""#!/bin/bash
echo "before"
false
echo "after"
""")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    # Should print both because no set -e
    assert "before" in result.stdout
    assert "after" in result.stdout
```

### Manual Verification Steps

1. Launch aegish: `uv run aegish`
2. Run: `true; echo $?` - should print "0"
3. Run: `false; echo $?` - should print "1"
4. Run: `exit 42; echo $?` - should print "42" (in bash context)
5. Run: `ls /nonexistent 2>/dev/null; echo $?` - should print non-zero
6. Run: `true && echo "success"` - should print "success"
7. Run: `false && echo "success"` - should print nothing
8. Run: `false || echo "fallback"` - should print "fallback"

## Previous Story Intelligence

### Key Learnings from Stories 1.3 and 1.4
- The `bash -c` delegation pattern means shell features work automatically
- Focus on **validation and testing** rather than new implementation
- Comprehensive test coverage is the main deliverable
- Use `tmp_path` fixture for temporary script files

### Established Patterns
- Tests use `run_bash_command()` for capturing output
- Tests use `execute_command()` for exit code verification
- Tests are grouped with comments indicating which AC they cover
- Naming: `test_<feature>_<scenario>()`

## Definition of Done

- [x] Manual verification of all AC scenarios passes
- [x] Automated tests added for all acceptance criteria
- [x] Script with `set -e` test validates bash compatibility
- [x] All tests pass (`uv run pytest`)
- [x] No regressions in existing functionality

## Story Points

**Estimate:** Small (1-2 points)

This is primarily a validation/testing story. Exit code preservation already works via the existing implementation. The effort is in writing comprehensive tests and verifying edge cases.

## Dev Agent Record

### Context Reference
Story context provided in Technical Notes section. Exit code preservation works via bash delegation pattern.

### Agent Model Used
Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References
- All 11 new Story 1.5 tests passed on first run
- Full test suite: 51/51 tests passing
- No code changes required to executor.py or shell.py - feature works via bash delegation

### Completion Notes List
- Verified exit code preservation works via existing `bash -c` delegation pattern
- Added 11 comprehensive tests covering all 6 acceptance criteria:
  - AC1: `test_exit_code_true_via_echo`
  - AC2: `test_exit_code_false_via_echo`, `test_exit_code_nonexistent_file`, `test_exit_code_command_not_found`
  - AC3: `test_exit_code_range`, `test_exit_code_subshell`
  - AC5: `test_exit_code_script_set_e`, `test_exit_code_script_no_set_e`
  - AC6: `test_exit_code_pipeline_success`, `test_exit_code_pipeline_failure`, `test_exit_code_complex_chain`
- AC4 already covered by existing `test_execute_command_last_exit_code` from earlier stories
- No implementation changes needed - this was a validation/testing story
- All tests pass with no regressions

### File List
- `tests/test_executor.py` - Added 11 Story 1.5 tests (lines 317-389)

### Change Log
- 2026-01-28: Story 1.5 implemented - Added comprehensive exit code preservation tests validating existing functionality
