# Story 1.4: Shell Script Execution

## Status: Done

## Story

As a **sysadmin**,
I want **to execute shell scripts through aegish**,
So that **my existing automation and .sh files work transparently**.

## Epic Context

**Epic 1: Working Shell Foundation** - User can launch aegish and execute commands exactly like bash. This story validates that shell scripts work correctly through aegish.

**FRs Addressed:** FR2 (Shell script execution)

**Dependencies:** Stories 1.1-1.3 (all COMPLETED)

## Acceptance Criteria

### AC1: Direct Script Execution
**Given** a valid shell script `test.sh` exists with execute permission
**When** I run `./test.sh` through aegish
**Then** the script executes completely
**And** output is displayed to the terminal

### AC2: Bash Explicit Invocation
**Given** a valid shell script `test.sh` exists
**When** I run `bash test.sh` through aegish
**Then** the script executes without requiring execute permission

### AC3: Script Arguments
**Given** a script that uses positional parameters `$1`, `$2`, etc.
**When** I run `./script.sh arg1 arg2` through aegish
**Then** arguments are passed correctly to the script
**And** `$@` and `$*` contain the correct values

### AC4: Script with Shebang Variations
**Given** scripts with different shebangs (`#!/bin/bash`, `#!/usr/bin/env bash`, `#!/bin/sh`)
**When** executed through aegish
**Then** the correct interpreter is used

### AC5: Script Exit Codes
**Given** a script that exits with a specific code (e.g., `exit 5`)
**When** executed through aegish
**Then** the exit code is preserved and available via `$?`

## Technical Notes

### Why This Likely Already Works

The current implementation in `executor.py` uses `subprocess.run(["bash", "-c", command])`. When the user types:
- `./test.sh` - bash interprets this and executes the script
- `bash test.sh` - bash runs the script directly
- `./script.sh arg1 arg2` - bash passes arguments naturally

**Key insight from Story 1.3:** The bash delegation pattern means shell features "just work" - this story is primarily about **validation and testing**, not new code.

### Implementation Approach

1. **Verify current behavior** - Test that scripts work as expected
2. **Add comprehensive tests** - Cover all acceptance criteria
3. **Document any edge cases** - If any script scenarios fail, document and fix

### Potential Edge Cases to Test

- Scripts with spaces in filenames
- Scripts in different directories (relative/absolute paths)
- Scripts that source other files
- Scripts that read from stdin
- Scripts with here-docs
- Scripts that spawn subshells

## Dependencies

- Story 1.2: Basic Interactive Shell Loop (COMPLETED)
- Story 1.3: Command Execution with Pipes and Redirects (COMPLETED)

## Architecture Compliance

### Module Boundaries
| Module | Responsibility |
|--------|----------------|
| `executor.py` | Run `bash -c "..."`, capture output - **NO CHANGES EXPECTED** |
| `shell.py` | readline loop, prompt - **NO CHANGES EXPECTED** |

### Code Patterns (from Architecture)
- PEP 8 naming: `snake_case` functions, `PascalCase` classes
- Standard Python exceptions
- Docstrings on all public functions

### Current Implementation Reference

**executor.py** (lines 10-32):
```python
def execute_command(command: str, last_exit_code: int = 0) -> int:
    wrapped_command = f"(exit {last_exit_code}); {command}"
    result = subprocess.run(["bash", "-c", wrapped_command])
    return result.returncode
```

This ALREADY supports script execution - bash handles the script interpretation.

## Test Guidance

### Test File Structure

Add to `tests/test_executor.py`:

```python
# =============================================================================
# Story 1.4: Shell Script Execution Tests
# =============================================================================

def test_script_direct_execution(tmp_path):
    """Test ./script.sh execution (AC1)."""
    script = tmp_path / "test.sh"
    script.write_text("#!/bin/bash\necho 'hello from script'")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert result.stdout.strip() == "hello from script"
    assert result.returncode == 0


def test_script_bash_invocation(tmp_path):
    """Test bash script.sh execution (AC2)."""
    script = tmp_path / "test.sh"
    script.write_text("#!/bin/bash\necho 'bash invoked'")
    # No execute permission needed for bash script.sh
    result = run_bash_command(f"bash {script}")
    assert result.stdout.strip() == "bash invoked"


def test_script_with_arguments(tmp_path):
    """Test script receives arguments correctly (AC3)."""
    script = tmp_path / "args.sh"
    script.write_text('#!/bin/bash\necho "arg1=$1 arg2=$2"')
    script.chmod(0o755)
    result = run_bash_command(f"{script} hello world")
    assert result.stdout.strip() == "arg1=hello arg2=world"


def test_script_all_args(tmp_path):
    """Test $@ contains all arguments (AC3)."""
    script = tmp_path / "allargs.sh"
    script.write_text('#!/bin/bash\necho "$@"')
    script.chmod(0o755)
    result = run_bash_command(f"{script} a b c d")
    assert result.stdout.strip() == "a b c d"


def test_script_exit_code(tmp_path):
    """Test script exit code is preserved (AC5)."""
    script = tmp_path / "exitcode.sh"
    script.write_text("#!/bin/bash\nexit 42")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert result.returncode == 42


def test_script_exit_code_zero(tmp_path):
    """Test successful script returns 0 (AC5)."""
    script = tmp_path / "success.sh"
    script.write_text("#!/bin/bash\necho 'success'\nexit 0")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert result.returncode == 0


def test_script_env_shebang(tmp_path):
    """Test #!/usr/bin/env bash shebang (AC4)."""
    script = tmp_path / "envbash.sh"
    script.write_text("#!/usr/bin/env bash\necho 'env bash'")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert result.stdout.strip() == "env bash"


def test_script_sh_shebang(tmp_path):
    """Test #!/bin/sh shebang (AC4)."""
    script = tmp_path / "sh.sh"
    script.write_text("#!/bin/sh\necho 'posix sh'")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert result.stdout.strip() == "posix sh"


def test_script_with_spaces_in_path(tmp_path):
    """Test script in path with spaces (edge case)."""
    dir_with_spaces = tmp_path / "my scripts"
    dir_with_spaces.mkdir()
    script = dir_with_spaces / "test.sh"
    script.write_text("#!/bin/bash\necho 'spaces work'")
    script.chmod(0o755)
    # Must quote the path
    result = run_bash_command(f'"{script}"')
    assert result.stdout.strip() == "spaces work"


def test_script_with_stdin(tmp_path):
    """Test script that reads from stdin (edge case)."""
    script = tmp_path / "stdin.sh"
    script.write_text("#!/bin/bash\nread line\necho \"got: $line\"")
    script.chmod(0o755)
    result = run_bash_command(f'echo "input" | {script}')
    assert result.stdout.strip() == "got: input"


def test_script_sources_other_file(tmp_path):
    """Test script that sources another file (edge case)."""
    lib = tmp_path / "lib.sh"
    lib.write_text("MYVAR='from lib'")
    script = tmp_path / "main.sh"
    script.write_text(f'#!/bin/bash\nsource {lib}\necho $MYVAR')
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert result.stdout.strip() == "from lib"


def test_script_with_heredoc(tmp_path):
    """Test script with here-doc (edge case)."""
    script = tmp_path / "heredoc.sh"
    script.write_text('''#!/bin/bash
cat <<EOF
line1
line2
EOF
''')
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert "line1" in result.stdout
    assert "line2" in result.stdout
```

### Manual Verification Steps

1. Create test script: `echo -e '#!/bin/bash\necho "test"' > /tmp/test.sh && chmod +x /tmp/test.sh`
2. In aegish: `/tmp/test.sh` - should print "test"
3. In aegish: `bash /tmp/test.sh` - should print "test"
4. Create args script: `echo -e '#!/bin/bash\necho "args: $1 $2"' > /tmp/args.sh && chmod +x /tmp/args.sh`
5. In aegish: `/tmp/args.sh hello world` - should print "args: hello world"
6. Create exit script: `echo -e '#!/bin/bash\nexit 5' > /tmp/exit5.sh && chmod +x /tmp/exit5.sh`
7. In aegish: `/tmp/exit5.sh; echo $?` - should print "5"

## Previous Story Intelligence

### Key Learnings from Story 1.3
- The `bash -c` delegation pattern means most shell features work automatically
- Focus on **validation and testing** rather than new implementation
- Comprehensive test coverage is the main deliverable
- Edge cases reveal behavior - document any surprises

### Established Patterns
- Tests use `run_bash_command()` for capturing output
- Tests use `tmp_path` fixture for temporary files
- Tests are grouped with comments indicating which AC they cover
- Naming: `test_<feature>_<scenario>()`

## Definition of Done

- [x] Manual verification of all AC scenarios passes
- [x] Automated tests added for all acceptance criteria
- [x] Edge case tests added (spaces, stdin, sourcing, heredoc)
- [x] All tests pass (`uv run pytest`)
- [x] No regressions in existing functionality

## Story Points

**Estimate:** Small (1-2 points)

This is primarily a validation/testing story. The feature already works via bash delegation. The effort is in writing comprehensive tests and verifying edge cases.

## Dev Agent Record

### Context Reference
Story context provided in Dev Notes section with bash delegation pattern insight from Story 1.3.

### Agent Model Used
Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References
- All 12 new tests passed on first run
- Full test suite: 40/40 tests passing
- No code changes required to executor.py or shell.py - feature works via bash delegation

### Completion Notes List
- Verified shell script execution works via existing `bash -c` delegation pattern
- Added 12 comprehensive tests covering all 5 acceptance criteria
- Added 4 edge case tests (spaces in path, stdin, sourcing, heredoc)
- No implementation changes needed - this was a validation/testing story
- All tests pass with no regressions

### File List
- `tests/test_executor.py` - Added 12 Story 1.4 tests (lines 198-276)

### Change Log
- 2026-01-28: Story 1.4 implemented - Added comprehensive shell script execution tests validating existing functionality
