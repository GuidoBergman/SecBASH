"""Command substitution resolver module.

Extracts $(...) patterns from canonical commands, validates inner commands
through the validation pipeline, and resolves ALLOW'd substitutions by
executing them and substituting their stdout output.

Resolution is recursive with a depth limit (default 2) and per-command
timeout (default 3s). Inner commands that are WARN'd or BLOCK'd are
annotated but not executed.
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ResolutionEntry:
    """Log entry for a single substitution resolution attempt."""

    pattern: str          # Original $(cmd) text
    inner_command: str    # The extracted inner command
    status: str           # "resolved" | "warned" | "blocked" | "error" | "depth_exceeded"
    output: str | None    # Captured stdout (when resolved)
    reason: str | None    # Why it wasn't resolved


def resolve_substitutions(
    command: str,
    depth: int = 0,
    max_depth: int = 2,
    timeout: int = 3,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> tuple[str, list[ResolutionEntry]]:
    """Resolve command substitutions in a canonical command.

    Extracts $(...) patterns, validates each inner command, and for
    ALLOW'd commands executes them to capture stdout. Resolved output
    replaces the substitution in the returned command text.

    Args:
        command: Canonical command text (backticks already converted to $()).
        depth: Current recursion depth.
        max_depth: Maximum allowed recursion depth.
        timeout: Seconds to allow each inner command execution.
        env: Shell environment dict for execution.
        cwd: Working directory for execution.

    Returns:
        Tuple of (resolved_command_text, resolution_log).
    """
    log: list[ResolutionEntry] = []

    if "$(" not in command:
        return command, log

    # Extract innermost $(...) patterns first (bottom-up resolution)
    substitutions = _extract_innermost_substitutions(command)
    if not substitutions:
        return command, log

    # Lazy import to avoid circular dependency
    from aegish.validator import validate_command as _validate_command
    from aegish.executor import execute_for_resolution

    resolved = command
    for pattern, inner_cmd in substitutions:
        if depth >= max_depth:
            entry = ResolutionEntry(
                pattern=pattern,
                inner_command=inner_cmd,
                status="depth_exceeded",
                output=None,
                reason=f"Recursion depth {depth} >= max {max_depth}",
            )
            log.append(entry)
            continue

        # Validate the inner command through the full pipeline
        try:
            result = _validate_command(inner_cmd, _depth=depth + 1)
        except Exception as exc:
            entry = ResolutionEntry(
                pattern=pattern,
                inner_command=inner_cmd,
                status="error",
                output=None,
                reason=f"Validation error: {exc}",
            )
            log.append(entry)
            continue

        action = result.get("action", "block")

        if action == "block":
            entry = ResolutionEntry(
                pattern=pattern,
                inner_command=inner_cmd,
                status="blocked",
                output=None,
                reason=result.get("reason", "Blocked by validation"),
            )
            log.append(entry)
            continue

        if action == "warn":
            entry = ResolutionEntry(
                pattern=pattern,
                inner_command=inner_cmd,
                status="warned",
                output=None,
                reason=result.get("reason", "Warned by validation"),
            )
            log.append(entry)
            continue

        # ALLOW — execute and capture stdout
        try:
            proc = execute_for_resolution(
                inner_cmd, env=env, cwd=cwd, timeout=timeout,
            )
            stdout = proc.stdout or ""
            # Strip trailing newline (bash substitution behavior)
            stdout = stdout.rstrip("\n")

            entry = ResolutionEntry(
                pattern=pattern,
                inner_command=inner_cmd,
                status="resolved",
                output=stdout,
                reason=None,
            )
            log.append(entry)

            # Substitute the resolved output into the command
            resolved = resolved.replace(pattern, stdout, 1)

        except Exception as exc:
            entry = ResolutionEntry(
                pattern=pattern,
                inner_command=inner_cmd,
                status="error",
                output=None,
                reason=f"Execution error: {exc}",
            )
            log.append(entry)

    return resolved, log


def _extract_innermost_substitutions(
    text: str,
) -> list[tuple[str, str]]:
    """Extract innermost $(...) substitutions from text.

    Uses a balanced-parenthesis scanner to correctly handle nested
    substitutions. Returns innermost patterns first for bottom-up
    resolution.

    Returns:
        List of (full_pattern, inner_command) tuples.
        full_pattern includes "$(" and ")".
    """
    results = []
    i = 0
    while i < len(text) - 1:
        # Find $( start
        if text[i] == "$" and text[i + 1] == "(":
            start = i
            # Scan for balanced closing paren
            depth = 0
            j = i + 1
            in_single_quote = False
            in_double_quote = False
            while j < len(text):
                ch = text[j]

                # Handle escapes
                if j > 0 and text[j - 1] == "\\":
                    j += 1
                    continue

                # Track quoting context
                if ch == "'" and not in_double_quote:
                    in_single_quote = not in_single_quote
                elif ch == '"' and not in_single_quote:
                    in_double_quote = not in_double_quote
                elif not in_single_quote and not in_double_quote:
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                        if depth == 0:
                            # Found the matching close paren
                            full_pattern = text[start:j + 1]
                            inner = text[start + 2:j]

                            if "$(" not in inner:
                                # Innermost — add it
                                results.append((full_pattern, inner))
                            # else: contains nested $() — don't add, the
                            # inner ones are already found or will be found.
                            break
                j += 1
            # Always advance past $( to continue scanning for inner/sibling patterns
            i = start + 2
            continue
        i += 1

    return results
