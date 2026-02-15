"""Fuzzer for _build_safe_env() - P1 target."""
import sys
import os
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aegish.executor import _build_safe_env, DANGEROUS_ENV_VARS

MARKER = "FUZZ_MARKER_8xK9qL"

# Candidates: (name, description, severity, why_dangerous)
CANDIDATES = [
    ("LD_PRELOAD", "Shared library preload injection", "CRITICAL",
     "Loads attacker .so into every dynamically-linked binary"),
    ("LD_LIBRARY_PATH", "Library search path hijacking", "CRITICAL",
     "Redirects library lookups to attacker-controlled directory"),
    ("LD_AUDIT", "Runtime linker audit library", "CRITICAL",
     "Loads .so for linker audit callbacks before main()"),
    ("BASH_LOADABLES_PATH", "Bash loadable builtins path", "CRITICAL",
     "enable -f loads .so from this path as bash builtins"),
    ("SHELLOPTS", "Bash shell options", "HIGH",
     "Can enable xtrace, allexport, force behaviors"),
    ("BASHOPTS", "Bash shopt options", "HIGH",
     "Can force dangerous shopt options"),
    ("IFS", "Internal field separator", "HIGH",
     "Alters word splitting, breaks PATH lookups"),
    ("CDPATH", "cd search path", "MEDIUM",
     "cd resolves to unexpected directories"),
    ("GLOBIGNORE", "Glob pattern ignore", "MEDIUM",
     "Hides files from glob expansion"),
    ("PS0", "Pre-command prompt", "HIGH",
     "Expanded before each command; supports command substitution"),
    ("PS1", "Primary prompt", "MEDIUM",
     "Command substitution in interactive mode"),
    ("PS2", "Continuation prompt", "LOW",
     "Command substitution in interactive mode"),
    ("PS4", "Debug trace prompt", "HIGH",
     "Expanded during xtrace; command substitution executes code"),
    ("INPUTRC", "Readline config file", "MEDIUM",
     "Custom readline macros can execute shell commands"),
    ("HISTFILE", "History file location", "MEDIUM",
     "Write command history to attacker-controlled path"),
    ("HISTCONTROL", "History control", "LOW",
     "Manipulate history recording behavior"),
    ("EXECIGNORE", "Command ignore pattern", "HIGH",
     "Bash skips matching executables in PATH lookup"),
    ("LESSOPEN", "Less input preprocessor", "HIGH",
     "Pipe input through arbitrary command when less opens a file"),
    ("LESSCLOSE", "Less cleanup command", "MEDIUM",
     "Executed when less exits"),
    ("PYTHONSTARTUP", "Python startup script", "HIGH",
     "Auto-executed by interactive Python sessions"),
    ("PYTHONPATH", "Python module search path", "HIGH",
     "Module injection via malicious directory"),
    ("PERL5OPT", "Perl command-line options", "HIGH",
     "Inject -e to run arbitrary Perl code"),
    ("PERL5LIB", "Perl library path", "MEDIUM",
     "Module injection for Perl programs"),
    ("RUBYLIB", "Ruby library path", "MEDIUM",
     "Module injection for Ruby programs"),
    ("NODE_OPTIONS", "Node.js CLI options", "HIGH",
     "--require loads arbitrary JS before main script"),
    ("GIT_SSH", "Git SSH transport binary", "HIGH",
     "Git executes this instead of ssh"),
    ("GIT_SSH_COMMAND", "Git SSH command string", "HIGH",
     "Git executes this command for SSH transport"),
    ("GIT_EXEC_PATH", "Git subcommand search path", "HIGH",
     "Git loads subcommands from this directory"),
    ("GIT_TEMPLATE_DIR", "Git template directory", "MEDIUM",
     "git init copies hooks from this directory"),
    ("GIT_CONFIG_GLOBAL", "Git global config", "MEDIUM",
     "Arbitrary git config injection"),
    ("SSH_ASKPASS", "SSH password dialog", "MEDIUM",
     "Executed when SSH needs password without terminal"),
    ("SSH_ASKPASS_REQUIRE", "Force SSH_ASKPASS usage", "MEDIUM",
     "Set to 'force' to always run SSH_ASKPASS even with terminal"),
    ("BROWSER", "Default browser command", "MEDIUM",
     "xdg-open and webbrowser module execute this"),
    ("TMPDIR", "Temp directory", "LOW",
     "Symlink/race attacks on temp file creation"),
    ("ZDOTDIR", "Zsh config directory", "MEDIUM",
     "If zsh is invoked, loads .zshrc from here"),
    ("TERMCAP", "Terminal capabilities", "LOW",
     "Terminal escape sequence injection"),
    ("TERMINFO", "Terminal info directory", "LOW",
     "Terminal capability injection"),
    ("MAILPATH", "Mail notification paths", "LOW",
     "Bash expands message part which may contain command subst"),
    ("FPATH", "Zsh function path", "MEDIUM",
     "Autoloaded function hijacking in zsh"),
]


def var_leaks(name, value="test"):
    original = os.environ.get(name)
    os.environ[name] = value
    try:
        env = _build_safe_env()
        return name in env
    finally:
        if original is not None:
            os.environ[name] = original
        else:
            os.environ.pop(name, None)


def bash_test(env_name, env_value, command):
    """Run command in bash subprocess with the env var set, using _build_safe_env."""
    original = os.environ.get(env_name)
    os.environ[env_name] = env_value
    try:
        env = _build_safe_env()
        result = subprocess.run(
            ["bash", "--norc", "--noprofile", "-c", command],
            env=env, capture_output=True, text=True, timeout=5,
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), -1
    finally:
        if original is not None:
            os.environ[env_name] = original
        else:
            os.environ.pop(env_name, None)


BASH_FUNC_VARIANTS = [
    "BASH_FUNC_test%%", "BASH_FUNC_x()", "BASH_FUNC_",
    "BASH_FUNC_test", "bash_func_test%%", "Bash_Func_x%%",
    "BASH_FUN_x%%", "BASH_FUNCS_x%%",
]


def main():
    print("=" * 70)
    print("FUZZER: _build_safe_env()")
    print(f"Blocklist: {sorted(DANGEROUS_ENV_VARS)} ({len(DANGEROUS_ENV_VARS)} entries)")
    print("=" * 70)

    leaked = []
    blocked = []

    # Phase 1: Leakage test
    print("\nPHASE 1: Environment Variable Leakage Test")
    print("-" * 70)
    for name, desc, sev, why in CANDIDATES:
        leaks = var_leaks(name)
        status = "LEAKED" if leaks else "BLOCKED"
        print(f"  {status:8s} [{sev:8s}] {name:25s} {desc}")
        entry = {"name": name, "desc": desc, "severity": sev, "why": why, "leaked": leaks}
        if leaks:
            leaked.append(entry)
        else:
            blocked.append(entry)

    # Phase 2: BASH_FUNC_ prefix bypass
    print("\nPHASE 2: BASH_FUNC_ Prefix Bypass")
    print("-" * 70)
    func_results = []
    for variant in BASH_FUNC_VARIANTS:
        leaks = var_leaks(variant, "() { echo pwned; }")
        print(f"  {'LEAKED' if leaks else 'BLOCKED':8s} {repr(variant)}")
        func_results.append({"variant": variant, "leaked": leaks})

    # Phase 3: Exploitability for key leaked vars
    print("\nPHASE 3: Exploitability PoC")
    print("-" * 70)
    exploit_results = []

    for entry in leaked:
        name = entry["name"]
        sev = entry["severity"]
        if sev not in ("CRITICAL", "HIGH"):
            continue

        if name == "LD_PRELOAD":
            stdout, stderr, rc = bash_test(name, "/tmp/evil.so", f'echo "LD_PRELOAD=$LD_PRELOAD"')
            exploitable = "/tmp/evil.so" in stdout
        elif name == "LD_LIBRARY_PATH":
            stdout, stderr, rc = bash_test(name, "/tmp/evil", f'echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH"')
            exploitable = "/tmp/evil" in stdout
        elif name == "LD_AUDIT":
            stdout, stderr, rc = bash_test(name, "/tmp/evil.so", f'echo "LD_AUDIT=$LD_AUDIT"')
            exploitable = "/tmp/evil.so" in stdout
        elif name == "SHELLOPTS":
            stdout, stderr, rc = bash_test(name, "xtrace", "echo hello")
            exploitable = "+" in stderr
        elif name == "IFS":
            stdout, stderr, rc = bash_test(name, "/", 'var="a/b/c"; for x in $var; do echo "PART:$x"; done')
            exploitable = "PART:a" in stdout and "PART:b" in stdout
        elif name == "PS4":
            stdout, stderr, rc = bash_test(name, f'$(echo {MARKER} >&2) + ', 'set -x; echo test')
            exploitable = MARKER in stderr
        elif name == "LESSOPEN":
            stdout, stderr, rc = bash_test(name, f'|echo {MARKER}; cat %s', f'echo "LESSOPEN=$LESSOPEN"')
            exploitable = MARKER in stdout or "LESSOPEN=|echo" in stdout
        elif name == "PYTHONPATH":
            stdout, stderr, rc = bash_test(name, "/tmp/evil_py", 'python3 -c "import sys; print(sys.path)"')
            exploitable = "/tmp/evil_py" in stdout
        elif name == "NODE_OPTIONS":
            stdout, stderr, rc = bash_test(name, "--require /tmp/evil.js", f'echo "NODE_OPTIONS=$NODE_OPTIONS"')
            exploitable = "/tmp/evil.js" in stdout
        elif name == "EXECIGNORE":
            stdout, stderr, rc = bash_test(name, "*/sudo", f'echo "EXECIGNORE=$EXECIGNORE"')
            exploitable = "*/sudo" in stdout
        elif name == "GIT_SSH_COMMAND":
            stdout, stderr, rc = bash_test(name, f'echo {MARKER}', f'echo "GIT_SSH_COMMAND=$GIT_SSH_COMMAND"')
            exploitable = MARKER in stdout
        elif name == "BASH_LOADABLES_PATH":
            stdout, stderr, rc = bash_test(name, "/tmp/evil_builtins", f'echo "BASH_LOADABLES_PATH=$BASH_LOADABLES_PATH"')
            exploitable = "/tmp/evil_builtins" in stdout
        elif name == "PYTHONSTARTUP":
            stdout, stderr, rc = bash_test(name, "/tmp/evil_startup.py", f'echo "PYTHONSTARTUP=$PYTHONSTARTUP"')
            exploitable = "/tmp/evil_startup.py" in stdout
        elif name == "PERL5OPT":
            stdout, stderr, rc = bash_test(name, f"-e system('echo {MARKER}')", f'echo "PERL5OPT=$PERL5OPT"')
            exploitable = MARKER in stdout or "PERL5OPT" in stdout
        elif name == "GIT_SSH":
            stdout, stderr, rc = bash_test(name, "/tmp/evil_ssh", f'echo "GIT_SSH=$GIT_SSH"')
            exploitable = "/tmp/evil_ssh" in stdout
        elif name == "GIT_EXEC_PATH":
            stdout, stderr, rc = bash_test(name, "/tmp/evil_git", f'echo "GIT_EXEC_PATH=$GIT_EXEC_PATH"')
            exploitable = "/tmp/evil_git" in stdout
        elif name == "PS0":
            stdout, stderr, rc = bash_test(name, f'$(echo {MARKER} >&2)', 'echo test')
            exploitable = MARKER in stderr
        elif name == "BASHOPTS":
            stdout, stderr, rc = bash_test(name, "extglob", f'echo "BASHOPTS=$BASHOPTS"')
            exploitable = "extglob" in stdout
        else:
            stdout, stderr, rc = bash_test(name, MARKER, f'echo "${name}=${{{name}}}"')
            exploitable = MARKER in stdout

        status = "EXPLOITABLE" if exploitable else "passed-through"
        print(f"  {status:16s} {name}")
        exploit_results.append({"name": name, "exploitable": exploitable, "stdout": stdout[:120], "stderr": stderr[:120]})

    # Phase 4: Case sensitivity
    print("\nPHASE 4: Case Sensitivity")
    print("-" * 70)
    case_results = []
    for var in sorted(DANGEROUS_ENV_VARS):
        for variant in [var.lower(), var.capitalize()]:
            if variant == var:
                continue
            leaks = var_leaks(variant, "test")
            print(f"  {variant:25s} -> {'leaked' if leaks else 'blocked'}")
            case_results.append({"original": var, "variant": variant, "leaked": leaks})

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    crit = [e for e in leaked if e["severity"] == "CRITICAL"]
    high = [e for e in leaked if e["severity"] == "HIGH"]
    print(f"  Total tested: {len(CANDIDATES)}")
    print(f"  Blocked: {len(blocked)}")
    print(f"  Leaked: {len(leaked)} (CRITICAL: {len(crit)}, HIGH: {len(high)})")
    print(f"  BASH_FUNC_ bypass: {sum(1 for r in func_results if r['leaked'])} leaked")

    if crit:
        print("\n  *** CRITICAL ***")
        for e in crit:
            print(f"    {e['name']}: {e['why']}")
    if high:
        print("\n  *** HIGH ***")
        for e in high:
            print(f"    {e['name']}: {e['why']}")

    # Generate report
    report = generate_report(leaked, blocked, func_results, exploit_results, case_results)
    out = "/home/gbergman/YDKHHICF/SecBASH/docs/security_vulnerabilities/v2/fuzzing/02-build-safe-env.md"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(report)
    print(f"\nReport: {out}")


def generate_report(leaked, blocked, func_results, exploit_results, case_results):
    lines = []
    lines.append("# Fuzzing Report: `_build_safe_env()`\n")
    lines.append("## Overview\n")
    lines.append(f"- **Date**: 2026-02-15")
    lines.append(f"- **Target**: `src/aegish/executor.py::_build_safe_env()`")
    lines.append(f"- **Current blocklist size**: {len(DANGEROUS_ENV_VARS)} entries")
    lines.append(f"- **Vars tested**: {len(CANDIDATES)}")
    lines.append(f"- **Leaked through**: {len(leaked)}")
    lines.append(f"- **Blocked**: {len(blocked)}\n")

    crit = [e for e in leaked if e["severity"] == "CRITICAL"]
    high = [e for e in leaked if e["severity"] == "HIGH"]
    med = [e for e in leaked if e["severity"] == "MEDIUM"]

    lines.append("## Severity Summary\n")
    lines.append("| Severity | Leaked Count |")
    lines.append("|----------|-------------|")
    lines.append(f"| CRITICAL | {len(crit)} |")
    lines.append(f"| HIGH | {len(high)} |")
    lines.append(f"| MEDIUM | {len(med)} |")
    lines.append(f"| LOW | {len([e for e in leaked if e['severity'] == 'LOW'])} |\n")

    lines.append("## Executive Summary\n")
    lines.append(f"The `_build_safe_env()` blocklist contains only {len(DANGEROUS_ENV_VARS)} entries. "
                 f"Testing {len(CANDIDATES)} known-dangerous environment variables reveals "
                 f"**{len(leaked)} that leak through**, including {len(crit)} CRITICAL and {len(high)} HIGH severity.\n")

    lines.append("## Leaked Variables\n")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        sev_leaked = [e for e in leaked if e["severity"] == sev]
        if not sev_leaked:
            continue
        lines.append(f"### {sev}\n")
        lines.append("| Variable | Description | Why Dangerous |")
        lines.append("|----------|-------------|---------------|")
        for e in sev_leaked:
            lines.append(f"| `{e['name']}` | {e['desc']} | {e['why']} |")
        lines.append("")

    lines.append("## Exploitability Results\n")
    lines.append("| Variable | Exploitable | Notes |")
    lines.append("|----------|:-----------:|-------|")
    for r in exploit_results:
        mark = "YES" if r["exploitable"] else "passed through"
        notes = r["stdout"][:80] if r["stdout"] else r["stderr"][:80]
        lines.append(f"| `{r['name']}` | {mark} | `{notes}` |")
    lines.append("")

    func_leaked = [r for r in func_results if r["leaked"]]
    lines.append(f"## BASH_FUNC_ Bypass ({len(func_leaked)} leaked)\n")
    lines.append("| Variant | Status |")
    lines.append("|---------|--------|")
    for r in func_results:
        lines.append(f"| `{r['variant']}` | {'LEAKED' if r['leaked'] else 'blocked'} |")
    lines.append("")

    lines.append("## Recommendations\n")
    lines.append("### 1. CRITICAL: Expand blocklist with high-impact variables\n")
    lines.append("```python")
    lines.append("DANGEROUS_ENV_VARS = {")
    lines.append('    # Current')
    lines.append('    "BASH_ENV", "ENV", "PROMPT_COMMAND", "EDITOR", "VISUAL",')
    lines.append('    "PAGER", "GIT_PAGER", "MANPAGER",')
    lines.append('    # Add: Library injection')
    lines.append('    "LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT",')
    lines.append('    "BASH_LOADABLES_PATH",')
    lines.append('    # Add: Shell behavior modification')
    lines.append('    "SHELLOPTS", "BASHOPTS", "IFS", "EXECIGNORE",')
    lines.append('    "PS0", "PS4", "CDPATH", "GLOBIGNORE",')
    lines.append('    # Add: Program-specific injection')
    lines.append('    "PYTHONSTARTUP", "PYTHONPATH", "PERL5OPT", "PERL5LIB",')
    lines.append('    "RUBYLIB", "NODE_OPTIONS",')
    lines.append('    # Add: Git hijacking')
    lines.append('    "GIT_SSH", "GIT_SSH_COMMAND", "GIT_EXEC_PATH",')
    lines.append('    "GIT_TEMPLATE_DIR", "GIT_CONFIG_GLOBAL",')
    lines.append('    # Add: Other')
    lines.append('    "LESSOPEN", "LESSCLOSE", "INPUTRC", "SSH_ASKPASS",')
    lines.append('}')
    lines.append("```\n")
    lines.append("### 2. Consider allowlist approach\n")
    lines.append("Instead of blocklisting dangerous vars, allowlist only needed ones "
                 "(PATH, HOME, USER, LANG, TERM, etc.).\n")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
