"""Integration tests for validation pipeline hardening (Story 7.8).

Tests cross-feature integration paths across the validation pipeline:
envsubst expansion, bashlex detection, command delimiters, fail-mode,
and oversized command blocking.
"""

import os
import subprocess

import pytest
from unittest.mock import MagicMock, patch

from aegish.llm_client import (
    MAX_COMMAND_LENGTH,
    _expand_env_vars,
    _get_messages_for_model,
    _get_safe_env,
    query_llm,
)
from aegish.validator import validate_command
from tests.utils import MockResponse, mock_providers


class TestEnvSubstExpansion:
    """Task 1.1: envsubst expansion, fallback, and short-circuit."""

    def test_exec_shell_produces_expanded_form(self):
        """AC1: exec $SHELL produces expanded form with real $SHELL value."""
        with patch("aegish.llm_client.subprocess") as mock_sub:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "/bin/zsh"
            mock_sub.run.return_value = mock_result
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired

            result = _expand_env_vars("exec $SHELL")
            assert result == "/bin/zsh"

    def test_graceful_fallback_when_envsubst_unavailable(self):
        """AC2: expansion returns None if envsubst unavailable."""
        with patch("aegish.llm_client.subprocess") as mock_sub:
            mock_sub.run.side_effect = FileNotFoundError("envsubst not found")
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired

            result = _expand_env_vars("exec $SHELL")
            assert result is None

    def test_no_dollar_short_circuits_subprocess(self):
        """No subprocess spawned when command has no $ character."""
        with patch("aegish.llm_client.subprocess") as mock_sub:
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired
            result = _expand_env_vars("ls -la /tmp")
            assert result == "ls -la /tmp"
            mock_sub.run.assert_not_called()

    def test_sensitive_var_filtered_from_expansion_env(self):
        """Sensitive variables (API keys) not leaked when filtering enabled."""
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-secret", "HOME": "/home/user"},
            clear=True,
        ):
            with patch("aegish.llm_client.get_filter_sensitive_vars", return_value=True):
                safe = _get_safe_env()
                assert "OPENAI_API_KEY" not in safe
                assert safe["HOME"] == "/home/user"


class TestBashlexDetection:
    """Task 1.2: bashlex variable-in-command-position detection."""

    def test_var_in_command_position_returns_block(self):
        """AC3: a=ba; b=sh; $a$b returns BLOCK (default action since Story 10.1)."""
        result = validate_command("a=ba; b=sh; $a$b")
        assert result["action"] == "block"
        assert "Variable expansion in command position" in result["reason"]
        assert result["confidence"] == 1.0

    def test_safe_echo_var_passes_through(self):
        """AC4: FOO=bar; echo $FOO passes through to LLM.

        Note: compound commands are now decomposed (Story 10.4), so each
        subcommand is validated independently via LLM.
        """
        mock_result = {"action": "allow", "reason": "Safe echo", "confidence": 0.9}
        with patch("aegish.validator.query_llm", return_value=mock_result) as mock_q:
            result = validate_command("FOO=bar; echo $FOO")
            assert mock_q.call_count == 2  # Decomposed into 2 subcommands
            assert result["action"] == "allow"

    def test_unparseable_command_falls_through_to_llm(self):
        """AC5: unparseable command passes through to LLM."""
        mock_result = {"action": "allow", "reason": "OK", "confidence": 0.8}
        with patch("aegish.validator.query_llm", return_value=mock_result) as mock_q:
            result = validate_command("if [[ $x ==")
            mock_q.assert_called_once()
            assert result["action"] == "allow"

    def test_bashlex_short_circuits_before_llm(self):
        """Bashlex BLOCK (default since Story 10.1) prevents any LLM call."""
        with patch("aegish.validator.query_llm") as mock_q:
            result = validate_command("a=ba; b=sh; $a$b")
            mock_q.assert_not_called()
            assert result["action"] == "block"


class TestCommandDelimiters:
    """Task 1.3: COMMAND tag wrapping in user messages."""

    def test_user_message_contains_command_tags(self):
        """AC6: user message contains <COMMAND> and </COMMAND> tags."""
        with patch("aegish.llm_client._expand_env_vars", return_value="ls -la"):
            messages = _get_messages_for_model("ls -la")
            user_content = messages[1]["content"]
            assert "<COMMAND>" in user_content
            assert "</COMMAND>" in user_content
            assert "<COMMAND>\nls -la\n</COMMAND>" in user_content

    def test_expansion_placed_after_command_tags(self):
        """Expansion note appears after </COMMAND>, not inside tags."""
        with patch("aegish.llm_client._expand_env_vars", return_value="exec /bin/bash"):
            messages = _get_messages_for_model("exec $SHELL")
            user_content = messages[1]["content"]
            # Raw command is inside tags
            assert "<COMMAND>\nexec $SHELL\n</COMMAND>" in user_content
            # Expansion is after closing tag
            cmd_end = user_content.index("</COMMAND>")
            exp_start = user_content.index("After environment expansion")
            assert exp_start > cmd_end

    def test_envsubst_plus_delimiters_plus_llm_flow(self):
        """Cross-feature: command with $VAR gets expanded, wrapped in tags, sent to LLM."""
        with patch("aegish.llm_client.subprocess") as mock_sub:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "exec /bin/bash"
            mock_sub.run.return_value = mock_result
            mock_sub.TimeoutExpired = subprocess.TimeoutExpired

            mock_content = '{"action": "block", "reason": "Shell escape", "confidence": 0.95}'
            with mock_providers(["openai"]):
                with patch("aegish.llm_client.completion") as mock_completion:
                    mock_completion.return_value = MockResponse(mock_content)
                    result = query_llm("exec $SHELL")

                    # Verify LLM received both raw + expanded in tagged format
                    messages = mock_completion.call_args.kwargs["messages"]
                    user_content = messages[1]["content"]
                    assert "<COMMAND>\nexec $SHELL\n</COMMAND>" in user_content
                    assert "After environment expansion: exec /bin/bash" in user_content
                    assert result["action"] == "block"


class TestFailMode:
    """Task 1.4: fail-safe and fail-open mode behavior."""

    def test_safe_mode_blocks_on_validation_failure(self):
        """AC7: AEGISH_FAIL_MODE=safe validation failure returns block."""
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                with patch("aegish.llm_client.get_fail_mode", return_value="safe"):
                    mock_completion.side_effect = ConnectionError("Provider down")
                    result = query_llm("ls -la")
                    assert result["action"] == "block"
                    assert result["confidence"] == 0.0
                    assert "could not validate" in result["reason"].lower()

    def test_open_mode_warns_on_validation_failure(self):
        """AC8: AEGISH_FAIL_MODE=open validation failure returns warn."""
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                with patch("aegish.llm_client.get_fail_mode", return_value="open"):
                    mock_completion.side_effect = ConnectionError("Provider down")
                    result = query_llm("ls -la")
                    assert result["action"] == "warn"
                    assert result["confidence"] == 0.0

    def test_default_fail_mode_is_safe(self, mocker):
        """Default (no env var) is safe mode = block on failure."""
        mocker.patch.dict(os.environ, {}, clear=True)
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                with patch("aegish.llm_client.get_fail_mode", return_value="safe"):
                    mock_completion.side_effect = TimeoutError("Timeout")
                    result = query_llm("ls -la")
                    assert result["action"] == "block"

    def test_fail_mode_end_to_end_with_validate_command(self):
        """End-to-end: validate_command with providers down returns block/warn."""
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                with patch("aegish.llm_client.get_fail_mode", return_value="safe"):
                    mock_completion.side_effect = ConnectionError("Down")
                    result = validate_command("ls -la")
                    assert result["action"] == "block"
                    assert result["confidence"] == 0.0


class TestOversizedCommand:
    """Task 1.5: oversized command blocking."""

    def test_5000_char_command_blocked(self):
        """AC9: 5000-char command returns BLOCK with confidence 1.0."""
        command = "x" * 5000
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                result = query_llm(command)
                mock_completion.assert_not_called()
                assert result["action"] == "block"
                assert result["confidence"] == 1.0

    def test_block_reason_includes_lengths(self):
        """Block reason includes actual length and limit."""
        command = "x" * 5000
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion"):
                result = query_llm(command)
                assert "5000" in result["reason"]
                assert str(MAX_COMMAND_LENGTH) in result["reason"]

    def test_oversized_short_circuits_envsubst_and_llm(self):
        """Oversized command in validate_command skips envsubst and LLM."""
        command = "echo " + "x" * 5000
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                with patch("aegish.llm_client._expand_env_vars") as mock_expand:
                    result = validate_command(command)
                    # query_llm blocks on length before envsubst or LLM
                    mock_completion.assert_not_called()
                    mock_expand.assert_not_called()
                    assert result["action"] == "block"
                    assert result["confidence"] == 1.0

    def test_at_max_length_command_processed(self):
        """Command at exactly MAX_COMMAND_LENGTH is processed normally."""
        command = "x" * MAX_COMMAND_LENGTH
        mock_content = '{"action": "allow", "reason": "Safe", "confidence": 0.9}'
        with mock_providers(["openai"]):
            with patch("aegish.llm_client.completion") as mock_completion:
                mock_completion.return_value = MockResponse(mock_content)
                result = query_llm(command)
                mock_completion.assert_called_once()
                assert result["action"] == "allow"
