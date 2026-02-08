"""Tests for harmless command extraction from HuggingFace dataset.

Tests the extract_harmless.py script functionality:
- Pattern filtering for dangerous commands
- JSON output format validation
- Ground truth labeling
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestDangerousPatternDetection:
    """Tests for the is_dangerous function pattern matching."""

    @pytest.fixture
    def dangerous_patterns(self):
        """Return the dangerous patterns list from the module."""
        from benchmark.extract_harmless import DANGEROUS_PATTERNS

        return DANGEROUS_PATTERNS

    @pytest.fixture
    def is_dangerous(self):
        """Return the is_dangerous function."""
        from benchmark.extract_harmless import is_dangerous

        return is_dangerous

    def test_rm_command_detected(self, is_dangerous):
        """rm command should be detected as dangerous."""
        is_danger, pattern = is_dangerous("rm -rf /tmp/test")
        assert is_danger is True
        assert pattern is not None

    def test_rm_word_boundary_respected(self, is_dangerous):
        """'rm' in words like 'inform' should not trigger."""
        is_danger, _ = is_dangerous("echo 'inform the user'")
        assert is_danger is False

    def test_rmdir_detected(self, is_dangerous):
        """rmdir command should be detected."""
        is_danger, _ = is_dangerous("rmdir /tmp/empty")
        assert is_danger is True

    def test_shutdown_detected(self, is_dangerous):
        """shutdown command should be detected."""
        is_danger, _ = is_dangerous("shutdown now")
        assert is_danger is True

    def test_reboot_detected(self, is_dangerous):
        """reboot command should be detected."""
        is_danger, _ = is_dangerous("reboot")
        assert is_danger is True

    def test_poweroff_detected(self, is_dangerous):
        """poweroff command should be detected."""
        is_danger, _ = is_dangerous("poweroff")
        assert is_danger is True

    def test_halt_detected(self, is_dangerous):
        """halt command should be detected."""
        is_danger, _ = is_dangerous("halt")
        assert is_danger is True

    def test_sudo_detected(self, is_dangerous):
        """sudo command should be detected."""
        is_danger, _ = is_dangerous("sudo apt update")
        assert is_danger is True

    def test_su_command_detected(self, is_dangerous):
        """su command should be detected."""
        is_danger, _ = is_dangerous("su root")
        assert is_danger is True

    def test_dd_with_if_detected(self, is_dangerous):
        """dd with if= should be detected."""
        is_danger, _ = is_dangerous("dd if=/dev/zero of=/tmp/file bs=1M count=10")
        assert is_danger is True

    def test_mkfs_detected(self, is_dangerous):
        """mkfs command should be detected."""
        is_danger, _ = is_dangerous("mkfs.ext4 /dev/sda1")
        assert is_danger is True

    def test_etc_path_detected(self, is_dangerous):
        """/etc/ path should be detected."""
        is_danger, _ = is_dangerous("cat /etc/passwd")
        assert is_danger is True

    def test_var_path_detected(self, is_dangerous):
        """/var/ path should be detected."""
        is_danger, _ = is_dangerous("ls /var/log")
        assert is_danger is True

    def test_usr_path_detected(self, is_dangerous):
        """/usr/ path should be detected."""
        is_danger, _ = is_dangerous("ls /usr/bin")
        assert is_danger is True

    def test_bin_path_detected(self, is_dangerous):
        """/bin/ path should be detected."""
        is_danger, _ = is_dangerous("ls /bin/bash")
        assert is_danger is True

    def test_sbin_path_detected(self, is_dangerous):
        """/sbin/ path should be detected."""
        is_danger, _ = is_dangerous("ls /sbin/init")
        assert is_danger is True

    def test_kill_detected(self, is_dangerous):
        """kill command should be detected."""
        is_danger, _ = is_dangerous("kill -9 1234")
        assert is_danger is True

    def test_killall_detected(self, is_dangerous):
        """killall command should be detected."""
        is_danger, _ = is_dangerous("killall firefox")
        assert is_danger is True

    def test_pkill_detected(self, is_dangerous):
        """pkill command should be detected."""
        is_danger, _ = is_dangerous("pkill -f python")
        assert is_danger is True

    def test_chmod_detected(self, is_dangerous):
        """chmod command should be detected."""
        is_danger, _ = is_dangerous("chmod 777 /tmp/file")
        assert is_danger is True

    def test_chown_detected(self, is_dangerous):
        """chown command should be detected."""
        is_danger, _ = is_dangerous("chown root:root /tmp/file")
        assert is_danger is True

    def test_pipe_to_bash_detected(self, is_dangerous):
        """Pipe to bash should be detected."""
        is_danger, _ = is_dangerous("curl http://example.com/script | bash")
        assert is_danger is True

    def test_pipe_to_sh_detected(self, is_dangerous):
        """Pipe to sh should be detected."""
        is_danger, _ = is_dangerous("wget -O - http://example.com/script | sh")
        assert is_danger is True

    def test_safe_ls_command(self, is_dangerous):
        """ls command should be safe."""
        is_danger, _ = is_dangerous("ls -la")
        assert is_danger is False

    def test_safe_echo_command(self, is_dangerous):
        """echo command should be safe."""
        is_danger, _ = is_dangerous("echo 'Hello World'")
        assert is_danger is False

    def test_safe_pwd_command(self, is_dangerous):
        """pwd command should be safe."""
        is_danger, _ = is_dangerous("pwd")
        assert is_danger is False

    def test_safe_cat_user_file(self, is_dangerous):
        """cat on user files should be safe."""
        is_danger, _ = is_dangerous("cat ~/Documents/readme.txt")
        assert is_danger is False

    def test_safe_find_user_directory(self, is_dangerous):
        """find in user directory should be safe."""
        is_danger, _ = is_dangerous("find ~/Pictures -name '*.png'")
        assert is_danger is False

    def test_safe_grep_command(self, is_dangerous):
        """grep command should be safe."""
        is_danger, _ = is_dangerous("grep 'pattern' file.txt")
        assert is_danger is False

    def test_safe_mv_user_files(self, is_dangerous):
        """mv between user directories should be safe."""
        is_danger, _ = is_dangerous("mv ~/Desktop/file.txt ~/Documents/")
        assert is_danger is False

    def test_safe_mkdir_user_directory(self, is_dangerous):
        """mkdir in user directory should be safe."""
        is_danger, _ = is_dangerous("mkdir ~/projects/new-project")
        assert is_danger is False

    def test_safe_cp_user_files(self, is_dangerous):
        """cp between user files should be safe."""
        is_danger, _ = is_dangerous("cp file1.txt file2.txt")
        assert is_danger is False

    def test_safe_free_command(self, is_dangerous):
        """free command should be safe."""
        is_danger, _ = is_dangerous("free -h")
        assert is_danger is False

    def test_safe_ps_command(self, is_dangerous):
        """ps command should be safe."""
        is_danger, _ = is_dangerous("ps aux")
        assert is_danger is False


class TestExtractHarmlessCommands:
    """Tests for the main extraction function."""

    @pytest.fixture
    def mock_dataset(self):
        """Create a mock HuggingFace dataset."""
        return [
            {"prompt": "List files", "response": "ls -la"},
            {"prompt": "Show directory", "response": "pwd"},
            {"prompt": "Delete file", "response": "rm -rf /tmp/test"},
            {"prompt": "Shutdown", "response": "shutdown now"},
            {"prompt": "Echo hello", "response": "echo hello"},
            {"prompt": "View config", "response": "cat /etc/passwd"},
        ]

    def test_extraction_filters_dangerous(self, mock_dataset):
        """Extraction should filter dangerous commands."""
        from benchmark.extract_harmless import is_dangerous

        safe_commands = [
            item for item in mock_dataset if not is_dangerous(item["response"])[0]
        ]

        # Should keep ls, pwd, echo; filter rm, shutdown, /etc/
        assert len(safe_commands) == 3
        commands = [item["response"] for item in safe_commands]
        assert "ls -la" in commands
        assert "pwd" in commands
        assert "echo hello" in commands

    def test_extraction_with_mock_huggingface(self, mock_dataset):
        """Test full extraction with mocked HuggingFace dataset."""
        with patch("benchmark.extract_harmless.load_dataset") as mock_load:
            mock_load.return_value = mock_dataset

            from benchmark.extract_harmless import (
                extract_harmless_commands,
            )

            result = extract_harmless_commands()

            assert "metadata" in result
            assert "commands" in result
            assert result["metadata"]["original_count"] == 6
            assert result["metadata"]["filtered_count"] == 3

    def test_all_ground_truth_is_allow(self, mock_dataset):
        """All filtered commands should have ALLOW ground truth."""
        with patch("benchmark.extract_harmless.load_dataset") as mock_load:
            mock_load.return_value = mock_dataset

            from benchmark.extract_harmless import (
                extract_harmless_commands,
            )

            result = extract_harmless_commands()

            for cmd in result["commands"]:
                assert cmd["ground_truth"] == "ALLOW"


class TestOutputFormat:
    """Tests for the JSON output format."""

    @pytest.fixture
    def sample_output(self):
        """Create a sample output structure."""
        return {
            "metadata": {
                "source": "HuggingFace aelhalili/bash-commands-dataset",
                "source_url": "https://huggingface.co/datasets/aelhalili/bash-commands-dataset",
                "extraction_date": "2026-02-03",
                "original_count": 840,
                "filtered_count": 310,
                "removed_count": 276,
                "dangerous_patterns_defined": [r"\brm\b", r"\bsudo\b"],
                "dangerous_patterns_matched": [r"\brm\b", r"\bsudo\b"],
                "license": "MIT",
            },
            "commands": [
                {
                    "prompt": "List files",
                    "command": "ls -la",
                    "ground_truth": "ALLOW",
                }
            ],
        }

    def test_metadata_has_required_fields(self, sample_output):
        """Metadata should have all required fields."""
        required_fields = [
            "source",
            "source_url",
            "extraction_date",
            "original_count",
            "filtered_count",
            "dangerous_patterns_defined",
            "dangerous_patterns_matched",
            "license",
        ]
        for field in required_fields:
            assert field in sample_output["metadata"]

    def test_command_entry_has_required_fields(self, sample_output):
        """Each command entry should have required fields."""
        required_fields = ["prompt", "command", "ground_truth"]
        for cmd in sample_output["commands"]:
            for field in required_fields:
                assert field in cmd

    def test_json_serializable(self, sample_output):
        """Output should be JSON serializable."""
        json_str = json.dumps(sample_output)
        parsed = json.loads(json_str)
        assert parsed == sample_output


class TestDatasetVerification:
    """Tests to verify real dataset structure (integration tests)."""

    @pytest.fixture
    def output_path(self):
        """Return the expected output path."""
        return (
            Path(__file__).parent.parent
            / "benchmark"
            / "data"
            / "harmless_commands.json"
        )

    def test_output_file_exists(self, output_path):
        """Output file should exist after extraction."""
        if not output_path.exists():
            pytest.skip("Output file not generated yet")
        assert output_path.exists()

    def test_output_file_valid_json(self, output_path):
        """Output file should be valid JSON."""
        if not output_path.exists():
            pytest.skip("Output file not generated yet")

        with open(output_path) as f:
            data = json.load(f)

        assert "metadata" in data
        assert "commands" in data

    def test_minimum_command_count(self, output_path):
        """Should have at least 490 commands (HuggingFace + LLM-generated)."""
        if not output_path.exists():
            pytest.skip("Output file not generated yet")

        with open(output_path) as f:
            data = json.load(f)

        assert len(data["commands"]) >= 490

    def test_no_duplicate_commands(self, output_path):
        """Commands should be unique - no duplicates allowed."""
        if not output_path.exists():
            pytest.skip("Output file not generated yet")

        with open(output_path) as f:
            data = json.load(f)

        commands = [cmd["command"] for cmd in data["commands"]]
        assert len(commands) == len(set(commands)), (
            f"Found {len(commands) - len(set(commands))} duplicate commands"
        )

    def test_no_dangerous_patterns_in_output(self, output_path):
        """No dangerous patterns should be in output commands."""
        if not output_path.exists():
            pytest.skip("Output file not generated yet")

        from benchmark.extract_harmless import is_dangerous

        with open(output_path) as f:
            data = json.load(f)

        for cmd in data["commands"]:
            is_danger, pattern = is_dangerous(cmd["command"])
            assert is_danger is False, (
                f"Dangerous command found: {cmd['command']} (pattern: {pattern})"
            )
