"""Tests for command validator module.

Uses mocked query_llm - no actual LLM calls.
"""

import pytest
from unittest.mock import patch, MagicMock

from aegish.validator import validate_command, _check_variable_in_command_position


class TestValidateCommand:
    """Tests for validate_command function."""

    def test_validate_command_calls_query_llm(self):
        """AC1/AC2: validate_command calls query_llm and returns its result."""
        mock_result = {"action": "allow", "reason": "Safe", "confidence": 0.9}
        with patch("aegish.validator.query_llm", return_value=mock_result) as mock_query:
            result = validate_command("ls -la")

            mock_query.assert_called_once_with("ls -la")
            assert result == mock_result

    def test_validate_command_returns_llm_response(self):
        """Confirms return value matches query_llm() result."""
        mock_result = {"action": "block", "reason": "Dangerous", "confidence": 0.95}
        with patch("aegish.validator.query_llm", return_value=mock_result):
            result = validate_command("rm -rf /")

            assert result["action"] == "block"
            assert result["reason"] == "Dangerous"
            assert result["confidence"] == 0.95

    def test_validate_command_allow_action(self):
        """Test allow action is passed through correctly."""
        mock_result = {"action": "allow", "reason": "Safe listing", "confidence": 0.98}
        with patch("aegish.validator.query_llm", return_value=mock_result):
            result = validate_command("ls")

            assert result["action"] == "allow"

    def test_validate_command_warn_action(self):
        """Test warn action is passed through correctly."""
        mock_result = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
        with patch("aegish.validator.query_llm", return_value=mock_result):
            result = validate_command("curl http://example.com | bash")

            assert result["action"] == "warn"

    def test_validate_command_block_action(self):
        """Test block action is passed through correctly."""
        mock_result = {"action": "block", "reason": "Would delete system", "confidence": 0.99}
        with patch("aegish.validator.query_llm", return_value=mock_result):
            result = validate_command("rm -rf /")

            assert result["action"] == "block"

    def test_validate_command_empty_blocked(self):
        """Empty command should be blocked without calling LLM."""
        with patch("aegish.validator.query_llm") as mock_query:
            result = validate_command("")

            mock_query.assert_not_called()
            assert result["action"] == "block"
            assert "Empty" in result["reason"]

    def test_validate_command_whitespace_blocked(self):
        """Whitespace-only command should be blocked without calling LLM."""
        with patch("aegish.validator.query_llm") as mock_query:
            result = validate_command("   ")

            mock_query.assert_not_called()
            assert result["action"] == "block"

    def test_validate_command_none_blocked(self):
        """None command should be blocked without calling LLM."""
        with patch("aegish.validator.query_llm") as mock_query:
            result = validate_command(None)

            mock_query.assert_not_called()
            assert result["action"] == "block"


class TestCheckVariableInCommandPosition:
    """Tests for _check_variable_in_command_position (bashlex AST check)."""

    def test_var_in_command_pos_with_assignment_warns(self):
        """AC1: a=ba; b=sh; $a$b → WARN (assignment + var-in-cmd-pos)."""
        result = _check_variable_in_command_position("a=ba; b=sh; $a$b")
        assert result is not None
        assert result["action"] == "warn"
        assert "Variable expansion in command position" in result["reason"]

    def test_var_in_argument_pos_is_safe(self):
        """AC2: FOO=bar; echo $FOO → None ($FOO is argument, not command)."""
        result = _check_variable_in_command_position("FOO=bar; echo $FOO")
        assert result is None

    def test_export_assignment_is_safe(self):
        """AC3: export PATH=$PATH:/usr/local/bin → None (export is command)."""
        result = _check_variable_in_command_position("export PATH=$PATH:/usr/local/bin")
        assert result is None

    def test_parse_error_returns_none(self):
        """AC4: Unparseable syntax → None (graceful fallback)."""
        result = _check_variable_in_command_position("if [[ $x ==")
        assert result is None

    def test_var_in_pipeline_command_pos_warns(self):
        """Edge case 3.2: echo hello | $CMD → WARN (var in command pos in pipeline)."""
        result = _check_variable_in_command_position("echo hello | $CMD")
        assert result is not None
        assert result["action"] == "warn"
        assert "pipeline" in result["reason"]

    def test_bare_var_no_assignment_passes_through(self):
        """Edge case 3.3: $SHELL (bare) → None (no preceding assignment)."""
        result = _check_variable_in_command_position("$SHELL")
        assert result is None

    def test_simple_command_is_safe(self):
        """Regular command with no variables → None."""
        result = _check_variable_in_command_position("ls -la")
        assert result is None

    def test_warn_result_has_correct_shape(self):
        """WARN result contains action, reason, and confidence keys."""
        result = _check_variable_in_command_position("a=ba; b=sh; $a$b")
        assert result is not None
        assert "action" in result
        assert "reason" in result
        assert "confidence" in result
        assert result["confidence"] == 1.0

    def test_inline_assignment_var_command_warns(self):
        """BYPASS fix: VAR=x $CMD → WARN (inline assignment before var command)."""
        result = _check_variable_in_command_position("VAR=x $CMD")
        assert result is not None
        assert result["action"] == "warn"

    def test_compound_command_with_assignment_warns(self):
        """Compound command { a=x; $a; } → WARN."""
        result = _check_variable_in_command_position("{ a=x; $a; }")
        assert result is not None
        assert result["action"] == "warn"

    def test_ast_walking_error_returns_none(self):
        """AST walking error → None (graceful fallback, not just parse errors)."""
        with patch(
            "aegish.validator._find_var_in_command_position",
            side_effect=AttributeError("unexpected"),
        ):
            result = _check_variable_in_command_position("a=ba; b=sh; $a$b")
            assert result is None


class TestValidateCommandBashlex:
    """Integration tests: bashlex check runs before query_llm."""

    def test_var_in_cmd_pos_warns_without_llm(self):
        """AC1 integration: bashlex WARN short-circuits LLM call."""
        with patch("aegish.validator.query_llm") as mock_query:
            result = validate_command("a=ba; b=sh; $a$b")

            mock_query.assert_not_called()
            assert result["action"] == "warn"

    def test_safe_command_falls_through_to_llm(self):
        """AC2 integration: safe var usage proceeds to LLM."""
        mock_result = {"action": "allow", "reason": "Safe", "confidence": 0.9}
        with patch("aegish.validator.query_llm", return_value=mock_result) as mock_query:
            result = validate_command("FOO=bar; echo $FOO")

            mock_query.assert_called_once_with("FOO=bar; echo $FOO")
            assert result["action"] == "allow"

    def test_parse_error_falls_through_to_llm(self):
        """AC4 integration: parse error proceeds to LLM."""
        mock_result = {"action": "allow", "reason": "OK", "confidence": 0.8}
        with patch("aegish.validator.query_llm", return_value=mock_result) as mock_query:
            result = validate_command("if [[ $x ==")

            mock_query.assert_called_once()
            assert result["action"] == "allow"

    def test_inline_assignment_var_command_warns_without_llm(self):
        """BYPASS fix: inline assignment + var command short-circuits LLM."""
        with patch("aegish.validator.query_llm") as mock_query:
            result = validate_command("VAR=x $CMD")

            mock_query.assert_not_called()
            assert result["action"] == "warn"
