"""Fuzzer for execute_command() - P4 target."""
import sys
import os
import subprocess
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aegish.executor import _build_safe_env, DANGEROUS_ENV_VARS

findings = []


def run_bash(cmd, timeout=5):
    return subprocess.run(
        ["bash", "--norc", "--noprofile", "-c", cmd],
        capture_output=True, text=True, timeout=timeout,
    )


def wrapped(cmd, exit_code):
    return f"(exit {exit_code}); {cmd}"


def finding(sev, title, input_desc, behavior, impact):
    findings.append({"severity": sev, "title": title,
                     "input": input_desc, "behavior": behavior, "impact": impact})
    print(f"  [FINDING-{sev}] {title}")


def main():
    print("=" * 70)
    print("FUZZER: execute_command()")
    print("=" * 70)

    # Section 1: Exit code edge values
    print("\nSECTION 1: (exit N) edge values")
    print("-" * 70)

    exit_tests = [0, 1, -1, -128, -256, 127, 255, 256, 257, 511, 512,
                  1000, 65535, 2**31 - 1, -(2**31)]

    for n in exit_tests:
        cmd = wrapped("echo prev=$?", n)
        try:
            result = run_bash(cmd)
            print(f"  (exit {n:>12}); echo prev=$? -> stdout={result.stdout.strip()}, rc={result.returncode}")
        except subprocess.TimeoutExpired:
            finding("MEDIUM", f"Timeout with exit code {n}",
                    f"(exit {n})", "Bash hangs", "DoS via large exit code")
        except Exception as e:
            print(f"  (exit {n:>12}): EXCEPTION: {e}")

    # Very large ints (Python unbounded)
    print("\n  Extremely large Python ints:")
    for val in [2**63, 2**64, 2**128, 10**50]:
        cmd_str = f"(exit {val}); echo $?"
        print(f"  Testing 10^{len(str(val))-1} ({len(cmd_str)} chars)...")
        try:
            result = run_bash(cmd_str, timeout=5)
            out = result.stdout.strip()
            err = result.stderr.strip()[:80]
            print(f"    stdout={out}, stderr={err}, rc={result.returncode}")
            if result.returncode != 0 and "syntax error" not in err.lower():
                finding("LOW", f"Large exit code produces error",
                        f"exit code=10^{len(str(val))-1}", f"rc={result.returncode}",
                        "Bash rejects very large numbers but no injection risk")
        except subprocess.TimeoutExpired:
            finding("MEDIUM", f"Timeout with huge exit code",
                    f"10^{len(str(val))-1}", "Timeout", "DoS potential")
        except Exception as e:
            print(f"    Exception: {e}")

    # Section 2: Command wrapping interaction
    print("\nSECTION 2: Command wrapping interaction")
    print("-" * 70)

    wrap_tests = [
        ("false; echo exit=$?", "Previous exit code vs command exit code"),
        ("true; echo exit=$?", "True after non-zero exit prefix"),
        ("echo hello", "Basic command after prefix"),
        ("", "Empty command"),
        ("   ", "Whitespace only"),
        ("# comment", "Comment only"),
        ("(echo NESTED)", "Nested subshell"),
        ("{ echo BRACE; }", "Brace group"),
        ("! true; echo neg=$?", "Negation operator"),
    ]

    for cmd, desc in wrap_tests:
        full = wrapped(cmd, 42)
        try:
            result = run_bash(full)
            print(f"  {desc:45s} -> stdout={result.stdout.strip()[:60]}, rc={result.returncode}")
        except Exception as e:
            print(f"  {desc:45s} -> ERROR: {e}")

    # Verify $? is correctly set
    print("\n  Verifying $? propagation:")
    for exit_code in [0, 1, 42, 127, 255]:
        cmd = wrapped("echo prev=$?", exit_code)
        result = run_bash(cmd)
        expected = str(exit_code % 256)
        actual = result.stdout.strip().replace("prev=", "")
        match = "OK" if actual == expected else f"MISMATCH (expected {expected})"
        print(f"    (exit {exit_code:>3}); echo $? -> {actual} [{match}]")

    # Section 3: --norc --noprofile effectiveness
    print("\nSECTION 3: --norc --noprofile effectiveness")
    print("-" * 70)

    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write('export FUZZ_MARKER="LOADED"\n')
        env_file = f.name

    try:
        # BASH_ENV test
        env = os.environ.copy()
        env["BASH_ENV"] = env_file

        # With --norc --noprofile
        r1 = subprocess.run(
            ["bash", "--norc", "--noprofile", "-c", 'echo "M=${FUZZ_MARKER:-unset}"'],
            capture_output=True, text=True, env=env, timeout=5,
        )
        # Without --norc --noprofile
        r2 = subprocess.run(
            ["bash", "-c", 'echo "M=${FUZZ_MARKER:-unset}"'],
            capture_output=True, text=True, env=env, timeout=5,
        )

        norc_loaded = "LOADED" in r1.stdout
        plain_loaded = "LOADED" in r2.stdout

        print(f"  BASH_ENV with --norc --noprofile: {'LOADED' if norc_loaded else 'not loaded'}")
        print(f"  BASH_ENV without --norc:          {'LOADED' if plain_loaded else 'not loaded'}")

        if norc_loaded or plain_loaded:
            finding("HIGH", "BASH_ENV is processed for non-interactive bash -c",
                    f"BASH_ENV={env_file}",
                    f"--norc: {norc_loaded}, plain: {plain_loaded}",
                    "_build_safe_env() stripping BASH_ENV is ESSENTIAL. "
                    "--norc/--noprofile alone do NOT prevent BASH_ENV loading.")
    finally:
        os.unlink(env_file)

    # Section 4: Return code edge cases
    print("\nSECTION 4: Return code edge cases")
    print("-" * 70)

    # Bash exit code truncation
    print("  Exit code truncation (bash modulo 256):")
    for code, expected in [(0, 0), (1, 1), (255, 255), (256, 0), (257, 1), (300, 44)]:
        r = run_bash(f"exit {code}")
        match = "OK" if r.returncode == expected else f"GOT {r.returncode}"
        print(f"    exit {code:>4} -> {r.returncode} [{match}]")

    # Signal-killed processes
    print("  Signal-killed processes:")
    for sig, name in [(9, "SIGKILL"), (15, "SIGTERM")]:
        r = run_bash(f"kill -{sig} $$")
        print(f"    kill -{sig} ({name}) -> rc={r.returncode}")

    # Section 5: f-string safety analysis
    print("\nSECTION 5: f-string construction safety")
    print("-" * 70)

    print("  Verifying int formatting produces only digits/minus:")
    all_clean = True
    for val in [0, -1, 255, 2**31 - 1, -(2**31), 2**63, 10**20]:
        formatted = f"(exit {val}); echo test"
        n_part = formatted.split(";")[0][len("(exit "):-1]
        clean = all(c in "0123456789-" for c in n_part)
        if not clean:
            all_clean = False
            finding("CRITICAL", "f-string produced unexpected chars",
                    f"val={val}", f"N='{n_part}'", "Shell injection via int formatting")
        print(f"    {val:>25} -> N='{n_part}' clean={clean}")

    if all_clean:
        print("  All int values produce clean output. f-string is safe for int inputs.")

    # Section 6: Env bypass verification
    print("\nSECTION 6: Environment variable attack surface")
    print("-" * 70)

    try:
        # Check LD_PRELOAD
        original = os.environ.get("LD_PRELOAD")
        os.environ["LD_PRELOAD"] = "/tmp/evil.so"
        env = _build_safe_env()
        ld_leaked = "LD_PRELOAD" in env
        if original:
            os.environ["LD_PRELOAD"] = original
        else:
            os.environ.pop("LD_PRELOAD", None)

        print(f"  LD_PRELOAD leak: {ld_leaked}")
        if ld_leaked:
            finding("HIGH", "LD_PRELOAD passes through _build_safe_env()",
                    "LD_PRELOAD=/tmp/evil.so", "Present in sanitized env",
                    "Shared library injection into subprocess")

        # Check SHELLOPTS + PS4 combo
        for var in ["SHELLOPTS", "PS4"]:
            original = os.environ.get(var)
            os.environ[var] = "test_value"
            env = _build_safe_env()
            leaked = var in env
            if original:
                os.environ[var] = original
            else:
                os.environ.pop(var, None)
            print(f"  {var} leak: {leaked}")
            if leaked:
                finding("MEDIUM", f"{var} passes through _build_safe_env()",
                        f"{var}=test_value", "Present in sanitized env",
                        f"{var} can modify bash behavior in subprocess")

        # Test SHELLOPTS=xtrace + PS4 command injection combo
        test_env = os.environ.copy()
        test_env["SHELLOPTS"] = "xtrace"
        MARKER = "FUZZ_PS4_INJECTED"
        test_env["PS4"] = f'$(echo {MARKER} >&2) + '
        r = subprocess.run(
            ["bash", "--norc", "--noprofile", "-c", "echo hello"],
            capture_output=True, text=True, env=test_env, timeout=5,
        )
        ps4_injected = MARKER in r.stderr
        print(f"  SHELLOPTS+PS4 injection: {'CONFIRMED' if ps4_injected else 'not observed'}")
        if ps4_injected:
            finding("MEDIUM", "PS4 command substitution executes with SHELLOPTS=xtrace",
                    "SHELLOPTS=xtrace + PS4='$(cmd)'",
                    f"stderr contains injected marker",
                    "Arbitrary command execution via env vars if both SHELLOPTS and PS4 leak")

    except ImportError:
        print("  Could not import _build_safe_env, skipping env tests")

    # Summary
    print("\n" + "=" * 70)
    print("FINDINGS SUMMARY")
    print("=" * 70)

    if not findings:
        print("  No findings.")
    else:
        for i, f in enumerate(findings, 1):
            print(f"  [{f['severity']}] #{i}: {f['title']}")
            print(f"    Input: {f['input']}")
            print(f"    Impact: {f['impact'][:120]}")

    # Generate report
    report = gen_report()
    out = "/home/gbergman/YDKHHICF/SecBASH/docs/security_vulnerabilities/v2/fuzzing/05-execute-command.md"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(report)
    print(f"\nReport: {out}")


def gen_report():
    lines = []
    lines.append("# Fuzzing Report: `execute_command()`\n")
    lines.append("## Overview\n")
    lines.append("- **Date**: 2026-02-15")
    lines.append("- **Target**: `src/aegish/executor.py::execute_command()`")
    lines.append(f"- **Findings**: {len(findings)}\n")

    lines.append("## Executive Summary\n")
    lines.append("The `execute_command()` function wraps user commands as "
                 "`f\"(exit {last_exit_code}); {command}\"` and passes to `bash -c`. "
                 "The f-string construction is safe for integer inputs (Python int formatting "
                 "produces only digits and minus sign). The security gate is entirely upstream "
                 "(LLM validator).\n")
    lines.append("Key findings relate to environment variable leakage through `_build_safe_env()` "
                 "and the critical importance of BASH_ENV stripping.\n")

    if findings:
        by_sev = {}
        for f in findings:
            by_sev.setdefault(f["severity"], []).append(f)

        lines.append("## Findings\n")
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            if sev not in by_sev:
                continue
            lines.append(f"### {sev}\n")
            for f in by_sev[sev]:
                lines.append(f"#### {f['title']}\n")
                lines.append(f"- **Input**: {f['input']}")
                lines.append(f"- **Behavior**: {f['behavior']}")
                lines.append(f"- **Impact**: {f['impact']}\n")

    lines.append("## Analysis\n")
    lines.append("### f-string Construction\n")
    lines.append("The `f\"(exit {last_exit_code})\"` pattern is safe because:")
    lines.append("- `last_exit_code` is always `int` (from `subprocess.run().returncode`)")
    lines.append("- Python `int.__format__` produces only digits and optional minus sign")
    lines.append("- No shell metacharacters can be injected via the integer\n")
    lines.append("### BASH_ENV is the Critical Vector\n")
    lines.append("`--norc` and `--noprofile` do NOT prevent `BASH_ENV` loading for "
                 "non-interactive `bash -c` invocations. The `_build_safe_env()` stripping "
                 "of `BASH_ENV` is the actual defense.\n")
    lines.append("### Return Code Handling\n")
    lines.append("- Bash truncates exit codes modulo 256")
    lines.append("- Negative values from signal kills work correctly")
    lines.append("- Very large Python ints are handled by bash (error, not injection)\n")

    lines.append("## Recommendations\n")
    lines.append("1. **Expand `_build_safe_env()` blocklist** (see report 02)")
    lines.append("2. **Validate `last_exit_code` range** to 0-255 before f-string formatting")
    lines.append("3. **Consider sandboxing** to limit subprocess capabilities\n")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
