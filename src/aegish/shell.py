"""Shell interaction module.

Handles the readline loop, prompt display, and user interaction
for the aegish shell.

Shell state (working directory, environment variables) persists across
commands. See docs/shell-state-persistence.md for design details.

readline is imported for line editing and command history support.
When imported, readline enables:
- Line editing (Ctrl+A, Ctrl+E, backspace, etc.)
- Session history navigation (up/down arrows)
- Persistent history across sessions (when init_history is called)
"""

import atexit
import logging
import os
import readline  # Provides line editing and history support
import sys

from aegish.config import (
    DEFAULT_FALLBACK_MODELS,
    DEFAULT_PRIMARY_MODEL,
    get_api_key,
    get_fail_mode,
    get_fallback_models,
    get_mode,
    get_model_chain,
    get_primary_model,
    get_provider_from_model,
    get_role,
    validate_runner_binary,
    validate_sandboxer_library,
)
from aegish.executor import (
    _build_safe_env,
    execute_command,
    is_bare_cd,
    resolve_cd,
)
from aegish.llm_client import health_check
from aegish.sandbox import landlock_available
from aegish.audit import init_audit_log, log_validation, log_warn_override
from aegish.validator import validate_command

logger = logging.getLogger(__name__)

# History configuration
HISTORY_FILE: str = os.path.expanduser("~/.aegish_history")
HISTORY_LENGTH: int = 1000
_history_initialized: bool = False  # Guard against duplicate atexit registration

# Exit code constants for consistency and documentation
EXIT_SUCCESS = 0
EXIT_BLOCKED = 1  # Command was blocked by security validation
EXIT_CANCELLED = 2  # User cancelled a warned command
EXIT_KEYBOARD_INTERRUPT = 130  # Standard exit code for Ctrl+C (128 + SIGINT)


def _is_login_shell() -> bool:
    """Detect if aegish is running as a login shell.

    Returns True if any of these conditions hold:
    - sys.argv[0] starts with '-' (login shell convention)
    - $SHELL points to an aegish binary
    - An aegish path appears in /etc/shells

    Returns:
        True if login shell context is detected.
    """
    # Convention: login shells have argv[0] starting with '-'
    if sys.argv[0].startswith("-"):
        return True

    # Check if $SHELL points to aegish
    shell_var = os.environ.get("SHELL", "")
    if "aegish" in os.path.basename(shell_var):
        return True

    # Check /etc/shells for aegish entries
    try:
        with open("/etc/shells") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "aegish" in os.path.basename(line):
                    return True
    except (FileNotFoundError, OSError):
        pass

    return False


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


def _handle_cd(
    command: str,
    current_dir: str,
    previous_dir: str,
    env: dict[str, str],
) -> tuple[int, str, str, dict[str, str]]:
    """Handle a bare cd command as fast path (no subprocess spawn).

    Args:
        command: The cd command string.
        current_dir: Current working directory.
        previous_dir: Previous working directory (for cd -).
        env: Current environment dict.

    Returns:
        Tuple of (exit_code, new_current_dir, new_previous_dir, updated_env).
    """
    stripped = command.strip()
    parts = stripped.split(None, 1)
    target = parts[1].strip() if len(parts) > 1 else ""

    resolved, error = resolve_cd(target, current_dir, env)
    if error:
        print(error)
        return 1, current_dir, previous_dir, env

    # cd - prints the new directory (bash behavior)
    if target == "-":
        print(resolved)

    new_previous = current_dir
    new_current = resolved

    # Update PWD/OLDPWD in env
    updated_env = dict(env)
    updated_env["PWD"] = new_current
    updated_env["OLDPWD"] = new_previous

    return 0, new_current, new_previous, updated_env


def _execute_and_update(
    command: str,
    last_exit_code: int,
    current_dir: str,
    previous_dir: str,
    env: dict[str, str],
) -> tuple[int, str, str, dict[str, str]]:
    """Execute a command via subprocess and update shell state.

    Args:
        command: The command string to execute.
        last_exit_code: Previous command's exit code (for $?).
        current_dir: Current working directory.
        previous_dir: Previous working directory.
        env: Current environment dict.

    Returns:
        Tuple of (exit_code, new_current_dir, new_previous_dir, updated_env).
    """
    exit_code, new_env, new_cwd = execute_command(
        command, last_exit_code, env=env, cwd=current_dir,
    )

    # If cwd changed (e.g. compound command with cd), update previous_dir
    new_previous = previous_dir
    if new_cwd != current_dir:
        new_previous = current_dir

    return exit_code, new_cwd, new_previous, new_env


def run_shell() -> int:
    """Run the interactive shell loop.

    Provides readline-based input with line editing support.
    Handles Ctrl+C (cancel input) and Ctrl+D (exit).
    Shell state (cwd, env) persists across commands.

    Returns:
        Exit code (0 for normal exit).
    """
    # Initialize persistent command history
    init_history()

    # Initialize audit logging (Story 15.1)
    if not init_audit_log():
        print("WARNING: Audit logging unavailable.", file=sys.stderr)

    # Track last exit code for $? expansion
    last_exit_code = 0

    # Initialize shell state
    current_dir = os.getcwd()
    previous_dir = current_dir
    env = _build_safe_env()
    env["PWD"] = current_dir
    env["OLDPWD"] = previous_dir

    print("aegish \u2014 LLM-powered security shell")
    print("\u2500" * 42)

    # Model chain: show primary + fallback summary
    model_chain = get_model_chain()
    primary = model_chain[0] if model_chain else "none"
    active_count = sum(
        1 for m in model_chain
        if get_api_key(get_provider_from_model(m)) is not None
    )
    inactive = len(model_chain) - active_count
    fallback_info = f"{active_count - 1} active" if active_count > 1 else "none"
    if inactive:
        fallback_info += f", {inactive} no key"
    print(f"  Primary:   {primary}")
    print(f"  Fallbacks: {fallback_info}")

    mode = get_mode()
    if mode == "production":
        print("  Mode:      production (login shell + Landlock)")
    else:
        print("  Mode:      development")
    fail_mode = get_fail_mode()
    if fail_mode == "safe":
        print("  Fail mode: safe (block on error)")
    else:
        print("  Fail mode: open (warn on error)")
    role = get_role()
    print(f"  Role:      {role}")

    print("\u2500" * 42)
    # Validate runner binary and sandboxer library in production mode
    if mode == "production":
        runner_ok, runner_msg = validate_runner_binary()
        if not runner_ok:
            print(f"FATAL: {runner_msg}", file=sys.stderr)
            sys.exit(1)

    if mode == "production":
        sandboxer_ok, sandboxer_msg = validate_sandboxer_library()
        if not sandboxer_ok:
            print(f"ERROR: {sandboxer_msg}")
            print("Falling back to development mode.\n")
            os.environ["AEGISH_MODE"] = "development"
            mode = "development"

    # Landlock availability warning in production mode
    if mode == "production":
        ll_available, ll_version = landlock_available()
        if ll_available:
            print(f"Landlock: active (ABI v{ll_version})")
        else:
            print("WARNING: Landlock not supported on this kernel. Sandbox disabled.")

    # Login shell lockout warning (Story 12.6)
    login_shell = _is_login_shell()
    if login_shell:
        print(
            "WARNING: aegish is configured as login shell. "
            "If LLM API becomes unreachable, you may be unable to execute commands."
        )

    print("Type 'exit' or press Ctrl+D to quit.\n")

    # Non-default model warnings (Story 9.3, FR50)
    primary = get_primary_model()
    if primary != DEFAULT_PRIMARY_MODEL:
        print(f"WARNING: Using non-default primary model: {primary}")
        print(f"         Default is: {DEFAULT_PRIMARY_MODEL}")

    fallbacks = get_fallback_models()
    if not fallbacks:
        print("WARNING: No fallback models configured. Single-provider mode.")
    elif fallbacks != DEFAULT_FALLBACK_MODELS:
        print(f"WARNING: Using non-default fallback models: {', '.join(fallbacks)}")
        print(f"         Default is: {DEFAULT_FALLBACK_MODELS[0]}")

    # Verify primary model responds correctly before entering shell loop
    success, reason, active_model = health_check()
    if not success:
        logger.warning("Health check failed: %s", reason)
        print(reason)
        if login_shell:
            print(
                "WARNING: All models unreachable. "
                "This is your login shell \u2014 commands may be blocked."
            )
        else:
            print("WARNING: All models unreachable. Operating in degraded mode.")
    elif active_model and active_model != get_primary_model():
        print(f"NOTE: Using fallback model: {active_model}")

    while True:
        try:
            # Get user input with prompt
            command = input(get_prompt())

            # Skip empty or whitespace-only input
            if not command.strip():
                continue

            # Handle exit command
            if command.strip() == "exit":
                if get_mode() == "production":
                    print("Session terminated.")
                    sys.exit(0)
                else:
                    print("WARNING: Leaving aegish. The parent shell is NOT security-monitored.")
                    break

            # Fast path: bare cd commands (no subprocess needed)
            if is_bare_cd(command):
                last_exit_code, current_dir, previous_dir, env = _handle_cd(
                    command, current_dir, previous_dir, env,
                )
                continue

            # Validate command with LLM before execution
            result = validate_command(command)

            if result["action"] == "allow":
                log_validation(command, "allow", result["reason"], result.get("confidence", 0.0))
                # Execute the command with state persistence
                last_exit_code, current_dir, previous_dir, env = (
                    _execute_and_update(
                        command, last_exit_code,
                        current_dir, previous_dir, env,
                    )
                )
            elif result["action"] == "block":
                log_validation(command, "block", result["reason"], result.get("confidence", 0.0))
                print(f"\nBLOCKED: {result['reason']}")
                last_exit_code = EXIT_BLOCKED
            elif result["action"] == "warn":
                log_validation(command, "warn", result["reason"], result.get("confidence", 0.0))
                print(f"\nWARNING: {result['reason']}")

                # Get user confirmation
                try:
                    response = input("Proceed anyway? [y/N]: ").strip().lower()
                    if response in ("y", "yes"):
                        log_warn_override(command, result["reason"])
                        # User confirmed, execute the command
                        last_exit_code, current_dir, previous_dir, env = (
                            _execute_and_update(
                                command, last_exit_code,
                                current_dir, previous_dir, env,
                            )
                        )
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
                        last_exit_code, current_dir, previous_dir, env = (
                            _execute_and_update(
                                command, last_exit_code,
                                current_dir, previous_dir, env,
                            )
                        )
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
            if get_mode() == "production":
                print("Session terminated.")
                sys.exit(0)
            else:
                print("WARNING: Leaving aegish. The parent shell is NOT security-monitored.")
                break

    return 0
