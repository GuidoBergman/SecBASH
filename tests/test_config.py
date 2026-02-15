"""Tests for config module.

Tests credential validation and model configuration functionality.
"""

import os

import pytest

from aegish.config import (
    DEFAULT_ALLOWED_PROVIDERS,
    DEFAULT_FALLBACK_MODELS,
    DEFAULT_PRIMARY_MODEL,
    DEFAULT_RUNNER_PATH,
    get_allowed_providers,
    get_api_key,
    get_available_providers,
    get_fail_mode,
    get_fallback_models,
    get_mode,
    get_model_chain,
    get_primary_model,
    get_provider_from_model,
    get_runner_path,
    has_fallback_models,
    is_default_fallback_models,
    is_default_primary_model,
    is_valid_model_string,
    validate_credentials,
    validate_model_provider,
    validate_runner_binary,
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


class TestGetApiKeyExtendedProviders:
    """Tests for get_api_key support of groq, together_ai, ollama (review fix H1)."""

    def test_groq_api_key(self, mocker):
        """Groq provider reads GROQ_API_KEY."""
        mocker.patch.dict(os.environ, {"GROQ_API_KEY": "groq-key"}, clear=True)
        assert get_api_key("groq") == "groq-key"

    def test_together_ai_api_key(self, mocker):
        """Together AI provider reads TOGETHERAI_API_KEY."""
        mocker.patch.dict(os.environ, {"TOGETHERAI_API_KEY": "tai-key"}, clear=True)
        assert get_api_key("together_ai") == "tai-key"

    def test_ollama_needs_no_key(self, mocker):
        """Ollama (local) returns truthy value without any env var."""
        mocker.patch.dict(os.environ, {}, clear=True)
        result = get_api_key("ollama")
        assert result is not None
        assert result  # truthy

    def test_groq_missing_key_returns_none(self, mocker):
        """Groq without GROQ_API_KEY returns None."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert get_api_key("groq") is None


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


class TestGetMode:
    """Tests for get_mode function."""

    def test_default_mode_when_no_env_var(self, mocker):
        """AC1: Default mode is development when AEGISH_MODE not set."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert get_mode() == "development"

    def test_production_mode_from_env_var(self, mocker):
        """AC2: Production mode when AEGISH_MODE=production."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        assert get_mode() == "production"

    def test_development_mode_from_env_var(self, mocker):
        """AC3: Development mode when explicitly set."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "development"}, clear=True)
        assert get_mode() == "development"

    @pytest.mark.parametrize("invalid_value", ["staging", "test", "prod", "Production123"])
    def test_invalid_mode_falls_back_to_development(self, mocker, invalid_value):
        """AC4: Invalid value falls back to development."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": invalid_value}, clear=True)
        assert get_mode() == "development"

    def test_invalid_mode_logs_debug_warning(self, mocker, caplog):
        """AC4: Invalid value logs a debug-level warning."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "staging"}, clear=True)
        import logging
        with caplog.at_level(logging.DEBUG, logger="aegish.config"):
            get_mode()
        assert "Invalid AEGISH_MODE" in caplog.text
        assert "staging" in caplog.text

    def test_empty_mode_does_not_log(self, mocker, caplog):
        """Empty/unset AEGISH_MODE should not produce a debug log."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": ""}, clear=True)
        import logging
        with caplog.at_level(logging.DEBUG, logger="aegish.config"):
            get_mode()
        assert "Invalid AEGISH_MODE" not in caplog.text

    def test_mode_normalized_whitespace_and_case(self, mocker):
        """AC5: Whitespace and mixed case are normalized."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": " Production "}, clear=True)
        assert get_mode() == "production"

    def test_empty_mode_returns_development(self, mocker):
        """AC1: Empty string falls back to development."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": ""}, clear=True)
        assert get_mode() == "development"


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
            {"AEGISH_PRIMARY_MODEL": "anthropic/claude-3-haiku-20240307"},
            clear=True
        )

        result = get_primary_model()

        assert result == "anthropic/claude-3-haiku-20240307"

    def test_empty_primary_model_uses_default(self, mocker):
        """AC3: Empty env var uses default."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_PRIMARY_MODEL": ""},
            clear=True
        )

        result = get_primary_model()

        assert result == "openai/gpt-4"

    def test_whitespace_primary_model_uses_default(self, mocker):
        """AC3: Whitespace-only env var uses default."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_PRIMARY_MODEL": "   "},
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
            {"AEGISH_FALLBACK_MODELS": "openai/gpt-4-turbo,anthropic/claude-3-opus-20240229"},
            clear=True
        )

        result = get_fallback_models()

        assert result == ["openai/gpt-4-turbo", "anthropic/claude-3-opus-20240229"]

    def test_empty_fallback_models_returns_empty_list(self, mocker):
        """AC5: Empty env var means no fallbacks (single provider mode)."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_FALLBACK_MODELS": ""},
            clear=True
        )

        result = get_fallback_models()

        assert result == []

    def test_whitespace_fallback_models_returns_empty_list(self, mocker):
        """Whitespace-only env var means no fallbacks."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_FALLBACK_MODELS": "   "},
            clear=True
        )

        result = get_fallback_models()

        assert result == []

    def test_single_fallback_model(self, mocker):
        """Single fallback model works correctly."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_FALLBACK_MODELS": "openai/gpt-4"},
            clear=True
        )

        result = get_fallback_models()

        assert result == ["openai/gpt-4"]

    def test_fallback_models_whitespace_trimmed(self, mocker):
        """Whitespace around model names is trimmed."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_FALLBACK_MODELS": " openai/gpt-4 , anthropic/claude-3-haiku-20240307 "},
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
                "AEGISH_PRIMARY_MODEL": "anthropic/claude-3-opus-20240229",
                "AEGISH_FALLBACK_MODELS": "openai/gpt-4-turbo",
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
                "AEGISH_PRIMARY_MODEL": "anthropic/claude-3-haiku-20240307",
                "AEGISH_FALLBACK_MODELS": "",
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
                "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
                "AEGISH_FALLBACK_MODELS": "openai/gpt-4,anthropic/claude-3-haiku-20240307",
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
            {"AEGISH_FALLBACK_MODELS": "openai/gpt-4,anthropic/claude-3-haiku-20240307,"},
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


class TestGetAllowedProviders:
    """Tests for get_allowed_providers function."""

    def test_default_allowed_providers(self, mocker):
        """Default providers returned when no env var set."""
        mocker.patch.dict(os.environ, {}, clear=True)

        result = get_allowed_providers()

        assert result == DEFAULT_ALLOWED_PROVIDERS
        assert "openai" in result
        assert "anthropic" in result
        assert "groq" in result
        assert "together_ai" in result
        assert "ollama" in result

    def test_custom_allowed_providers(self, mocker):
        """Custom providers from env var."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_ALLOWED_PROVIDERS": "openai,custom-corp"},
            clear=True,
        )

        result = get_allowed_providers()

        assert result == {"openai", "custom-corp"}

    def test_empty_env_var_uses_default(self, mocker):
        """Empty env var uses default allowlist."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_ALLOWED_PROVIDERS": ""},
            clear=True,
        )

        result = get_allowed_providers()

        assert result == DEFAULT_ALLOWED_PROVIDERS

    def test_whitespace_only_env_var_uses_default(self, mocker):
        """Whitespace-only env var uses default allowlist."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_ALLOWED_PROVIDERS": "   "},
            clear=True,
        )

        result = get_allowed_providers()

        assert result == DEFAULT_ALLOWED_PROVIDERS

    def test_whitespace_trimmed_in_providers(self, mocker):
        """Whitespace around provider names is trimmed."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_ALLOWED_PROVIDERS": " openai , anthropic , groq "},
            clear=True,
        )

        result = get_allowed_providers()

        assert result == {"openai", "anthropic", "groq"}

    def test_providers_lowercased(self, mocker):
        """Provider names are lowercased."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_ALLOWED_PROVIDERS": "OpenAI,ANTHROPIC"},
            clear=True,
        )

        result = get_allowed_providers()

        assert result == {"openai", "anthropic"}

    def test_trailing_comma_handled(self, mocker):
        """Trailing comma does not produce empty entry."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_ALLOWED_PROVIDERS": "openai,anthropic,"},
            clear=True,
        )

        result = get_allowed_providers()

        assert result == {"openai", "anthropic"}


class TestValidateModelProvider:
    """Tests for validate_model_provider function."""

    def test_known_provider_accepted(self, mocker):
        """Known provider (openai) is accepted."""
        mocker.patch.dict(os.environ, {}, clear=True)

        is_valid, msg = validate_model_provider("openai/gpt-4")

        assert is_valid is True
        assert msg == ""

    def test_anthropic_provider_accepted(self, mocker):
        """Known provider (anthropic) is accepted."""
        mocker.patch.dict(os.environ, {}, clear=True)

        is_valid, msg = validate_model_provider("anthropic/claude-3-haiku-20240307")

        assert is_valid is True

    def test_ollama_provider_accepted(self, mocker):
        """Ollama (local) provider accepted by default (AC6)."""
        mocker.patch.dict(os.environ, {}, clear=True)

        is_valid, msg = validate_model_provider("ollama/llama3")

        assert is_valid is True

    def test_unknown_provider_rejected(self, mocker):
        """Unknown provider is rejected with clear error (AC2)."""
        mocker.patch.dict(os.environ, {}, clear=True)

        is_valid, msg = validate_model_provider("evil-corp/permissive-model")

        assert is_valid is False
        assert "evil-corp" in msg
        assert "openai" in msg  # shows allowed list

    def test_rejection_message_includes_allowed_list(self, mocker):
        """Rejection message includes all allowed providers."""
        mocker.patch.dict(os.environ, {}, clear=True)

        is_valid, msg = validate_model_provider("evil-corp/bad")

        assert is_valid is False
        for provider in DEFAULT_ALLOWED_PROVIDERS:
            assert provider in msg

    def test_custom_allowlist_provider_accepted(self, mocker):
        """Custom allowlist provider accepted (AC3)."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_ALLOWED_PROVIDERS": "openai,custom-corp"},
            clear=True,
        )

        is_valid, msg = validate_model_provider("custom-corp/my-model")

        assert is_valid is True
        assert msg == ""

    def test_custom_allowlist_rejects_non_listed(self, mocker):
        """Custom allowlist rejects providers not in the list."""
        mocker.patch.dict(
            os.environ,
            {"AEGISH_ALLOWED_PROVIDERS": "openai,custom-corp"},
            clear=True,
        )

        is_valid, msg = validate_model_provider("anthropic/claude-3-haiku-20240307")

        assert is_valid is False
        assert "anthropic" in msg


class TestGetFailMode:
    """Tests for get_fail_mode function (Story 7.4)."""

    def test_default_fail_mode_is_safe(self, mocker):
        """AC1: Default is safe when AEGISH_FAIL_MODE not set."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert get_fail_mode() == "safe"

    def test_safe_mode_from_env(self, mocker):
        """AC1: Explicit safe mode."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": "safe"}, clear=True)
        assert get_fail_mode() == "safe"

    def test_open_mode_from_env(self, mocker):
        """AC2: Open mode."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": "open"}, clear=True)
        assert get_fail_mode() == "open"

    def test_invalid_value_defaults_to_safe(self, mocker):
        """AC4: Invalid value falls back to safe."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": "invalid"}, clear=True)
        assert get_fail_mode() == "safe"

    def test_whitespace_and_case_normalized(self, mocker):
        """Whitespace and mixed case are normalized."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": " Open "}, clear=True)
        assert get_fail_mode() == "open"

    def test_empty_defaults_to_safe(self, mocker):
        """Empty string defaults to safe."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": ""}, clear=True)
        assert get_fail_mode() == "safe"

    def test_invalid_value_logs_debug_warning(self, mocker, caplog):
        """H1 fix: Invalid value logs a debug-level warning."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": "closed"}, clear=True)
        import logging
        with caplog.at_level(logging.DEBUG, logger="aegish.config"):
            get_fail_mode()
        assert "Invalid AEGISH_FAIL_MODE" in caplog.text
        assert "closed" in caplog.text

    def test_empty_fail_mode_does_not_log(self, mocker, caplog):
        """Empty/unset AEGISH_FAIL_MODE should not produce a debug log."""
        mocker.patch.dict(os.environ, {"AEGISH_FAIL_MODE": ""}, clear=True)
        import logging
        with caplog.at_level(logging.DEBUG, logger="aegish.config"):
            get_fail_mode()
        assert "Invalid AEGISH_FAIL_MODE" not in caplog.text


class TestIsDefaultPrimaryModel:
    """Tests for is_default_primary_model function."""

    def test_default_when_env_not_set(self, mocker):
        """Returns True when AEGISH_PRIMARY_MODEL not set."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert is_default_primary_model() is True

    def test_non_default_when_env_set(self, mocker):
        """Returns False when env var is a different model."""
        mocker.patch.dict(os.environ, {"AEGISH_PRIMARY_MODEL": "anthropic/claude-sonnet-4-5-20250929"}, clear=True)
        assert is_default_primary_model() is False

    def test_default_when_env_set_to_default(self, mocker):
        """Returns True when env var matches default."""
        mocker.patch.dict(os.environ, {"AEGISH_PRIMARY_MODEL": "openai/gpt-4"}, clear=True)
        assert is_default_primary_model() is True

    def test_default_when_env_empty(self, mocker):
        """Returns True when env var is empty (falls back to default)."""
        mocker.patch.dict(os.environ, {"AEGISH_PRIMARY_MODEL": ""}, clear=True)
        assert is_default_primary_model() is True


class TestIsDefaultFallbackModels:
    """Tests for is_default_fallback_models function."""

    def test_default_when_env_not_set(self, mocker):
        """Returns True when AEGISH_FALLBACK_MODELS not set."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert is_default_fallback_models() is True

    def test_non_default_when_env_set(self, mocker):
        """Returns False when env var is a different model list."""
        mocker.patch.dict(os.environ, {"AEGISH_FALLBACK_MODELS": "openai/gpt-3.5-turbo"}, clear=True)
        assert is_default_fallback_models() is False

    def test_non_default_when_env_empty(self, mocker):
        """Returns False when env var is empty (single-provider mode)."""
        mocker.patch.dict(os.environ, {"AEGISH_FALLBACK_MODELS": ""}, clear=True)
        assert is_default_fallback_models() is False


class TestHasFallbackModels:
    """Tests for has_fallback_models function."""

    def test_has_fallbacks_with_defaults(self, mocker):
        """Returns True with default fallback models."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert has_fallback_models() is True

    def test_no_fallbacks_when_empty(self, mocker):
        """Returns False when AEGISH_FALLBACK_MODELS is empty string."""
        mocker.patch.dict(os.environ, {"AEGISH_FALLBACK_MODELS": ""}, clear=True)
        assert has_fallback_models() is False

    def test_has_fallbacks_when_custom(self, mocker):
        """Returns True with custom fallback models."""
        mocker.patch.dict(os.environ, {"AEGISH_FALLBACK_MODELS": "openai/gpt-3.5-turbo"}, clear=True)
        assert has_fallback_models() is True


class TestGetRunnerPath:
    """Tests for get_runner_path function (Story 8.4)."""

    def test_default_runner_path(self, mocker):
        """AC4: Default path when AEGISH_RUNNER_PATH not set."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert get_runner_path() == DEFAULT_RUNNER_PATH

    def test_custom_runner_path(self, mocker):
        """AC4: Custom path from AEGISH_RUNNER_PATH env var."""
        mocker.patch.dict(os.environ, {"AEGISH_RUNNER_PATH": "/custom/runner"}, clear=True)
        assert get_runner_path() == "/custom/runner"

    def test_empty_runner_path_uses_default(self, mocker):
        """Empty env var falls back to default."""
        mocker.patch.dict(os.environ, {"AEGISH_RUNNER_PATH": ""}, clear=True)
        assert get_runner_path() == DEFAULT_RUNNER_PATH

    def test_whitespace_runner_path_uses_default(self, mocker):
        """Whitespace-only env var falls back to default."""
        mocker.patch.dict(os.environ, {"AEGISH_RUNNER_PATH": "   "}, clear=True)
        assert get_runner_path() == DEFAULT_RUNNER_PATH

    def test_runner_path_whitespace_trimmed(self, mocker):
        """Whitespace around path is trimmed."""
        mocker.patch.dict(os.environ, {"AEGISH_RUNNER_PATH": "  /custom/runner  "}, clear=True)
        assert get_runner_path() == "/custom/runner"


class TestValidateRunnerBinary:
    """Tests for validate_runner_binary function (Story 8.4)."""

    def test_valid_runner_binary(self, mocker, tmp_path):
        """AC1: Returns True when runner binary exists and is executable."""
        runner = tmp_path / "runner"
        runner.write_text("#!/bin/bash")
        runner.chmod(0o755)
        mocker.patch.dict(os.environ, {"AEGISH_RUNNER_PATH": str(runner)}, clear=True)

        is_valid, msg = validate_runner_binary()

        assert is_valid is True
        assert "ready" in msg

    def test_missing_runner_binary(self, mocker):
        """AC2: Returns False with instructions when runner is missing."""
        mocker.patch.dict(os.environ, {"AEGISH_RUNNER_PATH": "/nonexistent/runner"}, clear=True)

        is_valid, msg = validate_runner_binary()

        assert is_valid is False
        assert "not found" in msg
        assert "ln" in msg  # setup instructions

    def test_non_executable_runner_binary(self, mocker, tmp_path):
        """Returns False when runner exists but is not executable."""
        runner = tmp_path / "runner"
        runner.write_text("#!/bin/bash")
        runner.chmod(0o644)
        mocker.patch.dict(os.environ, {"AEGISH_RUNNER_PATH": str(runner)}, clear=True)

        is_valid, msg = validate_runner_binary()

        assert is_valid is False
        assert "not executable" in msg
        assert "chmod" in msg
