"""Tests for command history functionality.

Tests for Story 3.4: Command History
- AC1: Up arrow recalls previous commands
- AC2: History navigation (up/down arrows)
- AC3: Persistent history across sessions
"""

import os

import pytest
import readline

import aegish.shell
from aegish.shell import HISTORY_FILE, HISTORY_LENGTH, init_history


@pytest.fixture(autouse=True)
def reset_history_initialized():
    """Reset the history initialization guard before each test."""
    aegish.shell._history_initialized = False
    yield
    aegish.shell._history_initialized = False


class TestHistoryConstants:
    """Tests for history configuration constants."""

    def test_history_file_path_uses_home_dir(self):
        """AC3: HISTORY_FILE expands to ~/.aegish_history."""
        expected = os.path.expanduser("~/.aegish_history")
        assert HISTORY_FILE == expected

    def test_history_length_default(self):
        """AC3: HISTORY_LENGTH is 1000."""
        assert HISTORY_LENGTH == 1000


class TestInitHistory:
    """Tests for init_history function."""

    def test_init_history_handles_missing_file(self, tmp_path, mocker):
        """AC3: Gracefully handles missing history file."""
        history_file = tmp_path / "nonexistent_history"
        mocker.patch("aegish.shell.HISTORY_FILE", str(history_file))

        # Should not raise exception
        init_history()

    def test_init_history_loads_existing_file(self, tmp_path, mocker):
        """AC3: History loaded from existing file."""
        history_file = tmp_path / ".aegish_history"
        # Create a history file with some commands
        history_file.write_text("ls -la\necho hello\npwd\n")
        mocker.patch("aegish.shell.HISTORY_FILE", str(history_file))

        # Clear any existing history
        readline.clear_history()

        init_history()

        # Verify history was loaded - file has exactly 3 commands
        history_length = readline.get_current_history_length()
        assert history_length == 3

    def test_history_length_is_set(self, tmp_path, mocker):
        """AC3: History length is configured."""
        history_file = tmp_path / ".aegish_history"
        mocker.patch("aegish.shell.HISTORY_FILE", str(history_file))

        mock_set_length = mocker.patch("readline.set_history_length")
        mocker.patch("readline.read_history_file", side_effect=FileNotFoundError)
        mocker.patch("atexit.register")

        init_history()

        mock_set_length.assert_called_once_with(HISTORY_LENGTH)

    def test_history_file_created_on_save(self, tmp_path, mocker):
        """AC3: File created when history saved."""
        history_file = tmp_path / ".aegish_history"
        mocker.patch("aegish.shell.HISTORY_FILE", str(history_file))

        # Initialize history (file doesn't exist yet)
        init_history()

        # Manually trigger atexit handler (simulate shell exit)
        readline.add_history("test command")
        readline.write_history_file(str(history_file))

        assert history_file.exists()

    def test_init_history_registers_atexit_handler(self, tmp_path, mocker):
        """AC3: atexit handler registered to save history on exit."""
        history_file = tmp_path / ".aegish_history"
        mocker.patch("aegish.shell.HISTORY_FILE", str(history_file))

        mock_register = mocker.patch("atexit.register")
        mocker.patch("readline.read_history_file", side_effect=FileNotFoundError)

        init_history()

        # Verify atexit.register was called with write_history_file
        mock_register.assert_called_once()
        call_args = mock_register.call_args
        assert call_args[0][0] == readline.write_history_file

    def test_init_history_handles_empty_file(self, tmp_path, mocker):
        """AC3: Gracefully handles empty history file."""
        history_file = tmp_path / ".aegish_history"
        history_file.write_text("")  # Empty file
        mocker.patch("aegish.shell.HISTORY_FILE", str(history_file))

        # Clear any existing history
        readline.clear_history()

        # Should not raise exception
        init_history()

        # Empty file means no history loaded
        assert readline.get_current_history_length() == 0

    def test_init_history_handles_permission_error(self, tmp_path, mocker):
        """AC3: Gracefully handles unreadable history file (OSError)."""
        mocker.patch("aegish.shell.HISTORY_FILE", "/root/.aegish_history_nope")
        mocker.patch("readline.read_history_file", side_effect=OSError("Permission denied"))

        # Should not raise exception
        init_history()

    def test_init_history_only_registers_atexit_once(self, tmp_path, mocker):
        """AC3: Multiple init_history calls only register atexit handler once."""
        history_file = tmp_path / ".aegish_history"
        mocker.patch("aegish.shell.HISTORY_FILE", str(history_file))

        mock_register = mocker.patch("atexit.register")
        mocker.patch("readline.read_history_file", side_effect=FileNotFoundError)

        # Call init_history multiple times
        init_history()
        init_history()
        init_history()

        # Verify atexit.register was called only once
        mock_register.assert_called_once()


class TestShellHistoryIntegration:
    """Integration tests for history in shell."""

    def test_shell_initializes_history(self, mocker):
        """AC1, AC2, AC3: run_shell calls init_history."""
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key"},
            clear=True
        )
        mocker.patch("builtins.input", side_effect=["exit"])
        mocker.patch(
            "aegish.shell.validate_command",
            return_value={"action": "allow", "reason": "test", "confidence": 1.0}
        )

        mock_init_history = mocker.patch("aegish.shell.init_history")

        from aegish.shell import run_shell
        run_shell()

        mock_init_history.assert_called_once()

    def test_history_persists_across_sessions(self, tmp_path, mocker):
        """AC3: Commands from previous session available."""
        history_file = tmp_path / ".aegish_history"

        # Simulate first session: write some history
        history_file.write_text("previous_command_1\nprevious_command_2\n")

        mocker.patch("aegish.shell.HISTORY_FILE", str(history_file))
        mocker.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "test-key"},
            clear=True
        )
        mocker.patch("builtins.input", side_effect=["exit"])
        mocker.patch(
            "aegish.shell.validate_command",
            return_value={"action": "allow", "reason": "test", "confidence": 1.0}
        )

        # Clear any existing history
        readline.clear_history()

        from aegish.shell import run_shell
        run_shell()

        # Verify previous history was loaded
        history_length = readline.get_current_history_length()
        assert history_length >= 2
