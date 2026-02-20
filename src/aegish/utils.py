"""Utility functions for aegish.

Contains helper functions for:
- Script file detection and reading
- Environment variable expansion
- Path and file utilities
- Error message formatting
- Command tag escaping
"""

import fnmatch
import logging
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from aegish.constants import (
    COMMAND_PREFIXES,
    F_FLAG_INTERPRETERS,
    INPUT_REDIR_RE,
    INTERPRETER_ARG_FLAGS,
    MAX_SOURCE_SCRIPT_SIZE,
    PYTHON_VERSIONED_RE,
    SCRIPT_INTERPRETERS,
    SENSITIVE_READ_GLOBS,
    SENSITIVE_READ_PATHS,
    SENSITIVE_VAR_PATTERNS,
    SOURCE_DOT_RE,
)

logger = logging.getLogger(__name__)

# Resolve envsubst path once at module load for security (prevents PATH manipulation)
_envsubst_path: str | None = shutil.which("envsubst")
if _envsubst_path is None:
    logger.warning(
        "envsubst not found on PATH; environment variable expansion will be disabled"
    )


# =============================================================================
# Command tag escaping
# =============================================================================


def escape_command_tags(command: str) -> str:
    """Escape COMMAND XML tags in user input to prevent tag injection.

    Replaces literal <COMMAND> and </COMMAND> with backslash-escaped
    versions so an attacker cannot prematurely close the COMMAND block
    and inject instructions outside it.

    Args:
        command: Raw command string.

    Returns:
        Command with COMMAND tags escaped.
    """
    return command.replace("</COMMAND>", r"<\/COMMAND>").replace(
        "<COMMAND>", r"<\/COMMAND>"
    )


# =============================================================================
# Environment variable expansion
# =============================================================================


def get_safe_env() -> dict[str, str]:
    """Get environment dict for envsubst expansion.

    By default (AEGISH_FILTER_SENSITIVE_VARS=false): returns ALL environment
    variables for full expansion fidelity.

    When opt-in filtering is enabled (AEGISH_FILTER_SENSITIVE_VARS=true):
    removes variables matching sensitive patterns to prevent leaking
    API keys, secrets, and tokens into LLM prompts.
    """
    from aegish.config import get_filter_sensitive_vars

    if not get_filter_sensitive_vars():
        return dict(os.environ)

    logger.debug("Sensitive variable filtering enabled (opt-in)")
    return {
        key: value
        for key, value in os.environ.items()
        if not any(pat in key.upper() for pat in SENSITIVE_VAR_PATTERNS)
    }


def expand_env_vars(command: str) -> str | None:
    """Expand environment variables in a command using envsubst.

    Only expands $VAR and ${VAR} patterns. Does NOT execute command
    substitutions like $(...) or backticks.

    Uses the absolute path to envsubst resolved at module load time
    to prevent PATH manipulation attacks.

    When AEGISH_FILTER_SENSITIVE_VARS is enabled, sensitive variables
    (API keys, secrets, tokens) are filtered out before expansion.

    Returns:
        Expanded command string, or None if envsubst is unavailable.
    """
    if "$" not in command:
        return command

    if _envsubst_path is None:
        logger.debug("envsubst not available (not found at module load)")
        return None

    try:
        result = subprocess.run(
            [_envsubst_path],
            input=command,
            capture_output=True,
            text=True,
            timeout=5,
            env=get_safe_env(),
        )
        if result.returncode == 0:
            return result.stdout.rstrip("\n")
        logger.debug("envsubst returned non-zero exit code: %d", result.returncode)
        return None
    except FileNotFoundError:
        logger.debug("envsubst not available on this system")
        return None
    except subprocess.TimeoutExpired:
        logger.debug("envsubst timed out")
        return None
    except Exception as e:
        logger.debug("envsubst failed: %s", e)
        return None


# =============================================================================
# Path and file utilities
# =============================================================================


def strip_bash_quoting(s: str) -> str:
    """Strip common bash quoting from a string.

    Handles double quotes, single quotes, and backslash escapes.
    """
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (
        s.startswith("'") and s.endswith("'")
    ):
        s = s[1:-1]
    # Remove backslash escapes (e.g., file\ name -> file name)
    s = s.replace("\\ ", " ")
    return s


def is_sensitive_path(path: str) -> bool:
    """Check if a resolved path matches sensitive read patterns."""
    if path in SENSITIVE_READ_PATHS:
        return True
    return any(fnmatch.fnmatch(path, g) for g in SENSITIVE_READ_GLOBS)


def is_binary_file(path: str) -> bool:
    """Check if a file appears to be binary by looking for NUL bytes."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(512)
            return b"\x00" in chunk
    except OSError:
        return False


# =============================================================================
# Script detection and reading
# =============================================================================


def read_source_script(command: str) -> str | None:
    """Detect source/dot commands and read the script contents.

    Detects `source file` or `. file` patterns in the command,
    resolves the file path (expanding ~ and env vars, resolving symlinks),
    checks for sensitive paths, and reads the file contents up to
    MAX_SOURCE_SCRIPT_SIZE bytes.

    Args:
        command: The shell command string.

    Returns:
        Script contents string if a source/dot command is detected and
        the file can be read, or a descriptive note (e.g., "[file not found]",
        "[sensitive path blocked]"). Returns None if the command is not a
        source/dot command.
    """
    match = SOURCE_DOT_RE.search(command)
    if not match:
        return None

    raw_path = strip_bash_quoting(match.group(1).split()[0])

    # Expand ~ and environment variables in the path
    expanded = os.path.expanduser(os.path.expandvars(raw_path))

    try:
        resolved = str(Path(expanded).resolve(strict=False))
    except (OSError, ValueError):
        return f"[could not resolve path: {raw_path}]"

    # Block sensitive paths
    if is_sensitive_path(resolved):
        logger.warning(
            "Source script blocked: %s resolves to sensitive path %s",
            raw_path,
            resolved,
        )
        return f"[sensitive path blocked: {resolved}]"

    # Try to read the file
    try:
        file_size = os.path.getsize(resolved)
    except OSError:
        return f"[file not found: {raw_path}]"

    if file_size > MAX_SOURCE_SCRIPT_SIZE:
        return (
            f"[file too large: {file_size} bytes, "
            f"limit {MAX_SOURCE_SCRIPT_SIZE}]"
        )

    try:
        with open(resolved, "r", errors="replace") as f:
            return f.read(MAX_SOURCE_SCRIPT_SIZE)
    except OSError as e:
        return f"[could not read file: {e}]"


def is_known_interpreter(basename: str) -> bool:
    """Check if a basename is a known script interpreter.

    Handles exact matches from SCRIPT_INTERPRETERS, F_FLAG_INTERPRETERS,
    and versioned python binaries like python3.11.
    """
    if basename in SCRIPT_INTERPRETERS:
        return True
    if basename in F_FLAG_INTERPRETERS:
        return True
    if PYTHON_VERSIONED_RE.match(basename):
        return True
    return False


def extract_script_path(tokens: list[str], interpreter: str) -> str | None:
    """Extract the script file path from tokens after the interpreter.

    Skips flags and their arguments. Returns None when the command uses
    inline code (-c, -e, -m) rather than a file argument.

    Args:
        tokens: Remaining tokens after the interpreter.
        interpreter: Basename of the interpreter (e.g. "python3", "awk").

    Returns:
        The script file path, or None if no file argument is found.
    """
    interp_base = os.path.basename(interpreter)

    # Handle -f flag interpreters (awk, sed)
    if interp_base in F_FLAG_INTERPRETERS:
        for i, tok in enumerate(tokens):
            if tok == "-f" and i + 1 < len(tokens):
                return tokens[i + 1]
        return None

    # Walk tokens, skip flags
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        # If we hit a flag that means inline code, no file to read
        if tok in INTERPRETER_ARG_FLAGS:
            return None
        # Skip other flags (single-dash options)
        if tok.startswith("-"):
            # Flags like --verbose or -v: skip
            i += 1
            continue
        # First non-flag token is the script file
        return tok
    return None


def read_script_file(path_str: str) -> tuple[str, str]:
    """Read a script file for LLM analysis.

    Expands ~, resolves symlinks, checks sensitive paths and size limits.

    Args:
        path_str: Raw file path string (may include quotes).

    Returns:
        Tuple of (label, content) where label describes the file
        and content is the file text or a bracketed status note.
    """
    raw_path = strip_bash_quoting(path_str)
    expanded = os.path.expanduser(os.path.expandvars(raw_path))

    try:
        resolved = str(Path(expanded).resolve(strict=False))
    except (OSError, ValueError):
        return (raw_path, f"[could not resolve path: {raw_path}]")

    if is_sensitive_path(resolved):
        logger.warning(
            "Script file blocked: %s resolves to sensitive path %s",
            raw_path,
            resolved,
        )
        return (raw_path, f"[sensitive path blocked: {resolved}]")

    try:
        file_size = os.path.getsize(resolved)
    except OSError:
        return (raw_path, f"[file not found: {raw_path}]")

    if file_size > MAX_SOURCE_SCRIPT_SIZE:
        return (
            raw_path,
            f"[file too large: {file_size} bytes, limit {MAX_SOURCE_SCRIPT_SIZE}]",
        )

    if is_binary_file(resolved):
        return (raw_path, "[binary file \u2014 cannot analyze contents]")

    try:
        with open(resolved, "r", errors="replace") as f:
            return (raw_path, f.read(MAX_SOURCE_SCRIPT_SIZE))
    except OSError as e:
        return (raw_path, f"[could not read file: {e}]")


def detect_script_files(command: str) -> list[tuple[str, str]]:
    """Detect script files referenced by a command.

    Handles:
    - Interpreter + file: python3 script.py, ruby script.rb, etc.
    - Direct execution: ./script.sh, /tmp/script.sh
    - Input redirection: python3 < script.py, bash < script.sh
    - Command prefixes: env python3 script.py, nohup bash script.sh

    Does NOT handle source/dot commands (those use read_source_script).

    Args:
        command: The shell command string.

    Returns:
        List of (label, content) tuples for each detected script file.
    """
    results: list[tuple[str, str]] = []

    # --- Check for input redirection: interpreter < file ---
    redir_match = INPUT_REDIR_RE.search(command)
    if redir_match:
        redir_file = redir_match.group(1)
        # Strip the redirection part before tokenizing for interpreter detection
        command_no_redir = INPUT_REDIR_RE.sub("", command).strip()
        try:
            tokens = shlex.split(command_no_redir)
        except ValueError:
            tokens = command_no_redir.split()

        # Skip command prefixes
        idx = 0
        while idx < len(tokens) and os.path.basename(tokens[idx]) in COMMAND_PREFIXES:
            idx += 1

        if idx < len(tokens):
            basename = os.path.basename(tokens[idx])
            if is_known_interpreter(basename):
                results.append(read_script_file(redir_file))
                return results

    # --- Tokenize the command ---
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    if not tokens:
        return results

    # Skip command prefixes (env, nohup, nice, etc.)
    idx = 0
    while idx < len(tokens):
        basename = os.path.basename(tokens[idx])
        if basename in COMMAND_PREFIXES:
            idx += 1
            # Skip flag arguments for prefixes that take them
            # e.g. nice -n 10, timeout 30, ionice -c 2
            while idx < len(tokens) and tokens[idx].startswith("-"):
                idx += 1
                # Skip the flag's value if present
                if idx < len(tokens) and not tokens[idx].startswith("-"):
                    idx += 1
            continue
        break

    if idx >= len(tokens):
        return results

    first_token = tokens[idx]
    first_basename = os.path.basename(first_token)

    # --- Case 1: Known interpreter + script file ---
    if is_known_interpreter(first_basename):
        remaining = tokens[idx + 1:]
        script_path = extract_script_path(remaining, first_token)
        if script_path:
            results.append(read_script_file(script_path))
        return results

    # --- Case 2: Direct execution (./script, /path/to/script) ---
    if first_token.startswith("./") or first_token.startswith("/"):
        # Only read if it looks like a script (has extension or is executable text)
        results.append(read_script_file(first_token))
        return results

    return results


# =============================================================================
# Error formatting
# =============================================================================


def friendly_error(model: str, exc: Exception) -> str:
    """Extract a clean, one-line error message from a litellm exception.

    Detects common root causes and returns actionable guidance instead of
    raw tracebacks.

    Args:
        model: The model string that failed.
        exc: The exception raised by litellm.

    Returns:
        A concise, human-readable error string.
    """
    from aegish.config import get_provider_from_model

    msg = str(exc)
    exc_type = type(exc).__name__

    # Detect trailing \r in API keys (Windows line endings in .env files)
    if "\\r" in msg or "\r" in msg or "Illegal header value" in msg:
        provider = get_provider_from_model(model)
        env_var_hints = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }
        env_hint = env_var_hints.get(provider, "the API key")
        return (
            f"API key for '{provider}' has a trailing carriage return (\\r). "
            f"This usually means your .env file has Windows-style (CRLF) line endings. "
            f"Fix: run `sed -i 's/\\r$//' .env` or re-save with Unix (LF) line endings, "
            f"then re-export {env_hint}."
        )

    # Detect invalid URL with \r (same root cause, different symptom)
    if "Invalid non-printable ASCII character in URL" in msg:
        provider = get_provider_from_model(model)
        return (
            f"API key for '{provider}' contains non-printable characters (likely \\r from CRLF line endings). "
            f"Fix: run `sed -i 's/\\r$//' .env` and re-export the key."
        )

    # Detect connection errors
    if "Connection error" in msg or "ConnectionError" in msg:
        return f"Connection error \u2014 cannot reach {model}. Check network access and firewall rules."

    # Detect missing provider
    if "LLM Provider NOT provided" in msg:
        return (
            f"Unrecognized model format '{model}'. "
            f"litellm could not determine the provider. "
            f"Check the model string follows 'provider/model-name' format."
        )

    # Detect content filter / empty response
    if "content_filter" in msg:
        return f"Content filter activated for {model} \u2014 model refused to respond."

    # Generic: extract just the first meaningful line, drop tracebacks
    first_line = msg.split("\n")[0].strip()
    # Strip nested litellm prefixes like "litellm.InternalServerError: InternalServerError:"
    for prefix in ("litellm.InternalServerError: ", "litellm.BadRequestError: ",
                    "litellm.APIConnectionError: ", "litellm.AuthenticationError: "):
        if prefix in first_line:
            first_line = first_line.split(prefix, 1)[-1]
    return f"{exc_type}: {first_line}"
