"""Command validation module.

Validates commands using the LLM client and returns
security decisions (allow, warn, or block).
"""

import logging

import bashlex

from aegish.llm_client import query_llm

logger = logging.getLogger(__name__)


def _has_parameter_expansion(node) -> bool:
    """Check if a word node contains parameter expansion."""
    return bool(
        hasattr(node, "parts")
        and node.parts
        and any(p.kind == "parameter" for p in node.parts)
    )


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
                first_word = next(
                    (p for p in cmd.parts if p.kind == "word"), None
                )
                if first_word is not None and _has_parameter_expansion(first_word):
                    return "Variable expansion in command position in pipeline"

        elif node.kind == "command":
            # Find first word part, skipping leading inline assignments
            first_word = next(
                (p for p in node.parts if p.kind == "word"), None
            )
            if (
                first_word is not None
                and _has_parameter_expansion(first_word)
                and has_assignment
            ):
                return (
                    "Variable expansion in command position"
                    " with preceding assignment"
                )

        elif node.kind == "list":
            # Collect whether any command in the list has assignments
            list_has_assignment = any(
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

    return None


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
            logger.info(
                "Variable expansion in command position detected: %s", command
            )
            return {
                "action": "warn",
                "reason": reason,
                "confidence": 1.0,
            }
    except Exception:
        logger.debug("bashlex analysis failed for command: %s", command)

    return None


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

    bashlex_result = _check_variable_in_command_position(command)
    if bashlex_result is not None:
        return bashlex_result

    return query_llm(command)
