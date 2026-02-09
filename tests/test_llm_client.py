"""Tests for LLM client module.

Uses mocked LiteLLM responses - no actual API calls.
"""

import os

import pytest
from unittest.mock import patch

from aegish.config import get_provider_from_model
from aegish.llm_client import (
    query_llm,
    _parse_response,
)
from tests.utils import MockResponse, mock_providers


class TestQueryLLM:
    """Tests for query_llm function."""

    def test_returns_structured_response(self):
        """AC5: Response has action, reason, confidence."""
        mock_content = '{"action": "allow", "reason": "Safe command", "confidence": 0.95}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm("ls -la")

                assert "action" in result
                assert "reason" in result
                assert "confidence" in result
                assert result["action"] in ["allow", "warn", "block"]

    def test_allow_action_response(self):
        """Test allow action is parsed correctly."""
        mock_content = '{"action": "allow", "reason": "Safe listing command", "confidence": 0.98}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm("ls -la")

                assert result["action"] == "allow"
                assert result["reason"] == "Safe listing command"
                assert result["confidence"] == 0.98

    def test_warn_action_response(self):
        """Test warn action is parsed correctly."""
        mock_content = '{"action": "warn", "reason": "Command modifies files", "confidence": 0.75}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm("rm file.txt")

                assert result["action"] == "warn"
                assert result["reason"] == "Command modifies files"
                assert result["confidence"] == 0.75

    def test_block_action_response(self):
        """Test block action is parsed correctly."""
        mock_content = '{"action": "block", "reason": "Dangerous recursive delete", "confidence": 0.99}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm("rm -rf /")

                assert result["action"] == "block"
                assert result["reason"] == "Dangerous recursive delete"
                assert result["confidence"] == 0.99

    def test_warns_on_connection_error(self):
        """When all providers fail with ConnectionError, warn user."""
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.side_effect = ConnectionError("All providers failed")
                result = query_llm("ls -la")

                assert result["action"] == "warn"
                assert result["confidence"] == 0.0
                assert "could not validate" in result["reason"].lower()

    def test_warns_on_timeout_error(self):
        """When request times out, warn user."""
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.side_effect = TimeoutError("Request timed out")
                result = query_llm("ls -la")

                assert result["action"] == "warn"
                assert result["confidence"] == 0.0

    def test_warns_on_generic_exception(self):
        """On unexpected exceptions, warn user."""
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.side_effect = Exception("Unexpected error")
                result = query_llm("ls -la")

                assert result["action"] == "warn"
                assert result["confidence"] == 0.0

    def test_handles_invalid_json_response(self):
        """Test graceful handling of malformed JSON from LLM."""
        mock_content = "This is not valid JSON"
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm("ls -la")

                # Should warn when parsing fails
                assert result["action"] == "warn"
                assert result["confidence"] == 0.0

    def test_handles_missing_fields_in_response(self):
        """Test handling of response missing required fields."""
        mock_content = '{"action": "allow"}'  # Missing reason and confidence
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm("ls -la")

                # Should still return valid structure with defaults
                assert result["action"] == "allow"
                assert "reason" in result
                assert "confidence" in result

    def test_primary_provider_is_openai(self):
        """AC1: Primary provider should be OpenAI when available."""
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                query_llm("ls -la")

                # Verify the model used is OpenAI (first call)
                call_args = mock_completion.call_args
                assert "openai" in call_args.kwargs.get("model", "").lower()

    def test_fallback_on_parsing_failure(self):
        """When parsing fails for one provider, try the next."""
        with mock_providers(["openai", "anthropic"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                # First call (openai) returns unparseable, second (anthropic) succeeds
                mock_completion.side_effect = [
                    MockResponse("garbage response"),
                    MockResponse('{"action": "allow", "reason": "Safe", "confidence": 0.9}'),
                ]
                result = query_llm("ls -la")

                # Should have tried both providers
                assert mock_completion.call_count == 2
                # Should return the successful result from anthropic
                assert result["action"] == "allow"
                assert result["reason"] == "Safe"

    def test_fallback_on_api_failure(self):
        """When API fails for one provider, try the next."""
        with mock_providers(["openai", "anthropic"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                # First call fails, second succeeds
                mock_completion.side_effect = [
                    ConnectionError("OpenAI down"),
                    MockResponse('{"action": "block", "reason": "Dangerous", "confidence": 0.95}'),
                ]
                result = query_llm("rm -rf /")

                # Should have tried both providers
                assert mock_completion.call_count == 2
                # Should return the successful result
                assert result["action"] == "block"

    def test_caching_enabled(self):
        """AC4: Caching should be enabled for LiteLLM calls."""
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                query_llm("ls -la")

                # Verify caching is enabled
                call_args = mock_completion.call_args
                assert call_args.kwargs.get("caching") is True

    def test_confidence_is_float(self):
        """Test that confidence is always a float between 0 and 1."""
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.85}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm("ls -la")

                assert isinstance(result["confidence"], float)
                assert 0.0 <= result["confidence"] <= 1.0


class TestNoProvidersConfigured:
    """Tests for behavior when no API keys are configured."""

    def test_warns_when_no_providers(self):
        """Should warn when no providers are available."""
        with mock_providers([]):
            result = query_llm("ls -la")

            assert result["action"] == "warn"
            assert result["confidence"] == 0.0
            assert "no api keys" in result["reason"].lower()


class TestInvalidActionHandling:
    """Tests for invalid action value handling."""

    def test_invalid_action_triggers_fallback(self):
        """Invalid action values should trigger fallback to next provider."""
        with mock_providers(["openai", "anthropic"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.side_effect = [
                    MockResponse('{"action": "invalid", "reason": "Test", "confidence": 0.9}'),
                    MockResponse('{"action": "allow", "reason": "Valid", "confidence": 0.8}'),
                ]
                result = query_llm("ls -la")

                # Should have tried both providers
                assert mock_completion.call_count == 2
                assert result["action"] == "allow"
                assert result["reason"] == "Valid"

    def test_invalid_action_all_providers_warns(self):
        """Invalid action from all providers should warn."""
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse('{"action": "invalid", "reason": "Test", "confidence": 0.9}')
                result = query_llm("ls -la")

                assert result["action"] == "warn"
                assert result["confidence"] == 0.0


class TestConfidenceClamping:
    """Tests for confidence value clamping."""

    def test_confidence_above_one_clamped(self):
        """Confidence > 1.0 should be clamped to 1.0."""
        mock_content = '{"action": "allow", "reason": "Test", "confidence": 1.5}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm("ls -la")

                assert result["confidence"] == 1.0

    def test_confidence_below_zero_clamped(self):
        """Confidence < 0.0 should be clamped to 0.0."""
        mock_content = '{"action": "allow", "reason": "Test", "confidence": -0.5}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm("ls -la")

                assert result["confidence"] == 0.0


class TestModelSelection:
    """Tests for dynamic model selection based on available providers."""

    def test_uses_openai_as_primary(self):
        """Should use OpenAI model as primary provider."""
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                query_llm("ls -la")

                call_args = mock_completion.call_args
                assert "openai" in call_args.kwargs.get("model", "").lower()

    def test_uses_anthropic_when_only_anthropic(self):
        """Should use Anthropic model when only Anthropic available."""
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with mock_providers(["anthropic"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                query_llm("ls -la")

                call_args = mock_completion.call_args
                assert "anthropic" in call_args.kwargs.get("model", "").lower()

    def test_tries_providers_in_priority_order(self):
        """Should try providers in priority order: openai, anthropic."""
        with mock_providers(["anthropic", "openai"]):  # Available in different order
            with patch("aegish.llm_client.completion") as mock_completion:
                # First fails, second succeeds
                mock_completion.side_effect = [
                    ConnectionError("openai down"),
                    MockResponse('{"action": "allow", "reason": "Safe", "confidence": 0.9}'),
                ]
                result = query_llm("ls -la")

                # Should have tried both in priority order
                assert mock_completion.call_count == 2
                # Verify order of model calls
                calls = mock_completion.call_args_list
                assert "openai" in calls[0].kwargs["model"]
                assert "anthropic" in calls[1].kwargs["model"]
                assert result["action"] == "allow"


class TestCommandLengthValidation:
    """Tests for command length validation."""

    def test_long_command_warns(self):
        """Commands exceeding MAX_COMMAND_LENGTH should warn user."""
        from aegish.llm_client import MAX_COMMAND_LENGTH

        long_command = "x" * (MAX_COMMAND_LENGTH + 1)
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                result = query_llm(long_command)

                # Should NOT call the LLM
                mock_completion.assert_not_called()

                # Should warn user
                assert result["action"] == "warn"
                assert result["confidence"] == 0.0
                assert "too long" in result["reason"].lower()

    def test_max_length_command_allowed(self):
        """Commands at exactly MAX_COMMAND_LENGTH should be processed."""
        from aegish.llm_client import MAX_COMMAND_LENGTH

        max_command = "x" * MAX_COMMAND_LENGTH
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm(max_command)

                # Should call the LLM
                mock_completion.assert_called_once()
                assert result["action"] == "allow"


class TestEdgeCaseCommands:
    """Tests for edge case command inputs."""

    def test_empty_command_sent_to_llm(self):
        """Empty commands are still sent to LLM (shell handles filtering)."""
        mock_content = '{"action": "allow", "reason": "Empty command", "confidence": 1.0}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm("")

                # LLM is called even for empty (shell filters before this)
                mock_completion.assert_called_once()
                assert result["action"] == "allow"

    def test_whitespace_command_sent_to_llm(self):
        """Whitespace-only commands are still sent to LLM."""
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm("   ")

                mock_completion.assert_called_once()


class TestParseResponse:
    """Tests for _parse_response function."""

    def test_parse_valid_json(self):
        """Should parse valid JSON response."""
        content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        result = _parse_response(content)

        assert result["action"] == "allow"
        assert result["reason"] == "Safe"
        assert result["confidence"] == 0.9

    def test_parse_invalid_json_returns_none(self):
        """Should return None for invalid JSON."""
        result = _parse_response("not json")
        assert result is None

    def test_parse_invalid_action_returns_none(self):
        """Should return None for invalid action."""
        result = _parse_response('{"action": "invalid", "reason": "Test", "confidence": 0.5}')
        assert result is None

    def test_parse_empty_action_returns_none(self):
        """Should return None for empty action."""
        result = _parse_response('{"action": "", "reason": "Test", "confidence": 0.5}')
        assert result is None

    def test_parse_missing_reason_uses_default(self):
        """Should use default reason if missing."""
        result = _parse_response('{"action": "allow", "confidence": 0.5}')
        assert result["reason"] == "No reason provided"

    def test_parse_missing_confidence_uses_default(self):
        """Should use default confidence if missing."""
        result = _parse_response('{"action": "allow", "reason": "Test"}')
        assert result["confidence"] == 0.5


class TestGetProviderFromModel:
    """Tests for get_provider_from_model helper function."""

    def test_extract_openai_provider(self):
        """Should extract 'openai' from model string."""
        assert get_provider_from_model("openai/gpt-4") == "openai"

    def test_extract_anthropic_provider(self):
        """Should extract 'anthropic' from model string."""
        assert get_provider_from_model("anthropic/claude-3-haiku-20240307") == "anthropic"


class TestConfigurableModels:
    """Tests for configurable model support (Story 3.6)."""

    def test_uses_custom_primary_model(self, mocker):
        """AC1: Custom primary model is used when configured."""
        mocker.patch.dict(
            os.environ,
            {
                "AEGISH_PRIMARY_MODEL": "anthropic/claude-3-opus-20240229",
                "AEGISH_FALLBACK_MODELS": "",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=True
        )
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse(mock_content)
            query_llm("ls -la")

            call_args = mock_completion.call_args
            assert call_args.kwargs["model"] == "anthropic/claude-3-opus-20240229"

    def test_uses_custom_fallback_models(self, mocker):
        """AC2: Custom fallback models are used when configured."""
        mocker.patch.dict(
            os.environ,
            {
                "AEGISH_PRIMARY_MODEL": "openai/gpt-4-turbo",
                "AEGISH_FALLBACK_MODELS": "anthropic/claude-3-opus-20240229",
                "OPENAI_API_KEY": "test-key",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=True
        )
        with patch("aegish.llm_client.completion") as mock_completion:
            # First model fails, second succeeds
            mock_completion.side_effect = [
                ConnectionError("API error"),
                MockResponse('{"action": "allow", "reason": "Safe", "confidence": 0.9}'),
            ]
            result = query_llm("ls -la")

            # Verify both models were tried
            assert mock_completion.call_count == 2
            calls = mock_completion.call_args_list
            assert calls[0].kwargs["model"] == "openai/gpt-4-turbo"
            assert calls[1].kwargs["model"] == "anthropic/claude-3-opus-20240229"
            assert result["action"] == "allow"

    def test_single_model_no_fallbacks(self, mocker):
        """AC5: Single model with no fallbacks works correctly."""
        mocker.patch.dict(
            os.environ,
            {
                "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
                "AEGISH_FALLBACK_MODELS": "",
                "OPENAI_API_KEY": "test-key",
            },
            clear=True
        )
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.side_effect = ConnectionError("API error")
            result = query_llm("ls -la")

            # Should only try once (no fallbacks)
            assert mock_completion.call_count == 1
            # Should warn since single model failed
            assert result["action"] == "warn"

    def test_missing_api_key_for_model_skips(self, mocker):
        """Model is skipped if its provider's API key is missing."""
        mocker.patch.dict(
            os.environ,
            {
                "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
                "AEGISH_FALLBACK_MODELS": "anthropic/claude-3-haiku-20240307",
                # Only ANTHROPIC_API_KEY set, not OPENAI_API_KEY
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=True
        )
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse(mock_content)
            result = query_llm("ls -la")

            # Should skip openai (no key) and use anthropic
            assert mock_completion.call_count == 1
            call_args = mock_completion.call_args
            assert "anthropic" in call_args.kwargs["model"]
            assert result["action"] == "allow"

    def test_default_models_when_no_config(self, mocker):
        """AC3: Default models are used when no config env vars set."""
        mocker.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
            },
            clear=True
        )
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse(mock_content)
            query_llm("ls -la")

            call_args = mock_completion.call_args
            # Should use default primary: openai/gpt-4
            assert call_args.kwargs["model"] == "openai/gpt-4"

    def test_invalid_model_error_logged_and_skipped(self, mocker):
        """AC4: Invalid model errors are logged and model is skipped."""
        # Use a provider that has a key configured (openai for "invalid" model)
        # This tests that the API error from an invalid model triggers fallback
        mocker.patch.dict(
            os.environ,
            {
                "AEGISH_PRIMARY_MODEL": "openai/invalid-model-name",
                "AEGISH_FALLBACK_MODELS": "anthropic/claude-3-haiku-20240307",
                "OPENAI_API_KEY": "test-key",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=True
        )
        with patch("aegish.llm_client.completion") as mock_completion:
            # First call (invalid model) raises error, second succeeds
            mock_completion.side_effect = [
                Exception("Unknown model: openai/invalid-model-name"),
                MockResponse('{"action": "allow", "reason": "Safe", "confidence": 0.9}'),
            ]
            result = query_llm("ls -la")

            # Should have tried both models
            assert mock_completion.call_count == 2
            # Should succeed with fallback
            assert result["action"] == "allow"

    def test_malformed_model_string_skipped(self, mocker):
        """AC4: Model string without '/' is skipped with warning."""
        mocker.patch.dict(
            os.environ,
            {
                "AEGISH_PRIMARY_MODEL": "gpt-4",  # Invalid: missing provider prefix
                "AEGISH_FALLBACK_MODELS": "anthropic/claude-3-haiku-20240307",
                "ANTHROPIC_API_KEY": "test-key",
            },
            clear=True
        )
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse(mock_content)
            result = query_llm("ls -la")

            # Should skip malformed model and only try anthropic
            assert mock_completion.call_count == 1
            call_args = mock_completion.call_args
            assert "anthropic" in call_args.kwargs["model"]
            assert result["action"] == "allow"
