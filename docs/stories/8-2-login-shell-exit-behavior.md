# Story 8.2: Login Shell Exit Behavior

Status: done

## Story

As a **sysadmin**,
I want **production mode exit to terminate the session and development mode exit to warn**,
So that **there is no parent shell to escape to in production, while developers can exit normally**.

## Acceptance Criteria

1. Production mode + `exit`: process terminates (exit code 0), message "Session terminated." displayed
2. Production mode + Ctrl+D: same as `exit`
3. Development mode + `exit`: shell loop ends, message "WARNING: Leaving aegish. The parent shell is NOT security-monitored." displayed
4. Development mode + Ctrl+D: same as development `exit`

## Tasks / Subtasks

- [ ] Task 1: Update exit handling in `src/aegish/shell.py`
  - [ ] 1.1: Import `sys` for `sys.exit(0)` in production mode
  - [ ] 1.2: Update `exit` command handler to branch on `get_mode()`
  - [ ] 1.3: Update `EOFError` handler (Ctrl+D) to branch on `get_mode()`
  - [ ] 1.4: Production: print "Session terminated." then `sys.exit(0)`
  - [ ] 1.5: Development: print warning then `break`
- [ ] Task 2: Add tests in `tests/test_shell.py`
  - [ ] 2.1: Test production `exit` calls `sys.exit(0)` with "Session terminated."
  - [ ] 2.2: Test production Ctrl+D calls `sys.exit(0)`
  - [ ] 2.3: Test development `exit` prints warning, returns normally
  - [ ] 2.4: Test development Ctrl+D prints warning, returns normally

## Dev Notes

### Implementation

`get_mode()` already exists in config.py and is imported in shell.py (Story 8.1 done). Only `shell.py` needs changes.

Current exit handling: `exit` at ~line 152 with `break`, Ctrl+D at ~line 204 with `break`. Both need mode branching.

```python
import sys

# exit handler:
if command.strip() == "exit":
    if get_mode() == "production":
        print("Session terminated.")
        sys.exit(0)
    else:
        print("WARNING: Leaving aegish. The parent shell is NOT security-monitored.")
        break

# EOFError handler:
except EOFError:
    print()
    if get_mode() == "production":
        print("Session terminated.")
        sys.exit(0)
    else:
        print("WARNING: Leaving aegish. The parent shell is NOT security-monitored.")
        break
```

**Why `sys.exit(0)`:** Makes intent explicit that entire process terminates. `atexit` handlers (history) still run.

### Testing

Production tests use `pytest.raises(SystemExit)`. Development tests verify normal return.
Mock pattern: `patch("aegish.shell.get_mode", return_value="production")`

### Files

- Modify: `src/aegish/shell.py`
- Modify: `tests/test_shell.py` (add `TestExitBehavior` class)
