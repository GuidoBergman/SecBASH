"""Tests for command validator module.

Uses mocked query_llm - no actual LLM calls.
"""

import pytest
from unittest.mock import patch, MagicMock

from secbash.validator import validate_command


class TestValidateCommand:
    """Tests for validate_command function."""

    def test_validate_command_calls_query_llm(self):
        """AC1/AC2: validate_command calls query_llm and returns its result."""
        mock_result = {"action": "allow", "reason": "Safe", "confidence": 0.9}
        with patch("secbash.validator.query_llm", return_value=mock_result) as mock_query:
            result = validate_command("ls -la")

            mock_query.assert_called_once_with("ls -la")
            assert result == mock_result

    def test_validate_command_returns_llm_response(self):
        """Confirms return value matches query_llm() result."""
        mock_result = {"action": "block", "reason": "Dangerous", "confidence": 0.95}
        with patch("secbash.validator.query_llm", return_value=mock_result):
            result = validate_command("rm -rf /")

            assert result["action"] == "block"
            assert result["reason"] == "Dangerous"
            assert result["confidence"] == 0.95

    def test_validate_command_allow_action(self):
        """Test allow action is passed through correctly."""
        mock_result = {"action": "allow", "reason": "Safe listing", "confidence": 0.98}
        with patch("secbash.validator.query_llm", return_value=mock_result):
            result = validate_command("ls")

            assert result["action"] == "allow"

    def test_validate_command_warn_action(self):
        """Test warn action is passed through correctly."""
        mock_result = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
        with patch("secbash.validator.query_llm", return_value=mock_result):
            result = validate_command("curl http://example.com | bash")

            assert result["action"] == "warn"

    def test_validate_command_block_action(self):
        """Test block action is passed through correctly."""
        mock_result = {"action": "block", "reason": "Would delete system", "confidence": 0.99}
        with patch("secbash.validator.query_llm", return_value=mock_result):
            result = validate_command("rm -rf /")

            assert result["action"] == "block"

    def test_validate_command_empty_blocked(self):
        """Empty command should be blocked without calling LLM."""
        with patch("secbash.validator.query_llm") as mock_query:
            result = validate_command("")

            mock_query.assert_not_called()
            assert result["action"] == "block"
            assert "Empty" in result["reason"]

    def test_validate_command_whitespace_blocked(self):
        """Whitespace-only command should be blocked without calling LLM."""
        with patch("secbash.validator.query_llm") as mock_query:
            result = validate_command("   ")

            mock_query.assert_not_called()
            assert result["action"] == "block"

    def test_validate_command_none_blocked(self):
        """None command should be blocked without calling LLM."""
        with patch("secbash.validator.query_llm") as mock_query:
            result = validate_command(None)

            mock_query.assert_not_called()
            assert result["action"] == "block"
