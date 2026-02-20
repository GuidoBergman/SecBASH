"""Command validation module.

Validates commands using the LLM client and returns
security decisions (allow, warn, or block).
"""

import logging

import bashlex

from aegish.config import get_var_cmd_action
from aegish.constants import ACTION_SEVERITY, META_EXEC_BUILTINS, STATIC_BLOCK_PATTERNS
from aegish.llm_client import query_llm

logger = logging.getLogger(__name__)

# Backward-compatible aliases (constants moved to aegish.constants)
_META_EXEC_BUILTINS = META_EXEC_BUILTINS
_STATIC_BLOCK_PATTERNS = STATIC_BLOCK_PATTERNS
_ACTION_SEVERITY = ACTION_SEVERITY


# ---- Primary public API ----


def validate_command(command: str) -> dict:
    """Validate a command using the LLM.

    Args:
        command: The shell command to validate.

    Returns:
        dict with keys:
            - action: "allow" | "warn" | "block"
            - reason: Human-readable explanation
            - confidence: float 0.0 - 1.0
    """
    if not command or not command.strip():
        return {
            "action": "block",
            "reason": "Empty command",
            "confidence": 1.0,
        }

    # Static blocklist check (Story 10.5) — fastest, runs first
    blocklist_result = _check_static_blocklist(command)
    if blocklist_result is not None:
        return blocklist_result

    # Bashlex AST check for variable-in-command-position
    bashlex_result = _check_variable_in_command_position(command)
    if bashlex_result is not None:
        return bashlex_result

    # Recursive decomposition for compound commands (Story 10.4)
    decomposed = _decompose_and_validate(command)
    if decomposed is not None:
        return decomposed

    # Single-pass LLM fallback
    return query_llm(command)


# ---- Fast path: static blocklist ----


def _check_static_blocklist(command: str) -> dict | None:
    """Check command against static regex blocklist.

    Returns BLOCK dict if a known dangerous pattern is matched, None otherwise.
    """
    for pattern, reason in _STATIC_BLOCK_PATTERNS:
        if pattern.search(command):
            logger.info("Static blocklist match (%s): %s", reason, command)
            return {
                "action": "block",
                "reason": reason,
                "confidence": 1.0,
            }
    return None


# ---- Bashlex check: variable in command position ----


def _check_variable_in_command_position(command: str) -> dict | None:
    """Detect variable expansion in command position with preceding assignment.

    Parses the command with bashlex and walks the AST to find patterns like
    `a=ba; b=sh; $a$b` where variables are constructed and then used as commands.

    Returns:
        WARN dict if suspicious pattern detected, None if safe or on parse error.
    """
    try:
        parts = bashlex.parse(command)

        # Top-level: check for assignments among all top-level command nodes
        top_has_assignment = any(
            sub.kind == "assignment"
            for node in parts
            if node.kind == "command"
            for sub in node.parts
        )

        reason = _find_var_in_command_position(parts, top_has_assignment)
        if reason is not None:
            action = get_var_cmd_action()
            logger.info(
                "Variable expansion in command position detected (%s): %s",
                action,
                command,
            )
            return {
                "action": action,
                "reason": reason,
                "confidence": 1.0,
            }
    except Exception:
        logger.debug("bashlex analysis failed for command: %s", command)

    return None


# ---- Compound command handling ----


def _decompose_and_validate(command: str) -> dict | None:
    """Decompose compound commands and validate subcommands independently.

    For compound commands (;, &&, ||): splits into subcommands and validates
    each via the LLM independently. Most-restrictive-wins aggregation.
    Early-exits on BLOCK.

    For command substitutions in execution position: blocks immediately.

    Returns:
        Aggregated validation result if decomposition succeeded,
        None if command is not compound or parse fails (fall through to LLM).
    """
    # Check for command substitution in execution position
    cmdsub_reason = _has_command_substitution_in_exec_pos(command)
    if cmdsub_reason is not None:
        logger.info("Command substitution in exec pos: %s", command)
        return {
            "action": "block",
            "reason": cmdsub_reason,
            "confidence": 1.0,
        }

    # Decompose compound commands
    subcommands = _extract_subcommand_strings(command)
    if subcommands is None:
        return None  # Not compound, fall through to single-pass LLM

    logger.debug(
        "Decomposed '%s' into %d subcommands: %s",
        command,
        len(subcommands),
        subcommands,
    )

    results = []
    for sub in subcommands:
        # Run each subcommand through the full validation pipeline
        # (static blocklist + bashlex + LLM)
        result = validate_command(sub)
        results.append(result)

        # Early exit on BLOCK
        if result.get("action") == "block":
            logger.info(
                "Early exit: subcommand '%s' blocked: %s",
                sub,
                result.get("reason"),
            )
            return result

    return _most_restrictive(results)


# ---- AST helpers ----


def _find_var_in_command_position(nodes, has_assignment: bool) -> str | None:
    """Walk AST nodes to find variable expansion in command position.

    Finds the first word-kind part in each CommandNode (skipping leading
    inline assignments like ``FOO=bar $CMD``) and checks for parameter
    expansion.  If the compound command also contains assignments, this
    is a suspicious pattern.

    For pipelines, each pipeline segment is checked independently —
    variable in command position in any segment triggers detection.

    Returns:
        Reason string if detected, None if safe.
    """
    for node in nodes:
        if node.kind == "pipeline":
            # Check each command in the pipeline independently
            pipe_commands = [p for p in node.parts if p.kind == "command"]
            for cmd in pipe_commands:
                result = _check_meta_exec_command(cmd, has_assignment)
                if result is not None:
                    return result
                # Also check for bare var-in-cmd-pos in pipeline
                first_word = next(
                    (p for p in cmd.parts if p.kind == "word"), None
                )
                if first_word is not None and _has_parameter_expansion(first_word):
                    return "Variable expansion in command position in pipeline"

        elif node.kind == "command":
            result = _check_meta_exec_command(node, has_assignment)
            if result is not None:
                return result

        elif node.kind == "list":
            # Collect whether any command in the list has assignments,
            # or inherit from parent scope (Story 10.3: propagate into
            # control-flow bodies)
            list_has_assignment = has_assignment or any(
                sub.kind == "assignment"
                for part in node.parts
                if part.kind == "command"
                for sub in part.parts
            )
            result = _find_var_in_command_position(
                node.parts, list_has_assignment
            )
            if result is not None:
                return result

        elif node.kind == "compound":
            result = _find_var_in_command_position(node.list, has_assignment)
            if result is not None:
                return result

        elif node.kind == "for":
            # For-loops implicitly assign the loop variable, so treat
            # has_assignment as True for the loop body (Story 10.3)
            if hasattr(node, "parts") and node.parts:
                result = _find_var_in_command_position(
                    node.parts, True
                )
                if result is not None:
                    return result

        elif node.kind in ("if", "while", "until", "function"):
            # Control-flow and function nodes: recurse into their parts
            # to find nested list/command/compound nodes (Story 10.3)
            if hasattr(node, "parts") and node.parts:
                result = _find_var_in_command_position(
                    node.parts, has_assignment
                )
                if result is not None:
                    return result

        else:
            # Generic fallback for unknown node kinds: recurse into
            # parts if present (Story 10.3)
            if hasattr(node, "parts") and node.parts:
                result = _find_var_in_command_position(
                    node.parts, has_assignment
                )
                if result is not None:
                    return result

    return None


def _check_meta_exec_command(cmd_node, has_assignment: bool) -> str | None:
    """Check a single command node for meta-exec builtin + variable pattern.

    Returns reason string if detected, None if safe.
    """
    words = [p for p in cmd_node.parts if p.kind == "word"]
    if not words:
        return None

    first_word = words[0]

    # Check for variable expansion in command position (original logic)
    if _has_parameter_expansion(first_word) and has_assignment:
        return (
            "Variable expansion in command position"
            " with preceding assignment"
        )

    # Check for meta-exec builtins (Story 10.2)
    if (
        not _has_parameter_expansion(first_word)
        and hasattr(first_word, "word")
        and first_word.word in _META_EXEC_BUILTINS
        and has_assignment
        and len(words) > 1
        and any(_has_variable_reference(w) for w in words[1:])
    ):
        return (
            f"Meta-execution builtin '{first_word.word}' with variable"
            " reference after assignment"
        )

    return None


def _has_parameter_expansion(node) -> bool:
    """Check if a word node contains parameter expansion."""
    return bool(
        hasattr(node, "parts")
        and node.parts
        and any(p.kind == "parameter" for p in node.parts)
    )


def _has_variable_reference(node) -> bool:
    """Check if a word node references a variable (including inside quotes).

    This is broader than _has_parameter_expansion: it also catches
    single-quoted ``$var`` references that bashlex treats as literals
    but meta-exec builtins like ``eval`` will re-expand at runtime.
    """
    if _has_parameter_expansion(node):
        return True
    # Catch single-quoted $var that bashlex doesn't parse as ParameterNode
    return hasattr(node, "word") and "$" in node.word


# ---- Decomposition helpers ----


def _extract_subcommand_strings(command: str) -> list[str] | None:
    """Extract individual subcommand strings from a compound command.

    Parses the command with bashlex and extracts text spans for each
    command node found in list (;, &&, ||) and pipeline (|) constructs.

    Returns:
        List of subcommand strings if compound command detected,
        None if simple command or parse failure.
    """
    try:
        parts = bashlex.parse(command)
    except Exception:
        return None

    subcommands = []

    def _collect_commands(nodes):
        for node in nodes:
            if node.kind == "command":
                # Extract the text span from the original command
                sub = command[node.pos[0]:node.pos[1]].strip()
                if sub:
                    subcommands.append(sub)
            elif node.kind == "pipeline":
                # For pipelines, treat the whole pipeline as one unit
                sub = command[node.pos[0]:node.pos[1]].strip()
                if sub:
                    subcommands.append(sub)
            elif node.kind == "list":
                _collect_commands(node.parts)
            elif node.kind == "compound":
                # Compound braces/subshells: extract as whole unit
                sub = command[node.pos[0]:node.pos[1]].strip()
                if sub:
                    subcommands.append(sub)
            elif node.kind in ("for", "if", "while", "until", "function"):
                # Control-flow: extract as whole unit
                sub = command[node.pos[0]:node.pos[1]].strip()
                if sub:
                    subcommands.append(sub)

    _collect_commands(parts)

    # Only decompose if we found multiple subcommands
    if len(subcommands) <= 1:
        return None

    return subcommands


def _has_command_substitution_in_exec_pos(command: str) -> str | None:
    """Check for command substitution ($() or backticks) in execution position.

    A command substitution in execution position means the output of the
    substitution will be used as the command name itself, e.g. $(echo rm) -rf /.

    Returns:
        Reason string if detected, None if safe or on parse error.
    """
    try:
        parts = bashlex.parse(command)
    except Exception:
        return None

    def _check_nodes(nodes):
        for node in nodes:
            if node.kind == "command":
                first_word = next(
                    (p for p in node.parts if p.kind == "word"), None
                )
                if (
                    first_word is not None
                    and hasattr(first_word, "parts")
                    and first_word.parts
                    and any(
                        p.kind == "commandsubstitution"
                        for p in first_word.parts
                    )
                ):
                    return (
                        "Command substitution in execution position"
                    )
            elif node.kind == "pipeline":
                for sub in node.parts:
                    if sub.kind == "command":
                        r = _check_nodes([sub])
                        if r is not None:
                            return r
            elif node.kind == "list":
                r = _check_nodes(node.parts)
                if r is not None:
                    return r
            elif node.kind == "compound":
                r = _check_nodes(node.list)
                if r is not None:
                    return r
        return None

    return _check_nodes(parts)


def _most_restrictive(results: list[dict]) -> dict:
    """Return the most restrictive result from a list of validation results.

    Uses _ACTION_SEVERITY ordering: block > warn > allow.
    """
    if not results:
        return {"action": "allow", "reason": "No subcommands", "confidence": 1.0}
    return max(results, key=lambda r: _ACTION_SEVERITY.get(r.get("action", "allow"), 0))
