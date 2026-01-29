"""Command validation module.

Parses LLM responses and decides the action to take
(allow, warn, or block) based on the security assessment.
"""


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
    raise NotImplementedError("Command validation not yet implemented")


def parse_llm_response(response: str) -> dict:
    """Parse the LLM response into a structured decision.

    Args:
        response: Raw LLM response text.

    Returns:
        dict with action, reason, and confidence.
    """
    raise NotImplementedError("LLM response parsing not yet implemented")
