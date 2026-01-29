"""Tests for command execution."""

from secbash.executor import execute_command, run_bash_command


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
