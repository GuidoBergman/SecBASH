"""Tests for sensible defaults behavior.

Verifies that SecBASH works with minimal configuration and
applies reasonable defaults.
"""

import os
from io import StringIO
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from secbash import __version__
from secbash.config import get_available_providers, validate_credentials
from secbash.llm_client import PROVIDER_PRIORITY
from secbash.main import app
from secbash.shell import get_prompt


class TestDefaultPrompt:
    """Tests for default shell prompt."""

    def test_default_prompt_returns_secbash(self):
        """AC2: Default prompt is 'secbash> '."""
        prompt = get_prompt()

        assert prompt == "secbash> "


class TestDefaultProviderPriority:
    """Tests for default LLM provider priority."""

    def test_default_provider_priority_order(self):
        """AC2: Provider priority is openrouter, openai, anthropic."""
        assert PROVIDER_PRIORITY == ["openrouter", "openai", "anthropic"]


class TestWorksWithOneApiKey:
    """Tests that system works with just one API key (AC1)."""

    def test_works_with_only_openrouter_key(self, mocker):
        """AC1: System starts with just OPENROUTER_API_KEY."""
        mocker.patch.dict(
            os.environ,
            {"OPENROUTER_API_KEY": "test-key"},
            clear=True
        )

        is_valid, message = validate_credentials()

        assert is_valid is True
        assert "openrouter" in message.lower()

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


class TestStartupShowsActiveProviders:
    """Tests for startup message showing active providers."""

    def test_startup_shows_active_providers(self, mocker):
        """AC2: Startup message includes provider info."""
        mocker.patch.dict(
            os.environ,
            {"OPENROUTER_API_KEY": "test-key", "OPENAI_API_KEY": "test-key2"},
            clear=True
        )

        # Capture stdout
        captured_output = StringIO()
        mocker.patch("sys.stdout", captured_output)

        # Mock input to raise EOFError immediately (simulating Ctrl+D)
        mocker.patch("builtins.input", side_effect=EOFError)

        from secbash.shell import run_shell
        run_shell()

        output = captured_output.getvalue()

        # Should show providers in startup message
        assert "openrouter" in output.lower()
        assert "openai" in output.lower()


class TestDefaultShell:
    """Tests for default shell being bash."""

    def test_default_shell_is_bash(self, mocker):
        """AC2: Default shell is bash."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=0)

        from secbash.executor import execute_command
        execute_command("echo hello", 0)

        # Verify bash is used
        call_args = mock_run.call_args
        assert call_args[0][0][0] == "bash"
        assert call_args[0][0][1] == "-c"


class TestVersionFlag:
    """Tests for --version flag."""

    def test_version_flag_outputs_version(self):
        """AC2: --version shows version string."""
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert __version__ in result.output
        assert "SecBASH" in result.output

    def test_version_short_flag_outputs_version(self):
        """AC2: -v shows version string."""
        runner = CliRunner()
        result = runner.invoke(app, ["-v"])

        assert result.exit_code == 0
        assert __version__ in result.output
