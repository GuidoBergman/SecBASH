# Fuzzing Report: `_find_var_in_command_position()`

## Summary

- **Total tests**: 38
- **Detected**: 9
- **Evasions**: 18
- **Parse errors**: 4
- **False positives**: 0

The function only handles `pipeline`, `command`, `list`, and `compound` node kinds. Control-flow nodes (`for`, `if`, `while`, `until`) are silently ignored.

## Category Breakdown

| Category | Total | Detected | Evasions | Parse Errors |
|----------|-------|----------|----------|--------------|
| for_loop | 3 | 0 | 2 | 0 |
| if_stmt | 4 | 0 | 3 | 0 |
| while_loop | 1 | 0 | 1 | 0 |
| until_loop | 1 | 0 | 1 | 0 |
| subshell | 1 | 1 | 0 | 0 |
| brace_group | 1 | 1 | 0 | 0 |
| pipeline | 3 | 3 | 0 | 0 |
| classic | 2 | 2 | 0 | 0 |
| has_assignment | 2 | 0 | 2 | 0 |
| logical_ops | 3 | 1 | 2 | 0 |
| nested | 4 | 0 | 4 | 0 |
| evasion | 2 | 0 | 2 | 0 |
| function | 1 | 0 | 1 | 0 |
| safe | 5 | 0 | 0 | 0 |
| crasher | 5 | 1 | 0 | 4 |

## Evasion Details

**18 commands evade detection.**

### FOR-01: `for i in bash; do \$i; done`

- **Category**: for_loop
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, compound, for, list, operator, parameter, reservedword, word
- **Notes**: Variable from for-loop var used as command
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
compound
  for
    reservedword [for]
    word [i]
    reservedword [in]
    word [bash]
    reservedword [;]
    reservedword [do]
    list
      command
        word [$i]
          parameter
      operator
    reservedword [done]
```

### FOR-02: `CMD=bash; for i in 1; do \$CMD; done`

- **Category**: for_loop
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: assignment, command, compound, for, list, operator, parameter, reservedword, word
- **Notes**: Assignment + for loop execution
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
list
  command
    assignment [CMD=bash]
  operator
  compound
    for
      reservedword [for]
      word [i]
      reservedword [in]
      word [1]
      reservedword [;]
      reservedword [do]
      list
        command
          word [$CMD]
            parameter
        operator
      reservedword [done]
```

### IF-01: `if true; then \$CMD; fi`

- **Category**: if_stmt
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, compound, if, list, operator, parameter, reservedword, word
- **Notes**: Variable as command in then-branch
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
compound
  if
    reservedword [if]
    list
      command
        word [true]
      operator
    reservedword [then]
    list
      command
        word [$CMD]
          parameter
      operator
    reservedword [fi]
```

### IF-02: `if false; then echo ok; else \$CMD; fi`

- **Category**: if_stmt
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, compound, if, list, operator, parameter, reservedword, word
- **Notes**: Variable as command in else-branch
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
compound
  if
    reservedword [if]
    list
      command
        word [false]
      operator
    reservedword [then]
    list
      command
        word [echo]
        word [ok]
      operator
    reservedword [else]
    list
      command
        word [$CMD]
          parameter
      operator
    reservedword [fi]
```

### IF-03: `CMD=bash; if true; then \$CMD; fi`

- **Category**: if_stmt
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: assignment, command, compound, if, list, operator, parameter, reservedword, word
- **Notes**: Assignment + if execution
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
list
  command
    assignment [CMD=bash]
  operator
  compound
    if
      reservedword [if]
      list
        command
          word [true]
        operator
      reservedword [then]
      list
        command
          word [$CMD]
            parameter
        operator
      reservedword [fi]
```

### WHILE-01: `while true; do \$CMD; break; done`

- **Category**: while_loop
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, compound, list, operator, parameter, reservedword, while, word
- **Notes**: Variable as command in while body
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
compound
  while
    reservedword [while]
    list
      command
        word [true]
      operator
    reservedword [do]
    list
      command
        word [$CMD]
          parameter
      operator
      command
        word [break]
      operator
    reservedword [done]
```

### UNTIL-01: `until false; do \$CMD; break; done`

- **Category**: until_loop
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, compound, list, operator, parameter, reservedword, until, word
- **Notes**: Variable as command in until body
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
compound
  until
    reservedword [until]
    list
      command
        word [false]
      operator
    reservedword [do]
    list
      command
        word [$CMD]
          parameter
      operator
      command
        word [break]
      operator
    reservedword [done]
```

### ASSIGN-01: `\$CMD`

- **Category**: has_assignment
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, parameter, word
- **Notes**: Bare variable as command, no visible assignment
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
command
  word [$CMD]
    parameter
```

### ASSIGN-02: `export CMD=bash; \$CMD`

- **Category**: has_assignment
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, list, operator, parameter, word
- **Notes**: Export + execution
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
list
  command
    word [export]
    word [CMD=bash]
  operator
  command
    word [$CMD]
      parameter
```

### LOGIC-01: `true && \$CMD`

- **Category**: logical_ops
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, list, operator, parameter, word
- **Notes**: Variable after &&
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
list
  command
    word [true]
  operator
  command
    word [$CMD]
      parameter
```

### LOGIC-02: `false \|\| \$CMD`

- **Category**: logical_ops
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, list, operator, parameter, word
- **Notes**: Variable after ||
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
list
  command
    word [false]
  operator
  command
    word [$CMD]
      parameter
```

### NEST-01: `for i in 1; do for j in 1; do \$CMD; done; done`

- **Category**: nested
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, compound, for, list, operator, parameter, reservedword, word
- **Notes**: Nested for loops
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
compound
  for
    reservedword [for]
    word [i]
    reservedword [in]
    word [1]
    reservedword [;]
    reservedword [do]
    list
      compound
        for
          reservedword [for]
          word [j]
          reservedword [in]
          word [1]
          reservedword [;]
          reservedword [do]
          list
            command
              word [$CMD]
                parameter
            operator
          reservedword [done]
      operator
    reservedword [done]
```

### NEST-02: `if true; then for i in 1; do \$CMD; done; fi`

- **Category**: nested
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, compound, for, if, list, operator, parameter, reservedword, word
- **Notes**: If wrapping for
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
compound
  if
    reservedword [if]
    list
      command
        word [true]
      operator
    reservedword [then]
    list
      compound
        for
          reservedword [for]
          word [i]
          reservedword [in]
          word [1]
          reservedword [;]
          reservedword [do]
          list
            command
              word [$CMD]
                parameter
            operator
          reservedword [done]
      operator
    reservedword [fi]
```

### NEST-03: `{ for i in 1; do \$CMD; done; }`

- **Category**: nested
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, compound, for, list, operator, parameter, reservedword, word
- **Notes**: Brace wrapping for
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
compound
  reservedword [{]
  list
    compound
      for
        reservedword [for]
        word [i]
        reservedword [in]
        word [1]
        reservedword [;]
        reservedword [do]
        list
          command
            word [$CMD]
              parameter
          operator
        reservedword [done]
    operator
  reservedword [}]
```

### NEST-04: `(if true; then \$CMD; fi)`

- **Category**: nested
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, compound, if, list, operator, parameter, reservedword, word
- **Notes**: Subshell wrapping if
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
compound
  reservedword [(]
  compound
    if
      reservedword [if]
      list
        command
          word [true]
        operator
      reservedword [then]
      list
        command
          word [$CMD]
            parameter
        operator
      reservedword [fi]
  reservedword [)]
```

### EVADE-01: `CMD=bash; eval \$CMD`

- **Category**: evasion
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: assignment, command, list, operator, parameter, word
- **Notes**: eval with variable arg
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
list
  command
    assignment [CMD=bash]
  operator
  command
    word [eval]
    word [$CMD]
      parameter
```

### EVADE-02: `CMD=bash; exec \$CMD`

- **Category**: evasion
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: assignment, command, list, operator, parameter, word
- **Notes**: exec with variable arg
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
list
  command
    assignment [CMD=bash]
  operator
  command
    word [exec]
    word [$CMD]
      parameter
```

### FUNC-01: `f() { \$CMD; }`

- **Category**: function
- **Expected**: Detected
- **Actual**: Not detected (evasion)
- **AST kinds**: command, compound, function, list, operator, parameter, reservedword, word
- **Notes**: Variable in function body
- **Security impact**: Attacker can execute arbitrary commands via this construct

```
function
  word [f]
  reservedword [(]
  reservedword [)]
  compound
    reservedword [{]
    list
      command
        word [$CMD]
          parameter
      operator
    reservedword [}]
  compound
    reservedword [{]
    list
      command
        word [$CMD]
          parameter
      operator
    reservedword [}]
```

## Root Cause Analysis

### Unhandled Node Kinds

- `for`
- `function`
- `if`
- `until`
- `while`

### The `has_assignment` Asymmetry

- **`pipeline` branch**: No `has_assignment` required
- **`command` branch**: Requires `has_assignment=True`
- A bare `$CMD` is not flagged, but `echo | $CMD` is.

## Parse Errors

- `arr=(bash); ${arr[0]}`: `ParsingError: unexpected token '(' (position 4)` (SHOULD DETECT)
- `case x in x) $CMD;; esac`: `NotImplementedError: type = {pattern}, token = {x}` (SHOULD DETECT)
- `select i in a; do $CMD; done`: `NotImplementedError: type = {select command}, token = {select}, parts = {i}` (SHOULD DETECT)
- `for ((i=0;i<1;i++)); do $CMD; done`: `ParsingError: unexpected token '(' (position 4)` (SHOULD DETECT)

## Recommendations

### 1. Handle all control-flow node kinds

```python
elif node.kind in ("for", "if", "while", "until"):
    for part in node.parts:
        if part.kind == "list":
            result = _find_var_in_command_position(part.parts, has_assignment)
            if result is not None:
                return result
```

### 2. Add generic recursive fallback

### 3. Remove `has_assignment` requirement

### 4. Handle parse failures conservatively


## Full Results

| ID | Category | Command | Expected | Actual | Result |
|---|---|---|---|---|---|
| FOR-01 | for_loop | `for i in bash; do \$i; done` | Detect | None | **EVASION** |
| FOR-02 | for_loop | `CMD=bash; for i in 1; do \$CMD; done` | Detect | None | **EVASION** |
| FOR-03 | for_loop | `for i in 1 2 3; do echo \$i; done` | Safe | None | PASS |
| IF-01 | if_stmt | `if true; then \$CMD; fi` | Detect | None | **EVASION** |
| IF-02 | if_stmt | `if false; then echo ok; else \$CMD; fi` | Detect | None | **EVASION** |
| IF-03 | if_stmt | `CMD=bash; if true; then \$CMD; fi` | Detect | None | **EVASION** |
| IF-04 | if_stmt | `if true; then echo ok; fi` | Safe | None | PASS |
| WHILE-01 | while_loop | `while true; do \$CMD; break; done` | Detect | None | **EVASION** |
| UNTIL-01 | until_loop | `until false; do \$CMD; break; done` | Detect | None | **EVASION** |
| SUB-01 | subshell | `(CMD=bash; \$CMD)` | Detect | Detected | PASS |
| BRACE-01 | brace_group | `{ CMD=bash; \$CMD; }` | Detect | Detected | PASS |
| PIPE-01 | pipeline | `echo hi \| \$CMD` | Detect | Detected | PASS |
| PIPE-02 | pipeline | `\$CMD \| grep foo` | Detect | Detected | PASS |
| PIPE-03 | pipeline | `echo \| \$CMD \| grep` | Detect | Detected | PASS |
| CLASSIC-01 | classic | `a=ba; b=sh; \$a\$b` | Detect | Detected | PASS |
| CLASSIC-02 | classic | `X=bash; \$X` | Detect | Detected | PASS |
| ASSIGN-01 | has_assignment | `\$CMD` | Detect | None | **EVASION** |
| ASSIGN-02 | has_assignment | `export CMD=bash; \$CMD` | Detect | None | **EVASION** |
| LOGIC-01 | logical_ops | `true && \$CMD` | Detect | None | **EVASION** |
| LOGIC-02 | logical_ops | `false \|\| \$CMD` | Detect | None | **EVASION** |
| LOGIC-03 | logical_ops | `CMD=bash; true && \$CMD` | Detect | Detected | PASS |
| NEST-01 | nested | `for i in 1; do for j in 1; do \$CMD; done; done` | Detect | None | **EVASION** |
| NEST-02 | nested | `if true; then for i in 1; do \$CMD; done; fi` | Detect | None | **EVASION** |
| NEST-03 | nested | `{ for i in 1; do \$CMD; done; }` | Detect | None | **EVASION** |
| NEST-04 | nested | `(if true; then \$CMD; fi)` | Detect | None | **EVASION** |
| EVADE-01 | evasion | `CMD=bash; eval \$CMD` | Detect | None | **EVASION** |
| EVADE-02 | evasion | `CMD=bash; exec \$CMD` | Detect | None | **EVASION** |
| FUNC-01 | function | `f() { \$CMD; }` | Detect | None | **EVASION** |
| SAFE-01 | safe | `echo hello` | Safe | None | PASS |
| SAFE-02 | safe | `ls -la /home` | Safe | None | PASS |
| SAFE-03 | safe | `cat /etc/hostname` | Safe | None | PASS |
| SAFE-04 | safe | `echo \$HOME` | Safe | None | PASS |
| SAFE-05 | safe | `X=hello; echo \$X` | Safe | None | PASS |
| CRASH-01 | crasher | `arr=(bash); \${arr[0]}` | Detect | Error | PARSE_ERR |
| CRASH-02 | crasher | `X=bash; \$X <(echo hi)` | Detect | Detected | PASS |
| CRASH-03 | crasher | `case x in x) \$CMD;; esac` | Detect | Error | PARSE_ERR |
| CRASH-04 | crasher | `select i in a; do \$CMD; done` | Detect | Error | PARSE_ERR |
| CRASH-05 | crasher | `for ((i=0;i<1;i++)); do \$CMD; done` | Detect | Error | PARSE_ERR |
