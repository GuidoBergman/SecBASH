"""Command execution module.

Runs shell commands via subprocess and captures output.
Preserves exit codes for bash compatibility.
"""

import subprocess


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
        ["bash", "-c", wrapped_command],
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
        ["bash", "-c", command],
        capture_output=True,
        text=True,
    )
