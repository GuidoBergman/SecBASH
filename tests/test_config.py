"""Tests for config module.

Tests credential validation and model configuration functionality.
"""

import os

import pytest

from secbash.config import (
    get_api_key,
    get_available_providers,
    get_fallback_models,
    get_model_chain,
    get_primary_model,
    get_provider_from_model,
    is_valid_model_string,
    validate_credentials,
)


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

        result = get_api_key("openai")

        assert result is None

    def test_get_api_key_invalid_provider_returns_none(self, mocker):
        """Invalid provider name returns None."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key"},
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
            {"OPENAI_API_KEY": "test-key"},
            clear=True
        )

        is_valid, message = validate_credentials()

        assert is_valid is True
        assert "openai" in message.lower()

    def test_validate_credentials_all_keys_returns_true(self, mocker):
        """AC1: All providers configured returns (True, message)."""
        mocker.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "key1",
                "ANTHROPIC_API_KEY": "key2",
            },
            clear=True
        )

        is_valid, message = validate_credentials()

        assert is_valid is True
        assert "openai" in message.lower()
        assert "anthropic" in message.lower()

    def test_validate_credentials_error_has_instructions(self, mocker):
        """AC2: Error message includes env var names and setup instructions."""
        mocker.patch.dict(os.environ, {}, clear=True)

        is_valid, message = validate_credentials()

        assert is_valid is False
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
            {"OPENAI_API_KEY": ""},
            clear=True
        )

        is_valid, message = validate_credentials()

        assert is_valid is False
        assert "No LLM API credentials configured" in message


class TestGetPrimaryModel:
    """Tests for get_primary_model function."""

    def test_default_primary_model_when_no_env_var(self, mocker):
        """AC3: Default primary model when no env var set."""
        mocker.patch.dict(os.environ, {}, clear=True)

        result = get_primary_model()

        assert result == "openai/gpt-4"

    def test_custom_primary_model_from_env_var(self, mocker):
        """AC1: Custom primary model via env var."""
        mocker.patch.dict(
            os.environ,
            {"SECBASH_PRIMARY_MODEL": "anthropic/claude-3-haiku-20240307"},
            clear=True
        )

        result = get_primary_model()

        assert result == "anthropic/claude-3-haiku-20240307"

    def test_empty_primary_model_uses_default(self, mocker):
        """AC3: Empty env var uses default."""
        mocker.patch.dict(
            os.environ,
            {"SECBASH_PRIMARY_MODEL": ""},
            clear=True
        )

        result = get_primary_model()

        assert result == "openai/gpt-4"

    def test_whitespace_primary_model_uses_default(self, mocker):
        """AC3: Whitespace-only env var uses default."""
        mocker.patch.dict(
            os.environ,
            {"SECBASH_PRIMARY_MODEL": "   "},
            clear=True
        )

        result = get_primary_model()

        assert result == "openai/gpt-4"


class TestGetFallbackModels:
    """Tests for get_fallback_models function."""

    def test_default_fallback_models_when_no_env_var(self, mocker):
        """AC3: Default fallback models when no env var set."""
        mocker.patch.dict(os.environ, {}, clear=True)

        result = get_fallback_models()

        assert result == ["anthropic/claude-3-haiku-20240307"]

    def test_custom_fallback_models_from_env_var(self, mocker):
        """AC2: Custom fallback models via env var."""
        mocker.patch.dict(
            os.environ,
            {"SECBASH_FALLBACK_MODELS": "openai/gpt-4-turbo,anthropic/claude-3-opus-20240229"},
            clear=True
        )

        result = get_fallback_models()

        assert result == ["openai/gpt-4-turbo", "anthropic/claude-3-opus-20240229"]

    def test_empty_fallback_models_returns_empty_list(self, mocker):
        """AC5: Empty env var means no fallbacks (single provider mode)."""
        mocker.patch.dict(
            os.environ,
            {"SECBASH_FALLBACK_MODELS": ""},
            clear=True
        )

        result = get_fallback_models()

        assert result == []

    def test_whitespace_fallback_models_returns_empty_list(self, mocker):
        """Whitespace-only env var means no fallbacks."""
        mocker.patch.dict(
            os.environ,
            {"SECBASH_FALLBACK_MODELS": "   "},
            clear=True
        )

        result = get_fallback_models()

        assert result == []

    def test_single_fallback_model(self, mocker):
        """Single fallback model works correctly."""
        mocker.patch.dict(
            os.environ,
            {"SECBASH_FALLBACK_MODELS": "openai/gpt-4"},
            clear=True
        )

        result = get_fallback_models()

        assert result == ["openai/gpt-4"]

    def test_fallback_models_whitespace_trimmed(self, mocker):
        """Whitespace around model names is trimmed."""
        mocker.patch.dict(
            os.environ,
            {"SECBASH_FALLBACK_MODELS": " openai/gpt-4 , anthropic/claude-3-haiku-20240307 "},
            clear=True
        )

        result = get_fallback_models()

        assert result == ["openai/gpt-4", "anthropic/claude-3-haiku-20240307"]


class TestGetModelChain:
    """Tests for get_model_chain function."""

    def test_default_model_chain_when_no_env_vars(self, mocker):
        """AC3: Default model chain when no env vars set."""
        mocker.patch.dict(os.environ, {}, clear=True)

        result = get_model_chain()

        assert result == [
            "openai/gpt-4",
            "anthropic/claude-3-haiku-20240307",
        ]

    def test_custom_model_chain(self, mocker):
        """Custom primary and fallback models form correct chain."""
        mocker.patch.dict(
            os.environ,
            {
                "SECBASH_PRIMARY_MODEL": "anthropic/claude-3-opus-20240229",
                "SECBASH_FALLBACK_MODELS": "openai/gpt-4-turbo",
            },
            clear=True
        )

        result = get_model_chain()

        assert result == [
            "anthropic/claude-3-opus-20240229",
            "openai/gpt-4-turbo",
        ]

    def test_single_model_no_fallbacks(self, mocker):
        """AC5: Single model with no fallbacks configured."""
        mocker.patch.dict(
            os.environ,
            {
                "SECBASH_PRIMARY_MODEL": "anthropic/claude-3-haiku-20240307",
                "SECBASH_FALLBACK_MODELS": "",
            },
            clear=True
        )

        result = get_model_chain()

        assert result == ["anthropic/claude-3-haiku-20240307"]

    def test_model_chain_no_duplicates(self, mocker):
        """Model chain does not contain duplicates."""
        mocker.patch.dict(
            os.environ,
            {
                "SECBASH_PRIMARY_MODEL": "openai/gpt-4",
                "SECBASH_FALLBACK_MODELS": "openai/gpt-4,anthropic/claude-3-haiku-20240307",
            },
            clear=True
        )

        result = get_model_chain()

        # Primary is first, duplicate in fallbacks should be removed
        assert result == ["openai/gpt-4", "anthropic/claude-3-haiku-20240307"]

    def test_fallback_models_trailing_comma_handled(self, mocker):
        """Trailing comma in fallback models should not create empty entries."""
        mocker.patch.dict(
            os.environ,
            {"SECBASH_FALLBACK_MODELS": "openai/gpt-4,anthropic/claude-3-haiku-20240307,"},
            clear=True
        )

        result = get_fallback_models()

        # Should not have empty string in list
        assert "" not in result
        assert result == ["openai/gpt-4", "anthropic/claude-3-haiku-20240307"]


class TestGetProviderFromModel:
    """Tests for get_provider_from_model function."""

    def test_extract_openai_provider(self):
        """Should extract 'openai' from model string."""
        assert get_provider_from_model("openai/gpt-4") == "openai"

    def test_extract_anthropic_provider(self):
        """Should extract 'anthropic' from model string."""
        assert get_provider_from_model("anthropic/claude-3-haiku-20240307") == "anthropic"

    def test_invalid_format_returns_full_string(self):
        """Invalid format (no '/') should return the full string."""
        assert get_provider_from_model("gpt-4") == "gpt-4"


class TestIsValidModelString:
    """Tests for is_valid_model_string function."""

    def test_valid_openai_model(self):
        """Valid OpenAI model string."""
        assert is_valid_model_string("openai/gpt-4") is True

    def test_valid_anthropic_model(self):
        """Valid Anthropic model string."""
        assert is_valid_model_string("anthropic/claude-3-haiku-20240307") is True

    def test_invalid_no_slash(self):
        """Invalid: missing slash."""
        assert is_valid_model_string("gpt-4") is False

    def test_invalid_empty_provider(self):
        """Invalid: empty provider (starts with slash)."""
        assert is_valid_model_string("/gpt-4") is False

    def test_invalid_empty_string(self):
        """Invalid: empty string."""
        assert is_valid_model_string("") is False
