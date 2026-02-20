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


def _sandboxed_bash_exec(container_id: str, command: str) -> tuple[int, str, str]:
    """Run *command* through sandboxed /bin/bash (replicating aegish production mode)."""
    script = (
        "import ctypes, os, sys\n"
        "libc = ctypes.CDLL('libc.so.6', use_errno=True)\n"
        "libc.prctl(38, 1, 0, 0, 0)\n"
        "os.environ['LD_PRELOAD'] = '/opt/aegish/lib/landlock_sandboxer.so'\n"
        "os.execv('/bin/bash', "
        "['bash', '--norc', '--noprofile', '-c', sys.argv[1]])\n"
    )
    result = subprocess.run(
        ["docker", "exec", container_id, "python3", "-c", script, command],
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
        "ret = libc.syscall(444, None, 0, 1); "  # flags=LANDLOCK_CREATE_RULESET_VERSION
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
        rc, out, err = _sandboxed_bash_exec(production_container, "bash")
        # bash execution must be denied (126 = cannot execute, 127 = not found)
        assert rc in (126, 127), f"Expected bash blocked (rc 126/127), got {rc}. out: {out}"

    def test_python3_os_system_bash_blocked(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sandboxed_bash_exec(
            production_container,
            'python3 -c "import os; r=os.system(\'bash\'); exit(os.WEXITSTATUS(r) if os.WIFEXITED(r) else 1)"',
        )
        assert rc != 0, f"python3 os.system('bash') should fail, got rc={rc}"

    def test_python3_os_execv_bash_blocked(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sandboxed_bash_exec(
            production_container,
            "python3 -c \"import os; os.execv('/bin/bash', ['bash'])\"",
        )
        assert rc != 0, f"python3 os.execv('/bin/bash') should fail, got rc={rc}"
        # PermissionError or OSError expected in stderr
        assert "PermissionError" in err or "Permission denied" in err or rc != 0


# ===================================================================
# Sandboxed /bin/bash execution (runner removed in Story 17)
# ===================================================================

@skip_no_docker
class TestSandboxedBashDirect:
    """Verify sandboxed /bin/bash execution pipeline (runner removed)."""

    def test_sandboxed_bash_blocks_child_bash(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sandboxed_bash_exec(production_container, "bash")
        assert rc in (126, 127), f"Expected bash blocked (rc 126/127), got {rc}. out: {out}"

    def test_sandboxed_bash_allows_echo(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sandboxed_bash_exec(production_container, "echo works")
        assert rc == 0, f"echo should succeed under sandbox, got rc={rc}. err: {err}"
        assert "works" in out

    def test_bash_executes_echo(self, production_container):
        rc, out, err = docker_exec(
            production_container,
            "/bin/bash -c 'echo works'",
        )
        assert rc == 0, f"/bin/bash failed to execute echo: {err}"
        assert "works" in out


# ===================================================================
# BYPASS-13: GTFOBins shell escape techniques
# ===================================================================

@skip_no_docker
class TestBypass13GTFOBinsEscape:
    """BYPASS-13: GTFOBins shell escape techniques must be blocked by Landlock."""

    def test_git_pager_bash_blocked(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sandboxed_bash_exec(
            production_container, "git -c core.pager=bash diff",
        )
        assert rc != 0, (
            f"git core.pager=bash should be blocked, got rc={rc}. out: {out}"
        )

    def test_git_exec_bash_blocked(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sandboxed_bash_exec(
            production_container, "git -c core.editor=bash tag -a test -m x",
        )
        assert rc != 0, (
            f"git core.editor=bash should be blocked, got rc={rc}. out: {out}"
        )

    def test_man_pager_bash_blocked(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sandboxed_bash_exec(
            production_container, "PAGER=bash man man",
        )
        assert rc != 0, (
            f"PAGER=bash man should be blocked, got rc={rc}. out: {out}"
        )

    def test_man_pager_sh_blocked(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sandboxed_bash_exec(
            production_container, "PAGER=sh man man",
        )
        assert rc != 0, (
            f"PAGER=sh man should be blocked, got rc={rc}. out: {out}"
        )


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


# ===================================================================
# Story 16.1: Sudo post-elevation sandboxing
# ===================================================================

def _sudo_sandboxed_bash_exec(container_id: str, command: str) -> tuple[int, str, str]:
    """Run *command* as testuser via sudo with LD_PRELOAD sandboxer.

    Replicates the aegish sudo production path:
    sudo env LD_PRELOAD=<sandboxer> /bin/bash --norc --noprofile -c "<command>"
    """
    inner_cmd = (
        "sudo env "
        "LD_PRELOAD=/opt/aegish/lib/landlock_sandboxer.so "
        "/bin/bash --norc --noprofile -c "
        f"'{command}'"
    )
    result = subprocess.run(
        ["docker", "exec", "-u", "testuser", container_id,
         "bash", "--norc", "--noprofile", "-c", inner_cmd],
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


@skip_no_docker
class TestSudoSandboxedExecution:
    """Story 16.1: Sudo commands are elevated then sandboxed by Landlock."""

    def test_sudo_whoami_returns_root(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sudo_sandboxed_bash_exec(production_container, "whoami")
        assert rc == 0, f"sudo whoami failed: rc={rc}, err={err}"
        assert "root" in out, f"Expected 'root' in output, got: {out}"

    def test_sudo_command_sandboxed_blocks_bash(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sudo_sandboxed_bash_exec(production_container, "bash")
        assert rc in (126, 127), (
            f"Expected bash blocked (rc 126/127) even as root, got {rc}. out: {out}"
        )

    def test_sudo_command_sandboxed_blocks_sh(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sudo_sandboxed_bash_exec(production_container, "sh")
        assert rc in (126, 127), (
            f"Expected sh blocked (rc 126/127) even as root, got {rc}. out: {out}"
        )

    def test_sudo_sandboxed_allows_echo(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sudo_sandboxed_bash_exec(production_container, "echo elevated")
        assert rc == 0, f"echo should succeed elevated, got rc={rc}. err: {err}"
        assert "elevated" in out

    def test_sudo_sandboxed_allows_ls(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sudo_sandboxed_bash_exec(production_container, "ls /")
        assert rc == 0, f"ls should succeed elevated, got rc={rc}. err: {err}"

    def test_sudo_sandboxed_allows_apt(self, production_container, has_landlock):
        if not has_landlock:
            pytest.skip("Landlock not available (kernel too old or not enabled)")
        rc, out, err = _sudo_sandboxed_bash_exec(
            production_container, "apt list --installed 2>/dev/null | head -3",
        )
        assert rc == 0, f"apt list should succeed elevated, got rc={rc}. err: {err}"
