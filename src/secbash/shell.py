"""Shell interaction module.

Handles the readline loop, prompt display, and user interaction
for the SecBASH shell.
"""

import readline  # noqa: F401 - imported for side effects (line editing)

from secbash.config import get_available_providers
from secbash.executor import execute_command
from secbash.validator import validate_command

# Exit code constants for consistency and documentation
EXIT_SUCCESS = 0
EXIT_BLOCKED = 1  # Command was blocked by security validation
EXIT_CANCELLED = 1  # User cancelled a warned command
EXIT_KEYBOARD_INTERRUPT = 130  # Standard exit code for Ctrl+C (128 + SIGINT)


def get_prompt() -> str:
    """Return the shell prompt string.

    The default prompt "secbash> " clearly identifies the shell
    while remaining concise. This is not configurable in the MVP.

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
    providers = get_available_providers()
    print(f"Active providers: {', '.join(providers)}")
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

            # Validate command with LLM before execution
            result = validate_command(command)

            if result["action"] == "allow":
                # Execute the command, passing last exit code for $?
                last_exit_code = execute_command(command, last_exit_code)
            elif result["action"] == "block":
                print(f"\nBLOCKED: {result['reason']}")
                last_exit_code = EXIT_BLOCKED
            elif result["action"] == "warn":
                print(f"\nWARNING: {result['reason']}")

                # Get user confirmation
                try:
                    response = input("Proceed anyway? [y/N]: ").strip().lower()
                    if response in ("y", "yes"):
                        # User confirmed, execute the command
                        last_exit_code = execute_command(command, last_exit_code)
                    else:
                        # User declined or pressed Enter
                        print("Command cancelled.\n")
                        last_exit_code = EXIT_CANCELLED
                except (KeyboardInterrupt, EOFError):
                    # Ctrl+C or Ctrl+D during prompt
                    print("\nCommand cancelled.\n")
                    last_exit_code = EXIT_KEYBOARD_INTERRUPT
            else:
                # Unknown action from LLM - treat as warning
                action = result.get("action", "unknown")
                print(f"\nWARNING: Unexpected validation response '{action}'. Proceed with caution.")

                # Get user confirmation (same as warn flow)
                try:
                    response = input("Proceed anyway? [y/N]: ").strip().lower()
                    if response in ("y", "yes"):
                        last_exit_code = execute_command(command, last_exit_code)
                    else:
                        print("Command cancelled.\n")
                        last_exit_code = EXIT_CANCELLED
                except (KeyboardInterrupt, EOFError):
                    print("\nCommand cancelled.\n")
                    last_exit_code = EXIT_KEYBOARD_INTERRUPT

        except KeyboardInterrupt:
            # Ctrl+C: cancel current input, show new prompt
            print()  # Move to new line
            last_exit_code = EXIT_KEYBOARD_INTERRUPT
            continue

        except EOFError:
            # Ctrl+D: exit the shell
            print()  # Move to new line
            break

    return 0
