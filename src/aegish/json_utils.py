"""JSON extraction utilities for parsing LLM responses.

Ported from benchmark/scorers/security_scorer.py for production use.
Handles common LLM response quirks: markdown fences, double braces,
and extra text surrounding JSON objects.
"""

import re


def find_balanced_json(text: str) -> str | None:
    """Find and extract the first balanced JSON object from text.

    Handles:
    - Markdown ```json fences: strips fence wrapper, extracts JSON inside
    - Raw JSON: finds first { and tracks balanced braces
    - Double-braced ``{{...}}``: normalizes to single braces before parsing

    This is safe for our expected schema (flat objects with no nesting).

    Args:
        text: Raw text potentially containing a JSON object.

    Returns:
        The extracted JSON string, or None if no balanced JSON found.
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # Strip markdown code fences first
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Normalize double braces to single before depth tracking
    normalized = text.replace("{{", "{").replace("}}", "}")

    start = normalized.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i, char in enumerate(normalized[start:], start):
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return normalized[start : i + 1]

    return None
