"""Shared test utilities for SecBASH tests.

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
    """Helper to mock get_available_providers.

    Args:
        providers: List of provider names to mock as available.

    Returns:
        A patch context manager for get_available_providers.
    """
    return patch("secbash.llm_client.get_available_providers", return_value=providers)
