"""Command validation module.

Validates commands using the LLM client and returns
security decisions (allow, warn, or block).
"""

from secbash.llm_client import query_llm


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
    return query_llm(command)
