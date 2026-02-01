"""Configuration module.

Loads API keys and settings from environment variables.

Environment Variables
---------------------
OPENROUTER_API_KEY : str
    API key for OpenRouter (recommended for LlamaGuard security model).
    Get one at: https://openrouter.ai/

OPENAI_API_KEY : str
    API key for OpenAI.
    Get one at: https://platform.openai.com/api-keys

ANTHROPIC_API_KEY : str
    API key for Anthropic.
    Get one at: https://console.anthropic.com/

At least one API key must be configured for SecBASH to operate.
Multiple keys can be configured; providers are tried in priority order:
openrouter -> openai -> anthropic.
"""

import os


def get_api_key(provider: str) -> str | None:
    """Get the API key for a provider from environment.

    Args:
        provider: One of "openrouter", "openai", "anthropic".

    Returns:
        The API key string or None if not set.
    """
    env_vars = {
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    env_var = env_vars.get(provider.lower())
    if env_var:
        key = os.environ.get(env_var)
        # Treat empty or whitespace-only strings as not configured
        return key if key and key.strip() else None
    return None


def get_available_providers() -> list[str]:
    """Get list of providers with configured API keys.

    Returns:
        List of provider names that have API keys set.
    """
    providers = ["openrouter", "openai", "anthropic"]
    return [p for p in providers if get_api_key(p)]


def validate_credentials() -> tuple[bool, str]:
    """Validate that at least one LLM provider credential is configured.

    Returns:
        Tuple of (is_valid, message).
        If valid: (True, "credentials configured message")
        If invalid: (False, "error message with instructions")
    """
    available = get_available_providers()

    if not available:
        return (False, """No LLM API credentials configured.

SecBASH requires at least one API key to validate commands.

Set one or more of these environment variables:
  export OPENROUTER_API_KEY="your-key-here"
  export OPENAI_API_KEY="your-key-here"
  export ANTHROPIC_API_KEY="your-key-here"

Recommended: Use OpenRouter for LlamaGuard (security-specific model).""")

    return (True, f"Using providers: {', '.join(available)}")

