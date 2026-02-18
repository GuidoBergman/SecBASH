"""Audit logging module.

Logs all command validation decisions to a persistent structured audit trail.
Production: /var/log/aegish/audit.log (root-owned directory)
Development: ~/.aegish/audit.log (user-owned, best-effort)
"""

import getpass
import json
import logging
import os
from datetime import datetime, timezone

from aegish.config import get_mode

logger = logging.getLogger(__name__)

# Audit log paths
PRODUCTION_AUDIT_DIR = "/var/log/aegish"
PRODUCTION_AUDIT_LOG = os.path.join(PRODUCTION_AUDIT_DIR, "audit.log")
DEV_AUDIT_DIR = os.path.expanduser("~/.aegish")
DEV_AUDIT_LOG = os.path.join(DEV_AUDIT_DIR, "audit.log")

_audit_fd = None
_audit_available = False


def init_audit_log() -> bool:
    """Initialize the audit log file.

    In production: uses /var/log/aegish/audit.log
    In development: falls back to ~/.aegish/audit.log

    Returns:
        True if audit logging is available, False otherwise.
    """
    global _audit_fd, _audit_available

    mode = get_mode()

    if mode == "production":
        path = PRODUCTION_AUDIT_LOG
        if not os.path.isdir(PRODUCTION_AUDIT_DIR):
            logger.warning(
                "Audit log directory %s does not exist. "
                "Audit logging unavailable.",
                PRODUCTION_AUDIT_DIR,
            )
            _audit_available = False
            return False
        if not os.access(PRODUCTION_AUDIT_DIR, os.W_OK):
            logger.warning(
                "Audit log directory %s is not writable. "
                "Audit logging unavailable.",
                PRODUCTION_AUDIT_DIR,
            )
            _audit_available = False
            return False
    else:
        path = DEV_AUDIT_LOG
        try:
            os.makedirs(DEV_AUDIT_DIR, exist_ok=True)
        except OSError:
            logger.debug("Could not create audit dir %s", DEV_AUDIT_DIR)
            _audit_available = False
            return False

    try:
        _audit_fd = open(path, "a")
        _audit_available = True
        return True
    except OSError as e:
        logger.warning("Could not open audit log %s: %s", path, e)
        _audit_available = False
        return False


def log_validation(
    command: str,
    action: str,
    reason: str,
    confidence: float,
    source: str = "validation",
    model: str = "",
) -> None:
    """Log a validation decision to the audit trail.

    Args:
        command: The full command text.
        action: The validation action (allow/warn/block).
        reason: Human-readable reason for the decision.
        confidence: Confidence score (0.0-1.0).
        source: Decision source (validation, static_blocklist, etc.)
        model: Which model made the decision (empty for static checks).
    """
    if not _audit_available or _audit_fd is None:
        return

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": getpass.getuser(),
        "command": command,
        "action": action,
        "reason": reason,
        "confidence": confidence,
        "source": source,
        "model": model,
    }

    try:
        _audit_fd.write(json.dumps(entry) + "\n")
        _audit_fd.flush()
    except OSError:
        logger.debug("Failed to write audit log entry")


def log_warn_override(command: str, original_reason: str) -> None:
    """Log when a user overrides a WARN decision.

    Args:
        command: The command that was warned about.
        original_reason: The original warning reason.
    """
    if not _audit_available or _audit_fd is None:
        return

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user": getpass.getuser(),
        "command": command,
        "action": "warn_overridden",
        "reason": original_reason,
        "confidence": 0.0,
        "source": "user_override",
        "model": "",
    }

    try:
        _audit_fd.write(json.dumps(entry) + "\n")
        _audit_fd.flush()
    except OSError:
        logger.debug("Failed to write audit log entry")
