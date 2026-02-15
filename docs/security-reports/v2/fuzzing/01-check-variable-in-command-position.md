# Fuzzing Report: `_check_variable_in_command_position()`

## Overview

- **Date**: 2026-02-15
- **Target**: `src/aegish/validator.py::_check_variable_in_command_position()`
- **Total tests**: 82
- **Findings**: 48

| Severity | Count |
|----------|-------|
| CRITICAL | 31 |
| HIGH | 2 |
| MEDIUM | 15 |

## Executive Summary

The `_check_variable_in_command_position()` function has a broad `except Exception` handler (line 117) that silently swallows all bashlex parse errors, returning `None` (i.e., 'safe'). Any command that crashes bashlex bypasses the static validator.

The AST walker (`_find_var_in_command_position`) only handles: `pipeline`, `command`, `list`, and `compound`. Control-flow nodes (`for`, `if`, `while`, `until`) inside `compound.list` are iterated but silently skipped.

## AST Node Kind Gaps

**Count: 4**

### 1. [CRITICAL] `for i in bash; do $i; done`

- **Input**: `for i in bash; do $i; done`
- **Expected**: WARN
- **Actual**: None
- **Security Impact**: AST path 'compound->for->list' NOT traversed

### 2. [CRITICAL] `while true; do X=bash; $X; done`

- **Input**: `while true; do X=bash; $X; done`
- **Expected**: WARN
- **Actual**: None
- **Security Impact**: AST path 'compound->while->list' NOT traversed

### 3. [CRITICAL] `if true; then X=bash; $X; fi`

- **Input**: `if true; then X=bash; $X; fi`
- **Expected**: WARN
- **Actual**: None
- **Security Impact**: AST path 'compound->if->list' NOT traversed

### 4. [CRITICAL] `X=bash; until $X; do echo; done`

- **Input**: `X=bash; until $X; do echo; done`
- **Expected**: WARN
- **Actual**: None
- **Security Impact**: AST path 'compound->until' NOT traversed

## False Negatives (Parsed but Undetected)

**Count: 15**

### 1. [CRITICAL] `for i in bash; do $i; done`

- **Input**: `for i in bash; do $i; done`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Variable as command in for loop body

### 2. [CRITICAL] `if true; then $CMD; fi`

- **Input**: `if true; then $CMD; fi`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Variable as command in if-then body

### 3. [CRITICAL] `if false; then echo ok; else $CMD; fi`

- **Input**: `if false; then echo ok; else $CMD; fi`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Variable as command in else branch

### 4. [CRITICAL] `while true; do $CMD; break; done`

- **Input**: `while true; do $CMD; break; done`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Variable as command in while loop

### 5. [CRITICAL] `until false; do $CMD; break; done`

- **Input**: `until false; do $CMD; break; done`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Variable as command in until loop

### 6. [CRITICAL] `CMD=bash; for i in 1; do $CMD; done`

- **Input**: `CMD=bash; for i in 1; do $CMD; done`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Assignment then for-loop execution

### 7. [CRITICAL] `CMD=bash; if true; then $CMD; fi`

- **Input**: `CMD=bash; if true; then $CMD; fi`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Assignment then if-then execution

### 8. [CRITICAL] `CMD=bash; while true; do $CMD; break; done`

- **Input**: `CMD=bash; while true; do $CMD; break; done`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Assignment then while-loop execution

### 9. [CRITICAL] `if true; then for i in 1; do $CMD; done; fi`

- **Input**: `if true; then for i in 1; do $CMD; done; fi`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Nested for inside if

### 10. [CRITICAL] `while true; do if true; then $CMD; fi; break; done`

- **Input**: `while true; do if true; then $CMD; fi; break; done`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Nested if inside while

### 11. [CRITICAL] `f() { $CMD; }`

- **Input**: `f() { $CMD; }`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Variable as command in function body

### 12. [CRITICAL] `$CMD`

- **Input**: `$CMD`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Bare variable as command without visible assignment

### 13. [CRITICAL] `export CMD=bash; $CMD`

- **Input**: `export CMD=bash; $CMD`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Export as assignment, then variable as command

### 14. [CRITICAL] `true && $CMD`

- **Input**: `true && $CMD`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Variable as command after &&

### 15. [CRITICAL] `false || $CMD`

- **Input**: `false || $CMD`
- **Expected**: WARN
- **Actual**: None (not detected)
- **Security Impact**: AST walker miss: Variable as command after ||

## Malicious Command Evasions

**Count: 6**

### 1. [CRITICAL] `function f { X=bash; $X; }; f`

- **Input**: `function f { X=bash; $X; }; f`
- **Expected**: WARN
- **Actual**: None (parsed but not detected)
- **Security Impact**: Malicious evasion: function-alt-exec

### 2. [CRITICAL] `X='rm -rf /'; eval $X`

- **Input**: `X='rm -rf /'; eval $X`
- **Expected**: WARN
- **Actual**: None (parsed but not detected)
- **Security Impact**: Malicious evasion: eval-constructed

### 3. [CRITICAL] `X=/tmp/malicious.sh; source $X`

- **Input**: `X=/tmp/malicious.sh; source $X`
- **Expected**: WARN
- **Actual**: None (parsed but not detected)
- **Security Impact**: Malicious evasion: source-var

### 4. [CRITICAL] `X=/tmp/malicious.sh; . $X`

- **Input**: `X=/tmp/malicious.sh; . $X`
- **Expected**: WARN
- **Actual**: None (parsed but not detected)
- **Security Impact**: Malicious evasion: dot-var

### 5. [CRITICAL] `X=bash; exec $X`

- **Input**: `X=bash; exec $X`
- **Expected**: WARN
- **Actual**: None (parsed but not detected)
- **Security Impact**: Malicious evasion: exec-var

### 6. [CRITICAL] `X=bash; $(${X})`

- **Input**: `X=bash; $(${X})`
- **Expected**: WARN
- **Actual**: None (parsed but not detected)
- **Security Impact**: Malicious evasion: compound-cmd-sub

## Malicious Crasher Bypasses

**Count: 7**

### 1. [CRITICAL] `case x in x) X=bash; $X;; esac`

- **Input**: `case x in x) X=bash; $X;; esac`
- **Expected**: WARN
- **Actual**: None (crash: NotImplementedError)
- **Security Impact**: Malicious bypass via crash: case-assign-exec
- **Exception**: `NotImplementedError: type = {pattern}, token = {x}`

### 2. [CRITICAL] `X=bash; $X << 'EOF'`

- **Input**: `X=bash; $X << 'EOF'`
- **Expected**: WARN
- **Actual**: None (crash: ParsingError)
- **Security Impact**: Malicious bypass via crash: heredoc-unclosed-var
- **Exception**: `ParsingError: here-document at line 0 delimited by end-of-file (wanted "'EOF'") (position 20)`

### 3. [CRITICAL] `arr=(bash); ${arr[0]}`

- **Input**: `arr=(bash); ${arr[0]}`
- **Expected**: WARN
- **Actual**: None (crash: ParsingError)
- **Security Impact**: Malicious bypass via crash: array-exec
- **Exception**: `ParsingError: unexpected token '(' (position 4)`

### 4. [CRITICAL] `X=bash; $X +(a|b)`

- **Input**: `X=bash; $X +(a|b)`
- **Expected**: WARN
- **Actual**: None (crash: ParsingError)
- **Security Impact**: Malicious bypass via crash: extglob-var
- **Exception**: `ParsingError: unexpected token '(' (position 12)`

### 5. [HIGH] `coproc $X`

- **Input**: `coproc $X`
- **Expected**: WARN
- **Actual**: None (crash: NotImplementedError)
- **Security Impact**: Malicious bypass via crash: coproc-var
- **Exception**: `NotImplementedError: type = {coproc}, token = {coproc}, parts = {[WordNode(parts=[ParameterNode(pos=(7, 9) value='X')] pos=(7, 9) word='$X')]}`

### 6. [CRITICAL] `X=bash; select i in a; do $X; done`

- **Input**: `X=bash; select i in a; do $X; done`
- **Expected**: WARN
- **Actual**: None (crash: NotImplementedError)
- **Security Impact**: Malicious bypass via crash: select-var
- **Exception**: `NotImplementedError: type = {select command}, token = {select}, parts = {i}`

### 7. [CRITICAL] `for ((i=0;i<1;i++)); do X=bash; $X; done`

- **Input**: `for ((i=0;i<1;i++)); do X=bash; $X; done`
- **Expected**: WARN
- **Actual**: None (crash: ParsingError)
- **Security Impact**: Malicious bypass via crash: arith-for-exec
- **Exception**: `ParsingError: unexpected token '(' (position 4)`

## Evasion via Parser Crash

**Count: 1**

### 1. [HIGH] `case x in x) $CMD;; esac`

- **Input**: `case x in x) $CMD;; esac`
- **Expected**: WARN
- **Actual**: None (crash: NotImplementedError)
- **Security Impact**: Evasion via parser crash: Variable as command in case branch
- **Exception**: `NotImplementedError: type = {pattern}, token = {x}`

## General Parser Crashes

**Count: 15**

### 1. [MEDIUM] `X=bash; $X '`

- **Input**: `X=bash; $X '`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: MatchedPairError
- **Security Impact**: Parser crash, falls to LLM: unclosed-single-quote
- **Exception**: `MatchedPairError: unexpected EOF while looking for matching "'" (position 12)`

### 2. [MEDIUM] `X=bash; $X "`

- **Input**: `X=bash; $X "`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: MatchedPairError
- **Security Impact**: Parser crash, falls to LLM: unclosed-double-quote
- **Exception**: `MatchedPairError: unexpected EOF while looking for matching '"' (position 12)`

### 3. [MEDIUM] `X=bash; $X \``

- **Input**: `X=bash; $X \``
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: MatchedPairError
- **Security Impact**: Parser crash, falls to LLM: unclosed-backtick
- **Exception**: `MatchedPairError: unexpected EOF while looking for matching '\`' (position 12)`

### 4. [MEDIUM] `X=bash; $X (`

- **Input**: `X=bash; $X (`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: ParsingError
- **Security Impact**: Parser crash, falls to LLM: unmatched-paren
- **Exception**: `ParsingError: unexpected token '\n' (position 12)`

### 5. [MEDIUM] `arr=(bash); ${arr[0]}`

- **Input**: `arr=(bash); ${arr[0]}`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: ParsingError
- **Security Impact**: Parser crash, falls to LLM: array-syntax
- **Exception**: `ParsingError: unexpected token '(' (position 4)`

### 6. [MEDIUM] `X=bash; $X +(a|b)`

- **Input**: `X=bash; $X +(a|b)`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: ParsingError
- **Security Impact**: Parser crash, falls to LLM: extglob
- **Exception**: `ParsingError: unexpected token '(' (position 12)`

### 7. [MEDIUM] `coproc X=bash; $X`

- **Input**: `coproc X=bash; $X`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: NotImplementedError
- **Security Impact**: Parser crash, falls to LLM: coproc
- **Exception**: `NotImplementedError: type = {coproc}, token = {coproc}, parts = {[AssignmentNode(parts=[] pos=(7, 13) word='X=bash')]}`

### 8. [MEDIUM] `select i in a; do $CMD; done`

- **Input**: `select i in a; do $CMD; done`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: NotImplementedError
- **Security Impact**: Parser crash, falls to LLM: select
- **Exception**: `NotImplementedError: type = {select command}, token = {select}, parts = {i}`

### 9. [MEDIUM] `for ((i=0;i<1;i++)); do $CMD; done`

- **Input**: `for ((i=0;i<1;i++)); do $CMD; done`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: ParsingError
- **Security Impact**: Parser crash, falls to LLM: arith-for
- **Exception**: `ParsingError: unexpected token '(' (position 4)`

### 10. [MEDIUM] `\t`

- **Input**: `\t`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: AttributeError
- **Security Impact**: Parser crash, falls to LLM: tab-only
- **Exception**: `AttributeError: 'str' object has no attribute 'kind'`

### 11. [MEDIUM] `X=bash; $X << 'EOF'`

- **Input**: `X=bash; $X << 'EOF'`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: ParsingError
- **Security Impact**: Parser crash, falls to LLM: heredoc-unclosed
- **Exception**: `ParsingError: here-document at line 0 delimited by end-of-file (wanted "'EOF'") (position 20)`

### 12. [MEDIUM] `X=bash;; $X`

- **Input**: `X=bash;; $X`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: ParsingError
- **Security Impact**: Parser crash, falls to LLM: double-semicolon
- **Exception**: `ParsingError: unexpected token ';;' (position 6)`

### 13. [MEDIUM] `&`

- **Input**: `&`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: ParsingError
- **Security Impact**: Parser crash, falls to LLM: ampersand-only
- **Exception**: `ParsingError: unexpected token '&' (position 0)`

### 14. [MEDIUM] `|`

- **Input**: `|`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: ParsingError
- **Security Impact**: Parser crash, falls to LLM: pipe-only
- **Exception**: `ParsingError: unexpected token '|' (position 0)`

### 15. [MEDIUM] `X=bash ||| $X`

- **Input**: `X=bash ||| $X`
- **Expected**: Parse or handle gracefully
- **Actual**: Crash: ParsingError
- **Security Impact**: Parser crash, falls to LLM: triple-pipe
- **Exception**: `ParsingError: unexpected token '|' (position 9)`

## Recommendations

### 1. CRITICAL: Handle `for`, `if`, `while`, `until` in AST walker

```python
elif node.kind in ('for', 'if', 'while', 'until'):
    for part in node.parts:
        if part.kind == 'list':
            local_assign = has_assignment or any(
                sub.kind == 'assignment'
                for p in part.parts if p.kind == 'command'
                for sub in p.parts)
            result = _find_var_in_command_position(part.parts, local_assign)
            if result is not None:
                return result
```

### 2. HIGH: Narrow the exception handler

Replace `except Exception` with specific bashlex exceptions.

### 3. MEDIUM: Add generic recursive fallback

```python
else:
    for attr in ('parts', 'list'):
        children = getattr(node, attr, None)
        if children:
            result = _find_var_in_command_position(children, has_assignment)
            if result is not None:
                return result
```

### 4. MEDIUM: Remove `has_assignment` requirement for `command` branch

A bare `$CMD` is suspicious regardless of visible assignments.
