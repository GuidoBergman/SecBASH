"""Shared pytest fixtures for SecBASH tests.

Provides common fixtures that can be used across test modules.
For mock utilities (MockChoice, MockResponse, mock_providers),
see tests/utils.py which can be imported directly.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_openai_provider():
    """Fixture that mocks OpenAI as the only available provider."""
    with patch("secbash.llm_client.get_available_providers", return_value=["openai"]):
        yield


@pytest.fixture
def mock_all_providers():
    """Fixture that mocks all providers as available."""
    with patch("secbash.llm_client.get_available_providers", return_value=["openai", "anthropic"]):
        yield
