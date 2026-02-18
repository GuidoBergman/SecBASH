"""Command execution module.

Runs shell commands via subprocess and captures output.
Preserves exit codes for bash compatibility.

Shell state (cwd, env) persists across commands via pipe-based
environment capture. See docs/shell-state-persistence.md.

Architecture (Story 14.2):
    In production mode, Landlock enforcement is handled by an LD_PRELOAD
    shared library (landlock_sandboxer.so) whose constructor applies
    restrictions inside the runner (bash) process before main(). The
    preexec_fn only sets NO_NEW_PRIVS (required by landlock_restrict_self).
    No ruleset fd or pass_fds is needed.
"""

import logging
import os
import re
import subprocess

from aegish.config import get_mode, get_runner_path
from aegish.sandbox import make_no_new_privs_fn

logger = logging.getLogger(__name__)

# Maximum bytes to read from env capture pipe (1 MB safety limit).
MAX_ENV_SIZE = 1048576

# Default path to the LD_PRELOAD sandboxer library
DEFAULT_SANDBOXER_PATH = "/opt/aegish/lib/landlock_sandboxer.so"

# Allowlist approach: only known-safe variables are passed to child processes.
# Unknown variables (including future attack vectors) are blocked by default.
ALLOWED_ENV_VARS = {
    "PATH", "HOME", "USER", "LOGNAME", "SHELL",
    "PWD", "OLDPWD", "SHLVL",
    "TERM", "COLORTERM", "TERM_PROGRAM",
    "LANG", "LANGUAGE", "TZ", "TMPDIR",
    "DISPLAY", "WAYLAND_DISPLAY",
    "SSH_AUTH_SOCK", "SSH_AGENT_PID", "GPG_AGENT_INFO",
    "DBUS_SESSION_BUS_ADDRESS", "HOSTNAME",
}

# Prefixes for variable families that are safe to pass through.
ALLOWED_ENV_PREFIXES = ("LC_", "XDG_", "AEGISH_")

# Regex to detect bare cd commands for fast-path interception.
# Matches: cd, cd ~, cd -, cd /path, cd relative, cd ~user
_CD_PATTERN = re.compile(r"^\s*cd\s*($|\s+\S+\s*$)")


def _get_sandboxer_path() -> str:
    """Get the path to the sandboxer shared library.

    Reads from AEGISH_SANDBOXER_PATH environment variable.
    Falls back to DEFAULT_SANDBOXER_PATH if not set.

    Returns:
        Path to landlock_sandboxer.so.
    """
    return os.environ.get("AEGISH_SANDBOXER_PATH", DEFAULT_SANDBOXER_PATH)


def _build_safe_env() -> dict[str, str]:
    """Build a sanitized environment for subprocess execution.

    Uses an allowlist approach: only known-safe variables are passed
    to child processes. Unknown variables are stripped by default,
    blocking BASH_ENV, LD_PRELOAD (user-supplied), and other injection
    vectors without needing to enumerate them.

    In production mode, injects LD_PRELOAD with the sandboxer library
    path so the Landlock constructor runs inside the runner process.
    """
    env = {}
    for key, value in os.environ.items():
        if key in ALLOWED_ENV_VARS or key.startswith(ALLOWED_ENV_PREFIXES):
            env[key] = value

    # In production: inject LD_PRELOAD so the sandboxer library applies
    # Landlock inside the runner process before bash main() runs.
    # This is safe because the env is built by us, not the user.
    if get_mode() == "production":
        env["LD_PRELOAD"] = _get_sandboxer_path()
        # Pass runner path so the C library knows what to deny
        env["AEGISH_RUNNER_PATH"] = get_runner_path()

    return env


def sanitize_env(captured: dict[str, str]) -> dict[str, str]:
    """Sanitize a captured environment dict through the allowlist.

    Applied on every capture cycle to prevent commands like
    ``export LD_PRELOAD=/tmp/evil.so`` from propagating to
    subsequent commands.

    In production mode, re-injects LD_PRELOAD with the sandboxer
    library path (the user-exported value was already stripped by
    the allowlist).

    Args:
        captured: Raw environment dict from subprocess.

    Returns:
        Filtered dict containing only allowlisted variables.
    """
    env = {}
    for key, value in captured.items():
        if key in ALLOWED_ENV_VARS or key.startswith(ALLOWED_ENV_PREFIXES):
            env[key] = value

    # Re-inject production sandboxer LD_PRELOAD
    if get_mode() == "production":
        env["LD_PRELOAD"] = _get_sandboxer_path()
        env["AEGISH_RUNNER_PATH"] = get_runner_path()

    return env


def parse_nul_env(raw: bytes) -> dict[str, str]:
    """Parse NUL-delimited env output from ``env -0``.

    Each entry is KEY=VALUE separated by NUL bytes.
    Values may contain newlines (handled correctly by NUL delimiter).

    Args:
        raw: Raw bytes from pipe read.

    Returns:
        Parsed environment dict.
    """
    env = {}
    if not raw:
        return env
    for entry in raw.split(b"\x00"):
        if not entry:
            continue
        text = entry.decode("utf-8", errors="replace")
        eq_pos = text.find("=")
        if eq_pos > 0:
            env[text[:eq_pos]] = text[eq_pos + 1:]
    return env


def is_bare_cd(command: str) -> bool:
    """Check if command is a bare cd (fast-path candidate).

    Returns True for: cd, cd ~, cd -, cd /path, cd relative, cd ~user
    Returns False for compound commands: cd /tmp && ls, cd; echo hi
    """
    stripped = command.strip()
    if any(c in stripped for c in (";", "&&", "||", "|", "&")):
        return False
    return _CD_PATTERN.match(stripped) is not None


def resolve_cd(
    target: str,
    current_dir: str,
    env: dict[str, str],
) -> tuple[str | None, str | None]:
    """Resolve the target directory for a bare cd command.

    Args:
        target: The cd argument (empty string for bare cd).
        current_dir: Current working directory.
        env: Current environment dict.

    Returns:
        Tuple of (resolved_path, error_message).
        On success: (path, None). On failure: (None, error_string).
    """
    if not target or target == "~":
        home = env.get("HOME", os.path.expanduser("~"))
        resolved = home
    elif target == "-":
        oldpwd = env.get("OLDPWD")
        if not oldpwd:
            return None, "cd: OLDPWD not set"
        resolved = oldpwd
    elif target.startswith("~"):
        resolved = os.path.expanduser(target)
    elif os.path.isabs(target):
        resolved = target
    else:
        resolved = os.path.join(current_dir, target)

    resolved = os.path.realpath(resolved)

    if not os.path.isdir(resolved):
        return None, f"cd: {target or '~'}: No such file or directory"

    return resolved, None


def _get_shell_binary() -> str:
    """Get the shell binary path based on operational mode.

    Production mode: uses the runner binary (hardlink of bash).
    Development mode: uses "bash" from PATH.

    Returns:
        Path to the shell binary.
    """
    if get_mode() == "production":
        return get_runner_path()
    return "bash"


def _sandbox_kwargs() -> dict:
    """Build subprocess kwargs for sandboxing in production mode.

    In production, sets preexec_fn for NO_NEW_PRIVS only. Landlock
    enforcement is handled by the LD_PRELOAD sandboxer library.
    No pass_fds is needed -- no ruleset fd is created in Python.

    Returns empty dict in development mode (no sandbox).
    """
    if get_mode() != "production":
        return {}

    return {
        "preexec_fn": make_no_new_privs_fn(),
    }


def execute_command(
    command: str,
    last_exit_code: int = 0,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> tuple[int, dict[str, str], str]:
    """Execute a shell command via bash with environment capture.

    Runs the command through bash -c, streaming output directly
    to the terminal. After execution, captures the subprocess
    environment via a pipe to persist state across commands.

    Args:
        command: The command string to execute.
        last_exit_code: Exit code from the previous command (for $?).
        env: Environment dict to use. If None, builds from os.environ.
        cwd: Working directory. If None, uses os.getcwd().

    Returns:
        Tuple of (exit_code, updated_env, updated_cwd).
    """
    if env is None:
        env = _build_safe_env()
    if cwd is None:
        cwd = os.getcwd()

    # Create pipe for env capture
    env_r, env_w = os.pipe()

    try:
        # Append env capture suffix that preserves the user command's exit code
        suffix = (
            f"; __aegish_rc=$?; env -0 >&{env_w}; exit $__aegish_rc"
        )
        wrapped_command = f"(exit {last_exit_code}); {command}{suffix}"

        # Build sandbox kwargs and add pipe fd to pass_fds
        sandbox_kw = _sandbox_kwargs()
        sandbox_kw["pass_fds"] = (env_w,)

        result = subprocess.run(
            [_get_shell_binary(), "--norc", "--noprofile", "-c", wrapped_command],
            env=env,
            cwd=cwd,
            **sandbox_kw,
        )
    finally:
        os.close(env_w)

    # Read captured env from pipe
    try:
        raw = os.read(env_r, MAX_ENV_SIZE)
    finally:
        os.close(env_r)

    # Parse and sanitize captured env
    if raw:
        captured = parse_nul_env(raw)
        new_env = sanitize_env(captured)
    else:
        new_env = env

    # Update cwd from captured PWD
    new_cwd = new_env.get("PWD", cwd)
    if not os.path.isdir(new_cwd):
        new_cwd = cwd

    return result.returncode, new_env, new_cwd


def run_bash_command(command: str) -> subprocess.CompletedProcess:
    """Run a command through bash -c with captured output.

    In production mode, the child process is sandboxed via LD_PRELOAD.

    Args:
        command: The command to run.

    Returns:
        CompletedProcess with stdout, stderr, and returncode.
    """
    return subprocess.run(
        [_get_shell_binary(), "--norc", "--noprofile", "-c", command],
        env=_build_safe_env(),
        capture_output=True,
        text=True,
        **_sandbox_kwargs(),
    )
