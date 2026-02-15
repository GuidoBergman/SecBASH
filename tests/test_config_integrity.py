"""Cross-feature integration tests for Epic 9 config integrity.

Tests that provider allowlist, health check, and model warnings work
together correctly across module boundaries (config -> llm_client -> shell).

Individual unit tests exist in test_config.py, test_llm_client.py, and
test_shell.py. These tests verify cross-feature integration scenarios.
"""

import os

import pytest
from unittest.mock import patch

from aegish.llm_client import health_check, query_llm
from aegish.shell import run_shell
from tests.utils import MockResponse


class TestProviderAllowlistIntegration:
    """Allowlist validation flows through query_llm end-to-end."""

    def test_unknown_provider_rejected_in_query_llm(self, mocker):
        """Unknown provider model is rejected at query level, not sent to LLM."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "evil-corp/permissive-model",
            "AEGISH_FALLBACK_MODELS": "",
            "AEGISH_FAIL_MODE": "safe",
        }, clear=True)
        with patch("aegish.llm_client.completion") as mock_completion:
            result = query_llm("ls -la")

            mock_completion.assert_not_called()
            assert result["action"] == "block"
            assert result["confidence"] == 0.0

    def test_custom_allowlist_accepts_custom_provider(self, mocker):
        """Custom AEGISH_ALLOWED_PROVIDERS lets non-default providers through."""
        mocker.patch.dict(os.environ, {
            "AEGISH_ALLOWED_PROVIDERS": "openai,custom-corp",
            "AEGISH_PRIMARY_MODEL": "custom-corp/my-model",
            "AEGISH_FALLBACK_MODELS": "",
        }, clear=True)
        mocker.patch("aegish.llm_client.get_api_key", return_value="test-key")
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse(mock_content)
            result = query_llm("ls -la")

            assert mock_completion.call_count == 1
            assert result["action"] == "allow"

    def test_unknown_provider_rejected_in_health_check(self, mocker):
        """Health check rejects model from unknown provider before API call."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "evil-corp/bad-model",
        }, clear=True)
        with patch("aegish.llm_client.completion") as mock_completion:
            success, reason = health_check()

            mock_completion.assert_not_called()
            assert success is False
            assert "not in the allowed" in reason.lower()

    def test_all_rejected_falls_back_to_defaults_in_query(self, mocker):
        """When all configured models fail allowlist, query falls back to defaults."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "evil-corp/bad",
            "AEGISH_FALLBACK_MODELS": "evil-corp/worse",
            "OPENAI_API_KEY": "test-key",
        }, clear=True)
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse(mock_content)
            result = query_llm("ls -la")

            # Default chain openai/gpt-4 should be used
            assert mock_completion.call_count == 1
            assert mock_completion.call_args.kwargs["model"] == "openai/gpt-4"
            assert result["action"] == "allow"


class TestHealthCheckIntegration:
    """Health check validates config + API connectivity together."""

    def test_valid_config_and_response_passes(self, mocker):
        """Correct model, key, and response -> (True, "")."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
            "OPENAI_API_KEY": "test-key",
        }, clear=True)
        mock_content = '{"action": "allow", "reason": "Safe echo", "confidence": 0.99}'
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse(mock_content)
            success, reason = health_check()

            assert success is True
            assert reason == ""

    def test_no_api_key_fails_without_crash(self, mocker):
        """Missing API key -> (False, description), no exception."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
        }, clear=True)
        success, reason = health_check()

        assert success is False
        assert "api key" in reason.lower() or "no api" in reason.lower()

    def test_unparseable_response_fails_without_crash(self, mocker):
        """Malformed JSON from LLM -> (False, description), no exception."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
            "OPENAI_API_KEY": "test-key",
        }, clear=True)
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse("not json at all")
            success, reason = health_check()

            assert success is False
            assert "unparseable" in reason.lower()

    def test_timeout_fails_without_blocking(self, mocker):
        """Timeout -> (False, description), does not hang."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
            "OPENAI_API_KEY": "test-key",
        }, clear=True)
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.side_effect = TimeoutError("Health check timed out")
            success, reason = health_check()

            assert success is False
            assert "TimeoutError" in reason

    def test_wrong_action_fails(self, mocker):
        """Model returning block for 'echo hello' -> failure."""
        mocker.patch.dict(os.environ, {
            "AEGISH_PRIMARY_MODEL": "openai/gpt-4",
            "OPENAI_API_KEY": "test-key",
        }, clear=True)
        mock_content = '{"action": "block", "reason": "Blocked", "confidence": 0.9}'
        with patch("aegish.llm_client.completion") as mock_completion:
            mock_completion.return_value = MockResponse(mock_content)
            success, reason = health_check()

            assert success is False
            assert "did not respond correctly" in reason.lower()


class TestStartupIntegration:
    """Startup flow: warnings appear BEFORE health check, all features combine."""

    @pytest.fixture(autouse=True)
    def _isolate_shell(self):
        """Mock model chain display and API key to isolate from real env."""
        with patch("aegish.shell.get_model_chain", return_value=["openai/gpt-4"]):
            with patch("aegish.shell.get_api_key", return_value="test-key"):
                yield

    def test_no_warnings_with_defaults(self, capsys):
        """Default config produces no model warnings."""
        with patch("aegish.shell.health_check", return_value=(True, "")):
            with patch("aegish.shell.get_primary_model", return_value="openai/gpt-4"):
                with patch("aegish.shell.get_fallback_models", return_value=["anthropic/claude-3-haiku-20240307"]):
                    with patch("builtins.input", side_effect=["exit"]):
                        run_shell()
                        output = capsys.readouterr().out
                        assert "WARNING: Using non-default" not in output
                        assert "WARNING: No fallback" not in output
                        assert "WARNING: Health check failed" not in output

    def test_non_default_primary_triggers_warning(self, capsys):
        """Non-default primary model produces warning in startup output."""
        with patch("aegish.shell.health_check", return_value=(True, "")):
            with patch("aegish.shell.get_primary_model", return_value="anthropic/claude-sonnet-4-5-20250929"):
                with patch("aegish.shell.get_fallback_models", return_value=["anthropic/claude-3-haiku-20240307"]):
                    with patch("builtins.input", side_effect=["exit"]):
                        run_shell()
                        output = capsys.readouterr().out
                        assert "WARNING: Using non-default primary model: anthropic/claude-sonnet-4-5-20250929" in output

    def test_empty_fallbacks_triggers_warning(self, capsys):
        """No fallback models produces single-provider warning."""
        with patch("aegish.shell.health_check", return_value=(True, "")):
            with patch("aegish.shell.get_primary_model", return_value="openai/gpt-4"):
                with patch("aegish.shell.get_fallback_models", return_value=[]):
                    with patch("builtins.input", side_effect=["exit"]):
                        run_shell()
                        output = capsys.readouterr().out
                        assert "WARNING: No fallback models configured. Single-provider mode." in output

    def test_warnings_appear_before_health_check_message(self, capsys):
        """Model warnings print BEFORE health check failure warning."""
        with patch("aegish.shell.health_check", return_value=(False, "API unreachable")):
            with patch("aegish.shell.get_primary_model", return_value="anthropic/claude-sonnet-4-5-20250929"):
                with patch("aegish.shell.get_fallback_models", return_value=[]):
                    with patch("builtins.input", side_effect=["exit"]):
                        run_shell()
                        output = capsys.readouterr().out

                        # Both warnings present
                        assert "WARNING: Using non-default primary model" in output
                        assert "WARNING: No fallback models configured" in output
                        assert "WARNING: Health check failed" in output

                        # Order: model warnings before health check warning
                        model_warn_pos = output.index("WARNING: Using non-default primary model")
                        fallback_warn_pos = output.index("WARNING: No fallback models configured")
                        health_warn_pos = output.index("WARNING: Health check failed")
                        assert model_warn_pos < health_warn_pos
                        assert fallback_warn_pos < health_warn_pos

    def test_health_check_failure_does_not_prevent_shell(self, capsys):
        """Shell continues operating after health check failure."""
        mock_validation = {"action": "allow", "reason": "Safe", "confidence": 0.95}
        with patch("aegish.shell.health_check", return_value=(False, "API down")):
            with patch("aegish.shell.get_primary_model", return_value="openai/gpt-4"):
                with patch("aegish.shell.get_fallback_models", return_value=["anthropic/claude-3-haiku-20240307"]):
                    with patch("aegish.shell.validate_command", return_value=mock_validation):
                        with patch("aegish.shell.execute_command", return_value=0) as mock_exec:
                            with patch("builtins.input", side_effect=["ls", "exit"]):
                                run_shell()
                                mock_exec.assert_called_once_with("ls", 0)

    def test_full_startup_all_three_features(self, capsys):
        """All three features (allowlist warning via non-default, empty fallbacks,
        health check failure) produce correct combined output."""
        with patch("aegish.shell.health_check", return_value=(False, "Connection refused")):
            with patch("aegish.shell.get_primary_model", return_value="groq/llama-3-70b"):
                with patch("aegish.shell.get_fallback_models", return_value=[]):
                    with patch("builtins.input", side_effect=["exit"]):
                        run_shell()
                        output = capsys.readouterr().out

                        assert "WARNING: Using non-default primary model: groq/llama-3-70b" in output
                        assert "WARNING: No fallback models configured. Single-provider mode." in output
                        assert "WARNING: Health check failed - Connection refused" in output
