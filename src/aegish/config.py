"""Configuration module.

Loads API keys and settings from environment variables.

Environment Variables
---------------------
OPENAI_API_KEY : str
    API key for OpenAI.
    Get one at: https://platform.openai.com/api-keys

ANTHROPIC_API_KEY : str
    API key for Anthropic.
    Get one at: https://console.anthropic.com/

AEGISH_PRIMARY_MODEL : str
    Primary LLM model for command validation (format: provider/model-name).
    Default: openai/gpt-4

AEGISH_FALLBACK_MODELS : str
    Comma-separated list of fallback models (format: provider/model,provider/model).
    Default: anthropic/claude-3-haiku-20240307
    Set to empty string for single-provider mode (no fallbacks).

AEGISH_ALLOWED_PROVIDERS : str
    Comma-separated list of allowed LLM providers (DD-10: provider allowlist).
    Default: openai, anthropic, groq, together_ai, ollama
    Models from providers not in this list are rejected at startup.

AEGISH_MODE : str
    Operational mode: "production" or "development" (DD-14).
    Default: development (normal shell behavior).
    Production: login shell + Landlock enforcement.

AEGISH_FAIL_MODE : str
    Behavior when validation fails: "safe" (block) or "open" (warn).
    Default: safe (block on validation failure, DD-05).
    Open: warn on validation failure (user can confirm to proceed).

At least one API key must be configured for aegish to operate.
Models are tried in order: primary model first, then fallbacks.
"""

import hashlib
import logging
import os
import stat
import sys

from aegish.constants import (
    CONFIG_FILE_PATH,
    DEFAULT_ALLOWED_PROVIDERS,
    DEFAULT_FAIL_MODE,
    DEFAULT_FALLBACK_MODELS,
    DEFAULT_FILTER_SENSITIVE_VARS,
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_MAX_QUERIES_PER_MINUTE,
    DEFAULT_MODE,
    DEFAULT_PRIMARY_MODEL,
    DEFAULT_ROLE,
    DEFAULT_SANDBOXER_PATH,
    DEFAULT_VAR_CMD_ACTION,
    LOCAL_PROVIDERS,
    PROVIDER_ENV_VARS,
    SECURITY_CRITICAL_KEYS,
    VALID_FAIL_MODES,
    VALID_MODES,
    VALID_ROLES,
    VALID_VAR_CMD_ACTIONS,
)

# Re-export all constants for backward compatibility (tests import them from here)
__all__ = [
    "CONFIG_FILE_PATH",
    "DEFAULT_ALLOWED_PROVIDERS",
    "DEFAULT_FAIL_MODE",
    "DEFAULT_FALLBACK_MODELS",
    "DEFAULT_FILTER_SENSITIVE_VARS",
    "DEFAULT_LLM_TIMEOUT",
    "DEFAULT_MAX_QUERIES_PER_MINUTE",
    "DEFAULT_MODE",
    "DEFAULT_PRIMARY_MODEL",
    "DEFAULT_ROLE",
    "DEFAULT_SANDBOXER_PATH",
    "DEFAULT_VAR_CMD_ACTION",
    "LOCAL_PROVIDERS",
    "PROVIDER_ENV_VARS",
    "SECURITY_CRITICAL_KEYS",
    "VALID_FAIL_MODES",
    "VALID_MODES",
    "VALID_ROLES",
    "VALID_VAR_CMD_ACTIONS",
]

logger = logging.getLogger(__name__)

# Module-level cache for config file contents (loaded once)
_config_file_cache: dict[str, str] | None = None
_config_file_loaded: bool = False


# =============================================================================
# 1. Most-used externally: model accessors
# =============================================================================


def get_primary_model() -> str:
    """Get the primary LLM model for command validation.

    In production: reads from config file (ignores env var).
    In development: reads from AEGISH_PRIMARY_MODEL env var.
    Falls back to default if not set or empty.

    Returns:
        The primary model string in provider/model-name format.
    """
    model = _get_security_config("AEGISH_PRIMARY_MODEL", "")
    if model and model.strip():
        return model.strip()
    return DEFAULT_PRIMARY_MODEL


def get_fallback_models() -> list[str]:
    """Get fallback models list.

    In production: reads from config file (ignores env var).
    In development: reads from AEGISH_FALLBACK_MODELS env var.
    If not set, returns default fallbacks.
    If set to empty string, returns empty list (single-provider mode).

    Returns:
        List of fallback model strings in provider/model-name format.
    """
    env_value = _get_security_config("AEGISH_FALLBACK_MODELS", "")

    if not env_value:
        # _get_security_config returns "" for both "not set" and "set to empty".
        # In dev mode, distinguish via raw env var: None = not set, "" = single-provider.
        if not _is_production_mode():
            raw = os.environ.get("AEGISH_FALLBACK_MODELS")
            if raw is not None:
                return []  # Explicitly set to empty = single-provider mode
        return DEFAULT_FALLBACK_MODELS.copy()

    # Set but whitespace-only - single provider mode
    if not env_value.strip():
        return []

    # Parse comma-separated list, trimming whitespace
    models = [m.strip() for m in env_value.split(",") if m.strip()]
    return models


def get_model_chain() -> list[str]:
    """Get the ordered list of models to try for validation.

    Returns primary model followed by fallback models, with duplicates removed.

    Returns:
        List of model strings in priority order.
    """
    primary = get_primary_model()
    fallbacks = get_fallback_models()

    # Start with primary, add fallbacks that aren't duplicates
    chain = [primary]
    for model in fallbacks:
        if model not in chain:
            chain.append(model)

    return chain


# =============================================================================
# 2. Settings: mode, fail_mode, role, var_cmd_action
# =============================================================================


def get_mode() -> str:
    """Get the operational mode for aegish.

    In production: reads from config file (ignores env var).
    In development: reads from AEGISH_MODE env var.
    Default: development (normal shell behavior).
    Production: login shell + Landlock enforcement.

    If AEGISH_MODE is explicitly set to an invalid value, prints an
    error and calls sys.exit(1). Unset or empty values default to
    development mode silently.

    Returns:
        Mode string: "production" or "development".
    """
    return _get_validated_setting(
        "AEGISH_MODE", VALID_MODES, DEFAULT_MODE, on_invalid="fatal",
    )


def get_fail_mode() -> str:
    """Get the fail mode for validation failures.

    In production: reads from config file (ignores env var).
    In development: reads from AEGISH_FAIL_MODE env var.
    Default: safe (block on validation failure).
    Open: warn on validation failure (user can confirm to proceed).

    Returns:
        Fail mode string: "safe" or "open".
    """
    return _get_validated_setting(
        "AEGISH_FAIL_MODE", VALID_FAIL_MODES, DEFAULT_FAIL_MODE, on_invalid="debug",
    )


def get_role() -> str:
    """Get the trust level role for the current session.

    In production: reads from config file (ignores env var).
    In development: reads from AEGISH_ROLE env var.
    Default: default (standard validation rules).

    Valid roles: default, sysadmin, restricted.
    Invalid roles fall back to default with a warning.

    Returns:
        Role string: "default", "sysadmin", or "restricted".
    """
    return _get_validated_setting(
        "AEGISH_ROLE", VALID_ROLES, DEFAULT_ROLE, on_invalid="warning",
    )


def get_var_cmd_action() -> str:
    """Get the action for variable-in-command-position detection.

    In production: reads from config file (ignores env var).
    In development: reads from AEGISH_VAR_CMD_ACTION env var.
    Default: block (block commands with variable expansion in command position).
    Warn: warn instead of blocking.

    Returns:
        Action string: "block" or "warn".
    """
    return _get_validated_setting(
        "AEGISH_VAR_CMD_ACTION", VALID_VAR_CMD_ACTIONS, DEFAULT_VAR_CMD_ACTION,
        on_invalid="debug",
    )


# =============================================================================
# 3. Credentials: get_api_key, validate_credentials, get_available_providers
# =============================================================================


def get_api_key(provider: str) -> str | None:
    """Get the API key for a provider from environment.

    Args:
        provider: Provider name (e.g., "openai", "anthropic", "gemini",
                  "featherless_ai", "huggingface", "ollama").

    Returns:
        The API key string, "local" for local providers, or None if not set.
    """
    # Local providers don't require API keys
    if provider.lower() in LOCAL_PROVIDERS:
        return "local"

    lookup = PROVIDER_ENV_VARS.get(provider.lower())
    if lookup is None:
        return None
    # Support multiple env var names (try in order)
    names = (lookup,) if isinstance(lookup, str) else lookup
    for env_var in names:
        key = os.environ.get(env_var)
        if key and key.strip():
            return key.strip()
    return None


def validate_credentials() -> tuple[bool, str]:
    """Validate that at least one LLM provider credential is configured.

    Returns:
        Tuple of (is_valid, message).
        If valid: (True, "credentials configured message")
        If invalid: (False, "error message with instructions")
    """
    available = get_available_providers()

    if not available:
        return (False, """No LLM API credentials configured.

aegish requires at least one API key to validate commands.

Set one or more of these environment variables:
  export OPENAI_API_KEY="your-key-here"        # https://platform.openai.com/api-keys
  export ANTHROPIC_API_KEY="your-key-here"     # https://console.anthropic.com/

Tip: Copy .env.example to .env and fill in your keys, then source it:
  cp .env.example .env && export $(grep -v '^#' .env | xargs)""")

    return (True, f"Using providers: {', '.join(available)}")


def get_available_providers() -> list[str]:
    """Get list of providers with configured API keys.

    Returns:
        List of provider names that have API keys set.
    """
    providers = ["openai", "anthropic"]
    return [p for p in providers if get_api_key(p)]


# =============================================================================
# 4. Timeouts and limits
# =============================================================================


def get_llm_timeout() -> int:
    """Get the LLM query timeout in seconds.

    Reads from AEGISH_LLM_TIMEOUT environment variable.
    Default: 30 seconds.

    Returns:
        Timeout in integer seconds.
    """
    raw = os.environ.get("AEGISH_LLM_TIMEOUT", "")
    if raw and raw.strip():
        try:
            value = int(raw.strip())
            if value > 0:
                return value
            logger.debug(
                "Invalid AEGISH_LLM_TIMEOUT '%s' (must be positive), "
                "falling back to %d",
                raw,
                DEFAULT_LLM_TIMEOUT,
            )
        except ValueError:
            logger.debug(
                "Invalid AEGISH_LLM_TIMEOUT '%s' (not an integer), "
                "falling back to %d",
                raw,
                DEFAULT_LLM_TIMEOUT,
            )
    return DEFAULT_LLM_TIMEOUT


def get_max_queries_per_minute() -> int:
    """Get the max LLM queries per minute rate limit.

    Reads from AEGISH_MAX_QUERIES_PER_MINUTE environment variable.
    Default: 30 queries per minute.

    Returns:
        Max queries per minute as integer.
    """
    raw = os.environ.get("AEGISH_MAX_QUERIES_PER_MINUTE", "")
    if raw and raw.strip():
        try:
            value = int(raw.strip())
            if value > 0:
                return value
        except ValueError:
            pass
    return DEFAULT_MAX_QUERIES_PER_MINUTE


def get_filter_sensitive_vars() -> bool:
    """Get whether sensitive variable filtering is enabled for env expansion.

    Reads from AEGISH_FILTER_SENSITIVE_VARS environment variable.
    Default: false (full expansion, no filtering).
    When enabled: pattern-based filtering removes API keys, secrets, tokens.

    Returns:
        True if filtering should be applied, False otherwise.
    """
    raw = os.environ.get("AEGISH_FILTER_SENSITIVE_VARS", "")
    if raw and raw.strip():
        return raw.strip().lower() in ("true", "1", "yes")
    return DEFAULT_FILTER_SENSITIVE_VARS


# =============================================================================
# 5. Model validation
# =============================================================================


def get_provider_from_model(model: str) -> str:
    """Extract the provider name from a model string.

    Model strings follow LiteLLM format: provider/model-name
    For example: "openai/gpt-4" -> "openai"

    Args:
        model: The model string (e.g., "openai/gpt-4").

    Returns:
        The provider name (first segment before '/').
        Returns the full string if no '/' is present (invalid format).
    """
    if "/" not in model:
        return model  # Invalid format, return as-is for error handling
    return model.split("/")[0]


def is_valid_model_string(model: str) -> bool:
    """Check if a model string follows the expected format.

    Valid format: provider/model-name (must contain at least one '/').

    Args:
        model: The model string to validate.

    Returns:
        True if the format is valid, False otherwise.
    """
    if "/" not in model:
        return False
    parts = model.split("/", 1)
    return len(parts[0]) > 0 and len(parts[1]) > 0


def validate_model_provider(
    model: str, allowed: set[str] | None = None
) -> tuple[bool, str]:
    """Validate that a model's provider is in the allowed providers list.

    Args:
        model: The model string (e.g., "openai/gpt-4").
        allowed: Pre-resolved allowed providers set. If None, resolves from
                 environment. Pass this when calling in a loop to avoid
                 repeated environment lookups.

    Returns:
        Tuple of (is_valid, error_message).
        If valid: (True, "")
        If invalid: (False, "error message with provider and allowed list")
    """
    provider = get_provider_from_model(model).lower()
    if allowed is None:
        allowed = get_allowed_providers()

    if provider in allowed:
        return (True, "")

    allowed_str = ", ".join(sorted(allowed))
    return (False, f"Provider '{provider}' is not in the allowed providers list. "
            f"Allowed: {allowed_str}")


def get_allowed_providers() -> set[str]:
    """Get the set of allowed LLM providers.

    In production: reads from config file (ignores env var).
    In development: reads from AEGISH_ALLOWED_PROVIDERS env var.
    If not set or empty, returns the default allowlist.

    Returns:
        Set of allowed provider name strings (lowercase).
    """
    raw_value = _get_security_config("AEGISH_ALLOWED_PROVIDERS", "")

    # Not set or empty/whitespace - use defaults
    if not raw_value or not raw_value.strip():
        return DEFAULT_ALLOWED_PROVIDERS.copy()

    # Parse comma-separated list, trimming whitespace, lowercase
    providers = {p.strip().lower() for p in raw_value.split(",") if p.strip()}
    return providers if providers else DEFAULT_ALLOWED_PROVIDERS.copy()


# =============================================================================
# 6. Convenience: default/fallback checks
# =============================================================================


def is_default_primary_model() -> bool:
    """Check if the primary model is the default."""
    return get_primary_model() == DEFAULT_PRIMARY_MODEL


def is_default_fallback_models() -> bool:
    """Check if fallback models match the defaults."""
    return get_fallback_models() == DEFAULT_FALLBACK_MODELS


def has_fallback_models() -> bool:
    """Check if any fallback models are configured."""
    return len(get_fallback_models()) > 0


# =============================================================================
# 7. Config file handling (internal)
# =============================================================================


def _get_validated_setting(
    key: str,
    valid_values: set[str],
    default: str,
    *,
    on_invalid: str = "debug",  # "debug", "warning", or "fatal"
) -> str:
    """Get a config setting, validate it against allowed values, and fall back.

    Encapsulates the common pattern used by get_mode(), get_fail_mode(),
    get_role(), and get_var_cmd_action():
      1. Read raw value from _get_security_config(key, "")
      2. Strip and lowercase
      3. If value is in valid_values -> return it
      4. If value is non-empty but invalid -> handle per on_invalid
      5. If empty -> return default

    Args:
        key: The configuration key (e.g., "AEGISH_MODE").
        valid_values: Set of acceptable lowercase values.
        default: Default value when unset or empty.
        on_invalid: What to do when a non-empty invalid value is found:
            - "debug": logger.debug(...)
            - "warning": logger.warning(...)
            - "fatal": print(stderr) + sys.exit(1)

    Returns:
        The validated setting string.
    """
    raw = _get_security_config(key, "")
    value = raw.strip().lower()
    if value in valid_values:
        return value
    if value:
        if on_invalid == "fatal":
            print(
                f"aegish: fatal: invalid {key} '{raw}'. "
                f"Valid modes: {', '.join(sorted(valid_values))}",
                file=sys.stderr,
            )
            sys.exit(1)
        elif on_invalid == "warning":
            logger.warning(
                "Invalid %s '%s', falling back to '%s'",
                key, raw, default,
            )
        else:  # "debug"
            logger.debug(
                "Invalid %s '%s', falling back to '%s'",
                key, raw, default,
            )
    return default


def _get_security_config(key: str, default: str = "") -> str:
    """Get a security-critical configuration value.

    In production mode: reads from config file only, ignores env vars.
    In development mode: reads from env vars (existing behavior).

    AEGISH_MODE is special: it's the bootstrap setting that determines
    whether we're in production mode. The config file can override it,
    but env var is always consulted as fallback for mode detection.

    Args:
        key: The configuration key (e.g., "AEGISH_FAIL_MODE").
        default: Default value if not found in any source.

    Returns:
        The configuration value string.
    """
    if _is_production_mode() and key in SECURITY_CRITICAL_KEYS:
        config = _load_config_file()
        value = config.get(key)
        if value is not None:
            return value

        # AEGISH_MODE is the bootstrap key: fall through to env var
        # so that AEGISH_MODE=production works without a config file
        if key == "AEGISH_MODE":
            return os.environ.get(key, default)

        # Other security keys: use secure default with warning
        logger.warning(
            "Security setting %s not found in config file; "
            "using secure default '%s'",
            key, default,
        )
        return default

    # Development mode: use env var
    return os.environ.get(key, default)


def _is_production_mode() -> bool:
    """Check if running in production mode without full get_mode() logic.

    Reads AEGISH_MODE directly from the config file first (if present),
    then falls back to env var. This avoids circular dependency with
    get_mode() which itself uses _get_security_config().

    Returns:
        True if mode is "production".
    """
    # Check config file first
    config = _load_config_file()
    mode_from_file = config.get("AEGISH_MODE", "").strip().lower()
    if mode_from_file in VALID_MODES:
        return mode_from_file == "production"

    # Fall back to env var
    mode_from_env = os.environ.get("AEGISH_MODE", "").strip().lower()
    return mode_from_env == "production"


def _load_config_file(path: str | None = None) -> dict[str, str]:
    """Load configuration from the config file.

    Parses a simple KEY=VALUE format file with # comments.
    Values can optionally be quoted (single or double quotes are stripped).

    Args:
        path: Path to config file. Defaults to CONFIG_FILE_PATH.

    Returns:
        Dictionary of key-value pairs from the config file.
        Empty dict if file doesn't exist or can't be read.
    """
    global _config_file_cache, _config_file_loaded

    if path is None:
        path = CONFIG_FILE_PATH

    # Use cache for default path
    if path == CONFIG_FILE_PATH and _config_file_loaded:
        return _config_file_cache if _config_file_cache is not None else {}

    config: dict[str, str] = {}

    if not os.path.exists(path):
        if path == CONFIG_FILE_PATH:
            _config_file_cache = config
            _config_file_loaded = True
        return config

    # Validate permissions in production
    is_valid, err = _validate_config_file_permissions(path)
    if not is_valid:
        logger.warning("Config file permission check failed: %s", err)
        if path == CONFIG_FILE_PATH:
            _config_file_cache = config
            _config_file_loaded = True
        return config

    try:
        with open(path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    logger.debug("Skipping malformed line %d in %s", line_num, path)
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Strip surrounding quotes
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                config[key] = value
    except OSError as e:
        logger.warning("Failed to read config file %s: %s", path, e)

    if path == CONFIG_FILE_PATH:
        _config_file_cache = config
        _config_file_loaded = True

    return config


def _validate_config_file_permissions(path: str) -> tuple[bool, str]:
    """Validate that the config file has secure ownership and permissions.

    The config file must be:
    - Owned by root (uid 0)
    - Not world-writable

    Args:
        path: Path to the config file.

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    try:
        file_stat = os.stat(path)
    except OSError as e:
        return (False, f"Cannot stat config file {path}: {e}")

    # Check root ownership
    if file_stat.st_uid != 0:
        return (False, f"Config file {path} is not owned by root "
                f"(owned by uid {file_stat.st_uid}). "
                f"Fix with: sudo chown root:root {path}")

    # Check not world-writable
    if file_stat.st_mode & stat.S_IWOTH:
        return (False, f"Config file {path} is world-writable. "
                f"Fix with: sudo chmod o-w {path}")

    return (True, "")


def _reset_config_cache() -> None:
    """Reset the config file cache. For testing only."""
    global _config_file_cache, _config_file_loaded
    _config_file_cache = None
    _config_file_loaded = False


# =============================================================================
# 8. Production validation: bash, sandboxer, hashing
# =============================================================================


def validate_bash_binary() -> tuple[bool, str]:
    """Validate /bin/bash exists, is executable, and has correct hash.

    In production mode: verifies SHA-256 hash integrity against
    AEGISH_BASH_HASH from config file. Refuses to start on mismatch
    or missing hash. On bare-metal, system bash updates break the hash
    and force acknowledgment (fail-loud, not silently stale).

    Returns:
        Tuple of (is_valid, message).
        If valid: (True, "bash binary verified message")
        If invalid: (False, "error message with remediation steps")
    """
    path = "/bin/bash"

    if not os.path.exists(path):
        return (False, "/bin/bash not found. This system has no bash.")

    if not os.access(path, os.X_OK):
        return (False, f"/bin/bash is not executable.\n"
                f"Fix with: sudo chmod +x {path}")

    # SHA-256 hash verification in production mode (Story 17.2)
    if _is_production_mode():
        expected_hash = _get_security_config("AEGISH_BASH_HASH", "")
        if not expected_hash:
            return (False,
                    "No bash hash configured in /etc/aegish/config. "
                    "Rebuild the container to embed AEGISH_BASH_HASH.")
        try:
            actual_hash = _compute_file_sha256(path)
            if actual_hash != expected_hash:
                return (False,
                        f"/bin/bash hash mismatch.\n"
                        f"  Expected: {expected_hash}\n"
                        f"  Actual:   {actual_hash}\n"
                        f"Step 1 — Verify the binary is a legitimate "
                        f"package update:\n"
                        f"  dpkg --verify bash        "
                        f"# Debian/Ubuntu — no output means OK\n"
                        f"  rpm -V bash               "
                        f"# RHEL/CentOS  — no output means OK\n"
                        f"Step 2 — Only after verification, update the "
                        f"stored hash:\n"
                        f"  sudo sed -i "
                        f"'s/^AEGISH_BASH_HASH=.*/"
                        f"AEGISH_BASH_HASH={actual_hash}/' "
                        f"/etc/aegish/config")
        except OSError as e:
            return (False, f"Cannot read /bin/bash for hash verification: {e}")

    return (True, "bash binary verified at /bin/bash")


def validate_sandboxer_library() -> tuple[bool, str]:
    """Validate that the sandboxer shared library exists and is readable.

    In production mode: also verifies SHA-256 hash integrity.
    Expected hash is read from config file via _get_security_config()
    (never from env vars in production -- prevents env var poisoning).
    Refuses to start on hash mismatch or missing hash in production.

    Returns:
        Tuple of (is_valid, message).
        If valid: (True, "sandboxer library ready message")
        If invalid: (False, "error message with build instructions")
    """
    path = get_sandboxer_path()

    if not os.path.exists(path):
        return (False, f"Sandboxer library not found at {path}.\n"
                f"Build it with: cd src/sandboxer && make && sudo make install")

    if not os.access(path, os.R_OK):
        return (False, f"Sandboxer library at {path} is not readable.\n"
                f"Fix with: sudo chmod +r {path}")

    # SHA-256 hash verification in production mode (Story 17.8)
    if _is_production_mode():
        expected_hash = _get_security_config("AEGISH_SANDBOXER_HASH", "")
        if not expected_hash:
            return (False,
                    "No sandboxer hash configured in /etc/aegish/config. "
                    "Rebuild the container to embed AEGISH_SANDBOXER_HASH.")
        try:
            actual_hash = _compute_file_sha256(path)
            if actual_hash != expected_hash:
                return (False,
                        f"Sandboxer library hash mismatch at {path}.\n"
                        f"  Expected: {expected_hash}\n"
                        f"  Actual:   {actual_hash}\n"
                        f"Step 1 — Verify the library is legitimate "
                        f"(rebuild from source and compare hashes).\n"
                        f"Step 2 — Only after verification, update the "
                        f"stored hash:\n"
                        f"  sudo sed -i "
                        f"'s/^AEGISH_SANDBOXER_HASH=.*/"
                        f"AEGISH_SANDBOXER_HASH={actual_hash}/' "
                        f"/etc/aegish/config")
        except OSError as e:
            return (False, f"Cannot read sandboxer library for hash verification: {e}")

    return (True, f"Sandboxer library ready at {path}")


def skip_bash_hash() -> bool:
    """Check if /bin/bash hash verification should be skipped.

    When AEGISH_SKIP_BASH_HASH=true in /etc/aegish/config, the bash
    hash check is bypassed. Intended for bare-metal deployments with
    automated package updates and host-level integrity monitoring.

    Read from config file in production (never from env vars).
    The sandboxer .so hash check is NOT affected by this setting.

    Returns:
        True if bash hash check should be skipped.
    """
    raw = _get_security_config("AEGISH_SKIP_BASH_HASH", "")
    return raw.strip().lower() == "true"


def get_sandboxer_path() -> str:
    """Get the path to the sandboxer shared library.

    In production: hardcoded to DEFAULT_SANDBOXER_PATH, ignores all config.
    In development: reads from AEGISH_SANDBOXER_PATH env var.
    Falls back to DEFAULT_SANDBOXER_PATH if not set or empty.

    Returns:
        Path to the sandboxer library.
    """
    if _is_production_mode():
        return DEFAULT_SANDBOXER_PATH

    raw = _get_security_config("AEGISH_SANDBOXER_PATH", "")
    if raw and raw.strip():
        return raw.strip()
    return DEFAULT_SANDBOXER_PATH


def _compute_file_sha256(path: str) -> str:
    """Compute the SHA-256 hash of a file.

    Args:
        path: Path to the file.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
