"""Tests for config module.

Tests credential validation functionality.
"""

import os

import pytest

from secbash.config import get_api_key, get_available_providers, validate_credentials


class TestGetApiKey:
    """Tests for get_api_key function."""

    def test_get_api_key_returns_value_when_set(self, mocker):
        """Valid key is returned."""
        mocker.patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "valid-key-123"},
            clear=True
        )

        result = get_api_key("anthropic")

        assert result == "valid-key-123"

    def test_get_api_key_returns_none_when_not_set(self, mocker):
        """Missing env var returns None."""
        mocker.patch.dict(os.environ, {}, clear=True)

        result = get_api_key("openrouter")

        assert result is None

    def test_get_api_key_invalid_provider_returns_none(self, mocker):
        """Invalid provider name returns None."""
        mocker.patch.dict(
            os.environ,
            {"OPENROUTER_API_KEY": "test-key"},
            clear=True
        )

        result = get_api_key("invalid_provider")

        assert result is None

    def test_get_api_key_case_insensitive(self, mocker):
        """Provider name is case-insensitive."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key"},
            clear=True
        )

        assert get_api_key("OPENAI") == "test-key"
        assert get_api_key("OpenAI") == "test-key"
        assert get_api_key("openai") == "test-key"


class TestGetApiKeyEmptyString:
    """Tests for get_api_key handling of empty strings - all providers."""

    def test_get_api_key_empty_string_openrouter_returns_none(self, mocker):
        """AC1: Empty OPENROUTER_API_KEY treated as not configured."""
        mocker.patch.dict(
            os.environ,
            {"OPENROUTER_API_KEY": ""},
            clear=True
        )

        result = get_api_key("openrouter")

        assert result is None

    def test_get_api_key_empty_string_openai_returns_none(self, mocker):
        """AC1: Empty OPENAI_API_KEY treated as not configured."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": ""},
            clear=True
        )

        result = get_api_key("openai")

        assert result is None

    def test_get_api_key_empty_string_anthropic_returns_none(self, mocker):
        """AC1: Empty ANTHROPIC_API_KEY treated as not configured."""
        mocker.patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": ""},
            clear=True
        )

        result = get_api_key("anthropic")

        assert result is None

    def test_get_api_key_whitespace_only_returns_none(self, mocker):
        """Whitespace-only env var treated as not configured."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "   "},
            clear=True
        )

        result = get_api_key("openai")

        assert result is None


class TestValidateCredentials:
    """Tests for validate_credentials function."""

    def test_validate_credentials_no_keys_returns_false(self, mocker):
        """AC2: No env vars set returns (False, error_message)."""
        mocker.patch.dict(os.environ, {}, clear=True)

        is_valid, message = validate_credentials()

        assert is_valid is False
        assert "No LLM API credentials configured" in message

    def test_validate_credentials_one_key_returns_true(self, mocker):
        """AC1: One provider configured returns (True, message)."""
        mocker.patch.dict(
            os.environ,
            {"OPENROUTER_API_KEY": "test-key"},
            clear=True
        )

        is_valid, message = validate_credentials()

        assert is_valid is True
        assert "openrouter" in message.lower()

    def test_validate_credentials_all_keys_returns_true(self, mocker):
        """AC1: All providers configured returns (True, message)."""
        mocker.patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "key1",
                "OPENAI_API_KEY": "key2",
                "ANTHROPIC_API_KEY": "key3",
            },
            clear=True
        )

        is_valid, message = validate_credentials()

        assert is_valid is True
        assert "openrouter" in message.lower()
        assert "openai" in message.lower()
        assert "anthropic" in message.lower()

    def test_validate_credentials_error_has_instructions(self, mocker):
        """AC2: Error message includes env var names and setup instructions."""
        mocker.patch.dict(os.environ, {}, clear=True)

        is_valid, message = validate_credentials()

        assert is_valid is False
        assert "OPENROUTER_API_KEY" in message
        assert "OPENAI_API_KEY" in message
        assert "ANTHROPIC_API_KEY" in message
        assert "export" in message  # Setup instruction

    def test_validate_credentials_success_lists_providers(self, mocker):
        """AC1: Success message includes provider names in correct format."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key"},
            clear=True
        )

        is_valid, message = validate_credentials()

        assert is_valid is True
        assert "Using providers:" in message
        assert "openai" in message.lower()

    def test_validate_credentials_empty_key_not_counted(self, mocker):
        """Empty string keys should not count as configured."""
        mocker.patch.dict(
            os.environ,
            {"OPENROUTER_API_KEY": ""},
            clear=True
        )

        is_valid, message = validate_credentials()

        assert is_valid is False
        assert "No LLM API credentials configured" in message
