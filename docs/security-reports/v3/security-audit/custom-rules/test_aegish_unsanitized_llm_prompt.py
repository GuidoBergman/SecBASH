# Test file for aegish-unsanitized-llm-prompt rules


def escape_command_tags(text):
    return text


def _escape_command_tags(text):
    return text


# --- TRUE POSITIVES ---

def dangerous_prompt_missing_escape(content):
    # ruleid: aegish-prompt-missing-escape
    msg = {"role": "user", "content": content}
    return msg


# --- TRUE NEGATIVES ---

def safe_prompt_with_escape(command):
    safe = _escape_command_tags(command)
    content = f"Validate: {safe}"
    # ok: aegish-prompt-missing-escape
    msg = {"role": "user", "content": content}
    return msg
