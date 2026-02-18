"""Tests for Landlock sandbox module.

Story 14.2 simplified sandbox.py: Landlock ruleset creation and activation
moved to the C sandboxer library (LD_PRELOAD). sandbox.py now provides:
- DENIED_SHELLS (reference copy)
- landlock_available() (kernel probe)
- make_no_new_privs_fn() (preexec_fn for NO_NEW_PRIVS only)
"""

import ctypes
import inspect
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Constants and struct definitions
# =============================================================================


class TestConstants:
    """Tests for Landlock constants, structs, and DENIED_SHELLS."""

    def test_syscall_numbers(self):
        """Verify x86_64 syscall numbers."""
        from aegish.sandbox import (
            SYS_landlock_add_rule,
            SYS_landlock_create_ruleset,
            SYS_landlock_restrict_self,
        )

        assert SYS_landlock_create_ruleset == 444
        assert SYS_landlock_add_rule == 445
        assert SYS_landlock_restrict_self == 446

    def test_landlock_ruleset_attr_struct(self):
        """Verify LandlockRulesetAttr fields."""
        from aegish.sandbox import LandlockRulesetAttr

        attr = LandlockRulesetAttr()
        attr.handled_access_fs = 1
        assert attr.handled_access_fs == 1

    def test_landlock_path_beneath_attr_struct(self):
        """Verify LandlockPathBeneathAttr fields and packing."""
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
        """Verify access flag constants."""
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
        """DENIED_SHELLS contains all required shell binary paths (Story 14.3)."""
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
            "/bin/ash", "/usr/bin/ash",
            "/bin/busybox", "/usr/bin/busybox",
            "/bin/mksh", "/usr/bin/mksh",
            "/bin/rbash", "/usr/bin/rbash",
            "/bin/elvish", "/usr/bin/elvish",
            "/bin/nu", "/usr/bin/nu",
            "/bin/pwsh", "/usr/bin/pwsh",
            "/bin/xonsh", "/usr/bin/xonsh",
        }
        assert required.issubset(DENIED_SHELLS)

    def test_denied_shells_has_bin_and_usr_bin_variants(self):
        """Both /bin/ and /usr/bin/ variants for each shell."""
        from aegish.sandbox import DENIED_SHELLS

        shells = [
            "bash", "sh", "dash", "zsh", "fish", "ksh", "csh", "tcsh",
            "ash", "busybox", "mksh", "rbash", "elvish", "nu", "pwsh", "xonsh",
        ]
        for shell in shells:
            assert f"/bin/{shell}" in DENIED_SHELLS, f"/bin/{shell} missing"
            assert f"/usr/bin/{shell}" in DENIED_SHELLS, f"/usr/bin/{shell} missing"

    def test_denied_shells_total_count(self):
        """DENIED_SHELLS has exactly 32 entries (16 shells x 2 paths each)."""
        from aegish.sandbox import DENIED_SHELLS

        assert len(DENIED_SHELLS) == 32

    def test_default_runner_path(self):
        """DEFAULT_RUNNER_PATH is correct."""
        from aegish.sandbox import DEFAULT_RUNNER_PATH

        assert DEFAULT_RUNNER_PATH == "/opt/aegish/bin/runner"


# =============================================================================
# landlock_available() function
# =============================================================================


class TestLandlockAvailable:
    """Tests for landlock_available() function."""

    def test_returns_tuple(self):
        """Returns (bool, int) tuple."""
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
        """Available when create_ruleset returns >= 0."""
        from aegish import sandbox

        sandbox._landlock_cache = None

        mock_libc = MagicMock()
        mock_libc.syscall.return_value = 5  # ABI version 5

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            result = sandbox.landlock_available()

        assert result == (True, 5)

        sandbox._landlock_cache = None

    def test_unavailable_when_syscall_fails(self):
        """Not available when syscall returns -1."""
        from aegish import sandbox

        sandbox._landlock_cache = None

        mock_libc = MagicMock()
        mock_libc.syscall.return_value = -1

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            result = sandbox.landlock_available()

        assert result == (False, 0)

        sandbox._landlock_cache = None

    def test_caching_avoids_repeated_syscalls(self):
        """Result is cached; second call does not make syscall."""
        from aegish import sandbox

        sandbox._landlock_cache = None

        mock_libc = MagicMock()
        mock_libc.syscall.return_value = 3

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            result1 = sandbox.landlock_available()
            result2 = sandbox.landlock_available()

        assert result1 == result2
        assert mock_libc.syscall.call_count == 1

        sandbox._landlock_cache = None

    def test_unavailable_returns_false_zero(self):
        """Returns (False, 0) when kernel doesn't support Landlock."""
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
# make_no_new_privs_fn() -- Story 14.2
# =============================================================================


class TestMakeNoNewPrivsFn:
    """Tests for make_no_new_privs_fn() (replacement for make_preexec_fn)."""

    def test_returns_callable(self):
        """Returns a callable with no arguments."""
        from aegish.sandbox import make_no_new_privs_fn

        fn = make_no_new_privs_fn()
        assert callable(fn)

    def test_callable_takes_no_arguments(self):
        """Closure signature is () -> None."""
        from aegish.sandbox import make_no_new_privs_fn

        fn = make_no_new_privs_fn()
        sig = inspect.signature(fn)
        assert len(sig.parameters) == 0

    def test_calls_prctl_only(self):
        """Calls prctl(PR_SET_NO_NEW_PRIVS) only -- no landlock_restrict_self."""
        from aegish import sandbox

        call_log = []
        mock_libc = MagicMock()

        def mock_prctl(*args):
            call_log.append(("prctl", args))
            return 0

        mock_libc.prctl = mock_prctl
        # syscall should NOT be called
        mock_libc.syscall = MagicMock(return_value=0)

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            fn = sandbox.make_no_new_privs_fn()
            fn()

        # Only prctl should be called
        assert len(call_log) == 1
        assert call_log[0][0] == "prctl"
        # Verify prctl arguments: PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0
        assert call_log[0][1] == (sandbox.PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
        # Verify no syscall was made (no landlock_restrict_self)
        mock_libc.syscall.assert_not_called()

    def test_raises_on_prctl_failure(self):
        """Raises OSError if prctl fails."""
        from aegish import sandbox

        mock_libc = MagicMock()
        mock_libc.prctl.return_value = -1

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            fn = sandbox.make_no_new_privs_fn()
            with pytest.raises(OSError, match="prctl"):
                fn()

    def test_does_not_call_landlock_restrict_self(self):
        """Landlock activation is handled by LD_PRELOAD, not preexec_fn."""
        from aegish import sandbox

        mock_libc = MagicMock()
        mock_libc.prctl.return_value = 0

        with patch.object(sandbox, "_get_libc", return_value=mock_libc):
            fn = sandbox.make_no_new_privs_fn()
            fn()

        # syscall should never be called (no landlock_restrict_self)
        mock_libc.syscall.assert_not_called()


# =============================================================================
# Removed functions no longer exist (Story 14.2)
# =============================================================================


class TestRemovedFunctions:
    """Verify that functions removed in Story 14.2 are no longer importable."""

    def test_create_sandbox_ruleset_removed(self):
        """create_sandbox_ruleset() was removed."""
        from aegish import sandbox
        assert not hasattr(sandbox, "create_sandbox_ruleset")

    def test_make_preexec_fn_removed(self):
        """make_preexec_fn() was removed (replaced by make_no_new_privs_fn)."""
        from aegish import sandbox
        assert not hasattr(sandbox, "make_preexec_fn")

    def test_get_sandbox_ruleset_removed(self):
        """get_sandbox_ruleset() was removed."""
        from aegish import sandbox
        assert not hasattr(sandbox, "get_sandbox_ruleset")

    def test_get_sandbox_preexec_removed(self):
        """get_sandbox_preexec() was removed."""
        from aegish import sandbox
        assert not hasattr(sandbox, "get_sandbox_preexec")
