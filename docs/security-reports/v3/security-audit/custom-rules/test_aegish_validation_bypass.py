# Test file for aegish-validation-bypass rules

import os
from aegish.executor import execute_command
from aegish.validator import validate_command


# --- TRUE POSITIVES ---

def dangerous_direct_execute(command):
    # ruleid: aegish-execute-without-validate
    execute_command(command)


def dangerous_env_fail_mode():
    # ruleid: aegish-env-var-security-config-bypass
    mode = os.environ.get("AEGISH_FAIL_MODE", "open")
    return mode


def dangerous_env_mode():
    # ruleid: aegish-env-var-mode-bypass
    mode = os.environ.get("AEGISH_MODE", "development")
    return mode


def dangerous_env_role():
    # ruleid: aegish-env-var-role-bypass
    role = os.environ.get("AEGISH_ROLE", "sysadmin")
    return role


# --- TRUE NEGATIVES ---

def safe_validated_execute(command):
    result = validate_command(command)
    if result["action"] == "allow":
        # ok: aegish-execute-without-validate
        execute_command(command)


def safe_config_api():
    from aegish.config import get_fail_mode
    # ok: aegish-env-var-security-config-bypass
    return get_fail_mode()


def safe_config_mode():
    from aegish.config import get_mode
    # ok: aegish-env-var-mode-bypass
    return get_mode()


def safe_config_role():
    from aegish.config import get_role
    # ok: aegish-env-var-role-bypass
    return get_role()
