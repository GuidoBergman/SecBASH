"""Tests for audit logging module."""
import json
import os
from unittest import mock

import pytest

from aegish.audit import init_audit_log, log_validation, log_warn_override


class TestInitAuditLog:
    def setup_method(self):
        """Reset audit state between tests."""
        import aegish.audit as audit_mod
        audit_mod._audit_fd = None
        audit_mod._audit_available = False

    def test_dev_mode_creates_log(self, tmp_path):
        """In development mode, creates ~/.aegish/audit.log."""
        import aegish.audit as audit_mod
        audit_mod.DEV_AUDIT_DIR = str(tmp_path / ".aegish")
        audit_mod.DEV_AUDIT_LOG = str(tmp_path / ".aegish" / "audit.log")

        with mock.patch("aegish.audit.get_mode", return_value="development"):
            result = init_audit_log()

        assert result is True
        assert os.path.exists(str(tmp_path / ".aegish" / "audit.log"))

        if audit_mod._audit_fd:
            audit_mod._audit_fd.close()

    def test_production_mode_missing_dir(self):
        """In production mode, returns False if dir doesn't exist."""
        import aegish.audit as audit_mod
        audit_mod.PRODUCTION_AUDIT_DIR = "/nonexistent/path"

        with mock.patch("aegish.audit.get_mode", return_value="production"):
            result = init_audit_log()

        assert result is False

    def test_production_mode_not_writable(self, tmp_path):
        """In production mode, returns False if dir is not writable."""
        import aegish.audit as audit_mod
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        read_only_dir.chmod(0o444)

        audit_mod.PRODUCTION_AUDIT_DIR = str(read_only_dir)
        audit_mod.PRODUCTION_AUDIT_LOG = str(read_only_dir / "audit.log")

        with mock.patch("aegish.audit.get_mode", return_value="production"):
            result = init_audit_log()

        assert result is False
        # Restore permissions for cleanup
        read_only_dir.chmod(0o755)

    def test_dev_mode_dir_creation_failure(self, tmp_path):
        """Returns False if dev audit dir cannot be created."""
        import aegish.audit as audit_mod
        audit_mod.DEV_AUDIT_DIR = "/nonexistent/deep/path/.aegish"
        audit_mod.DEV_AUDIT_LOG = "/nonexistent/deep/path/.aegish/audit.log"

        with mock.patch("aegish.audit.get_mode", return_value="development"):
            result = init_audit_log()

        assert result is False


class TestLogValidation:
    def setup_method(self):
        """Reset audit state between tests."""
        import aegish.audit as audit_mod
        audit_mod._audit_fd = None
        audit_mod._audit_available = False

    def test_logs_json_entry(self, tmp_path):
        """Writes structured JSON to audit log."""
        import aegish.audit as audit_mod
        audit_mod.DEV_AUDIT_DIR = str(tmp_path)
        audit_mod.DEV_AUDIT_LOG = str(tmp_path / "audit.log")

        with mock.patch("aegish.audit.get_mode", return_value="development"):
            init_audit_log()

        log_validation("ls -la", "allow", "safe command", 0.95, source="llm", model="openai/gpt-4")

        if audit_mod._audit_fd:
            audit_mod._audit_fd.close()

        with open(str(tmp_path / "audit.log")) as f:
            line = f.readline()
            entry = json.loads(line)

        assert entry["command"] == "ls -la"
        assert entry["action"] == "allow"
        assert entry["confidence"] == 0.95
        assert entry["source"] == "llm"
        assert "timestamp" in entry
        assert "user" in entry

    def test_noop_when_not_initialized(self):
        """Does nothing if audit logging is not initialized."""
        # Should not raise
        log_validation("ls", "allow", "safe", 0.9)

    def test_logs_block_entry(self, tmp_path):
        """Logs block action correctly."""
        import aegish.audit as audit_mod
        audit_mod.DEV_AUDIT_DIR = str(tmp_path)
        audit_mod.DEV_AUDIT_LOG = str(tmp_path / "audit.log")

        with mock.patch("aegish.audit.get_mode", return_value="development"):
            init_audit_log()

        log_validation("rm -rf /", "block", "destructive command", 0.99)

        if audit_mod._audit_fd:
            audit_mod._audit_fd.close()

        with open(str(tmp_path / "audit.log")) as f:
            entry = json.loads(f.readline())

        assert entry["action"] == "block"
        assert entry["command"] == "rm -rf /"


class TestLogWarnOverride:
    def setup_method(self):
        """Reset audit state between tests."""
        import aegish.audit as audit_mod
        audit_mod._audit_fd = None
        audit_mod._audit_available = False

    def test_logs_override_entry(self, tmp_path):
        """Logs warn_overridden action."""
        import aegish.audit as audit_mod
        audit_mod.DEV_AUDIT_DIR = str(tmp_path)
        audit_mod.DEV_AUDIT_LOG = str(tmp_path / "audit.log")

        with mock.patch("aegish.audit.get_mode", return_value="development"):
            init_audit_log()

        log_warn_override("wget http://example.com", "Download without execution")

        if audit_mod._audit_fd:
            audit_mod._audit_fd.close()

        with open(str(tmp_path / "audit.log")) as f:
            entry = json.loads(f.readline())

        assert entry["action"] == "warn_overridden"
        assert entry["command"] == "wget http://example.com"
        assert entry["source"] == "user_override"
        assert entry["confidence"] == 0.0

    def test_noop_when_not_initialized(self):
        """Does nothing if audit logging is not initialized."""
        # Should not raise
        log_warn_override("wget http://example.com", "reason")
