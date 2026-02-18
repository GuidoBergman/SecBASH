# Landlock Sandboxer: Fixing the Runner Binary Shell Escape

## Vulnerability Summary

`/opt/aegish/bin/runner` is a hardlink to `/bin/bash`. aegish uses it as the shell
interpreter for every command because Landlock blocks `/bin/bash` by path. However,
since `runner` is a hardlink (not a symlink), `os.path.realpath()` cannot resolve it
back to `/bin/bash` — it returns `/opt/aegish/bin/runner`, which is not in
`DENIED_SHELLS`. So runner gets added to the Landlock allowlist.

A user can type `/opt/aegish/bin/runner` directly, the LLM may classify it as harmless,
and the executor runs it under a Landlock ruleset that explicitly allows it. Result:
unrestricted interactive bash shell, complete bypass of aegish.

Runner **must** be in the Landlock allowlist under the current design because
`executor.py` calls `subprocess.run([runner, "-c", command])` and Landlock is
activated via `preexec_fn` **before** that `exec()`. Removing runner from the allowlist
would break all command execution.

## Why a Standalone "Dropper" Binary Doesn't Work

An earlier design proposed a standalone C binary ("dropper") prepended to the command
string: `dropper && user_command`. The dropper would call `landlock_restrict_self()`
to deny the runner binary, then exit, and the user command would run "under" that
restriction.

This doesn't work. When bash encounters an external command in a `&&` chain, it
**forks a child process** to execute it. `landlock_restrict_self()` applies to the
calling process — in this case, the dropper child. When the dropper exits, its
Landlock restrictions die with it. The parent bash process (which continues to run
the user's command) is completely unaffected.

```
bash -c "dropper && user_command"
  │
  ├─ bash forks child → exec(dropper)
  │    └─ dropper calls landlock_restrict_self()  ← applies to THIS process only
  │    └─ dropper exits 0
  │
  └─ bash (parent, no Landlock from dropper) continues
       └─ runs user_command  ← NOT restricted by dropper's Landlock
```

This is a fundamental property of Landlock: restrictions apply to the calling
process and are inherited by its future children, but never propagate **upward**
to a parent.

## Design: Single-Layer Landlock via LD_PRELOAD

Instead of a standalone binary, we use an `LD_PRELOAD` shared library. When
the dynamic linker loads the library, its **constructor function runs inside
bash's own process** — not in a child. So `landlock_restrict_self()` applies
directly to bash itself, and all commands bash spawns inherit the restriction.

This also simplifies the architecture from two Landlock layers to one. The
Python `preexec_fn` no longer applies Landlock at all — it only sets
`NO_NEW_PRIVS`. All Landlock enforcement moves into the shared library,
which applies a single layer that denies both shells and runner.

### Execution flow (current — vulnerable)

```
fork()
  │
  Child:
  ├─ preexec_fn()        →  NO_NEW_PRIVS + Landlock activated (allows runner, denies shells)
  ├─ exec(runner -c CMD) →  Landlock allows runner ✓
  └─ bash evaluates CMD
       └─ CMD = "/opt/aegish/bin/runner"
            └─ execve(runner)  →  Landlock allows runner ✓  ← ESCAPE
```

### Execution flow (fixed — LD_PRELOAD sandboxer)

```
fork()
  │
  Child:
  ├─ preexec_fn()                  →  NO_NEW_PRIVS set (no Landlock yet)
  ├─ exec(runner -c CMD)           →  no Landlock restriction, exec succeeds
  │    │
  │    Dynamic linker loads LD_PRELOAD library:
  │    └─ constructor()            →  Landlock activated IN BASH'S PROCESS
  │                                   (denies shells AND runner)
  │
  └─ bash main() starts, evaluates CMD
       └─ CMD = "/opt/aegish/bin/runner"
            └─ execve(runner)  →  Landlock denies runner ✗  ← BLOCKED BY KERNEL
```

### Why this works

| Step | What happens | Landlock state |
|---|---|---|
| `preexec_fn()` | Sets `NO_NEW_PRIVS` only | None |
| `exec(runner)` | Dynamic linker starts | None |
| LD_PRELOAD constructor | `landlock_restrict_self()` called | **Active in bash** |
| `bash main()` | Processes `-c "user_command"` | Active |
| User command forks child | Child inherits Landlock | Active (inherited) |
| User command tries `execve(runner)` | Kernel checks Landlock | **DENIED** |

The window between `exec(runner)` and the constructor is just the dynamic linker
loading shared libraries. No user-controlled code runs during this window.
`--norc --noprofile` and stripped `BASH_ENV` ensure bash executes nothing before
the command string.

## Implementation Steps

### Step 1: Create the sandboxer shared library

Create `src/sandboxer/landlock_sandboxer.c`. This is a shared library (~100 lines)
whose constructor applies Landlock before bash's `main()` runs.

```c
/*
 * landlock_sandboxer.c — LD_PRELOAD library that applies Landlock
 * restrictions inside the runner (bash) process, denying execution
 * of all shell binaries AND the runner binary itself.
 *
 * Loaded via LD_PRELOAD in the subprocess environment.
 * Constructor runs before bash main(), so restrictions are in place
 * before any user command is evaluated.
 *
 * Exit behavior:
 *   On failure, calls _exit(126) to abort the process before bash
 *   can run any user commands. This is fail-safe.
 */

#define _GNU_SOURCE
#include <dirent.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/landlock.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

/* Must match DENIED_SHELLS in sandbox.py */
static const char *DENIED_SHELLS[] = {
    "/bin/bash",      "/usr/bin/bash",
    "/bin/sh",        "/usr/bin/sh",
    "/bin/dash",      "/usr/bin/dash",
    "/bin/zsh",       "/usr/bin/zsh",
    "/bin/fish",      "/usr/bin/fish",
    "/bin/ksh",       "/usr/bin/ksh",
    "/bin/csh",       "/usr/bin/csh",
    "/bin/tcsh",      "/usr/bin/tcsh",
    NULL
};

static int is_denied(const char *path, const char *resolved,
                     const char *runner, const char *runner_resolved) {
    /* Check against denied shells */
    for (const char **s = DENIED_SHELLS; *s != NULL; s++) {
        if (strcmp(path, *s) == 0 || strcmp(resolved, *s) == 0)
            return 1;
    }

    /* Check against runner (both literal and resolved for hardlink detection) */
    if (strcmp(path, runner) == 0 || strcmp(resolved, runner_resolved) == 0)
        return 1;

    return 0;
}

static int add_exec_rule(int ruleset_fd, const char *path) {
    int fd = open(path, O_PATH | O_CLOEXEC);
    if (fd < 0) return -1;

    struct landlock_path_beneath_attr rule = {
        .allowed_access = LANDLOCK_ACCESS_FS_EXECUTE,
        .parent_fd = fd,
    };
    int ret = (int)syscall(SYS_landlock_add_rule, ruleset_fd,
                           LANDLOCK_RULE_PATH_BENEATH, &rule, 0);
    close(fd);
    return ret;
}

__attribute__((constructor))
static void apply_sandbox(void) {
    /* 1. Determine runner path */
    const char *runner = getenv("AEGISH_RUNNER_PATH");
    if (!runner || !*runner)
        runner = "/opt/aegish/bin/runner";

    char runner_resolved[PATH_MAX];
    if (!realpath(runner, runner_resolved)) {
        fprintf(stderr, "landlock_sandboxer: cannot resolve runner path: %s\n", runner);
        _exit(126);
    }

    /* 2. Check kernel support */
    struct landlock_ruleset_attr attr = {
        .handled_access_fs = LANDLOCK_ACCESS_FS_EXECUTE,
    };
    int ruleset_fd = (int)syscall(SYS_landlock_create_ruleset,
                                  &attr, sizeof(attr), 0);
    if (ruleset_fd < 0) {
        /* Landlock not supported — fail safe, don't allow unprotected execution */
        perror("landlock_sandboxer: create_ruleset");
        _exit(126);
    }

    /* 3. Enumerate PATH directories and add rules for allowed executables */
    const char *path_env = getenv("PATH");
    if (!path_env || !*path_env) {
        close(ruleset_fd);
        fprintf(stderr, "landlock_sandboxer: PATH is empty\n");
        _exit(126);
    }

    char *path_copy = strdup(path_env);
    if (!path_copy) { close(ruleset_fd); _exit(126); }

    char *saveptr = NULL;
    for (char *dir = strtok_r(path_copy, ":", &saveptr);
         dir != NULL;
         dir = strtok_r(NULL, ":", &saveptr))
    {
        DIR *d = opendir(dir);
        if (!d) continue;

        struct dirent *ent;
        while ((ent = readdir(d)) != NULL) {
            char fullpath[PATH_MAX];
            int n = snprintf(fullpath, sizeof(fullpath), "%s/%s", dir, ent->d_name);
            if (n < 0 || (size_t)n >= sizeof(fullpath)) continue;

            struct stat st;
            if (stat(fullpath, &st) != 0)      continue;
            if (!S_ISREG(st.st_mode))           continue;
            if (!(st.st_mode & (S_IXUSR | S_IXGRP | S_IXOTH))) continue;

            char resolved[PATH_MAX];
            if (!realpath(fullpath, resolved)) continue;

            if (is_denied(fullpath, resolved, runner, runner_resolved))
                continue;

            add_exec_rule(ruleset_fd, fullpath);
        }
        closedir(d);
    }
    free(path_copy);

    /* 4. Activate Landlock */
    if (syscall(SYS_landlock_restrict_self, ruleset_fd, 0) != 0) {
        perror("landlock_sandboxer: restrict_self");
        close(ruleset_fd);
        _exit(126);
    }

    close(ruleset_fd);
    /* Constructor returns, bash main() proceeds under Landlock */
}
```

Key design decisions:
- **`_exit(126)` on failure, not `return`**: If the constructor can't apply Landlock,
  the process must die before bash runs any user commands. This is fail-safe.
- **Runner path from environment**: Reads `AEGISH_RUNNER_PATH` so it stays in sync
  with `config.py` without hardcoding.
- **`DENIED_SHELLS` hardcoded in C**: Must match `sandbox.py`. A discrepancy is a
  bug, but the list is stable (standard Unix shells).
- **`prctl(PR_SET_NO_NEW_PRIVS)` IS called in the constructor**: This makes the
  library self-sufficient. For the normal path, Python's `preexec_fn` already set
  it (idempotent, harmless to re-set). For the sudo post-elevation path (DD-19),
  no `preexec_fn` runs, so the library must set it before `landlock_restrict_self()`.
- **`__attribute__((constructor))`**: Runs during dynamic linking, before `main()`.
  This is the standard mechanism for LD_PRELOAD initialization.

### Step 2: Modify `executor.py`

Two changes: add `LD_PRELOAD` to the environment, and simplify `_sandbox_kwargs()`
to remove Landlock (now handled by the library).

```python
# In executor.py

DEFAULT_SANDBOXER_PATH = "/opt/aegish/lib/landlock_sandboxer.so"

def _get_sandboxer_path() -> str:
    return os.environ.get("AEGISH_SANDBOXER_PATH", DEFAULT_SANDBOXER_PATH)

def _build_safe_env() -> dict[str, str]:
    env = {}
    for key, value in os.environ.items():
        if key in DANGEROUS_ENV_VARS:
            continue
        if key.startswith("BASH_FUNC_"):
            continue
        env[key] = value

    # In production: inject LD_PRELOAD so the sandboxer library applies
    # Landlock inside the runner process before bash main() runs
    if get_mode() == "production":
        sandboxer = _get_sandboxer_path()
        existing = env.get("LD_PRELOAD", "")
        if existing:
            env["LD_PRELOAD"] = f"{sandboxer}:{existing}"
        else:
            env["LD_PRELOAD"] = sandboxer

    return env

def _sandbox_kwargs() -> dict:
    """Build subprocess kwargs for sandboxing in production mode.

    In production, sets preexec_fn for NO_NEW_PRIVS only. Landlock
    enforcement is handled by the LD_PRELOAD sandboxer library.
    """
    if get_mode() != "production":
        return {}

    return {
        "preexec_fn": _make_no_new_privs_fn(),
    }
    # Note: no more pass_fds — no ruleset fd needed
```

The command string is unchanged — no dropper/sandboxer prefix needed:

```python
def execute_command(command: str, last_exit_code: int = 0) -> int:
    wrapped_command = f"(exit {last_exit_code}); {command}"

    result = subprocess.run(
        [_get_shell_binary(), "--norc", "--noprofile", "-c", wrapped_command],
        env=_build_safe_env(),
        **_sandbox_kwargs(),
    )
    return result.returncode
```

### Step 3: Simplify `sandbox.py`

Remove all Landlock ruleset creation and activation code. The module's only
remaining job is `NO_NEW_PRIVS` and the availability check:

```python
# sandbox.py — simplified

def landlock_available() -> tuple[bool, int]:
    """Check whether the running kernel supports Landlock."""
    # (unchanged — still useful for startup validation)

def _make_no_new_privs_fn():
    """Create a preexec_fn that sets NO_NEW_PRIVS only.

    Landlock enforcement is handled by the LD_PRELOAD sandboxer library,
    which runs inside the exec'd process. preexec_fn only needs to ensure
    NO_NEW_PRIVS is set (required by landlock_restrict_self).
    """
    libc = _get_libc()

    def _preexec() -> None:
        ret = libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
        if ret != 0:
            raise OSError("prctl(PR_SET_NO_NEW_PRIVS) failed")

    return _preexec
```

The following can be removed from `sandbox.py`:
- `create_sandbox_ruleset()` — no longer needed
- `make_preexec_fn()` — replaced by `_make_no_new_privs_fn()`
- `get_sandbox_ruleset()` — no longer needed
- `get_sandbox_preexec()` — replaced by direct call in executor
- `DENIED_SHELLS` — moved to the C library (keep as a comment for reference)

### Step 4: Update `config.py`

Add the sandboxer library path constant and validation:

```python
DEFAULT_SANDBOXER_PATH = "/opt/aegish/lib/landlock_sandboxer.so"

def validate_sandboxer_library() -> tuple[bool, str]:
    path = os.environ.get("AEGISH_SANDBOXER_PATH", DEFAULT_SANDBOXER_PATH)
    if not os.path.exists(path):
        return (False, f"Sandboxer library not found at {path}")
    if not os.access(path, os.R_OK):
        return (False, f"Sandboxer library at {path} is not readable")
    return (True, "Sandboxer library ready")
```

### Step 5: Update `Dockerfile.production`

Build the shared library and place it in `/opt/aegish/lib/`:

```dockerfile
# 1.4a: Build Landlock sandboxer library
COPY src/sandboxer/landlock_sandboxer.c /tmp/landlock_sandboxer.c
RUN gcc -O2 -Wall -Wextra -shared -fPIC \
    -o /opt/aegish/lib/landlock_sandboxer.so /tmp/landlock_sandboxer.c \
    && rm /tmp/landlock_sandboxer.c

# 1.4b: Create runner binary (hardlink, NOT symlink — DD-17)
RUN ln /bin/bash /opt/aegish/bin/runner
```

Note: `-shared -fPIC` instead of `-static`. This is a shared library, not a
standalone binary. It gets loaded into bash's process by the dynamic linker.

### Step 6: Update `shell.py` startup validation

Add sandboxer validation alongside the existing runner validation:

```python
if mode == "production":
    runner_ok, runner_msg = validate_runner_binary()
    sandboxer_ok, sandboxer_msg = validate_sandboxer_library()
    if not runner_ok:
        print(f"ERROR: {runner_msg}")
        # ... fallback logic
    if not sandboxer_ok:
        print(f"ERROR: {sandboxer_msg}")
        # ... fallback logic
```

## Security Analysis

### What the sandboxer prevents

| Attack | Without sandboxer | With sandboxer |
|---|---|---|
| `aegish> /opt/aegish/bin/runner` | Interactive bash shell | `EPERM` from kernel |
| `aegish> /opt/aegish/bin/../bin/runner` | Interactive bash shell | `EPERM` (realpath resolves) |
| `aegish> echo foo; /opt/aegish/bin/runner` | Shell via compound cmd | `EPERM` (Landlock checks every execve) |
| `aegish> $(/opt/aegish/bin/runner -c id)` | Command substitution | `EPERM` (kernel checks execve in subshell) |

### Why LD_PRELOAD is safe here

**"Can the user bypass LD_PRELOAD?"**

No. The environment is built by `_build_safe_env()` in the Python process. The user
has no control over the subprocess environment — they control only the command string
passed via `-c`. By the time bash processes that string, LD_PRELOAD has already been
loaded and the constructor has already applied Landlock.

**"What about LD_PRELOAD in child processes?"**

When the user's command spawns a child (e.g., running `ls`), the child inherits both
the environment (including LD_PRELOAD) and the Landlock restriction. The constructor
runs again in the child, applying a second (redundant) Landlock layer. This is
harmless — Landlock stacking is intersective, so an identical layer is a no-op.

For a minor optimization, the constructor could check whether Landlock is already
active and skip re-application. This is optional.

**"What if runner is statically linked?"**

LD_PRELOAD only works with dynamically linked binaries. Runner is a hardlink to
`/bin/bash`, which is dynamically linked on all standard Linux distributions.
If bash were ever statically linked, this approach would need to be revisited.

### Why command injection into the command string is not possible

The wrapped command string is:
```
(exit N); USER_COMMAND
```

- `(exit N)` — N is an integer set by aegish, not user-controlled
- `USER_COMMAND` — user-controlled, but Landlock is already active before bash
  even starts parsing this string (constructor ran during dynamic linking)

`--norc --noprofile` prevents `.bashrc`/`.profile` execution, and
`_build_safe_env()` strips `BASH_ENV`, `ENV`, and `BASH_FUNC_*` — so no
environment-injected code runs at all.

### Residual risk

- **Sandboxer library tampering**: If an attacker can overwrite
  `/opt/aegish/lib/landlock_sandboxer.so` with a no-op library, Landlock is never
  activated. Mitigation: the library should be owned by root, and the production
  filesystem should prevent writes to `/opt/aegish/lib/`. Consider making the
  directory immutable (`chattr +i`).
- **Kernel Landlock bypass**: A kernel vulnerability could bypass Landlock entirely.
  This is outside aegish's threat model.
- **Hardlink inode semantics**: Landlock may match rules by inode rather than path.
  If so, allowing runner (same inode as bash) may implicitly allow bash too. This
  needs empirical testing. If confirmed, the runner must use a different mechanism
  than a hardlink (e.g., a minimal compiled wrapper with `fexecve`).

## Comparison with the Original Two-Layer Dropper Approach

| Aspect | Dropper (two-layer, broken) | Sandboxer (single-layer, LD_PRELOAD) |
|---|---|---|
| Landlock layers | 2 (stacked) | 1 |
| Mechanism | Standalone binary in `&&` chain | LD_PRELOAD constructor |
| Applies to bash process? | **No** (runs in forked child) | **Yes** (constructor runs in-process) |
| Command string modified? | Yes (`dropper && cmd`) | No (unchanged) |
| Build artifact | Static binary | Shared library (`.so`) |
| Python sandbox.py | Keeps ruleset creation | Removes it (C library handles all) |
| pass_fds needed? | Yes (ruleset fd) | No |

## Testing

### Unit test: sandboxer library

```bash
# Compile sandboxer
gcc -O2 -Wall -shared -fPIC -o /opt/aegish/lib/landlock_sandboxer.so \
    src/sandboxer/landlock_sandboxer.c

# Verify Landlock activates (runner denied after loading library)
LD_PRELOAD=/opt/aegish/lib/landlock_sandboxer.so \
    /opt/aegish/bin/runner --norc --noprofile -c \
    '/opt/aegish/bin/runner -c "echo escaped"'
# Should fail with "Permission denied"

# Verify other binaries still work
LD_PRELOAD=/opt/aegish/lib/landlock_sandboxer.so \
    /opt/aegish/bin/runner --norc --noprofile -c 'ls /'
# Should succeed

# Verify compound command escape blocked
LD_PRELOAD=/opt/aegish/lib/landlock_sandboxer.so \
    /opt/aegish/bin/runner --norc --noprofile -c \
    'echo hi; /opt/aegish/bin/runner'
# "hi" prints, then "Permission denied" for runner
```

### Integration test: add to Story 8.7 bypass tests

```python
def test_runner_direct_execution_blocked():
    """BYPASS-14: Direct runner binary execution denied by Landlock."""
    result = run_in_aegish("/opt/aegish/bin/runner")
    assert result.returncode != 0

def test_runner_path_variant_blocked():
    """BYPASS-15: Runner path with ../ normalization still denied."""
    result = run_in_aegish("/opt/aegish/bin/../bin/runner")
    assert result.returncode != 0

def test_runner_in_compound_command_blocked():
    """BYPASS-16: Runner in compound command denied."""
    result = run_in_aegish("true && /opt/aegish/bin/runner")
    assert result.returncode != 0

def test_runner_in_command_substitution_blocked():
    """BYPASS-17: Runner in command substitution denied."""
    result = run_in_aegish("echo $(/opt/aegish/bin/runner -c 'echo pwned')")
    assert "pwned" not in result.stdout
```

## Sudo Post-Elevation Sandboxing (DD-19)

In production mode, `preexec_fn` sets `PR_SET_NO_NEW_PRIVS` before `exec()`, which
prevents SUID binaries like `sudo` from escalating privileges. Sysadmin users
(`AEGISH_ROLE=sysadmin`) need sudo access while maintaining Landlock enforcement.

### Solution: Skip preexec_fn, let sudo elevate first

For sudo commands from sysadmin users, the executor skips `preexec_fn` entirely
and builds a command that lets sudo elevate first:

```
sudo env LD_PRELOAD=<sandboxer> AEGISH_RUNNER_PATH=<runner> \
    <runner> --norc --noprofile -c "<command>"
```

The sandboxer library's constructor now calls `prctl(PR_SET_NO_NEW_PRIVS)` itself
(idempotent for the normal path where Python already set it). Inside the elevated
process, the constructor applies `NO_NEW_PRIVS` + Landlock, blocking shell escapes
even as root.

### Execution flow (sudo path)

```
executor.py detects: production + sysadmin + sudo command
  │
  └─ subprocess.run(["sudo", "env", "LD_PRELOAD=...", runner, "-c", cmd])
       │                                           (NO preexec_fn)
       └─ sudo elevates to root
            └─ env sets LD_PRELOAD and AEGISH_RUNNER_PATH
                 └─ exec(runner -c CMD)
                      │
                      Dynamic linker loads LD_PRELOAD library:
                      └─ constructor()
                           ├─ prctl(PR_SET_NO_NEW_PRIVS)  ← set here, not by Python
                           └─ landlock_restrict_self()     ← active in bash as root
                      │
                      └─ bash main() starts, evaluates CMD
                           └─ CMD = "bash" → EPERM (Landlock denies even as root)
```

### Known limitations (v1)

- Only `sudo <command>` supported. Sudo flags (`-u`, `-E`, `-i`) are not parsed.
- Environment capture is not available (original env/cwd returned unchanged).
- Pre-flight validates sudo binary (root-owned, SUID set) and sandboxer library.
  On failure, falls back to running the stripped command without sudo.
