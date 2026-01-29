"""Shell interaction module.

Handles the readline loop, prompt display, and user interaction
for the SecBASH shell.
"""

import readline  # noqa: F401 - imported for side effects (line editing)

from secbash.executor import execute_command


def get_prompt() -> str:
    """Return the shell prompt string.

    Returns:
        Prompt string, default is "secbash> "
    """
    return "secbash> "


def run_shell() -> int:
    """Run the interactive shell loop.

    Provides readline-based input with line editing support.
    Handles Ctrl+C (cancel input) and Ctrl+D (exit).

    Returns:
        Exit code (0 for normal exit).
    """
    # Track last exit code for $? expansion
    last_exit_code = 0

    print("SecBASH - LLM-powered shell with security validation")
    print("Type 'exit' or press Ctrl+D to quit.\n")

    while True:
        try:
            # Get user input with prompt
            command = input(get_prompt())

            # Skip empty or whitespace-only input
            if not command.strip():
                continue

            # Handle exit command
            if command.strip() == "exit":
                break

            # Execute the command, passing last exit code for $?
            last_exit_code = execute_command(command, last_exit_code)

        except KeyboardInterrupt:
            # Ctrl+C: cancel current input, show new prompt
            print()  # Move to new line
            last_exit_code = 130  # Standard exit code for Ctrl+C
            continue

        except EOFError:
            # Ctrl+D: exit the shell
            print()  # Move to new line
            break

    return 0
