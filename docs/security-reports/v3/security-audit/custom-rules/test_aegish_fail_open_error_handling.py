# Test file for aegish-fail-open-error-handling rules


def validate_command(cmd):
    return {"action": "allow"}


def execute(cmd):
    pass


# --- TRUE POSITIVES ---

def dangerous_wrapped_validation(command):
    # ruleid: aegish-fail-open-error-handling
    try:
        result = validate_command(command)
        return result
    except Exception:
        return execute(command)


def dangerous_default_allow(result):
    # ruleid: aegish-fail-open-default-action
    action = result.get("action", "allow")
    return action


def dangerous_or_allow(result):
    # ruleid: aegish-fail-open-default-action
    action = result.get("action") or "allow"
    return action


# --- TRUE NEGATIVES ---

def safe_default_block(result):
    # ok: aegish-fail-open-default-action
    action = result.get("action", "block")
    return action


def safe_explicit_check(result):
    # ok: aegish-fail-open-default-action
    action = result["action"]
    return action
