"""Tests for command execution."""

import os
import stat
from unittest.mock import MagicMock, patch, sentinel

from aegish.executor import (
    ALLOWED_ENV_PREFIXES,
    ALLOWED_ENV_VARS,
    DEFAULT_SANDBOXER_PATH,
    SUDO_BINARY_PATH,
    _build_safe_env,
    _execute_sudo_sandboxed,
    _get_sandboxer_path,
    _get_shell_binary,
    _is_sudo_command,
    _sandbox_kwargs,
    _strip_sudo_prefix,
    _validate_sudo_binary,
    execute_command,
    is_bare_cd,
    parse_nul_env,
    resolve_cd,
    run_bash_command,
    sanitize_env,
)


def test_execute_command_exit_code_success():
    """Test that successful commands return 0."""
    exit_code, _, _ = execute_command("true")
    assert exit_code == 0


def test_execute_command_exit_code_failure():
    """Test that failed commands return non-zero."""
    exit_code, _, _ = execute_command("false")
    assert exit_code == 1


def test_execute_command_specific_exit_code():
    """Test that specific exit codes are preserved."""
    exit_code, _, _ = execute_command("exit 42")
    assert exit_code == 42


def test_run_bash_command_captures_stdout():
    """Test that run_bash_command captures stdout."""
    result = run_bash_command("echo hello")
    assert result.stdout.strip() == "hello"
    assert result.returncode == 0


def test_run_bash_command_captures_stderr():
    """Test that run_bash_command captures stderr."""
    result = run_bash_command("echo error >&2")
    assert result.stderr.strip() == "error"
    assert result.returncode == 0


def test_execute_command_with_pipe():
    """Test that pipes work correctly."""
    exit_code, _, _ = execute_command("echo hello | grep hello")
    assert exit_code == 0


def test_execute_command_with_failed_pipe():
    """Test that failed pipe commands return non-zero."""
    exit_code, _, _ = execute_command("echo hello | grep goodbye")
    assert exit_code == 1


def test_execute_command_last_exit_code():
    """Test that last_exit_code is available via $?."""
    result = run_bash_command("(exit 42); echo $?")
    assert result.stdout.strip() == "42"


def test_execute_command_preserves_last_exit():
    """Test that execute_command sets $? correctly."""
    # First run fails
    exit_code, _, _ = execute_command("false")
    assert exit_code == 1

    # Check that $? is 1 in the next command
    result = run_bash_command("(exit 1); echo $?")
    assert result.stdout.strip() == "1"


# =============================================================================
# Story 1.3: Pipes, Redirects, and Command Chaining Tests
# =============================================================================


def test_pipe_command():
    """Test that piped commands work (AC1)."""
    result = run_bash_command("echo hello | tr 'h' 'H'")
    assert result.stdout.strip() == "Hello"
    assert result.returncode == 0


def test_multiple_pipes():
    """Test multiple pipes in sequence (AC1)."""
    result = run_bash_command('echo "c\na\nb" | sort | head -1')
    assert result.stdout.strip() == "a"


def test_pipe_with_grep():
    """Test pipe with grep (AC1)."""
    result = run_bash_command("echo -e 'foo.txt\nbar.log\nbaz.txt' | grep txt")
    assert "foo.txt" in result.stdout
    assert "baz.txt" in result.stdout
    assert "bar.log" not in result.stdout


def test_pipe_chain_cat_sort_uniq_head():
    """Test cat | sort | uniq | head chain (AC1)."""
    result = run_bash_command('echo -e "b\na\nb\nc\na" | sort | uniq | head -2')
    assert result.stdout.strip() == "a\nb"


def test_output_redirect(tmp_path):
    """Test output redirection > (AC2)."""
    test_file = tmp_path / "test.txt"
    result = run_bash_command(f'echo "content" > {test_file}')
    assert result.returncode == 0
    assert test_file.read_text().strip() == "content"


def test_append_redirect(tmp_path):
    """Test append redirection >> (AC2)."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\n")
    result = run_bash_command(f'echo "line2" >> {test_file}')
    assert result.returncode == 0
    assert test_file.read_text() == "line1\nline2\n"


def test_stderr_redirect(tmp_path):
    """Test stderr redirection 2> (AC2)."""
    error_file = tmp_path / "errors.txt"
    result = run_bash_command(f"ls /nonexistent_path_12345 2> {error_file}")
    assert result.returncode != 0
    error_content = error_file.read_text()
    assert "nonexistent" in error_content or "No such file" in error_content


def test_input_redirect(tmp_path):
    """Test input redirection < (AC3)."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("cherry\napple\nbanana\n")
    result = run_bash_command(f"sort < {input_file}")
    assert result.stdout.strip() == "apple\nbanana\ncherry"


def test_chain_and_success():
    """Test && with successful first command (AC4)."""
    result = run_bash_command('true && echo "success"')
    assert result.stdout.strip() == "success"


def test_chain_and_failure():
    """Test && with failed first command - short-circuit (AC4)."""
    result = run_bash_command('false && echo "success"')
    assert result.stdout.strip() == ""


def test_chain_or_success():
    """Test || with successful first command - short-circuit (AC5)."""
    result = run_bash_command('true || echo "fallback"')
    assert result.stdout.strip() == ""


def test_chain_or_failure():
    """Test || with failed first command (AC5)."""
    result = run_bash_command('false || echo "fallback"')
    assert result.stdout.strip() == "fallback"


def test_sequential_semicolon():
    """Test ; for sequential execution (AC6)."""
    result = run_bash_command("echo a; echo b; echo c")
    assert result.stdout.strip() == "a\nb\nc"


def test_combined_pipe_and_chain():
    """Test combined operations (AC7)."""
    # ls | grep txt && echo "found" || echo "none"
    # When grep succeeds, "found" should print
    result = run_bash_command('echo "file.txt" | grep txt && echo "found" || echo "none"')
    assert "found" in result.stdout
    assert "none" not in result.stdout


def test_combined_pipe_and_chain_failure():
    """Test combined operations with failure (AC7)."""
    # When grep fails (no match), "none" should print
    result = run_bash_command('echo "file.log" | grep txt && echo "found" || echo "none"')
    assert "none" in result.stdout
    assert "found" not in result.stdout


def test_stderr_to_stdout_redirect():
    """Test 2>&1 redirection (edge case)."""
    result = run_bash_command("ls /nonexistent_path_12345 2>&1 | head -1")
    assert "nonexistent" in result.stdout or "No such file" in result.stdout


def test_combined_redirects(tmp_path):
    """Test combined input and output redirect."""
    input_file = tmp_path / "in.txt"
    output_file = tmp_path / "out.txt"
    input_file.write_text("3\n1\n2\n")
    result = run_bash_command(f"sort < {input_file} > {output_file}")
    assert result.returncode == 0
    assert output_file.read_text().strip() == "1\n2\n3"


# =============================================================================
# Story 1.4: Shell Script Execution Tests
# =============================================================================


def test_script_direct_execution(tmp_path):
    """Test ./script.sh execution (AC1)."""
    script = tmp_path / "test.sh"
    script.write_text("#!/bin/bash\necho 'hello from script'")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert result.stdout.strip() == "hello from script"
    assert result.returncode == 0


def test_script_bash_invocation(tmp_path):
    """Test bash script.sh execution (AC2)."""
    script = tmp_path / "test.sh"
    script.write_text("#!/bin/bash\necho 'bash invoked'")
    # No execute permission needed for bash script.sh
    result = run_bash_command(f"bash {script}")
    assert result.stdout.strip() == "bash invoked"


def test_script_with_arguments(tmp_path):
    """Test script receives arguments correctly (AC3)."""
    script = tmp_path / "args.sh"
    script.write_text('#!/bin/bash\necho "arg1=$1 arg2=$2"')
    script.chmod(0o755)
    result = run_bash_command(f"{script} hello world")
    assert result.stdout.strip() == "arg1=hello arg2=world"


def test_script_all_args(tmp_path):
    """Test $@ contains all arguments (AC3)."""
    script = tmp_path / "allargs.sh"
    script.write_text('#!/bin/bash\necho "$@"')
    script.chmod(0o755)
    result = run_bash_command(f"{script} a b c d")
    assert result.stdout.strip() == "a b c d"


def test_script_exit_code(tmp_path):
    """Test script exit code is preserved (AC5)."""
    script = tmp_path / "exitcode.sh"
    script.write_text("#!/bin/bash\nexit 42")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert result.returncode == 42


def test_script_exit_code_zero(tmp_path):
    """Test successful script returns 0 (AC5)."""
    script = tmp_path / "success.sh"
    script.write_text("#!/bin/bash\necho 'success'\nexit 0")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert result.returncode == 0


def test_script_env_shebang(tmp_path):
    """Test #!/usr/bin/env bash shebang (AC4)."""
    script = tmp_path / "envbash.sh"
    script.write_text("#!/usr/bin/env bash\necho 'env bash'")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert result.stdout.strip() == "env bash"


def test_script_sh_shebang(tmp_path):
    """Test #!/bin/sh shebang (AC4)."""
    script = tmp_path / "sh.sh"
    script.write_text("#!/bin/sh\necho 'posix sh'")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert result.stdout.strip() == "posix sh"


def test_script_with_spaces_in_path(tmp_path):
    """Test script in path with spaces (edge case)."""
    dir_with_spaces = tmp_path / "my scripts"
    dir_with_spaces.mkdir()
    script = dir_with_spaces / "test.sh"
    script.write_text("#!/bin/bash\necho 'spaces work'")
    script.chmod(0o755)
    # Must quote the path
    result = run_bash_command(f'"{script}"')
    assert result.stdout.strip() == "spaces work"


def test_script_with_stdin(tmp_path):
    """Test script that reads from stdin (edge case)."""
    script = tmp_path / "stdin.sh"
    script.write_text('#!/bin/bash\nread line\necho "got: $line"')
    script.chmod(0o755)
    result = run_bash_command(f'echo "input" | {script}')
    assert result.stdout.strip() == "got: input"


def test_script_sources_other_file(tmp_path):
    """Test script that sources another file (edge case)."""
    lib = tmp_path / "lib.sh"
    lib.write_text("MYVAR='from lib'")
    script = tmp_path / "main.sh"
    script.write_text(f'#!/bin/bash\nsource {lib}\necho $MYVAR')
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert result.stdout.strip() == "from lib"


def test_script_with_heredoc(tmp_path):
    """Test script with here-doc (edge case)."""
    script = tmp_path / "heredoc.sh"
    script.write_text('#!/bin/bash\ncat <<EOF\nline1\nline2\nEOF\n')
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    assert "line1" in result.stdout
    assert "line2" in result.stdout


# =============================================================================
# Story 1.5: Exit Code Preservation Tests
# =============================================================================


def test_exit_code_true_via_echo():
    """Test 'true' returns 0, verified via $? (AC1)."""
    result = run_bash_command("true; echo $?")
    assert result.stdout.strip() == "0"


def test_exit_code_false_via_echo():
    """Test 'false' returns 1, verified via $? (AC2)."""
    result = run_bash_command("false; echo $?")
    assert result.stdout.strip() == "1"


def test_exit_code_nonexistent_file():
    """Test ls on nonexistent file returns non-zero (AC2)."""
    result = run_bash_command("ls /nonexistent_file_12345 2>/dev/null")
    assert result.returncode != 0


def test_exit_code_range():
    """Test various exit codes in valid range are preserved (AC3)."""
    for code in [0, 1, 2, 127, 128, 255]:
        exit_code, _, _ = execute_command(f"exit {code}")
        assert exit_code == code, f"Expected {code}, got {exit_code}"


def test_exit_code_pipeline_success():
    """Test pipeline returns 0 when last command succeeds (AC6)."""
    result = run_bash_command("echo hello | grep hello")
    assert result.returncode == 0


def test_exit_code_pipeline_failure():
    """Test pipeline returns non-zero when last command fails (AC6)."""
    result = run_bash_command("echo hello | grep goodbye")
    assert result.returncode == 1


def test_exit_code_script_set_e(tmp_path):
    """Test script with set -e exits on first failure (AC5)."""
    script = tmp_path / "set_e.sh"
    script.write_text("""#!/bin/bash
set -e
echo "before"
false
echo "after"
""")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    # Should print "before" but not "after" due to set -e
    assert "before" in result.stdout
    assert "after" not in result.stdout
    assert result.returncode != 0


def test_exit_code_script_no_set_e(tmp_path):
    """Test script without set -e continues after failure (AC5 control)."""
    script = tmp_path / "no_set_e.sh"
    script.write_text("""#!/bin/bash
echo "before"
false
echo "after"
""")
    script.chmod(0o755)
    result = run_bash_command(f"{script}")
    # Should print both because no set -e
    assert "before" in result.stdout
    assert "after" in result.stdout


def test_exit_code_complex_chain():
    """Test complex chain with multiple exit codes (AC6)."""
    # (fail && skip) || run -> should run fallback
    result = run_bash_command('false && echo "A" || echo "B"')
    assert result.stdout.strip() == "B"

    # (success && run) || skip -> should run first, skip fallback
    result = run_bash_command('true && echo "A" || echo "B"')
    assert result.stdout.strip() == "A"


def test_exit_code_subshell():
    """Test exit code from subshell is preserved (AC3)."""
    result = run_bash_command("(exit 99); echo $?")
    assert result.stdout.strip() == "99"


def test_exit_code_command_not_found():
    """Test command not found returns 127 (AC2)."""
    result = run_bash_command("nonexistent_command_xyz123 2>/dev/null")
    assert result.returncode == 127


# =============================================================================
# Story 6.2: Environment Sanitization Tests
# =============================================================================


class TestBuildSafeEnv:
    """Tests for _build_safe_env() allowlist-based environment sanitization."""

    # --- Edge case: empty environment ---

    def test_empty_environment_returns_empty_dict(self, mocker):
        """Edge case: empty os.environ returns empty dict."""
        mocker.patch.dict(os.environ, {}, clear=True)
        env = _build_safe_env()
        assert env == {}

    # --- AC1: Allowlist replaces blocklist ---

    def test_allowed_env_vars_has_expected_entries(self):
        """Verify ALLOWED_ENV_VARS constant has the expected entries."""
        expected = {
            "PATH", "HOME", "USER", "LOGNAME", "SHELL",
            "PWD", "OLDPWD", "SHLVL",
            "TERM", "COLORTERM", "TERM_PROGRAM",
            "LANG", "LANGUAGE", "TZ", "TMPDIR",
            "DISPLAY", "WAYLAND_DISPLAY",
            "SSH_AUTH_SOCK", "SSH_AGENT_PID", "GPG_AGENT_INFO",
            "DBUS_SESSION_BUS_ADDRESS", "HOSTNAME",
        }
        assert ALLOWED_ENV_VARS == expected

    def test_allowed_env_prefixes(self):
        """Verify ALLOWED_ENV_PREFIXES tuple."""
        assert ALLOWED_ENV_PREFIXES == ("LC_", "XDG_", "AEGISH_")

    # --- AC2: Standard variables preserved ---

    def test_path_preserved(self, mocker):
        """AC2: PATH is preserved."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin:/usr/local/bin"}, clear=True)
        env = _build_safe_env()
        assert env["PATH"] == "/usr/bin:/usr/local/bin"

    def test_home_preserved(self, mocker):
        """AC2: HOME is preserved."""
        mocker.patch.dict(os.environ, {"HOME": "/home/user"}, clear=True)
        env = _build_safe_env()
        assert env["HOME"] == "/home/user"

    def test_user_preserved(self, mocker):
        """AC2: USER is preserved."""
        mocker.patch.dict(os.environ, {"USER": "testuser"}, clear=True)
        env = _build_safe_env()
        assert env["USER"] == "testuser"

    def test_term_preserved(self, mocker):
        """AC2: TERM is preserved."""
        mocker.patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=True)
        env = _build_safe_env()
        assert env["TERM"] == "xterm-256color"

    def test_all_allowed_vars_preserved(self, mocker):
        """AC2: All ALLOWED_ENV_VARS are preserved when present."""
        test_env = {var: f"value_{var}" for var in ALLOWED_ENV_VARS}
        mocker.patch.dict(os.environ, test_env, clear=True)
        env = _build_safe_env()
        for var in ALLOWED_ENV_VARS:
            assert env[var] == f"value_{var}", f"{var} should be preserved"

    # --- AC3: Safe prefixes preserved ---

    def test_lc_prefix_preserved(self, mocker):
        """AC3: LC_* variables are preserved via prefix matching."""
        mocker.patch.dict(os.environ, {"LC_ALL": "en_US.UTF-8", "LC_CTYPE": "en_US.UTF-8"}, clear=True)
        env = _build_safe_env()
        assert env["LC_ALL"] == "en_US.UTF-8"
        assert env["LC_CTYPE"] == "en_US.UTF-8"

    def test_xdg_prefix_preserved(self, mocker):
        """AC3: XDG_* variables are preserved via prefix matching."""
        mocker.patch.dict(os.environ, {"XDG_RUNTIME_DIR": "/run/user/1000"}, clear=True)
        env = _build_safe_env()
        assert env["XDG_RUNTIME_DIR"] == "/run/user/1000"

    def test_aegish_prefix_preserved(self, mocker):
        """AC3: AEGISH_* variables are preserved via prefix matching."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production", "AEGISH_FAIL_MODE": "safe"}, clear=True)
        env = _build_safe_env()
        assert env["AEGISH_MODE"] == "production"
        assert env["AEGISH_FAIL_MODE"] == "safe"

    # --- AC4: Dangerous variables blocked ---

    def test_ld_preload_blocked(self, mocker):
        """AC4: LD_PRELOAD is blocked (not on allowlist)."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "LD_PRELOAD": "/tmp/evil.so"}, clear=True)
        env = _build_safe_env()
        assert "LD_PRELOAD" not in env
        assert env["PATH"] == "/usr/bin"

    def test_ld_library_path_blocked(self, mocker):
        """AC4: LD_LIBRARY_PATH is blocked (not on allowlist)."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "LD_LIBRARY_PATH": "/tmp"}, clear=True)
        env = _build_safe_env()
        assert "LD_LIBRARY_PATH" not in env

    def test_ld_audit_blocked(self, mocker):
        """AC4: LD_AUDIT is blocked (not on allowlist)."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "LD_AUDIT": "/tmp/audit.so"}, clear=True)
        env = _build_safe_env()
        assert "LD_AUDIT" not in env

    def test_bash_env_blocked(self, mocker):
        """AC4: BASH_ENV is blocked (not on allowlist)."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "BASH_ENV": "/tmp/hook.sh"}, clear=True)
        env = _build_safe_env()
        assert "BASH_ENV" not in env

    def test_bash_loadables_path_blocked(self, mocker):
        """AC4: BASH_LOADABLES_PATH is blocked (not on allowlist)."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "BASH_LOADABLES_PATH": "/tmp"}, clear=True)
        env = _build_safe_env()
        assert "BASH_LOADABLES_PATH" not in env

    def test_prompt_command_blocked(self, mocker):
        """AC4: PROMPT_COMMAND is blocked (not on allowlist)."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "PROMPT_COMMAND": "evil"}, clear=True)
        env = _build_safe_env()
        assert "PROMPT_COMMAND" not in env

    def test_shellopts_blocked(self, mocker):
        """AC4: SHELLOPTS is blocked (not on allowlist)."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "SHELLOPTS": "xtrace"}, clear=True)
        env = _build_safe_env()
        assert "SHELLOPTS" not in env

    def test_pythonpath_blocked(self, mocker):
        """AC4: PYTHONPATH is blocked (not on allowlist)."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "PYTHONPATH": "/tmp"}, clear=True)
        env = _build_safe_env()
        assert "PYTHONPATH" not in env

    def test_bash_func_prefix_blocked(self, mocker):
        """AC4: BASH_FUNC_* variables are blocked (not on allowlist)."""
        mocker.patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "BASH_FUNC_myfunc%%": "() { echo pwned; }",
        }, clear=True)
        env = _build_safe_env()
        assert "BASH_FUNC_myfunc%%" not in env
        assert env["PATH"] == "/usr/bin"

    def test_env_var_blocked(self, mocker):
        """AC4: ENV is blocked (not on allowlist)."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "ENV": "/tmp/hook.sh"}, clear=True)
        env = _build_safe_env()
        assert "ENV" not in env

    def test_ps4_blocked(self, mocker):
        """AC4: PS4 is blocked (not on allowlist)."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "PS4": "$(evil)"}, clear=True)
        env = _build_safe_env()
        assert "PS4" not in env

    # --- API keys no longer preserved (not on allowlist) ---

    def test_openai_api_key_blocked(self, mocker):
        """API keys are NOT on the allowlist (passed via AEGISH_ prefix instead)."""
        mocker.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True)
        env = _build_safe_env()
        assert "OPENAI_API_KEY" not in env

    def test_custom_vars_blocked(self, mocker):
        """Custom variables like JAVA_HOME are not on the allowlist."""
        mocker.patch.dict(os.environ, {"JAVA_HOME": "/usr/lib/jvm"}, clear=True)
        env = _build_safe_env()
        assert "JAVA_HOME" not in env

    # --- Combined scenario ---

    def test_combined_allowed_and_blocked(self, mocker):
        """Only allowlisted vars pass through; everything else is blocked."""
        mocker.patch.dict(os.environ, {
            # Allowed by exact match
            "PATH": "/usr/bin",
            "HOME": "/home/user",
            "USER": "testuser",
            # Allowed by prefix
            "LC_ALL": "en_US.UTF-8",
            "XDG_DATA_HOME": "/home/user/.local/share",
            "AEGISH_MODE": "development",
            # Blocked (not on allowlist)
            "BASH_ENV": "/tmp/evil.sh",
            "LD_PRELOAD": "/tmp/evil.so",
            "PROMPT_COMMAND": "curl evil.com",
            "OPENAI_API_KEY": "sk-test",
            "JAVA_HOME": "/usr/lib/jvm",
            "BASH_FUNC_exploit%%": "() { echo pwned; }",
        }, clear=True)
        env = _build_safe_env()

        # Allowed vars preserved
        assert env["PATH"] == "/usr/bin"
        assert env["HOME"] == "/home/user"
        assert env["USER"] == "testuser"
        assert env["LC_ALL"] == "en_US.UTF-8"
        assert env["XDG_DATA_HOME"] == "/home/user/.local/share"
        assert env["AEGISH_MODE"] == "development"

        # Blocked vars absent
        assert "BASH_ENV" not in env
        assert "LD_PRELOAD" not in env
        assert "PROMPT_COMMAND" not in env
        assert "OPENAI_API_KEY" not in env
        assert "JAVA_HOME" not in env
        assert "BASH_FUNC_exploit%%" not in env
        assert len(env) == 6


class TestExecuteCommandHardening:
    """Tests for execute_command() subprocess hardening (AC4)."""

    # --- Task 2.1: --norc and --noprofile flags ---

    def test_execute_command_uses_norc_noprofile(self, mocker):
        """AC4: execute_command passes --norc and --noprofile to bash."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=0)

        execute_command("echo test")

        call_args = mock_run.call_args
        cmd_list = call_args[0][0]
        assert cmd_list[0] == "bash"
        assert "--norc" in cmd_list
        assert "--noprofile" in cmd_list
        assert "-c" in cmd_list

    # --- Task 2.2: env kwarg with sanitized dict ---

    def test_execute_command_passes_sanitized_env(self, mocker):
        """AC4: execute_command passes env kwarg with sanitized dict."""
        mocker.patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "BASH_ENV": "/tmp/evil.sh",
        }, clear=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=0)

        execute_command("echo test")

        call_args = mock_run.call_args
        assert "env" in call_args.kwargs
        env_dict = call_args.kwargs["env"]
        assert isinstance(env_dict, dict)
        assert env_dict["PATH"] == "/usr/bin"

    # --- Task 2.3: env dict excludes BASH_ENV ---

    def test_execute_command_env_excludes_bash_env(self, mocker):
        """AC4: env dict passed to subprocess does NOT contain BASH_ENV."""
        mocker.patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "BASH_ENV": "/tmp/evil.sh",
        }, clear=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=0)

        execute_command("echo test")

        env_dict = mock_run.call_args.kwargs["env"]
        assert "BASH_ENV" not in env_dict


class TestRunBashCommandHardening:
    """Tests for run_bash_command() subprocess hardening (AC5)."""

    # --- Task 3.1: --norc and --noprofile flags ---

    def test_run_bash_command_uses_norc_noprofile(self, mocker):
        """AC5: run_bash_command passes --norc and --noprofile to bash."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(
            returncode=0, stdout="", stderr=""
        )

        run_bash_command("echo test")

        call_args = mock_run.call_args
        cmd_list = call_args[0][0]
        assert cmd_list[0] == "bash"
        assert "--norc" in cmd_list
        assert "--noprofile" in cmd_list
        assert "-c" in cmd_list

    # --- Task 3.2: env kwarg with sanitized dict ---

    def test_run_bash_command_passes_sanitized_env(self, mocker):
        """AC5: run_bash_command passes env kwarg with sanitized dict."""
        mocker.patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "BASH_ENV": "/tmp/evil.sh",
            "PROMPT_COMMAND": "evil",
        }, clear=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(
            returncode=0, stdout="", stderr=""
        )

        run_bash_command("echo test")

        call_args = mock_run.call_args
        assert "env" in call_args.kwargs
        env_dict = call_args.kwargs["env"]
        assert isinstance(env_dict, dict)
        assert env_dict["PATH"] == "/usr/bin"
        assert "BASH_ENV" not in env_dict
        assert "PROMPT_COMMAND" not in env_dict


# =============================================================================
# Story 8.4: Runner Binary Setup Tests
# =============================================================================


class TestGetShellBinary:
    """Tests for _get_shell_binary() helper (Story 8.4)."""

    def test_development_mode_returns_bash(self, mocker):
        """AC5: Development mode returns 'bash'."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert _get_shell_binary() == "bash"

    def test_production_mode_returns_runner_path(self, mocker):
        """AC3: Production mode returns runner path."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        result = _get_shell_binary()
        assert result == "/opt/aegish/bin/runner"

    def test_production_mode_ignores_custom_runner_path(self, mocker):
        """Story 13.4: Production mode hardcodes runner path, ignores env var."""
        mocker.patch.dict(os.environ, {
            "AEGISH_MODE": "production",
            "AEGISH_RUNNER_PATH": "/custom/runner",
        }, clear=True)
        # In production, runner path is always the hardcoded production path
        from aegish.config import PRODUCTION_RUNNER_PATH
        assert _get_shell_binary() == PRODUCTION_RUNNER_PATH


class TestExecuteCommandRunner:
    """Tests for execute_command() using runner binary (Story 8.4)."""

    def test_execute_command_uses_bash_in_dev_mode(self, mocker):
        """AC5: Development mode uses 'bash' binary."""
        mocker.patch.dict(os.environ, {}, clear=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=0)

        execute_command("echo test")

        cmd_list = mock_run.call_args[0][0]
        assert cmd_list[0] == "bash"

    def test_execute_command_uses_runner_in_prod_mode(self, mocker):
        """AC3: Production mode uses runner binary."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=0)

        execute_command("echo test")

        cmd_list = mock_run.call_args[0][0]
        assert cmd_list[0] == "/opt/aegish/bin/runner"
        assert "--norc" in cmd_list
        assert "--noprofile" in cmd_list
        assert "-c" in cmd_list

    def test_run_bash_command_uses_runner_in_prod_mode(self, mocker):
        """AC3: run_bash_command also uses runner in production mode."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=0, stdout="", stderr="")

        run_bash_command("echo test")

        cmd_list = mock_run.call_args[0][0]
        assert cmd_list[0] == "/opt/aegish/bin/runner"


# =============================================================================
# Story 14.2: LD_PRELOAD Sandboxer Integration Tests
# =============================================================================


class TestSandboxerPath:
    """Tests for _get_sandboxer_path() helper."""

    def test_default_path(self, mocker):
        """Returns default path when env var not set."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert _get_sandboxer_path() == DEFAULT_SANDBOXER_PATH

    def test_custom_path(self, mocker):
        """Returns custom path from AEGISH_SANDBOXER_PATH."""
        mocker.patch.dict(os.environ, {"AEGISH_SANDBOXER_PATH": "/custom/lib.so"}, clear=True)
        assert _get_sandboxer_path() == "/custom/lib.so"


class TestBuildSafeEnvLdPreload:
    """Tests for LD_PRELOAD injection in _build_safe_env() (Story 14.2)."""

    def test_dev_mode_no_ld_preload(self, mocker):
        """Development mode does NOT inject LD_PRELOAD."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin"}, clear=True)
        env = _build_safe_env()
        assert "LD_PRELOAD" not in env

    def test_prod_mode_injects_ld_preload(self, mocker):
        """Production mode injects LD_PRELOAD with sandboxer path."""
        mocker.patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "AEGISH_MODE": "production",
        }, clear=True)
        env = _build_safe_env()
        assert env["LD_PRELOAD"] == DEFAULT_SANDBOXER_PATH

    def test_prod_mode_injects_runner_path(self, mocker):
        """Production mode injects AEGISH_RUNNER_PATH for the C library."""
        mocker.patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "AEGISH_MODE": "production",
        }, clear=True)
        env = _build_safe_env()
        assert "AEGISH_RUNNER_PATH" in env

    def test_prod_mode_custom_sandboxer_path(self, mocker):
        """Production mode uses custom AEGISH_SANDBOXER_PATH."""
        mocker.patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "AEGISH_MODE": "production",
            "AEGISH_SANDBOXER_PATH": "/custom/sandboxer.so",
        }, clear=True)
        env = _build_safe_env()
        assert env["LD_PRELOAD"] == "/custom/sandboxer.so"

    def test_user_ld_preload_blocked(self, mocker):
        """User's LD_PRELOAD from os.environ is blocked by allowlist."""
        mocker.patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "LD_PRELOAD": "/tmp/evil.so",
        }, clear=True)
        env = _build_safe_env()
        assert "LD_PRELOAD" not in env


class TestSandboxKwargs:
    """Tests for _sandbox_kwargs() helper (Story 14.2: NO_NEW_PRIVS only)."""

    def test_dev_mode_returns_empty(self, mocker):
        """Development mode returns empty dict (no sandbox)."""
        mocker.patch.dict(os.environ, {}, clear=True)
        assert _sandbox_kwargs() == {}

    def test_prod_mode_returns_preexec_fn(self, mocker):
        """Production mode returns preexec_fn for NO_NEW_PRIVS."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        mock_preexec = MagicMock()
        mocker.patch("aegish.executor.make_no_new_privs_fn", return_value=mock_preexec)

        result = _sandbox_kwargs()

        assert result["preexec_fn"] is mock_preexec
        assert "pass_fds" not in result

    def test_prod_mode_no_pass_fds(self, mocker):
        """Production mode does not include pass_fds (no ruleset fd)."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        mock_preexec = MagicMock()
        mocker.patch("aegish.executor.make_no_new_privs_fn", return_value=mock_preexec)

        result = _sandbox_kwargs()

        assert "pass_fds" not in result


class TestExecuteCommandLandlock:
    """Tests for execute_command() with LD_PRELOAD sandboxing (Story 14.2)."""

    def test_prod_mode_has_preexec_fn(self, mocker):
        """Production mode: subprocess gets preexec_fn for NO_NEW_PRIVS."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        mock_preexec = MagicMock()
        mocker.patch("aegish.executor.make_no_new_privs_fn", return_value=mock_preexec)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        execute_command("echo test")

        kwargs = mock_run.call_args.kwargs
        assert kwargs["preexec_fn"] is mock_preexec
        cmd_list = mock_run.call_args[0][0]
        assert cmd_list[0] == "/opt/aegish/bin/runner"

    def test_prod_mode_env_has_ld_preload(self, mocker):
        """Production mode: env dict includes LD_PRELOAD with sandboxer."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        mock_preexec = MagicMock()
        mocker.patch("aegish.executor.make_no_new_privs_fn", return_value=mock_preexec)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        execute_command("echo test")

        env_dict = mock_run.call_args.kwargs["env"]
        assert env_dict["LD_PRELOAD"] == DEFAULT_SANDBOXER_PATH

    def test_dev_mode_no_preexec(self, mocker):
        """Development mode: no preexec_fn."""
        mocker.patch.dict(os.environ, {}, clear=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        execute_command("echo test")

        kwargs = mock_run.call_args.kwargs
        assert "preexec_fn" not in kwargs
        cmd_list = mock_run.call_args[0][0]
        assert cmd_list[0] == "bash"


class TestRunBashCommandLandlock:
    """Tests for run_bash_command() with LD_PRELOAD sandboxing (Story 14.2)."""

    def test_prod_mode_has_preexec_fn(self, mocker):
        """Production: run_bash_command gets preexec_fn."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        mock_preexec = MagicMock()
        mocker.patch("aegish.executor.make_no_new_privs_fn", return_value=mock_preexec)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_bash_command("echo test")

        kwargs = mock_run.call_args.kwargs
        assert kwargs["preexec_fn"] is mock_preexec
        assert "pass_fds" not in kwargs

    def test_prod_mode_env_has_ld_preload(self, mocker):
        """Production: env dict includes LD_PRELOAD."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        mock_preexec = MagicMock()
        mocker.patch("aegish.executor.make_no_new_privs_fn", return_value=mock_preexec)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_bash_command("echo test")

        env_dict = mock_run.call_args.kwargs["env"]
        assert env_dict["LD_PRELOAD"] == DEFAULT_SANDBOXER_PATH

    def test_dev_mode_no_preexec(self, mocker):
        """Development: run_bash_command has no sandbox."""
        mocker.patch.dict(os.environ, {}, clear=True)
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_bash_command("echo test")

        kwargs = mock_run.call_args.kwargs
        assert "preexec_fn" not in kwargs
        assert "pass_fds" not in kwargs


# =============================================================================
# Story 14.1: Shell State Persistence Tests
# =============================================================================


class TestParseNulEnv:
    """Tests for parse_nul_env() NUL-delimited environment parsing."""

    def test_empty_bytes(self):
        """Empty input returns empty dict."""
        assert parse_nul_env(b"") == {}

    def test_single_entry(self):
        """Single KEY=VALUE entry."""
        raw = b"HOME=/home/user\x00"
        assert parse_nul_env(raw) == {"HOME": "/home/user"}

    def test_multiple_entries(self):
        """Multiple entries separated by NUL."""
        raw = b"PATH=/usr/bin\x00HOME=/home/user\x00TERM=xterm\x00"
        result = parse_nul_env(raw)
        assert result == {"PATH": "/usr/bin", "HOME": "/home/user", "TERM": "xterm"}

    def test_value_with_newline(self):
        """Values containing newlines are parsed correctly."""
        raw = b"MULTI=line1\nline2\x00PATH=/usr/bin\x00"
        result = parse_nul_env(raw)
        assert result["MULTI"] == "line1\nline2"
        assert result["PATH"] == "/usr/bin"

    def test_value_with_equals(self):
        """Values containing = are parsed correctly."""
        raw = b"FORMULA=a=b+c\x00"
        result = parse_nul_env(raw)
        assert result["FORMULA"] == "a=b+c"

    def test_empty_value(self):
        """Empty values are preserved."""
        raw = b"EMPTY=\x00"
        result = parse_nul_env(raw)
        assert result["EMPTY"] == ""

    def test_trailing_nul(self):
        """Trailing NUL produces empty entry which is skipped."""
        raw = b"A=1\x00B=2\x00"
        result = parse_nul_env(raw)
        assert len(result) == 2

    def test_no_equals_skipped(self):
        """Entries without = are skipped."""
        raw = b"VALID=ok\x00INVALID\x00"
        result = parse_nul_env(raw)
        assert result == {"VALID": "ok"}


class TestSanitizeEnv:
    """Tests for sanitize_env() per-cycle sanitization."""

    def test_allowed_vars_pass_through(self):
        """Allowlisted variables pass through sanitize_env."""
        captured = {"PATH": "/usr/bin", "HOME": "/home/user", "TERM": "xterm"}
        result = sanitize_env(captured)
        assert result == captured

    def test_dangerous_vars_stripped(self):
        """Non-allowlisted variables are stripped."""
        captured = {
            "PATH": "/usr/bin",
            "LD_PRELOAD": "/tmp/evil.so",
            "BASH_ENV": "/tmp/evil.sh",
        }
        result = sanitize_env(captured)
        assert "LD_PRELOAD" not in result
        assert "BASH_ENV" not in result
        assert result["PATH"] == "/usr/bin"

    def test_prefix_vars_pass_through(self):
        """Variables with allowed prefixes pass through."""
        captured = {"LC_ALL": "en_US.UTF-8", "AEGISH_MODE": "dev", "XDG_DATA": "/data"}
        result = sanitize_env(captured)
        assert result == captured

    def test_export_ld_preload_blocked(self):
        """Simulates user running 'export LD_PRELOAD=evil' -- blocked on next cycle."""
        captured = {
            "PATH": "/usr/bin",
            "HOME": "/home/user",
            "LD_PRELOAD": "/tmp/evil.so",
            "LD_LIBRARY_PATH": "/tmp",
            "SHELLOPTS": "xtrace",
        }
        result = sanitize_env(captured)
        assert "LD_PRELOAD" not in result
        assert "LD_LIBRARY_PATH" not in result
        assert "SHELLOPTS" not in result


class TestIsBareCd:
    """Tests for is_bare_cd() command detection."""

    def test_bare_cd(self):
        assert is_bare_cd("cd") is True

    def test_cd_home(self):
        assert is_bare_cd("cd ~") is True

    def test_cd_dash(self):
        assert is_bare_cd("cd -") is True

    def test_cd_absolute(self):
        assert is_bare_cd("cd /tmp") is True

    def test_cd_relative(self):
        assert is_bare_cd("cd foo") is True

    def test_cd_tilde_user(self):
        assert is_bare_cd("cd ~root") is True

    def test_cd_with_leading_spaces(self):
        assert is_bare_cd("  cd /tmp") is True

    def test_cd_with_trailing_spaces(self):
        assert is_bare_cd("cd /tmp  ") is True

    def test_cd_and_ls_rejected(self):
        """Compound cd command is not bare cd."""
        assert is_bare_cd("cd /tmp && ls") is False

    def test_cd_semicolon_rejected(self):
        assert is_bare_cd("cd /tmp; ls") is False

    def test_cd_pipe_rejected(self):
        assert is_bare_cd("cd /tmp | echo") is False

    def test_cd_or_rejected(self):
        assert is_bare_cd("cd /tmp || echo fail") is False

    def test_cd_background_rejected(self):
        assert is_bare_cd("cd /tmp &") is False

    def test_not_cd(self):
        assert is_bare_cd("ls -la") is False

    def test_echo_cd(self):
        assert is_bare_cd("echo cd") is False


class TestResolveCd:
    """Tests for resolve_cd() directory resolution."""

    def test_bare_cd_to_home(self, tmp_path):
        """cd with no args resolves to HOME."""
        home = str(tmp_path)
        env = {"HOME": home}
        resolved, error = resolve_cd("", "/tmp", env)
        assert error is None
        assert resolved == os.path.realpath(home)

    def test_cd_tilde_to_home(self, tmp_path):
        """cd ~ resolves to HOME."""
        home = str(tmp_path)
        env = {"HOME": home}
        resolved, error = resolve_cd("~", "/tmp", env)
        assert error is None
        assert resolved == os.path.realpath(home)

    def test_cd_dash_to_oldpwd(self):
        """cd - resolves to OLDPWD."""
        env = {"OLDPWD": "/tmp"}
        resolved, error = resolve_cd("-", "/home", env)
        assert error is None
        assert resolved == os.path.realpath("/tmp")

    def test_cd_dash_no_oldpwd(self):
        """cd - with no OLDPWD returns error."""
        env = {}
        resolved, error = resolve_cd("-", "/home", env)
        assert resolved is None
        assert "OLDPWD not set" in error

    def test_cd_absolute_path(self):
        """cd /tmp resolves to /tmp."""
        resolved, error = resolve_cd("/tmp", "/home", {})
        assert error is None
        assert resolved == os.path.realpath("/tmp")

    def test_cd_relative_path(self, tmp_path):
        """cd relative resolves against current_dir."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        resolved, error = resolve_cd("subdir", str(tmp_path), {})
        assert error is None
        assert resolved == os.path.realpath(str(subdir))

    def test_cd_nonexistent_path(self):
        """cd to nonexistent path returns error."""
        resolved, error = resolve_cd("/nonexistent_path_xyz123", "/home", {})
        assert resolved is None
        assert "No such file or directory" in error


class TestExecuteCommandStatePersistence:
    """Tests for execute_command() environment capture and state persistence."""

    def test_returns_tuple(self):
        """execute_command returns (exit_code, env, cwd) tuple."""
        result = execute_command("true")
        assert isinstance(result, tuple)
        assert len(result) == 3
        exit_code, env, cwd = result
        assert exit_code == 0
        assert isinstance(env, dict)
        assert isinstance(cwd, str)

    def test_captures_env(self):
        """Captured env contains expected variables."""
        _, env, _ = execute_command("true")
        # PATH should be in captured env
        assert "PATH" in env

    def test_env_export_persists(self):
        """export VAR=value persists to returned env."""
        _, env, _ = execute_command("export AEGISH_TEST_VAR=hello")
        assert env.get("AEGISH_TEST_VAR") == "hello"

    def test_env_export_dangerous_stripped(self):
        """export of dangerous var is stripped by sanitize_env."""
        _, env, _ = execute_command("export LD_PRELOAD=/tmp/evil.so")
        assert "LD_PRELOAD" not in env

    def test_cwd_from_cd(self, tmp_path):
        """cd in command updates returned cwd."""
        target = str(tmp_path)
        _, _, cwd = execute_command(f"cd {target}")
        assert cwd == os.path.realpath(target)

    def test_passes_env_to_subprocess(self):
        """Env dict is passed to subprocess and available."""
        initial_env = _build_safe_env()
        initial_env["AEGISH_TEST_PASS"] = "from_parent"
        _, env, _ = execute_command(
            "true", env=initial_env,
        )
        assert env.get("AEGISH_TEST_PASS") == "from_parent"

    def test_passes_cwd_to_subprocess(self, tmp_path):
        """cwd is passed to subprocess."""
        exit_code, _, cwd = execute_command(
            "pwd", cwd=str(tmp_path),
        )
        assert exit_code == 0
        assert cwd == os.path.realpath(str(tmp_path))

    def test_exit_code_preserved_through_env_capture(self):
        """Exit code of user command preserved despite env -0 suffix."""
        exit_code, _, _ = execute_command("exit 42")
        assert exit_code == 42

    def test_sequential_env_persistence(self):
        """Env persists across sequential calls."""
        _, env1, _ = execute_command("export AEGISH_SEQ_TEST=round1")
        assert env1.get("AEGISH_SEQ_TEST") == "round1"

        _, env2, _ = execute_command(
            "export AEGISH_SEQ_TEST=round2", env=env1,
        )
        assert env2.get("AEGISH_SEQ_TEST") == "round2"

    def test_sequential_cwd_persistence(self, tmp_path):
        """cwd persists across sequential calls."""
        target = str(tmp_path)
        _, _, cwd1 = execute_command(f"cd {target}")
        assert cwd1 == os.path.realpath(target)

        # Next command uses cwd from previous
        exit_code, _, cwd2 = execute_command("pwd", cwd=cwd1)
        assert exit_code == 0
        assert cwd2 == os.path.realpath(target)


# =============================================================================
# Story 16.1: Sudo Post-Elevation Sandboxing Tests
# =============================================================================


class TestIsSudoCommand:
    """Tests for _is_sudo_command() detection."""

    def test_sudo_with_command(self):
        """'sudo cmd' is a sudo command."""
        assert _is_sudo_command("sudo ls") is True

    def test_bare_sudo(self):
        """'sudo' alone is a sudo command."""
        assert _is_sudo_command("sudo") is True

    def test_sudo_with_tab(self):
        """'sudo\\tcmd' is a sudo command."""
        assert _is_sudo_command("sudo\tls") is True

    def test_sudo_with_leading_spaces(self):
        """'  sudo cmd' is a sudo command."""
        assert _is_sudo_command("  sudo ls") is True

    def test_sudoers_not_sudo(self):
        """'sudoers' is NOT a sudo command."""
        assert _is_sudo_command("sudoers") is False

    def test_echo_sudo_not_sudo(self):
        """'echo sudo' is NOT a sudo command."""
        assert _is_sudo_command("echo sudo") is False

    def test_empty_string(self):
        """Empty string is NOT a sudo command."""
        assert _is_sudo_command("") is False

    def test_sudo_with_flags(self):
        """'sudo -u root ls' is a sudo command."""
        assert _is_sudo_command("sudo -u root ls") is True

    def test_sudoedit(self):
        """'sudoedit' is NOT a sudo command."""
        assert _is_sudo_command("sudoedit /etc/hosts") is False


class TestStripSudoPrefix:
    """Tests for _strip_sudo_prefix() prefix removal."""

    def test_simple_strip(self):
        """Strip sudo prefix from 'sudo ls -la'."""
        assert _strip_sudo_prefix("sudo ls -la") == "ls -la"

    def test_extra_whitespace(self):
        """Strip sudo prefix with extra whitespace."""
        assert _strip_sudo_prefix("  sudo   ls -la  ") == "ls -la"

    def test_bare_sudo(self):
        """Strip sudo prefix from bare 'sudo' returns empty string."""
        assert _strip_sudo_prefix("sudo") == ""

    def test_sudo_with_tab(self):
        """Strip sudo prefix with tab separator."""
        assert _strip_sudo_prefix("sudo\tls") == "ls"


class TestValidateSudoBinary:
    """Tests for _validate_sudo_binary() validation."""

    def test_valid_sudo_binary(self, mocker):
        """Valid: root-owned, SUID set."""
        mock_stat = MagicMock()
        mock_stat.st_uid = 0
        mock_stat.st_mode = stat.S_ISUID | stat.S_IFREG | 0o4755
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.stat", return_value=mock_stat)

        ok, msg = _validate_sudo_binary()
        assert ok is True
        assert msg == ""

    def test_missing_sudo_binary(self, mocker):
        """Invalid: sudo binary does not exist."""
        mocker.patch("os.path.exists", return_value=False)

        ok, msg = _validate_sudo_binary()
        assert ok is False
        assert "not found" in msg

    def test_not_root_owned(self, mocker):
        """Invalid: not owned by root."""
        mock_stat = MagicMock()
        mock_stat.st_uid = 1000
        mock_stat.st_mode = stat.S_ISUID | stat.S_IFREG | 0o4755
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.stat", return_value=mock_stat)

        ok, msg = _validate_sudo_binary()
        assert ok is False
        assert "not owned by root" in msg

    def test_no_suid_bit(self, mocker):
        """Invalid: SUID bit not set."""
        mock_stat = MagicMock()
        mock_stat.st_uid = 0
        mock_stat.st_mode = stat.S_IFREG | 0o0755  # No SUID
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.stat", return_value=mock_stat)

        ok, msg = _validate_sudo_binary()
        assert ok is False
        assert "SUID" in msg


class TestExecuteSudoSandboxed:
    """Tests for _execute_sudo_sandboxed() execution path."""

    def test_correct_subprocess_args(self, mocker):
        """Verify the correct subprocess args are passed."""
        mocker.patch("aegish.executor._validate_sudo_binary", return_value=(True, ""))
        mocker.patch("aegish.executor.validate_sandboxer_library", return_value=(True, ""))
        mocker.patch("aegish.executor.get_sandboxer_path", return_value="/opt/aegish/lib/landlock_sandboxer.so")
        mocker.patch("aegish.executor.get_runner_path", return_value="/opt/aegish/bin/runner")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        env = {"PATH": "/usr/bin"}
        _execute_sudo_sandboxed("sudo ls -la", 0, env, "/tmp")

        args = mock_run.call_args[0][0]
        assert args[0] == SUDO_BINARY_PATH
        assert args[1] == "env"
        assert args[2] == "LD_PRELOAD=/opt/aegish/lib/landlock_sandboxer.so"
        assert args[3] == "AEGISH_RUNNER_PATH=/opt/aegish/bin/runner"
        assert args[4] == "/opt/aegish/bin/runner"
        assert "--norc" in args
        assert "--noprofile" in args
        assert "-c" in args
        assert args[-1] == "ls -la"

    def test_no_preexec_fn(self, mocker):
        """Verify no preexec_fn is passed to subprocess."""
        mocker.patch("aegish.executor._validate_sudo_binary", return_value=(True, ""))
        mocker.patch("aegish.executor.validate_sandboxer_library", return_value=(True, ""))
        mocker.patch("aegish.executor.get_sandboxer_path", return_value="/opt/aegish/lib/sandboxer.so")
        mocker.patch("aegish.executor.get_runner_path", return_value="/opt/aegish/bin/runner")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        _execute_sudo_sandboxed("sudo echo test", 0, {"PATH": "/usr/bin"}, "/tmp")

        kwargs = mock_run.call_args.kwargs
        assert "preexec_fn" not in kwargs

    def test_env_returned_unchanged(self, mocker):
        """Verify original env and cwd are returned unchanged."""
        mocker.patch("aegish.executor._validate_sudo_binary", return_value=(True, ""))
        mocker.patch("aegish.executor.validate_sandboxer_library", return_value=(True, ""))
        mocker.patch("aegish.executor.get_sandboxer_path", return_value="/opt/aegish/lib/sandboxer.so")
        mocker.patch("aegish.executor.get_runner_path", return_value="/opt/aegish/bin/runner")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        original_env = {"PATH": "/usr/bin", "HOME": "/home/test"}
        original_cwd = "/home/test"
        rc, env, cwd = _execute_sudo_sandboxed(
            "sudo whoami", 0, original_env, original_cwd,
        )

        assert rc == 0
        assert env is original_env
        assert cwd is original_cwd

    def test_fallback_on_missing_sandboxer(self, mocker):
        """Falls back to execute_command without sudo on missing sandboxer."""
        mocker.patch("aegish.executor._validate_sudo_binary", return_value=(True, ""))
        mocker.patch("aegish.executor.validate_sandboxer_library",
                     return_value=(False, "Sandboxer not found"))
        mock_exec = mocker.patch("aegish.executor.execute_command",
                                 return_value=(0, {"PATH": "/usr/bin"}, "/tmp"))

        rc, env, cwd = _execute_sudo_sandboxed(
            "sudo ls", 0, {"PATH": "/usr/bin"}, "/tmp",
        )

        # Should fall back to execute_command with stripped command
        mock_exec.assert_called_once_with("ls", 0, {"PATH": "/usr/bin"}, "/tmp")

    def test_fallback_on_invalid_sudo_binary(self, mocker):
        """Falls back to execute_command without sudo on invalid sudo binary."""
        mocker.patch("aegish.executor._validate_sudo_binary",
                     return_value=(False, "sudo not found"))
        mock_exec = mocker.patch("aegish.executor.execute_command",
                                 return_value=(0, {"PATH": "/usr/bin"}, "/tmp"))

        rc, env, cwd = _execute_sudo_sandboxed(
            "sudo ls", 0, {"PATH": "/usr/bin"}, "/tmp",
        )

        mock_exec.assert_called_once_with("ls", 0, {"PATH": "/usr/bin"}, "/tmp")

    def test_bare_sudo_fallback(self, mocker):
        """Bare 'sudo' falls back to regular execute_command."""
        mocker.patch("aegish.executor._validate_sudo_binary", return_value=(True, ""))
        mocker.patch("aegish.executor.validate_sandboxer_library", return_value=(True, ""))
        mock_exec = mocker.patch("aegish.executor.execute_command",
                                 return_value=(0, {"PATH": "/usr/bin"}, "/tmp"))

        _execute_sudo_sandboxed("sudo", 0, {"PATH": "/usr/bin"}, "/tmp")

        # Bare sudo falls back to execute_command("sudo", ...)
        mock_exec.assert_called_once_with("sudo", 0, {"PATH": "/usr/bin"}, "/tmp")


class TestExecuteCommandSudoDelegation:
    """Tests for execute_command() delegation to _execute_sudo_sandboxed."""

    def test_delegates_for_sysadmin_production_sudo(self, mocker):
        """Delegates to sudo path for sysadmin + production + sudo command."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        mocker.patch("aegish.executor.get_role", return_value="sysadmin")
        mock_sudo = mocker.patch(
            "aegish.executor._execute_sudo_sandboxed",
            return_value=(0, {"PATH": "/usr/bin"}, "/tmp"),
        )

        rc, env, cwd = execute_command("sudo ls -la")

        mock_sudo.assert_called_once()
        assert rc == 0

    def test_no_delegation_for_default_role(self, mocker):
        """Default role does NOT delegate to sudo path."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        mocker.patch("aegish.executor.get_role", return_value="default")
        mock_sudo = mocker.patch("aegish.executor._execute_sudo_sandboxed")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        execute_command("sudo ls")

        mock_sudo.assert_not_called()

    def test_no_delegation_for_restricted_role(self, mocker):
        """Restricted role does NOT delegate to sudo path."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        mocker.patch("aegish.executor.get_role", return_value="restricted")
        mock_sudo = mocker.patch("aegish.executor._execute_sudo_sandboxed")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        execute_command("sudo ls")

        mock_sudo.assert_not_called()

    def test_no_delegation_in_dev_mode(self, mocker):
        """Development mode does NOT delegate to sudo path."""
        mocker.patch.dict(os.environ, {}, clear=True)
        mock_sudo = mocker.patch("aegish.executor._execute_sudo_sandboxed")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        execute_command("sudo ls")

        mock_sudo.assert_not_called()

    def test_no_delegation_for_non_sudo_command(self, mocker):
        """Non-sudo commands in production + sysadmin do NOT delegate."""
        mocker.patch.dict(os.environ, {"AEGISH_MODE": "production"}, clear=True)
        mocker.patch("aegish.executor.get_role", return_value="sysadmin")
        mock_sudo = mocker.patch("aegish.executor._execute_sudo_sandboxed")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        execute_command("ls -la")

        mock_sudo.assert_not_called()
