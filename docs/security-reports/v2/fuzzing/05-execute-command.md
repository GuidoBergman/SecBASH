# Fuzzing Report: `execute_command()`

## Overview

- **Date**: 2026-02-15
- **Target**: `src/aegish/executor.py::execute_command()`
- **Findings**: 5

## Executive Summary

The `execute_command()` function wraps user commands as `f"(exit {last_exit_code}); {command}"` and passes to `bash -c`. The f-string construction is safe for integer inputs (Python int formatting produces only digits and minus sign). The security gate is entirely upstream (LLM validator).

Key findings relate to environment variable leakage through `_build_safe_env()` and the critical importance of BASH_ENV stripping.

## Findings

### HIGH

#### BASH_ENV is processed for non-interactive bash -c

- **Input**: BASH_ENV=/tmp/tmp061g8b3q.sh
- **Behavior**: --norc: True, plain: True
- **Impact**: _build_safe_env() stripping BASH_ENV is ESSENTIAL. --norc/--noprofile alone do NOT prevent BASH_ENV loading.

#### LD_PRELOAD passes through _build_safe_env()

- **Input**: LD_PRELOAD=/tmp/evil.so
- **Behavior**: Present in sanitized env
- **Impact**: Shared library injection into subprocess

### MEDIUM

#### SHELLOPTS passes through _build_safe_env()

- **Input**: SHELLOPTS=test_value
- **Behavior**: Present in sanitized env
- **Impact**: SHELLOPTS can modify bash behavior in subprocess

#### PS4 passes through _build_safe_env()

- **Input**: PS4=test_value
- **Behavior**: Present in sanitized env
- **Impact**: PS4 can modify bash behavior in subprocess

#### PS4 command substitution executes with SHELLOPTS=xtrace

- **Input**: SHELLOPTS=xtrace + PS4='$(cmd)'
- **Behavior**: stderr contains injected marker
- **Impact**: Arbitrary command execution via env vars if both SHELLOPTS and PS4 leak

## Analysis

### f-string Construction

The `f"(exit {last_exit_code})"` pattern is safe because:
- `last_exit_code` is always `int` (from `subprocess.run().returncode`)
- Python `int.__format__` produces only digits and optional minus sign
- No shell metacharacters can be injected via the integer

### BASH_ENV is the Critical Vector

`--norc` and `--noprofile` do NOT prevent `BASH_ENV` loading for non-interactive `bash -c` invocations. The `_build_safe_env()` stripping of `BASH_ENV` is the actual defense.

### Return Code Handling

- Bash truncates exit codes modulo 256
- Negative values from signal kills work correctly
- Very large Python ints are handled by bash (error, not injection)

## Recommendations

1. **Expand `_build_safe_env()` blocklist** (see report 02)
2. **Validate `last_exit_code` range** to 0-255 before f-string formatting
3. **Consider sandboxing** to limit subprocess capabilities
