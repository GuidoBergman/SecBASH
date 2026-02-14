"""Tests for sensible defaults behavior.

Verifies that aegish works with minimal configuration and
applies reasonable defaults.
"""

import os
from io import StringIO
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from aegish import __version__
from aegish.config import (
    get_available_providers,
    get_model_chain,
    get_primary_model,
    get_fallback_models,
    validate_credentials,
)
from aegish.main import app
from aegish.shell import get_prompt


class TestDefaultPrompt:
    """Tests for default shell prompt."""

    def test_default_prompt_returns_aegish(self):
        """AC2: Default prompt is 'aegish> '."""
        prompt = get_prompt()

        assert prompt == "aegish> "


class TestDefaultModelConfiguration:
    """Tests for default model configuration."""

    def test_default_primary_model(self, mocker):
        """AC2: Default primary model is openai/gpt-4."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert get_primary_model() == "openai/gpt-4"

    def test_default_fallback_models(self, mocker):
        """AC2: Default fallback is anthropic/claude-3-haiku."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert get_fallback_models() == [
            "anthropic/claude-3-haiku-20240307",
        ]

    def test_default_model_chain_order(self, mocker):
        """AC2: Model chain order is openai, anthropic."""
        mocker.patch.dict(os.environ, {}, clear=True)
        model_chain = get_model_chain()
        assert model_chain == [
            "openai/gpt-4",
            "anthropic/claude-3-haiku-20240307",
        ]


class TestWorksWithOneApiKey:
    """Tests that system works with just one API key (AC1)."""

    def test_works_with_only_openai_key(self, mocker):
        """AC1: System starts with just OPENAI_API_KEY."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key"},
            clear=True
        )

        is_valid, message = validate_credentials()

        assert is_valid is True
        assert "openai" in message.lower()

    def test_works_with_only_anthropic_key(self, mocker):
        """AC1: System starts with just ANTHROPIC_API_KEY."""
        mocker.patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "test-key"},
            clear=True
        )

        is_valid, message = validate_credentials()

        assert is_valid is True
        assert "anthropic" in message.lower()

    def test_no_config_file_required(self, mocker):
        """AC1: System works without any config files, just env vars."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key"},
            clear=True
        )

        # Validate credentials works without any file I/O
        is_valid, _ = validate_credentials()
        assert is_valid is True

        # get_available_providers works without any file I/O
        providers = get_available_providers()
        assert providers == ["openai"]

    def test_shell_works_with_one_api_key_no_config_files(self, mocker):
        """AC1: Shell starts and runs with just one API key, no config files.

        This is the integration test specified in Task 4.1 - verifies the
        shell can actually start and accept input with minimal configuration.
        """
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key"},
            clear=True
        )

        # Mock input to simulate user typing 'exit' immediately
        mocker.patch("builtins.input", side_effect=["exit"])

        # Mock the validator to avoid real LLM calls
        mocker.patch(
            "aegish.shell.validate_command",
            return_value={"action": "allow", "reason": "test", "confidence": 1.0}
        )

        from aegish.shell import run_shell
        exit_code = run_shell()

        # Shell should exit cleanly
        assert exit_code == 0


class TestStartupShowsModelChain:
    """Tests for startup message showing model chain with availability status."""

    def test_startup_shows_model_chain(self, mocker, capsys):
        """AC2: Startup message shows model chain with availability status."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key2"},
            clear=True
        )

        # Mock input to raise EOFError immediately (simulating Ctrl+D)
        mocker.patch("builtins.input", side_effect=EOFError)

        from aegish.shell import run_shell
        run_shell()

        # Use pytest's capsys for reliable stdout capture
        captured = capsys.readouterr()
        output = captured.out

        # Should show model chain format with active/inactive status
        assert "model chain:" in output.lower()
        assert "openai/gpt-4 (active)" in output.lower()
        assert "anthropic/claude-3-haiku-20240307 (active)" in output.lower()
        # Verify priority order indicator
        assert ">" in output

    def test_startup_shows_unconfigured_models(self, mocker, capsys):
        """AC2: Startup shows unconfigured models marked as inactive."""
        mocker.patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "test-key"},
            clear=True
        )

        mocker.patch("builtins.input", side_effect=EOFError)

        from aegish.shell import run_shell
        run_shell()

        captured = capsys.readouterr()
        output = captured.out

        # Only anthropic model should be active
        assert "anthropic/claude-3-haiku-20240307 (active)" in output.lower()
        assert "openai/gpt-4 (--)" in output.lower()


class TestDefaultShell:
    """Tests for default shell being bash."""

    def test_default_shell_is_bash(self, mocker):
        """AC2: Default shell is bash with hardened flags and sanitized env."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=0)

        from aegish.executor import execute_command
        execute_command("echo hello", 0)

        # Verify bash is used with hardened flags in correct order
        # (-c must come last before the command string)
        call_args = mock_run.call_args
        cmd_list = call_args[0][0]
        assert cmd_list == ["bash", "--norc", "--noprofile", "-c", "(exit 0); echo hello"]

        # Verify env sanitization is applied (AC1: env=safe_env)
        assert "env" in call_args.kwargs
        assert isinstance(call_args.kwargs["env"], dict)


class TestVersionFlag:
    """Tests for --version flag."""

    def test_version_flag_outputs_version(self, mocker):
        """AC2: --version shows version string and basic info."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key"},
            clear=True
        )
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert __version__ in result.output
        assert "aegish" in result.output
        # Task 2.3: Should show basic info (configured providers)
        assert "Configured providers:" in result.output

    def test_version_short_flag_outputs_version(self, mocker):
        """AC2: -v shows version string."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key"},
            clear=True
        )
        runner = CliRunner()
        result = runner.invoke(app, ["-v"])

        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_shows_no_providers_when_none_configured(self, mocker):
        """AC2: --version shows helpful message when no providers configured."""
        mocker.patch.dict(os.environ, {}, clear=True)
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "none" in result.output.lower()
