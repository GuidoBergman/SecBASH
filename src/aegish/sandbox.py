"""Landlock sandbox for denying shell execution by child processes.

This module implements a Landlock-based allowlist sandbox that prevents
child processes from spawning shells (bash, sh, dash, zsh, etc.) while
allowing execution of all other binaries.

Landlock is a default-deny access control system: once activated, only
binaries with explicit EXECUTE rules can be run via execve(). Shell
binaries are excluded from the ruleset, so any attempt to exec a shell
returns EPERM.

IMPORTANT for integration (Story 8.5):
    The ruleset_fd returned by create_sandbox_ruleset() must be passed
    to subprocess.run() via pass_fds=(ruleset_fd,) so the fd survives
    CPython's close_fds=True default. Without pass_fds, the fd is closed
    before preexec_fn runs and landlock_restrict_self() will fail with EBADF.

    Example:
        fd = get_sandbox_ruleset()
        if fd is not None:
            subprocess.run(
                [...],
                preexec_fn=make_preexec_fn(fd),
                pass_fds=(fd,),
            )
"""

import ctypes
import ctypes.util
import logging
import os
import stat

logger = logging.getLogger(__name__)

# =============================================================================
# Task 1: Constants and struct definitions
# =============================================================================

# Subtask 1.1: Syscall numbers (x86_64)
SYS_landlock_create_ruleset = 444
SYS_landlock_add_rule = 445
SYS_landlock_restrict_self = 446

# Subtask 1.2: ctypes struct definitions


class LandlockRulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class LandlockPathBeneathAttr(ctypes.Structure):
    _pack_ = 1  # Kernel struct is packed
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
    ]


# Subtask 1.3: Access flags
LANDLOCK_ACCESS_FS_EXECUTE = 1 << 0
LANDLOCK_RULE_PATH_BENEATH = 1
LANDLOCK_CREATE_RULESET_VERSION = 1 << 0
PR_SET_NO_NEW_PRIVS = 38

# Subtask 1.4: Denied shell binary paths
DENIED_SHELLS = {
    "/bin/bash", "/usr/bin/bash",
    "/bin/sh", "/usr/bin/sh",
    "/bin/dash", "/usr/bin/dash",
    "/bin/zsh", "/usr/bin/zsh",
    "/bin/fish", "/usr/bin/fish",
    "/bin/ksh", "/usr/bin/ksh",
    "/bin/csh", "/usr/bin/csh",
    "/bin/tcsh", "/usr/bin/tcsh",
}

# Subtask 1.5: Default runner path
DEFAULT_RUNNER_PATH = "/opt/aegish/bin/runner"

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
    return _libc


# =============================================================================
# Task 2: landlock_available() function
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
# Task 3: create_sandbox_ruleset() function
# =============================================================================


def _add_path_rule(libc, ruleset_fd: int, path: str) -> None:
    """Add an EXECUTE rule for a single file path.

    Opens the path with O_PATH | O_CLOEXEC, creates a LandlockPathBeneathAttr,
    and calls SYS_landlock_add_rule. Closes the fd after the syscall.

    Args:
        libc: Loaded libc CDLL instance.
        ruleset_fd: The Landlock ruleset file descriptor.
        path: Absolute path to the executable to allow.
    """
    try:
        fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
    except (FileNotFoundError, PermissionError, OSError) as e:
        logger.debug("Cannot open %s for Landlock rule: %s", path, e)
        return

    try:
        attr = LandlockPathBeneathAttr()
        attr.allowed_access = LANDLOCK_ACCESS_FS_EXECUTE
        attr.parent_fd = fd

        ret = libc.syscall(
            SYS_landlock_add_rule,
            ruleset_fd,
            LANDLOCK_RULE_PATH_BENEATH,
            ctypes.byref(attr),
            0,
        )
        if ret < 0:
            logger.debug("landlock_add_rule failed for %s", path)
    finally:
        os.close(fd)


def create_sandbox_ruleset() -> int:
    """Create a Landlock ruleset that allows execution of non-shell binaries.

    Enumerates executables from PATH and the runner directory, adding EXECUTE
    rules for each binary that is NOT in DENIED_SHELLS. Shell binaries are
    excluded, so they will be denied when the ruleset is activated.

    IMPORTANT: The returned fd must be passed to subprocess.run() via
    pass_fds=(ruleset_fd,) so the child process can use it in preexec_fn.

    Returns:
        Ruleset file descriptor. Caller is responsible for closing it.

    Raises:
        OSError: If the create_ruleset syscall fails.
    """
    libc = _get_libc()

    # Subtask 3.1: Create ruleset handling EXECUTE access
    attr = LandlockRulesetAttr()
    attr.handled_access_fs = LANDLOCK_ACCESS_FS_EXECUTE

    ruleset_fd = libc.syscall(
        SYS_landlock_create_ruleset,
        ctypes.byref(attr),
        ctypes.sizeof(attr),
        0,
    )
    if ruleset_fd < 0:
        raise OSError("landlock_create_ruleset failed")

    try:
        # Subtask 3.2: Enumerate directories from PATH
        path_env = os.environ.get("PATH", "")
        dirs = []
        seen_dirs = set()
        for d in path_env.split(":"):
            if not d:
                continue
            resolved = os.path.realpath(d)
            if resolved not in seen_dirs and os.path.isdir(resolved):
                seen_dirs.add(resolved)
                dirs.append(resolved)

        # Subtask 3.3: Add runner directory
        runner_dir = os.path.dirname(DEFAULT_RUNNER_PATH)
        runner_dir_resolved = os.path.realpath(runner_dir)
        if runner_dir_resolved not in seen_dirs and os.path.isdir(runner_dir_resolved):
            seen_dirs.add(runner_dir_resolved)
            dirs.append(runner_dir_resolved)

        # Build resolved DENIED_SHELLS set for comparison
        resolved_denied = {os.path.realpath(s) for s in DENIED_SHELLS if os.path.exists(s)}
        # Also keep the original paths for comparison on systems where shells don't exist
        all_denied = resolved_denied | DENIED_SHELLS

        # Subtask 3.4-3.7: Enumerate and add rules for non-shell executables
        for directory in dirs:
            try:
                entries = os.scandir(directory)
            except PermissionError:
                logger.debug("Permission denied scanning %s", directory)
                continue
            except OSError as e:
                logger.debug("Error scanning %s: %s", directory, e)
                continue

            with entries:
                for entry in entries:
                    try:
                        if not entry.is_file(follow_symlinks=True):
                            continue
                        st = entry.stat(follow_symlinks=True)
                        if not (st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)):
                            continue
                    except (OSError, PermissionError):
                        continue

                    resolved_path = os.path.realpath(entry.path)
                    if resolved_path in all_denied or entry.path in all_denied:
                        logger.debug("Skipping denied shell: %s", entry.path)
                        continue

                    _add_path_rule(libc, ruleset_fd, entry.path)
    except Exception:
        os.close(ruleset_fd)
        raise

    return ruleset_fd


# =============================================================================
# Task 4: make_preexec_fn() factory
# =============================================================================


def make_preexec_fn(ruleset_fd: int):
    """Create a preexec_fn closure that activates Landlock in the child process.

    The returned function:
    1. Calls prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) to prevent privilege escalation
    2. Calls landlock_restrict_self(ruleset_fd, 0) to activate the sandbox

    Once activated, the restriction is inherited by all child processes and
    is irrevocable.

    Args:
        ruleset_fd: Landlock ruleset fd (must be kept open via pass_fds).

    Returns:
        A callable with signature () -> None, suitable for subprocess preexec_fn.
    """
    # Resolve libc before fork — dlopen is async-signal-unsafe and must
    # not be called between fork() and exec() in the child process.
    libc = _get_libc()

    def _preexec() -> None:
        # Subtask 4.1: Set no-new-privs
        ret = libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
        if ret != 0:
            raise OSError("prctl(PR_SET_NO_NEW_PRIVS) failed")

        # Subtask 4.2: Activate Landlock restriction
        ret = libc.syscall(SYS_landlock_restrict_self, ruleset_fd, 0)
        if ret != 0:
            raise OSError("landlock_restrict_self failed")

    return _preexec


# =============================================================================
# Task 5: Module-level get_sandbox_ruleset() with lazy initialization
# =============================================================================

_cached_ruleset_fd = None
_ruleset_initialized = False


def get_sandbox_ruleset() -> int | None:
    """Get or create the cached Landlock sandbox ruleset.

    On first call, checks Landlock availability and creates the ruleset.
    On subsequent calls, returns the cached fd.

    Returns:
        Ruleset fd if Landlock is available, None otherwise.
    """
    global _cached_ruleset_fd, _ruleset_initialized

    if _ruleset_initialized:
        return _cached_ruleset_fd

    available, _version = landlock_available()
    if not available:
        _ruleset_initialized = True
        _cached_ruleset_fd = None
        return None

    _cached_ruleset_fd = create_sandbox_ruleset()
    _ruleset_initialized = True
    return _cached_ruleset_fd


def get_sandbox_preexec():
    """Get a preexec_fn for sandboxing, or None if Landlock is unavailable.

    Convenience function that combines get_sandbox_ruleset() and
    make_preexec_fn(). Returns None when Landlock is not supported,
    enabling graceful fallback.

    Returns:
        A callable () -> None for use as preexec_fn, or None.
    """
    fd = get_sandbox_ruleset()
    if fd is None:
        return None
    return make_preexec_fn(fd)
