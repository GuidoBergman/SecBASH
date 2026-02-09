"""Shared test utilities for aegish tests.

Provides common mock classes and helper functions used across test modules.
"""

from unittest.mock import MagicMock, patch


class MockChoice:
    """Mock LiteLLM choice object."""

    def __init__(self, content: str):
        self.message = MagicMock()
        self.message.content = content


class MockResponse:
    """Mock LiteLLM response object."""

    def __init__(self, content: str):
        self.choices = [MockChoice(content)]


def mock_providers(providers: list[str]):
    """Helper to mock API keys and model chain for specified providers.

    This mocks get_api_key to return a test key for specified providers,
    and sets up the model chain to use those providers' default models.

    Args:
        providers: List of provider names to mock as available
                   (e.g., ["openai", "anthropic"]).

    Returns:
        A patch context manager that mocks get_api_key and get_model_chain.

    Example:
        with mock_providers(["openai", "anthropic"]):
            result = query_llm("ls -la")
    """
    provider_keys = {p: "test-key" for p in providers}

    def mock_get_api_key(provider: str) -> str | None:
        return provider_keys.get(provider.lower())

    # Build a default model chain based on available providers
    default_models = {
        "openai": "openai/gpt-4",
        "anthropic": "anthropic/claude-3-haiku-20240307",
    }
    model_chain = [
        default_models[p]
        for p in ["openai", "anthropic"]
        if p in providers
    ]

    return patch.multiple(
        "aegish.llm_client",
        get_api_key=mock_get_api_key,
        get_model_chain=lambda: model_chain,
    )
