"""Command execution module.

Runs shell commands via subprocess and captures output.
Preserves exit codes for bash compatibility.
"""

import os
import subprocess

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


def execute_command(command: str, last_exit_code: int = 0) -> int:
    """Execute a shell command via bash.

    Runs the command through bash -c, streaming output directly
    to the terminal without capture. The previous command's exit
    code is made available via the special variable $?.

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
        ["bash", "--norc", "--noprofile", "-c", wrapped_command],
        env=_build_safe_env(),
        # Don't capture - stream directly to terminal
    )
    return result.returncode


def run_bash_command(command: str) -> subprocess.CompletedProcess:
    """Run a command through bash -c with captured output.

    Args:
        command: The command to run.

    Returns:
        CompletedProcess with stdout, stderr, and returncode.
    """
    return subprocess.run(
        ["bash", "--norc", "--noprofile", "-c", command],
        env=_build_safe_env(),
        capture_output=True,
        text=True,
    )
