"""Shell interaction module.

Handles the readline loop, prompt display, and user interaction
for the aegish shell.

readline is imported for line editing and command history support.
When imported, readline enables:
- Line editing (Ctrl+A, Ctrl+E, backspace, etc.)
- Session history navigation (up/down arrows)
- Persistent history across sessions (when init_history is called)
"""

import atexit
import os
import readline  # Provides line editing and history support

from aegish.config import get_api_key, get_model_chain, get_provider_from_model
from aegish.executor import execute_command
from aegish.validator import validate_command

# History configuration
HISTORY_FILE: str = os.path.expanduser("~/.aegish_history")
HISTORY_LENGTH: int = 1000
_history_initialized: bool = False  # Guard against duplicate atexit registration

# Exit code constants for consistency and documentation
EXIT_SUCCESS = 0
EXIT_BLOCKED = 1  # Command was blocked by security validation
EXIT_CANCELLED = 2  # User cancelled a warned command
EXIT_KEYBOARD_INTERRUPT = 130  # Standard exit code for Ctrl+C (128 + SIGINT)


def init_history() -> None:
    """Initialize readline history from persistent file.

    Loads command history from HISTORY_FILE if it exists.
    Registers atexit handler to save history on shell exit.

    History features enabled:
    - Session navigation with up/down arrows
    - Persistent history across sessions (stored in ~/.aegish_history)
    - History limited to HISTORY_LENGTH commands (default: 1000)
    """
    global _history_initialized

    readline.set_history_length(HISTORY_LENGTH)

    try:
        readline.read_history_file(HISTORY_FILE)
    except (FileNotFoundError, OSError):
        # No history file yet, or file not readable - will be created on exit
        pass

    # Register handler only once to avoid duplicate writes on exit
    if not _history_initialized:
        atexit.register(readline.write_history_file, HISTORY_FILE)
        _history_initialized = True


def get_prompt() -> str:
    """Return the shell prompt string.

    The default prompt "aegish> " clearly identifies the shell
    while remaining concise. This is not configurable in the MVP.

    Returns:
        Prompt string, default is "aegish> "
    """
    return "aegish> "


def run_shell() -> int:
    """Run the interactive shell loop.

    Provides readline-based input with line editing support.
    Handles Ctrl+C (cancel input) and Ctrl+D (exit).

    Returns:
        Exit code (0 for normal exit).
    """
    # Initialize persistent command history
    init_history()

    # Track last exit code for $? expansion
    last_exit_code = 0

    print("aegish - LLM-powered shell with security validation")
    # Show model chain with availability status
    model_chain = get_model_chain()
    model_display_parts = []
    for model in model_chain:
        provider = get_provider_from_model(model)
        has_key = get_api_key(provider) is not None
        status = "active" if has_key else "--"
        model_display_parts.append(f"{model} ({status})")
    print(f"Model chain: {' > '.join(model_display_parts)}")
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
