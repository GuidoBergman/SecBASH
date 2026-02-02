"""LLM client module.

Handles API calls to LLM providers with fallback chain:
1. OpenRouter (LlamaGuard)
2. OpenAI
3. Anthropic
4. Warn user when all providers fail (validation unavailable)
"""

import json
import logging

from litellm import completion

from secbash.config import get_available_providers

logger = logging.getLogger(__name__)

# Maximum command length to send to LLM (prevents token limit issues and excessive costs)
MAX_COMMAND_LENGTH = 4096

# Model configuration per provider
# Default models chosen for security validation:
# - OpenRouter: LlamaGuard 3 8B - purpose-built for content safety classification
# - OpenAI: GPT-4 - strong reasoning for security analysis
# - Anthropic: Claude 3 Haiku - fast, cost-effective fallback
PROVIDER_MODELS = {
    "openrouter": "openrouter/meta-llama/llama-guard-3-8b",
    "openai": "openai/gpt-4",
    "anthropic": "anthropic/claude-3-haiku-20240307",
}

# Provider priority order
# OpenRouter preferred: LlamaGuard is specifically designed for security checks.
# Fallback to general-purpose models if OpenRouter unavailable.
PROVIDER_PRIORITY = ["openrouter", "openai", "anthropic"]

# System prompt for general LLM providers (not LlamaGuard)
SYSTEM_PROMPT = """You are a security validator for shell commands. Analyze the given command and respond with a JSON object containing:
- "action": "allow", "warn", or "block"
- "reason": A brief explanation of your decision
- "confidence": A float between 0.0 and 1.0 indicating your confidence

DANGEROUS PATTERNS TO BLOCK:
- Destructive filesystem commands: rm -rf /, rm -rf /*, dd if=/dev/zero of=/dev/sdX, mkfs on mounted partitions
- Fork bombs and resource exhaustion: :(){ :|:& };:, infinite recursive process spawning
- Reverse shells and unauthorized remote access: bash -i >& /dev/tcp/*, nc -e /bin/bash
- System file modification: writing to /etc/passwd, /etc/shadow, /etc/sudoers
- Privilege escalation attacks: unauthorized sudo abuse, setuid manipulation
- Shell escape patterns that spawn interactive shells: vim -c ':!bash', python -c 'import os; os.system("bash")', less/more shell escapes, awk/perl/ruby/lua shell spawning, any command that spawns an unrestricted shell to bypass security controls
- Downloading and executing remote code: curl URL | bash, wget URL | sh, eval $(curl URL)

RISKY PATTERNS TO WARN:
- Excessive permissions: chmod 777 on system directories, recursive permission changes to sensitive paths
- Mass file operations: rm -rf on user directories (~/*)
- Commands with excessive privileges for the apparent task

SAFE COMMANDS TO ALLOW:
- Standard file operations on user directories: ls, cat, head, tail, cp, mv (within user space)
- Common utilities: pwd, whoami, date, hostname, uname, id, uptime
- System monitoring: ps, top, htop, df, du, free
- Search operations: grep, find, locate, wc
- Version control: git status, git log, git diff, git branch
- Package listing (not installing with elevated privileges)

Respond ONLY with valid JSON, no other text."""

# LlamaGuard-specific prompt (it has its own output format)
# Note: Curly braces must be doubled to escape them in .format() strings
LLAMAGUARD_PROMPT = """Evaluate this shell command for security risks: {command}

Consider these threat categories:
- Filesystem destruction: rm -rf /, rm -rf /*, dd to disk devices, mkfs formatting
- Fork bombs and denial of service: :(){{:|:&}};:, recursive process spawning
- Remote code execution: curl URL | bash, wget | sh, eval $(curl)
- Shell escape patterns: any command that spawns an interactive shell (vim :!sh, python os.system, perl exec, awk system, ruby exec, lua os.execute, less/more shell escapes)
- Reverse shells: bash -i >& /dev/tcp/*, nc -e /bin/bash
- System file tampering: /etc/passwd, /etc/shadow modifications"""


class ParseError(Exception):
    """Raised when LLM response cannot be parsed."""


def query_llm(command: str) -> dict:
    """Query the LLM to validate a shell command.

    Tries each available provider in priority order. If a provider fails
    (API error or unparseable response), tries the next one. If all fail,
    returns a warn response so the user can decide whether to proceed.

    Args:
        command: The shell command to validate.

    Returns:
        A dict with keys: action, reason, confidence.
        On failure, returns warn response (action="warn", confidence=0.0).
    """
    # Validate command length to prevent token limit issues and excessive costs
    if len(command) > MAX_COMMAND_LENGTH:
        logger.warning(
            "Command exceeds maximum length (%d > %d)",
            len(command),
            MAX_COMMAND_LENGTH,
        )
        return _validation_failed_response(
            f"Command too long ({len(command)} chars)"
        )

    # Check if any providers are available
    available = get_available_providers()
    if not available:
        logger.warning("No LLM providers configured")
        return _validation_failed_response("No API keys configured")

    # Get ordered list of available providers to try
    providers_to_try = [p for p in PROVIDER_PRIORITY if p in available]

    last_error = None
    for provider in providers_to_try:
        model = PROVIDER_MODELS[provider]
        try:
            result = _try_provider(command, provider, model)
            if result is not None:
                return result
            # Parsing failed, try next provider
            last_error = f"{provider}: response could not be parsed"
            logger.warning("Parsing failed for %s, trying next provider", provider)

        except Exception as e:
            last_error = f"{provider}: {type(e).__name__}: {str(e)}"
            logger.warning(
                "Provider %s failed (%s: %s), trying next provider",
                provider,
                type(e).__name__,
                str(e),
            )
            continue

    # All providers failed
    logger.warning("All LLM providers failed, last error: %s", last_error)
    return _validation_failed_response(last_error or "All providers failed")


def _try_provider(command: str, provider: str, model: str) -> dict | None:
    """Try a single provider and return parsed result.

    Args:
        command: The shell command to validate.
        provider: Provider name (openrouter, openai, anthropic).
        model: Full model string for LiteLLM.

    Returns:
        Parsed response dict if successful, None if parsing failed.

    Raises:
        Exception: If API call fails.
    """
    messages = _get_messages_for_model(command, provider)

    response = completion(
        model=model,
        messages=messages,
        caching=True,
    )

    content = response.choices[0].message.content

    # Parse based on provider type
    if provider == "openrouter":
        return _parse_llamaguard_response(content, command)
    return _parse_response(content)


def _get_messages_for_model(command: str, provider: str) -> list[dict]:
    """Get the appropriate message format for a provider.

    Args:
        command: The shell command to validate.
        provider: Provider name.

    Returns:
        List of message dicts for the LLM API.
    """
    if provider == "openrouter":
        return [{"role": "user", "content": LLAMAGUARD_PROMPT.format(command=command)}]

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Validate this command: {command}"},
    ]


def _parse_response(content: str) -> dict | None:
    """Parse LLM response content into structured format.

    Args:
        content: Raw response content from LLM.

    Returns:
        Parsed dict with action, reason, confidence.
        Returns None if parsing fails (caller should try next provider).
    """
    try:
        data = json.loads(content)

        action = data.get("action", "").lower()
        if action not in ["allow", "warn", "block"]:
            logger.warning("Invalid action '%s' in LLM response", action)
            return None

        reason = data.get("reason", "No reason provided")
        confidence = float(data.get("confidence", 0.5))

        # Clamp confidence to valid range
        confidence = max(0.0, min(1.0, confidence))

        return {
            "action": action,
            "reason": reason,
            "confidence": confidence,
        }

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("Failed to parse LLM response: %s", e)
        return None


def _parse_llamaguard_response(content: str, command: str) -> dict | None:
    """Parse LlamaGuard-specific response format.

    LlamaGuard returns either:
    - "safe" for safe content
    - "unsafe\\nS1" (or S2, etc.) for unsafe content with category

    Args:
        content: Raw LlamaGuard response.
        command: The original command (for reason text).

    Returns:
        Parsed dict with action, reason, confidence.
        Returns None if format is unknown (caller should try next provider).
    """
    content = content.strip().lower()

    if content == "safe":
        return {
            "action": "allow",
            "reason": "Command passed LlamaGuard safety check",
            "confidence": 0.9,
        }

    if content.startswith("unsafe"):
        # Extract category if present (e.g., "unsafe\nS1")
        lines = content.split("\n")
        category = lines[1].strip().upper() if len(lines) > 1 else "Unknown"

        # Map LlamaGuard categories to actions
        # S1-S6 are various unsafe categories, block by default
        return {
            "action": "block",
            "reason": f"LlamaGuard flagged as unsafe (category: {category})",
            "confidence": 0.9,
        }

    # Unknown format
    logger.warning("Unknown LlamaGuard response format: %s", content[:50])
    return None


def _validation_failed_response(reason: str) -> dict:
    """Create a warn response when validation cannot be completed.

    This allows the user to decide whether to proceed with an unvalidated command.

    Args:
        reason: The reason validation failed.

    Returns:
        A dict with action="warn", confidence=0.0.
    """
    return {
        "action": "warn",
        "reason": f"Could not validate command: {reason}",
        "confidence": 0.0,
    }
