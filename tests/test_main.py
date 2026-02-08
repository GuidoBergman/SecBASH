"""Tests for main module.

Tests CLI entry point and credential validation integration.
"""

import os
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from secbash.main import app


class TestMainCredentialValidation:
    """Integration tests for main.py credential validation."""

    def test_main_exits_on_no_credentials(self, mocker):
        """AC2: No credentials -> exit code 1."""
        mocker.patch.dict(os.environ, {}, clear=True)
        mocker.patch("secbash.main.run_shell")

        runner = CliRunner()
        result = runner.invoke(app)

        assert result.exit_code == 1

    def test_main_error_to_stderr(self):
        """AC2: Error message goes to stderr, not stdout.

        Uses subprocess to properly capture separated stdout/stderr streams.
        Runs from a temp directory to prevent .env auto-loading from injecting keys.
        """
        import tempfile

        # Run the CLI as a subprocess with cleared API key env vars
        env = {k: v for k, v in os.environ.items()
               if not k.endswith("_API_KEY")}

        # Run from temp dir to avoid .env auto-loading by litellm/dotenv
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, "-c", "from secbash.main import app; app()"],
                capture_output=True,
                text=True,
                env=env,
                cwd=tmpdir,
            )

        # Verify error is in stderr
        assert result.returncode == 1
        assert "No LLM API credentials configured" in result.stderr
        assert "OPENAI_API_KEY" in result.stderr
        # stdout should not contain the error message
        assert "No LLM API credentials configured" not in result.stdout

    def test_main_error_message_includes_instructions(self, mocker):
        """AC2: Error message includes setup instructions."""
        mocker.patch.dict(os.environ, {}, clear=True)
        mocker.patch("secbash.main.run_shell")

        runner = CliRunner()
        result = runner.invoke(app)

        # CliRunner mixes output, but we can verify content is present
        assert "export" in result.output
        assert "OPENAI_API_KEY" in result.output
        assert "ANTHROPIC_API_KEY" in result.output

    def test_main_proceeds_with_credentials(self, mocker):
        """AC1: Valid credentials -> shell starts."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key"},
            clear=True
        )
        mock_shell = mocker.patch("secbash.main.run_shell", return_value=0)

        runner = CliRunner()
        result = runner.invoke(app)

        mock_shell.assert_called_once()
        assert result.exit_code == 0

    def test_main_returns_shell_exit_code(self, mocker):
        """Main returns whatever exit code run_shell returns."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key"},
            clear=True
        )
        mocker.patch("secbash.main.run_shell", return_value=42)

        runner = CliRunner()
        result = runner.invoke(app)

        assert result.exit_code == 42
