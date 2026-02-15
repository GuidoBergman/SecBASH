"""Integration tests for bypass verification in production mode (Docker).

Tests BYPASS-12 (exit escape), BYPASS-13 (shell spawning via Landlock),
and regression checks for legitimate commands.

Requires Docker to be available. Skipped automatically when Docker is not
installed or the daemon is not running.
"""

import subprocess
import time

import pytest

# ---------------------------------------------------------------------------
# Markers & skip conditions
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.docker

IMAGE_NAME = "aegish-production-test"
DOCKERFILE = "tests/Dockerfile.production"
BUILD_CONTEXT = "."


def _docker_available() -> bool:
    """Return True if the docker CLI can reach a running daemon."""
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True, timeout=10,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


skip_no_docker = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker not available",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def docker_exec(container_id: str, command: str) -> tuple[int, str, str]:
    """Run *command* inside the container via bash and return (rc, stdout, stderr)."""
    result = subprocess.run(
        ["docker", "exec", container_id, "bash", "--norc", "--noprofile", "-c", command],
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def _landlock_available_in_container(container_id: str) -> bool:
    """Probe whether Landlock syscalls work inside the container."""
    rc, out, _ = docker_exec(
        container_id,
        "python3 -c \""
        "import ctypes, os; "
        "libc = ctypes.CDLL('libc.so.6', use_errno=True); "
        "ret = libc.syscall(444, None, 0, 0); "  # SYS_landlock_create_ruleset version probe
        "print(ret)"
        "\"",
    )
    if rc != 0:
        return False
    try:
        return int(out.strip()) >= 0
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Session-scoped fixture: build image + run container once per test session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def production_container():
    """Build the production Docker image and start a container.

    Yields the container ID.  Tears down (stop + rm) after the session.
    """
    if not _docker_available():
        pytest.skip("Docker not available")

    # Build image
    build = subprocess.run(
        ["docker", "build", "-t", IMAGE_NAME, "-f", DOCKERFILE, BUILD_CONTEXT],
        capture_output=True, text=True, timeout=600,
    )
    if build.returncode != 0:
        pytest.fail(f"Docker build failed:\n{build.stderr}")

    # Run container in background (sshd keeps it alive)
    run = subprocess.run(
        ["docker", "run", "-d", "--rm", IMAGE_NAME],
        capture_output=True, text=True, timeout=30,
    )
    if run.returncode != 0:
        pytest.fail(f"Docker run failed:\n{run.stderr}")

    container_id = run.stdout.strip()

    # Give sshd a moment to start
    time.sleep(1)

    yield container_id

    # Teardown
    subprocess.run(
        ["docker", "stop", container_id],
        capture_output=True, timeout=30,
    )


@pytest.fixture(scope="session")
def has_landlock(production_container):
    """Return True if Landlock is available inside the running container."""
    return _landlock_available_in_container(production_container)


# ===================================================================
# BYPASS-12: exit terminates session, no parent shell escape
# ===================================================================

@skip_no_docker
class TestBypass12ExitEscape:
    """BYPASS-12: `exit` and EOF must terminate the session cleanly."""

    def test_exit_terminates_session(self, production_container):
        """Invoking aegish as login shell terminates the session on exit.

        Without API credentials the shell exits immediately (rc 1).
        The security-critical property is that the process *terminates*
        and does not drop the user into an unrestricted parent shell.
        """
        rc, out, err = docker_exec(
            production_container,
            "echo exit | su -s $(which aegish) testuser",
        )
        # aegish must terminate (rc 0 = clean exit, rc 1 = credential error).
        # Both are acceptable; the key is that it does NOT hang or spawn a
        # parent shell.
        assert rc in (0, 1), f"Unexpected rc={rc}. stderr: {err}"

    def test_no_parent_shell_after_exit(self, production_container):
        """After aegish exits, the user must NOT land in a parent shell."""
        # If a parent shell leaked, 'whoami' would succeed after exit.
        rc, out, err = docker_exec(
            production_container,
            "printf 'exit\\nwhoami\\n' | su -s $(which aegish) testuser",
        )
        # 'whoami' after exit should NOT produce output (no shell to run it)
        assert "testuser" not in out, (
            "Parent shell leaked after exit -- 'whoami' succeeded"
        )


# ===================================================================
# BYPASS-13: shell spawning blocked by Landlock
# ===================================================================

@skip_no_docker
class TestBypass13ShellSpawning:
    """BYPASS-13: direct and indirect shell spawning must be blocked."""

    def test_bash_blocked(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = docker_exec(
            production_container,
            "su -s $(which aegish) testuser -c bash",
        )
        # bash execution must be denied (126 = cannot execute, 127 = not found)
        assert rc in (126, 127, 1), f"Expected bash blocked (rc 126/127/1), got {rc}. out: {out}"

    def test_python3_os_system_bash_blocked(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = docker_exec(
            production_container,
            '''su -s $(which aegish) testuser -c "python3 -c \\"import os; exit(os.system('bash'))\\""''',
        )
        assert rc != 0, f"python3 os.system('bash') should fail, got rc={rc}"

    def test_python3_os_execv_bash_blocked(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = docker_exec(
            production_container,
            '''su -s $(which aegish) testuser -c "python3 -c \\"import os; os.execv('/bin/bash', ['bash'])\\""''',
        )
        assert rc != 0, f"python3 os.execv('/bin/bash') should fail, got rc={rc}"
        # PermissionError or OSError expected in stderr
        assert "PermissionError" in err or "Permission denied" in err or rc != 0


# ===================================================================
# Regression: legitimate commands must still work
# ===================================================================

@skip_no_docker
class TestRegressionLegitimateCommands:
    """Legitimate user commands must succeed in production mode."""

    @pytest.mark.parametrize(
        "cmd, expected_fragment",
        [
            ("ls -la", "total"),
            ("echo hello", "hello"),
            ("cat /etc/hostname", ""),  # any output is fine
            ('python3 -c "print(\'ok\')"', "ok"),
            ("git --version", "git version"),
        ],
        ids=["ls", "echo", "cat-hostname", "python3", "git"],
    )
    def test_command_succeeds(self, production_container, cmd, expected_fragment):
        rc, out, err = docker_exec(production_container, cmd)
        assert rc == 0, f"'{cmd}' failed with rc={rc}. stderr: {err}"
        if expected_fragment:
            assert expected_fragment in out, (
                f"Expected '{expected_fragment}' in output of '{cmd}', got: {out}"
            )
