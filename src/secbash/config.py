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

SECBASH_PRIMARY_MODEL : str
    Primary LLM model for command validation (format: provider/model-name).
    Default: openrouter/meta-llama/llama-guard-3-8b

SECBASH_FALLBACK_MODELS : str
    Comma-separated list of fallback models (format: provider/model,provider/model).
    Default: openai/gpt-4,anthropic/claude-3-haiku-20240307
    Set to empty string for single-provider mode (no fallbacks).

At least one API key must be configured for SecBASH to operate.
Models are tried in order: primary model first, then fallbacks.
"""

import os

# Default model configuration
DEFAULT_PRIMARY_MODEL = "openrouter/meta-llama/llama-guard-3-8b"
DEFAULT_FALLBACK_MODELS = ["openai/gpt-4", "anthropic/claude-3-haiku-20240307"]


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


def get_primary_model() -> str:
    """Get the primary LLM model for command validation.

    Reads from SECBASH_PRIMARY_MODEL environment variable.
    Falls back to default if not set or empty.

    Returns:
        The primary model string in provider/model-name format.
    """
    model = os.environ.get("SECBASH_PRIMARY_MODEL", "")
    if model and model.strip():
        return model.strip()
    return DEFAULT_PRIMARY_MODEL


def get_fallback_models() -> list[str]:
    """Get the list of fallback LLM models.

    Reads from SECBASH_FALLBACK_MODELS environment variable.
    If not set, returns default fallbacks.
    If set to empty string, returns empty list (single-provider mode).

    Returns:
        List of fallback model strings in provider/model-name format.
    """
    env_value = os.environ.get("SECBASH_FALLBACK_MODELS")

    # Not set at all - use defaults
    # Use .copy() to prevent external mutation of the default list
    if env_value is None:
        return DEFAULT_FALLBACK_MODELS.copy()

    # Set but empty/whitespace - single provider mode
    if not env_value.strip():
        return []

    # Parse comma-separated list, trimming whitespace
    models = [m.strip() for m in env_value.split(",") if m.strip()]
    return models


def get_model_chain() -> list[str]:
    """Get the ordered list of models to try for validation.

    Returns primary model followed by fallback models, with duplicates removed.

    Returns:
        List of model strings in priority order.
    """
    primary = get_primary_model()
    fallbacks = get_fallback_models()

    # Start with primary, add fallbacks that aren't duplicates
    chain = [primary]
    for model in fallbacks:
        if model not in chain:
            chain.append(model)

    return chain


def get_provider_from_model(model: str) -> str:
    """Extract the provider name from a model string.

    Model strings follow LiteLLM format: provider/model-name
    For example: "openai/gpt-4" -> "openai"
                 "openrouter/meta-llama/llama-guard-3-8b" -> "openrouter"

    Args:
        model: The model string (e.g., "openai/gpt-4").

    Returns:
        The provider name (first segment before '/').
        Returns the full string if no '/' is present (invalid format).
    """
    if "/" not in model:
        return model  # Invalid format, return as-is for error handling
    return model.split("/")[0]


def is_valid_model_string(model: str) -> bool:
    """Check if a model string follows the expected format.

    Valid format: provider/model-name (must contain at least one '/').

    Args:
        model: The model string to validate.

    Returns:
        True if the format is valid, False otherwise.
    """
    return "/" in model and len(model.split("/")[0]) > 0

