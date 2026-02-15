# Fuzzing Report: `_build_safe_env()`

## Overview

- **Date**: 2026-02-15
- **Target**: `src/aegish/executor.py::_build_safe_env()`
- **Current blocklist size**: 8 entries
- **Vars tested**: 39
- **Leaked through**: 39
- **Blocked**: 0

## Severity Summary

| Severity | Leaked Count |
|----------|-------------|
| CRITICAL | 4 |
| HIGH | 14 |
| MEDIUM | 15 |
| LOW | 6 |

## Executive Summary

The `_build_safe_env()` blocklist contains only 8 entries. Testing 39 known-dangerous environment variables reveals **39 that leak through**, including 4 CRITICAL and 14 HIGH severity.

## Leaked Variables

### CRITICAL

| Variable | Description | Why Dangerous |
|----------|-------------|---------------|
| `LD_PRELOAD` | Shared library preload injection | Loads attacker .so into every dynamically-linked binary |
| `LD_LIBRARY_PATH` | Library search path hijacking | Redirects library lookups to attacker-controlled directory |
| `LD_AUDIT` | Runtime linker audit library | Loads .so for linker audit callbacks before main() |
| `BASH_LOADABLES_PATH` | Bash loadable builtins path | enable -f loads .so from this path as bash builtins |

### HIGH

| Variable | Description | Why Dangerous |
|----------|-------------|---------------|
| `SHELLOPTS` | Bash shell options | Can enable xtrace, allexport, force behaviors |
| `BASHOPTS` | Bash shopt options | Can force dangerous shopt options |
| `IFS` | Internal field separator | Alters word splitting, breaks PATH lookups |
| `PS0` | Pre-command prompt | Expanded before each command; supports command substitution |
| `PS4` | Debug trace prompt | Expanded during xtrace; command substitution executes code |
| `EXECIGNORE` | Command ignore pattern | Bash skips matching executables in PATH lookup |
| `LESSOPEN` | Less input preprocessor | Pipe input through arbitrary command when less opens a file |
| `PYTHONSTARTUP` | Python startup script | Auto-executed by interactive Python sessions |
| `PYTHONPATH` | Python module search path | Module injection via malicious directory |
| `PERL5OPT` | Perl command-line options | Inject -e to run arbitrary Perl code |
| `NODE_OPTIONS` | Node.js CLI options | --require loads arbitrary JS before main script |
| `GIT_SSH` | Git SSH transport binary | Git executes this instead of ssh |
| `GIT_SSH_COMMAND` | Git SSH command string | Git executes this command for SSH transport |
| `GIT_EXEC_PATH` | Git subcommand search path | Git loads subcommands from this directory |

### MEDIUM

| Variable | Description | Why Dangerous |
|----------|-------------|---------------|
| `CDPATH` | cd search path | cd resolves to unexpected directories |
| `GLOBIGNORE` | Glob pattern ignore | Hides files from glob expansion |
| `PS1` | Primary prompt | Command substitution in interactive mode |
| `INPUTRC` | Readline config file | Custom readline macros can execute shell commands |
| `HISTFILE` | History file location | Write command history to attacker-controlled path |
| `LESSCLOSE` | Less cleanup command | Executed when less exits |
| `PERL5LIB` | Perl library path | Module injection for Perl programs |
| `RUBYLIB` | Ruby library path | Module injection for Ruby programs |
| `GIT_TEMPLATE_DIR` | Git template directory | git init copies hooks from this directory |
| `GIT_CONFIG_GLOBAL` | Git global config | Arbitrary git config injection |
| `SSH_ASKPASS` | SSH password dialog | Executed when SSH needs password without terminal |
| `SSH_ASKPASS_REQUIRE` | Force SSH_ASKPASS usage | Set to 'force' to always run SSH_ASKPASS even with terminal |
| `BROWSER` | Default browser command | xdg-open and webbrowser module execute this |
| `ZDOTDIR` | Zsh config directory | If zsh is invoked, loads .zshrc from here |
| `FPATH` | Zsh function path | Autoloaded function hijacking in zsh |

### LOW

| Variable | Description | Why Dangerous |
|----------|-------------|---------------|
| `PS2` | Continuation prompt | Command substitution in interactive mode |
| `HISTCONTROL` | History control | Manipulate history recording behavior |
| `TMPDIR` | Temp directory | Symlink/race attacks on temp file creation |
| `TERMCAP` | Terminal capabilities | Terminal escape sequence injection |
| `TERMINFO` | Terminal info directory | Terminal capability injection |
| `MAILPATH` | Mail notification paths | Bash expands message part which may contain command subst |

## Exploitability Results

| Variable | Exploitable | Notes |
|----------|:-----------:|-------|
| `LD_PRELOAD` | YES | `LD_PRELOAD=/tmp/evil.so
` |
| `LD_LIBRARY_PATH` | YES | `LD_LIBRARY_PATH=/tmp/evil
` |
| `LD_AUDIT` | YES | `LD_AUDIT=/tmp/evil.so
` |
| `BASH_LOADABLES_PATH` | YES | `BASH_LOADABLES_PATH=/tmp/evil_builtins
` |
| `SHELLOPTS` | YES | `hello
` |
| `BASHOPTS` | YES | `BASHOPTS=checkwinsize:cmdhist:complete_fullquote:extglob:extquote:force_fignore:` |
| `IFS` | passed through | `PART:a/b/c
` |
| `PS0` | passed through | `test
` |
| `PS4` | YES | `test
` |
| `EXECIGNORE` | YES | `EXECIGNORE=*/sudo
` |
| `LESSOPEN` | YES | `LESSOPEN=|echo FUZZ_MARKER_8xK9qL; cat %s
` |
| `PYTHONSTARTUP` | YES | `PYTHONSTARTUP=/tmp/evil_startup.py
` |
| `PYTHONPATH` | YES | `['', '/tmp/evil_py', '/usr/lib/python312.zip', '/usr/lib/python3.12', '/usr/lib/` |
| `PERL5OPT` | YES | `PERL5OPT=-e system('echo FUZZ_MARKER_8xK9qL')
` |
| `NODE_OPTIONS` | YES | `NODE_OPTIONS=--require /tmp/evil.js
` |
| `GIT_SSH` | YES | `GIT_SSH=/tmp/evil_ssh
` |
| `GIT_SSH_COMMAND` | YES | `GIT_SSH_COMMAND=echo FUZZ_MARKER_8xK9qL
` |
| `GIT_EXEC_PATH` | YES | `GIT_EXEC_PATH=/tmp/evil_git
` |

## BASH_FUNC_ Bypass (4 leaked)

| Variant | Status |
|---------|--------|
| `BASH_FUNC_test%%` | blocked |
| `BASH_FUNC_x()` | blocked |
| `BASH_FUNC_` | blocked |
| `BASH_FUNC_test` | blocked |
| `bash_func_test%%` | LEAKED |
| `Bash_Func_x%%` | LEAKED |
| `BASH_FUN_x%%` | LEAKED |
| `BASH_FUNCS_x%%` | LEAKED |

## Recommendations

### 1. CRITICAL: Expand blocklist with high-impact variables

```python
DANGEROUS_ENV_VARS = {
    # Current
    "BASH_ENV", "ENV", "PROMPT_COMMAND", "EDITOR", "VISUAL",
    "PAGER", "GIT_PAGER", "MANPAGER",
    # Add: Library injection
    "LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT",
    "BASH_LOADABLES_PATH",
    # Add: Shell behavior modification
    "SHELLOPTS", "BASHOPTS", "IFS", "EXECIGNORE",
    "PS0", "PS4", "CDPATH", "GLOBIGNORE",
    # Add: Program-specific injection
    "PYTHONSTARTUP", "PYTHONPATH", "PERL5OPT", "PERL5LIB",
    "RUBYLIB", "NODE_OPTIONS",
    # Add: Git hijacking
    "GIT_SSH", "GIT_SSH_COMMAND", "GIT_EXEC_PATH",
    "GIT_TEMPLATE_DIR", "GIT_CONFIG_GLOBAL",
    # Add: Other
    "LESSOPEN", "LESSCLOSE", "INPUTRC", "SSH_ASKPASS",
}
```

### 2. Consider allowlist approach

Instead of blocklisting dangerous vars, allowlist only needed ones (PATH, HOME, USER, LANG, TERM, etc.).
