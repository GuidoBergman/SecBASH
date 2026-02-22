"""Command substitution resolver module.

Extracts $(...) patterns from canonical commands, validates inner commands
through the validation pipeline, and resolves ALLOW'd substitutions by
executing them and substituting their stdout output.

Resolution is recursive with a depth limit (default 2) and per-command
timeout (default 3s). Inner commands that are WARN'd or BLOCK'd are
annotated but not executed.
"""

import logging
from dataclasses import dataclass

import bashlex

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


def _contains_cmdsub(node) -> bool:
    """Check if any descendant of a bashlex AST node is a commandsubstitution."""
    if node.kind == "commandsubstitution":
        return True
    for attr in ("parts", "list"):
        children = getattr(node, attr, None)
        if children:
            for child in children:
                if _contains_cmdsub(child):
                    return True
    command = getattr(node, "command", None)
    if command and _contains_cmdsub(command):
        return True
    return False


def _collect_innermost_cmdsubs(node, results: list) -> None:
    """Walk a bashlex AST and collect innermost commandsubstitution nodes."""
    if node.kind == "commandsubstitution":
        # Innermost if .command subtree has no further commandsubstitution
        command = getattr(node, "command", None)
        if not command or not _contains_cmdsub(command):
            results.append(node)
            return
    # Recurse into children
    for attr in ("parts", "list"):
        children = getattr(node, attr, None)
        if children:
            for child in children:
                _collect_innermost_cmdsubs(child, results)
    command = getattr(node, "command", None)
    if command:
        _collect_innermost_cmdsubs(command, results)


def _extract_via_bashlex(text: str) -> list[tuple[str, str]]:
    """Extract innermost $() substitutions using bashlex AST.

    Raises on parse error — caller should catch and fall back.
    """
    parts = bashlex.parse(text)
    cmdsub_nodes: list = []
    for p in parts:
        _collect_innermost_cmdsubs(p, cmdsub_nodes)

    results = []
    for node in cmdsub_nodes:
        s, e = node.pos
        # bashlex sometimes excludes the closing ) from pos
        if e < len(text) and text[e] == ")" and (e == s or text[e - 1] != ")"):
            e += 1
        full_pattern = text[s:e]
        inner_command = text[s + 2:e - 1]
        results.append((full_pattern, inner_command))
    return results


def _extract_via_scanner(text: str) -> list[tuple[str, str]]:
    """Fallback: extract innermost $() using balanced-paren scanner.

    Used when bashlex cannot parse the input (arithmetic expansion,
    escaped dollar signs, bare parens, empty substitution, etc.).
    Tracks top-level quoting and escaping to avoid false extractions.

    Returns:
        List of (full_pattern, inner_command) tuples.
    """
    results = []
    i = 0
    outer_in_single_quote = False
    outer_in_double_quote = False

    while i < len(text) - 1:
        ch = text[i]

        # Track top-level quoting
        if ch == "'" and not outer_in_double_quote:
            outer_in_single_quote = not outer_in_single_quote
            i += 1
            continue
        if ch == '"' and not outer_in_single_quote:
            outer_in_double_quote = not outer_in_double_quote
            i += 1
            continue

        # Skip everything inside single quotes
        if outer_in_single_quote:
            i += 1
            continue

        # Find $( start
        if ch == "$" and text[i + 1] == "(":
            # Skip escaped $
            if i > 0 and text[i - 1] == "\\":
                i += 1
                continue

            # Skip arithmetic expansion $((
            if i + 2 < len(text) and text[i + 2] == "(":
                i += 3
                continue

            start = i
            # Scan for balanced closing paren
            depth = 0
            j = i + 1
            in_single_quote = False
            in_double_quote = False
            while j < len(text):
                ch2 = text[j]

                # Handle escapes
                if j > 0 and text[j - 1] == "\\":
                    j += 1
                    continue

                # Track quoting context
                if ch2 == "'" and not in_double_quote:
                    in_single_quote = not in_single_quote
                elif ch2 == '"' and not in_single_quote:
                    in_double_quote = not in_double_quote
                elif not in_single_quote and not in_double_quote:
                    if ch2 == "(":
                        depth += 1
                    elif ch2 == ")":
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


def _extract_innermost_substitutions(
    text: str,
) -> list[tuple[str, str]]:
    """Extract innermost $(...) substitutions from text.

    Uses bashlex as primary parser for correct handling of quoting,
    nesting, and escaping. Falls back to a balanced-parenthesis scanner
    when bashlex cannot parse the input (arithmetic expansion, escaped
    dollar signs, bare parens, empty substitution, etc.).

    Returns:
        List of (full_pattern, inner_command) tuples.
        full_pattern includes "$(" and ")".
    """
    try:
        return _extract_via_bashlex(text)
    except Exception:
        logger.debug(
            "bashlex parse failed for substitution extraction, "
            "using fallback scanner: %s",
            text,
        )
        return _extract_via_scanner(text)
