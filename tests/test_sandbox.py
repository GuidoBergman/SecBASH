"""Tests for Landlock sandbox module."""

import ctypes
import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest


class _MockScandirResult:
    """Mock os.scandir result: iterable + context manager like ScandirIterator."""

    def __init__(self, entries):
        self._entries = entries

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def __iter__(self):
        return iter(self._entries)


# =============================================================================
# Task 1: Constants and struct definitions (AC: #1, #2)
# =============================================================================


class TestConstants:
    """Tests for Landlock constants, structs, and DENIED_SHELLS."""

    def test_syscall_numbers(self):
        """Subtask 1.1: Verify x86_64 syscall numbers."""
        from aegish.sandbox import (
            SYS_landlock_add_rule,
            SYS_landlock_create_ruleset,
            SYS_landlock_restrict_self,
        )

        assert SYS_landlock_create_ruleset == 444
        assert SYS_landlock_add_rule == 445
        assert SYS_landlock_restrict_self == 446

    def test_landlock_ruleset_attr_struct(self):
        """Subtask 1.2: Verify LandlockRulesetAttr fields."""
        from aegish.sandbox import LandlockRulesetAttr

        attr = LandlockRulesetAttr()
        attr.handled_access_fs = 1
        assert attr.handled_access_fs == 1

    def test_landlock_path_beneath_attr_struct(self):
        """Subtask 1.2: Verify LandlockPathBeneathAttr fields and packing."""
        from aegish.sandbox import LandlockPathBeneathAttr

        attr = LandlockPathBeneathAttr()
        attr.allowed_access = 1
        attr.parent_fd = 5
        assert attr.allowed_access == 1
        assert attr.parent_fd == 5

    def test_struct_packing_size(self):
        """Verify ctypes.sizeof(LandlockPathBeneathAttr) == 12 (8 + 4, packed)."""
        from aegish.sandbox import LandlockPathBeneathAttr

        assert ctypes.sizeof(LandlockPathBeneathAttr) == 12

    def test_access_flags(self):
        """Subtask 1.3: Verify access flag constants."""
        from aegish.sandbox import (
            LANDLOCK_ACCESS_FS_EXECUTE,
            LANDLOCK_CREATE_RULESET_VERSION,
            LANDLOCK_RULE_PATH_BENEATH,
            PR_SET_NO_NEW_PRIVS,
        )

        assert LANDLOCK_ACCESS_FS_EXECUTE == (1 << 0)
        assert LANDLOCK_RULE_PATH_BENEATH == 1
        assert LANDLOCK_CREATE_RULESET_VERSION == (1 << 0)
        assert PR_SET_NO_NEW_PRIVS == 38

    def test_denied_shells_completeness(self):
        """Subtask 1.4: DENIED_SHELLS contains all required shell binary paths."""
        from aegish.sandbox import DENIED_SHELLS

        required = {
            "/bin/bash", "/usr/bin/bash",
            "/bin/sh", "/usr/bin/sh",
            "/bin/dash", "/usr/bin/dash",
            "/bin/zsh", "/usr/bin/zsh",
            "/bin/fish", "/usr/bin/fish",
            "/bin/ksh", "/usr/bin/ksh",
            "/bin/csh", "/usr/bin/csh",
            "/bin/tcsh", "/usr/bin/tcsh",
        }
        assert required.issubset(DENIED_SHELLS)

    def test_denied_shells_has_bin_and_usr_bin_variants(self):
        """Subtask 1.4: Both /bin/ and /usr/bin/ variants for each shell."""
        from aegish.sandbox import DENIED_SHELLS

        shells = ["bash", "sh", "dash", "zsh", "fish", "ksh", "csh", "tcsh"]
        for shell in shells:
            assert f"/bin/{shell}" in DENIED_SHELLS
            assert f"/usr/bin/{shell}" in DENIED_SHELLS

    def test_default_runner_path(self):
        """Subtask 1.5: DEFAULT_RUNNER_PATH is correct."""
        from aegish.sandbox import DEFAULT_RUNNER_PATH

        assert DEFAULT_RUNNER_PATH == "/opt/aegish/bin/runner"


# =============================================================================
# Task 2: landlock_available() function (AC: #5)
# =============================================================================


class TestLandlockAvailable:
    """Tests for landlock_available() function."""

    def test_returns_tuple(self):
        """Subtask 2.6: Returns (bool, int) tuple."""
        from aegish import sandbox

        sandbox._landlock_cache = None

        mock_libc = MagicMock()
        mock_libc.syscall.return_value = 3

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            result = sandbox.landlock_available()

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], int)

        sandbox._landlock_cache = None

    def test_available_when_syscall_succeeds(self):
        """Subtask 2.2-2.3: Available when create_ruleset returns >= 0."""
        from aegish import sandbox

        # Reset cache
        sandbox._landlock_cache = None

        mock_libc = MagicMock()
        mock_libc.syscall.return_value = 5  # ABI version 5

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            result = sandbox.landlock_available()

        assert result == (True, 5)
        # Note: ABI version probe returns an integer, NOT an fd — no os.close needed

        # Reset cache
        sandbox._landlock_cache = None

    def test_unavailable_when_syscall_fails(self):
        """Subtask 2.4: Not available when syscall returns -1."""
        from aegish import sandbox

        sandbox._landlock_cache = None

        mock_libc = MagicMock()
        mock_libc.syscall.return_value = -1

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            result = sandbox.landlock_available()

        assert result == (False, 0)

        sandbox._landlock_cache = None

    def test_caching_avoids_repeated_syscalls(self):
        """Subtask 2.5: Result is cached; second call does not make syscall."""
        from aegish import sandbox

        sandbox._landlock_cache = None

        mock_libc = MagicMock()
        mock_libc.syscall.return_value = 3

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            result1 = sandbox.landlock_available()
            result2 = sandbox.landlock_available()

        assert result1 == result2
        # syscall called only once (for the version check)
        assert mock_libc.syscall.call_count == 1

        sandbox._landlock_cache = None

    def test_unavailable_returns_false_zero(self):
        """AC#5: Returns (False, 0) when kernel doesn't support Landlock."""
        from aegish import sandbox

        sandbox._landlock_cache = None

        mock_libc = MagicMock()
        mock_libc.syscall.return_value = -1

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            available, version = sandbox.landlock_available()

        assert available is False
        assert version == 0

        sandbox._landlock_cache = None


# =============================================================================
# Task 3: create_sandbox_ruleset() function (AC: #1, #2)
# =============================================================================


class TestCreateSandboxRuleset:
    """Tests for create_sandbox_ruleset() function."""

    def test_creates_ruleset_fd(self):
        """Subtask 3.1: Creates a Landlock ruleset and returns fd."""
        from aegish import sandbox

        mock_libc = MagicMock()
        # First syscall: create_ruleset returns fd=7
        mock_libc.syscall.return_value = 7

        with patch.object(sandbox, "_get_libc", return_value=mock_libc), \
             patch("os.scandir", return_value=_MockScandirResult([])), \
             patch("os.environ", {"PATH": "/usr/bin"}):
            fd = sandbox.create_sandbox_ruleset()

        assert fd == 7

    def test_enumerates_path_directories(self):
        """Subtask 3.2: Enumerates executables from PATH."""
        from aegish import sandbox

        mock_libc = MagicMock()
        mock_libc.syscall.return_value = 7  # create_ruleset fd

        # Create mock scandir entries
        entry_ls = MagicMock()
        entry_ls.name = "ls"
        entry_ls.path = "/usr/bin/ls"
        entry_ls.is_file.return_value = True

        mock_stat = MagicMock()
        mock_stat.st_mode = 0o100755  # regular, executable
        entry_ls.stat.return_value = mock_stat

        with patch.object(sandbox, "_get_libc", return_value=mock_libc), \
             patch("os.scandir", return_value=_MockScandirResult([entry_ls])) as mock_scandir, \
             patch("os.path.realpath", side_effect=lambda p: p), \
             patch("os.path.isdir", return_value=True), \
             patch("os.environ", {"PATH": "/usr/bin"}), \
             patch.object(sandbox, "_add_path_rule"):
            sandbox.create_sandbox_ruleset()

        # scandir should be called for /usr/bin and the runner dir
        mock_scandir.assert_called()

    def test_shells_are_skipped(self):
        """Subtask 3.5: Shell binaries are NOT given EXECUTE rules."""
        from aegish import sandbox

        mock_libc = MagicMock()
        mock_libc.syscall.return_value = 7

        # Create entries: one shell (bash), one non-shell (ls)
        entry_bash = MagicMock()
        entry_bash.name = "bash"
        entry_bash.path = "/usr/bin/bash"
        entry_bash.is_file.return_value = True
        stat_bash = MagicMock()
        stat_bash.st_mode = 0o100755
        entry_bash.stat.return_value = stat_bash

        entry_ls = MagicMock()
        entry_ls.name = "ls"
        entry_ls.path = "/usr/bin/ls"
        entry_ls.is_file.return_value = True
        stat_ls = MagicMock()
        stat_ls.st_mode = 0o100755
        entry_ls.stat.return_value = stat_ls

        added_paths = []

        def mock_add_rule(libc, ruleset_fd, path):
            added_paths.append(path)

        with patch.object(sandbox, "_get_libc", return_value=mock_libc), \
             patch("os.scandir", return_value=_MockScandirResult([entry_bash, entry_ls])), \
             patch("os.path.realpath", side_effect=lambda p: p), \
             patch("os.path.isdir", return_value=True), \
             patch("os.environ", {"PATH": "/usr/bin"}), \
             patch.object(sandbox, "_add_path_rule", side_effect=mock_add_rule):
            sandbox.create_sandbox_ruleset()

        assert "/usr/bin/ls" in added_paths
        assert "/usr/bin/bash" not in added_paths

    def test_permission_error_skipped(self):
        """Subtask 3.7: PermissionError on scandir is caught and skipped."""
        from aegish import sandbox

        mock_libc = MagicMock()
        mock_libc.syscall.return_value = 7

        with patch.object(sandbox, "_get_libc", return_value=mock_libc), \
             patch("os.scandir", side_effect=PermissionError("denied")), \
             patch("os.path.isdir", return_value=True), \
             patch("os.environ", {"PATH": "/usr/bin"}):
            # Should not raise
            fd = sandbox.create_sandbox_ruleset()

        assert fd == 7

    def test_add_path_rule_invalid_path(self):
        """Subtask 3.6: _add_path_rule handles FileNotFoundError gracefully."""
        from aegish import sandbox

        mock_libc = MagicMock()

        # os.open raises FileNotFoundError
        with patch("os.open", side_effect=FileNotFoundError("/nonexistent")):
            # Should not raise
            sandbox._add_path_rule(mock_libc, 7, "/nonexistent/binary")


# =============================================================================
# Task 4: make_preexec_fn() factory (AC: #1, #3, #4)
# =============================================================================


class TestMakePreexecFn:
    """Tests for make_preexec_fn() factory."""

    def test_returns_callable(self):
        """Subtask 4.4: Returns a callable with no arguments."""
        from aegish.sandbox import make_preexec_fn

        fn = make_preexec_fn(7)
        assert callable(fn)

    def test_callable_takes_no_arguments(self):
        """Subtask 4.4: Closure signature is () -> None."""
        from aegish import sandbox

        fn = sandbox.make_preexec_fn(7)

        mock_libc = MagicMock()
        mock_libc.syscall.return_value = 0

        with patch.object(sandbox, "_get_libc", return_value=mock_libc), \
             patch("ctypes.CDLL") as mock_cdll:
            mock_prctl = MagicMock(return_value=0)
            mock_cdll.return_value.prctl = mock_prctl
            # The function should accept no arguments
            import inspect
            sig = inspect.signature(fn)
            assert len(sig.parameters) == 0

    def test_calls_prctl_then_restrict_self(self):
        """Subtask 4.1-4.2: Calls prctl first, then landlock_restrict_self."""
        from aegish import sandbox

        call_log = []
        mock_libc = MagicMock()

        def mock_prctl(*args):
            call_log.append(("prctl", args))
            return 0

        def mock_syscall(*args):
            call_log.append(("syscall", args))
            return 0

        mock_libc.prctl = mock_prctl
        mock_libc.syscall = mock_syscall

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            fn = sandbox.make_preexec_fn(7)
            fn()

        # Verify call order: prctl first, then restrict_self
        assert call_log[0][0] == "prctl"
        assert call_log[1][0] == "syscall"

        # Verify prctl receives correct arguments: PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0
        prctl_args = call_log[0][1]
        assert prctl_args == (sandbox.PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)

        # Verify restrict_self receives correct arguments: SYS_landlock_restrict_self, fd, 0
        syscall_args = call_log[1][1]
        assert syscall_args[0] == sandbox.SYS_landlock_restrict_self
        assert syscall_args[1] == 7  # ruleset_fd
        assert syscall_args[2] == 0  # flags

    def test_raises_on_prctl_failure(self):
        """Subtask 4.3: Raises OSError if prctl fails."""
        from aegish import sandbox

        mock_libc = MagicMock()
        mock_libc.prctl.return_value = -1

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            fn = sandbox.make_preexec_fn(7)
            with pytest.raises(OSError, match="prctl"):
                fn()

    def test_raises_on_restrict_self_failure(self):
        """Subtask 4.3: Raises OSError if landlock_restrict_self fails."""
        from aegish import sandbox

        mock_libc = MagicMock()
        mock_libc.prctl.return_value = 0
        mock_libc.syscall.return_value = -1

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            fn = sandbox.make_preexec_fn(7)
            with pytest.raises(OSError, match="landlock_restrict_self"):
                fn()


# =============================================================================
# Task 5: get_sandbox_ruleset() and get_sandbox_preexec() (AC: #1, #2, #5)
# =============================================================================


class TestGetSandboxRuleset:
    """Tests for get_sandbox_ruleset() and get_sandbox_preexec()."""

    def test_returns_none_when_unavailable(self):
        """Subtask 5.4: Returns None when Landlock not available."""
        from aegish import sandbox

        sandbox._cached_ruleset_fd = None
        sandbox._ruleset_initialized = False

        with patch.object(sandbox, "landlock_available", return_value=(False, 0)):
            result = sandbox.get_sandbox_ruleset()

        assert result is None

        sandbox._cached_ruleset_fd = None
        sandbox._ruleset_initialized = False

    def test_returns_fd_when_available(self):
        """Subtask 5.2: Creates and returns ruleset fd on first call."""
        from aegish import sandbox

        sandbox._cached_ruleset_fd = None
        sandbox._ruleset_initialized = False

        with patch.object(sandbox, "landlock_available", return_value=(True, 5)), \
             patch.object(sandbox, "create_sandbox_ruleset", return_value=10):
            result = sandbox.get_sandbox_ruleset()

        assert result == 10

        sandbox._cached_ruleset_fd = None
        sandbox._ruleset_initialized = False

    def test_caches_ruleset_fd(self):
        """Subtask 5.1, 5.3: Caches fd; second call returns same value."""
        from aegish import sandbox

        sandbox._cached_ruleset_fd = None
        sandbox._ruleset_initialized = False

        with patch.object(sandbox, "landlock_available", return_value=(True, 5)), \
             patch.object(sandbox, "create_sandbox_ruleset", return_value=10) as mock_create:
            result1 = sandbox.get_sandbox_ruleset()
            result2 = sandbox.get_sandbox_ruleset()

        assert result1 == result2 == 10
        mock_create.assert_called_once()

        sandbox._cached_ruleset_fd = None
        sandbox._ruleset_initialized = False

    def test_get_sandbox_preexec_returns_none_when_unavailable(self):
        """Subtask 5.5: get_sandbox_preexec() returns None when unavailable."""
        from aegish import sandbox

        sandbox._cached_ruleset_fd = None
        sandbox._ruleset_initialized = False

        with patch.object(sandbox, "landlock_available", return_value=(False, 0)):
            result = sandbox.get_sandbox_preexec()

        assert result is None

        sandbox._cached_ruleset_fd = None
        sandbox._ruleset_initialized = False

    def test_get_sandbox_preexec_returns_callable_when_available(self):
        """Subtask 5.5: get_sandbox_preexec() returns callable when available."""
        from aegish import sandbox

        sandbox._cached_ruleset_fd = None
        sandbox._ruleset_initialized = False

        with patch.object(sandbox, "landlock_available", return_value=(True, 5)), \
             patch.object(sandbox, "create_sandbox_ruleset", return_value=10):
            result = sandbox.get_sandbox_preexec()

        assert callable(result)

        sandbox._cached_ruleset_fd = None
        sandbox._ruleset_initialized = False
