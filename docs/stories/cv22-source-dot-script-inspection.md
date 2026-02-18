# CV-22: Source/Dot Commands Execute Uninspected Scripts

## Problem

`source script.sh` or `. script.sh` executes script contents without aegish inspecting them. The LLM validates the `source` command string but not the file contents. A script could contain `rm -rf /` and the LLM would only see `source deploy.sh`.

## Solution

Read the script file and include its contents in the LLM prompt so the LLM can validate what will actually be executed.

## All changes in `src/aegish/llm_client.py`

### A. Add imports

```python
import re
import fnmatch
```

### B. Add constants (after `MAX_COMMAND_LENGTH` on line 37)

```python
MAX_SOURCE_SCRIPT_SIZE = 8192

_SOURCE_DOT_RE = re.compile(
    r"^\s*(?:source|\.)\s+"  # source or . followed by whitespace
    r"([^\s;|&]+)"           # capture the file path (no shell metacharacters)
)

_SENSITIVE_READ_PATHS = (
    "/etc/shadow",
    "/etc/gshadow",
    "/etc/sudoers",
    "/etc/ssl/private/",
    "/proc/",
)

_SENSITIVE_READ_GLOBS = (
    "**/.ssh/id_*",
    "**/.ssh/authorized_keys",
    "**/.pgpass",
    "**/.my.cnf",
    "**/.aws/credentials",
)
```

### C. Add function `_read_source_script`

```python
def _read_source_script(command: str) -> str | None:
    """Read script contents for source/dot commands.

    Detects `source file` or `. file` patterns, resolves the path,
    and returns the file contents so the LLM can inspect what will
    actually be executed.

    Sensitive files (shadow, SSH keys, etc.) are excluded to prevent
    arbitrary file read as a data exfiltration side-channel.

    Returns:
        Script contents string, or None if not a source command or unreadable.
    """
    match = _SOURCE_DOT_RE.match(command)
    if not match:
        return None

    script_path = match.group(1)
    script_path = os.path.expanduser(script_path)
    script_path = os.path.expandvars(script_path)

    # Resolve symlinks to prevent aliasing attacks
    real_path = os.path.realpath(script_path)

    # Block sensitive paths (prefix match)
    if any(real_path == p or real_path.startswith(p) for p in _SENSITIVE_READ_PATHS):
        return None

    # Block sensitive globs (fnmatch on resolved path)
    if any(fnmatch.fnmatch(real_path, g) for g in _SENSITIVE_READ_GLOBS):
        return None

    try:
        size = os.path.getsize(real_path)
        if size > MAX_SOURCE_SCRIPT_SIZE:
            return (
                f"[Script {script_path} is {size} bytes, "
                f"exceeding {MAX_SOURCE_SCRIPT_SIZE} byte limit — contents not shown]"
            )
        with open(real_path) as f:
            return f.read()
    except FileNotFoundError:
        return f"[Script {script_path} not found on disk]"
    except PermissionError:
        return f"[Script {script_path} not readable — permission denied]"
    except OSError as e:
        logger.debug("Failed to read source script %s: %s", script_path, e)
        return None
```

### D. Modify `_get_messages_for_model` (~line 462)

After the existing env-expansion block (lines 477-479), add:

```python
script_contents = _read_source_script(command)
if script_contents is not None:
    content += (
        "\n\nThis command sources the following script. "
        "Validate the script contents:\n"
        f"<SCRIPT_CONTENTS>\n{script_contents}\n</SCRIPT_CONTENTS>"
    )
```

## No other files change

The system prompt, decision tree, validator, shell loop, and tests are all untouched. The LLM already knows how to evaluate dangerous patterns — it just gets the script body as additional context.

## Security considerations

| Concern | Mitigation |
|---|---|
| Arbitrary file read as exfiltration side-channel (`source /etc/shadow`) | Denylist + `realpath()` to resolve symlinks before check |
| Script too large / DoS | `MAX_SOURCE_SCRIPT_SIZE` cap checked via `getsize()` before read |
| File not found / unreadable | Bracketed note returned; LLM can still judge the command string |
| Prompt injection in script contents | Existing `<SCRIPT_CONTENTS>` delimiter tags + system prompt instruction to treat content as opaque data |
| Sensitive env vars in `.env` files | Accepted risk — user chose to source the file; LLM needs to see contents to validate |
