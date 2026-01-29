"""Configuration module.

Loads API keys and settings from environment variables.
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
        return os.environ.get(env_var)
    return None


def get_available_providers() -> list[str]:
    """Get list of providers with configured API keys.

    Returns:
        List of provider names that have API keys set.
    """
    providers = ["openrouter", "openai", "anthropic"]
    return [p for p in providers if get_api_key(p)]
