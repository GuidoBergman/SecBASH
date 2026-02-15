"""Command execution module.

Runs shell commands via subprocess and captures output.
Preserves exit codes for bash compatibility.
"""

import logging
import os
import subprocess

from aegish.config import get_mode, get_runner_path
from aegish.sandbox import get_sandbox_ruleset, make_preexec_fn

logger = logging.getLogger(__name__)

DANGEROUS_ENV_VARS = {
    "BASH_ENV",
    "ENV",
    "PROMPT_COMMAND",
    "EDITOR",
    "VISUAL",
    "PAGER",
    "GIT_PAGER",
    "MANPAGER",
}


def _build_safe_env() -> dict[str, str]:
    """Build a sanitized environment for subprocess execution.

    Strips dangerous environment variables that could be used for
    BASH_ENV injection, alias hijacking, or PAGER/EDITOR hijacking.
    Preserves all other variables including PATH, API keys, etc.
    """
    env = {}
    for key, value in os.environ.items():
        if key in DANGEROUS_ENV_VARS:
            continue
        if key.startswith("BASH_FUNC_"):
            continue
        env[key] = value
    return env


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
    """Build subprocess kwargs for Landlock sandboxing in production mode.

    Returns dict with preexec_fn and pass_fds if Landlock is available
    in production mode, otherwise empty dict.
    """
    if get_mode() != "production":
        return {}

    ruleset_fd = get_sandbox_ruleset()
    if ruleset_fd is None:
        logger.debug("Landlock unavailable, skipping sandbox")
        return {}

    return {
        "preexec_fn": make_preexec_fn(ruleset_fd),
        "pass_fds": (ruleset_fd,),
    }


def execute_command(command: str, last_exit_code: int = 0) -> int:
    """Execute a shell command via bash.

    Runs the command through bash -c, streaming output directly
    to the terminal without capture. The previous command's exit
    code is made available via the special variable $?.

    In production mode with Landlock available, the child process
    is sandboxed to prevent shell execution via execve().

    Args:
        command: The command string to execute.
        last_exit_code: Exit code from the previous command (for $?).

    Returns:
        Exit code from the command.
    """
    # Prepend the exit code setup so $? works correctly
    # We use (exit N) to set $? to the previous exit code
    wrapped_command = f"(exit {last_exit_code}); {command}"

    result = subprocess.run(
        [_get_shell_binary(), "--norc", "--noprofile", "-c", wrapped_command],
        env=_build_safe_env(),
        **_sandbox_kwargs(),
    )
    return result.returncode


def run_bash_command(command: str) -> subprocess.CompletedProcess:
    """Run a command through bash -c with captured output.

    In production mode with Landlock available, the child process
    is sandboxed to prevent shell execution via execve().

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
