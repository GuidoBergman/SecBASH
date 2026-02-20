"""Landlock sandbox support for denying shell execution by child processes.

This module provides:
- DENIED_SHELLS: Reference set of denied shell paths (authoritative copy
  is in the C sandboxer library, src/sandboxer/landlock_sandboxer.c).
- landlock_available(): Probes kernel for Landlock support (for startup
  validation and status display).
- make_no_new_privs_fn(): Creates a preexec_fn that sets PR_SET_NO_NEW_PRIVS
  before exec. Required by landlock_restrict_self() in the LD_PRELOAD library.

Architecture (Story 14.2):
    Landlock enforcement has moved from Python (preexec_fn) to a C shared
    library loaded via LD_PRELOAD. The library's constructor runs inside the
    bash process before main(), applying Landlock restrictions that
    deny all shell binaries listed in DENIED_SHELLS.

    preexec_fn now only sets NO_NEW_PRIVS. The LD_PRELOAD sandboxer library
    handles all Landlock ruleset creation and activation.
"""

import ctypes
import ctypes.util
import logging

from aegish.constants import (
    DENIED_SHELLS,
    LANDLOCK_ACCESS_FS_EXECUTE,
    LANDLOCK_CREATE_RULESET_VERSION,
    LANDLOCK_RULE_PATH_BENEATH,
    PR_SET_NO_NEW_PRIVS,
    SYS_LANDLOCK_ADD_RULE,
    SYS_LANDLOCK_CREATE_RULESET,
    SYS_LANDLOCK_RESTRICT_SELF,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Backward-compatible aliases (original names used lowercase)
# =============================================================================

SYS_landlock_create_ruleset = SYS_LANDLOCK_CREATE_RULESET
SYS_landlock_add_rule = SYS_LANDLOCK_ADD_RULE
SYS_landlock_restrict_self = SYS_LANDLOCK_RESTRICT_SELF

# =============================================================================
# ctypes struct definitions (kept for landlock_available() probe)
# =============================================================================


class LandlockRulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class LandlockPathBeneathAttr(ctypes.Structure):
    _pack_ = 1  # Kernel struct is packed
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
    ]


# =============================================================================
# Internal helpers
# =============================================================================

_libc = None


def _get_libc():
    """Load and cache libc for syscall access."""
    global _libc
    if _libc is None:
        libc_name = ctypes.util.find_library("c")
        if libc_name is None:
            libc_name = "libc.so.6"
        _libc = ctypes.CDLL(libc_name, use_errno=True)
        _libc.syscall.restype = ctypes.c_long
    return _libc


# =============================================================================
# landlock_available() -- kernel support probe
# =============================================================================

_landlock_cache = None


def landlock_available() -> tuple[bool, int]:
    """Check whether the running kernel supports Landlock.

    Uses SYS_landlock_create_ruleset with LANDLOCK_CREATE_RULESET_VERSION
    flag to probe for ABI version support. The result is cached to avoid
    repeated syscalls.

    Returns:
        Tuple of (is_available, abi_version). If unavailable, returns (False, 0).
    """
    global _landlock_cache

    if _landlock_cache is not None:
        return _landlock_cache

    libc = _get_libc()
    # Probe: create_ruleset(NULL, 0, LANDLOCK_CREATE_RULESET_VERSION)
    # Returns ABI version (>= 1) on success, -1 on failure
    abi_version = libc.syscall(
        SYS_landlock_create_ruleset,
        None,
        0,
        LANDLOCK_CREATE_RULESET_VERSION,
    )

    if abi_version >= 0:
        # Note: with LANDLOCK_CREATE_RULESET_VERSION flag, the return value
        # is the ABI version number (integer), NOT a file descriptor.
        _landlock_cache = (True, abi_version)
    else:
        _landlock_cache = (False, 0)

    return _landlock_cache


# =============================================================================
# make_no_new_privs_fn() -- preexec_fn for NO_NEW_PRIVS only
# =============================================================================


def make_no_new_privs_fn():
    """Create a preexec_fn that sets NO_NEW_PRIVS only.

    Landlock enforcement is handled by the LD_PRELOAD sandboxer library
    (src/sandboxer/landlock_sandboxer.c), which runs inside the exec'd
    process. preexec_fn only needs to ensure NO_NEW_PRIVS is set, which
    is required by landlock_restrict_self() in the sandboxer constructor.

    The libc reference is resolved before fork -- dlopen is
    async-signal-unsafe and must not be called between fork() and exec().

    Returns:
        A callable with signature () -> None, suitable for subprocess preexec_fn.
    """
    libc = _get_libc()

    def _preexec() -> None:
        ret = libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
        if ret != 0:
            raise OSError("prctl(PR_SET_NO_NEW_PRIVS) failed")

    return _preexec
