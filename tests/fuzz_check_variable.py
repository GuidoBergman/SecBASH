"""Fuzzer for _check_variable_in_command_position() - P0 target."""
import sys
import os
import time
import signal
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import bashlex
from aegish.validator import (
    _check_variable_in_command_position,
    _find_var_in_command_position,
)


@dataclass
class Finding:
    category: str
    severity: str
    input_cmd: str
    expected: str
    actual: str
    security_impact: str
    exception_type: str | None = None
    exception_msg: str | None = None


@dataclass
class Results:
    total: int = 0
    passed: int = 0
    findings: list = field(default_factory=list)


def check_parse(cmd):
    try:
        bashlex.parse(cmd)
        return True, None
    except Exception as e:
        return False, (type(e).__name__, str(e)[:200])


def test_fn(cmd, timeout=5):
    """Call _check_variable_in_command_position with timeout protection."""
    start = time.time()

    def handler(signum, frame):
        raise TimeoutError()

    old = signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)
    try:
        result = _check_variable_in_command_position(cmd)
        elapsed = time.time() - start
        return result, elapsed, False
    except TimeoutError:
        return None, time.time() - start, True
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def run_fuzzer():
    results = Results()

    # =========================================================================
    # CATEGORY 1: BASHLEX CRASHERS
    # =========================================================================
    print("=" * 70)
    print("CATEGORY 1: BASHLEX CRASHERS")
    print("=" * 70)

    crashers = {
        "unclosed-single-quote": "X=bash; $X '",
        "unclosed-double-quote": 'X=bash; $X "',
        "unclosed-backtick": "X=bash; $X `",
        "unmatched-paren": "X=bash; $X (",
        "unmatched-brace": "X=bash; $X {",
        "null-byte": "X=bash; $X\x00",
        "unicode-cmd": "X=bash; \u0410\u0411\u0412 $X",
        "process-sub": "X=bash; $X <(echo hi)",
        "array-syntax": "arr=(bash); ${arr[0]}",
        "extglob": "X=bash; $X +(a|b)",
        "coproc": "coproc X=bash; $X",
        "select": "select i in a; do $CMD; done",
        "arith-for": "for ((i=0;i<1;i++)); do $CMD; done",
        "function-keyword": "function f { $CMD; }; f",
        "here-string": "X=bash; $X <<< 'hello'",
        "nested-100-parens": "(" * 100 + "echo" + ")" * 100,
        "backslash-newline": "X=\\\nbash; $X",
        "cr-in-command": "X=bash;\r$X",
        "tab-only": "\t",
        "ansi-escape": "X=bash; \x1b[31m$X",
        "heredoc-unclosed": "X=bash; $X << 'EOF'",
        "double-semicolon": "X=bash;; $X",
        "ampersand-only": "&",
        "pipe-only": "|",
        "triple-pipe": "X=bash ||| $X",
    }

    for name, cmd in crashers.items():
        results.total += 1
        parseable, exc = check_parse(cmd)
        result, elapsed, timed_out = test_fn(cmd)

        if timed_out:
            results.findings.append(Finding(
                "timeout", "HIGH", cmd,
                "Complete within 5s", f"TIMEOUT {elapsed:.1f}s",
                f"Hang in validator: {name}",
            ))
            print(f"  [TIMEOUT] {name}")
        elif not parseable:
            results.findings.append(Finding(
                "crasher", "MEDIUM", cmd,
                "Parse or handle gracefully",
                f"Crash: {exc[0] if exc else '?'}",
                f"Parser crash, falls to LLM: {name}",
                exc[0] if exc else None, exc[1] if exc else None,
            ))
            print(f"  [CRASH] {name}: {exc[0] if exc else '?'}")
        else:
            results.passed += 1
            print(f"  [OK] {name}")

    # =========================================================================
    # CATEGORY 2: EVASION VIA UNHANDLED NODE KINDS
    # =========================================================================
    print("\n" + "=" * 70)
    print("CATEGORY 2: EVASION VIA UNHANDLED NODE KINDS")
    print("=" * 70)

    evasion_tests = [
        # (name, command, should_warn, description)
        # Control flow constructs
        ("for-loop-var-cmd", "for i in bash; do $i; done", True,
         "Variable as command in for loop body"),
        ("if-then-var-cmd", "if true; then $CMD; fi", True,
         "Variable as command in if-then body"),
        ("if-else-var-cmd", "if false; then echo ok; else $CMD; fi", True,
         "Variable as command in else branch"),
        ("while-var-cmd", "while true; do $CMD; break; done", True,
         "Variable as command in while loop"),
        ("until-var-cmd", "until false; do $CMD; break; done", True,
         "Variable as command in until loop"),
        ("case-var-cmd", "case x in x) $CMD;; esac", True,
         "Variable as command in case branch"),
        # Assignment + execution patterns
        ("assign-then-for", "CMD=bash; for i in 1; do $CMD; done", True,
         "Assignment then for-loop execution"),
        ("assign-then-if", "CMD=bash; if true; then $CMD; fi", True,
         "Assignment then if-then execution"),
        ("assign-then-while", "CMD=bash; while true; do $CMD; break; done", True,
         "Assignment then while-loop execution"),
        # Subshells and brace groups
        ("subshell-var-cmd", "(CMD=bash; $CMD)", True,
         "Assignment + execution in subshell"),
        ("brace-group-var-cmd", "{ CMD=bash; $CMD; }", True,
         "Assignment + execution in brace group"),
        # Pipelines (should be detected - no has_assignment needed)
        ("pipeline-var-first", "$CMD | grep foo", True,
         "Variable as first command in pipeline"),
        ("pipeline-var-second", "echo hi | $CMD", True,
         "Variable as second command in pipeline"),
        ("pipeline-var-middle", "echo hi | $CMD | grep foo", True,
         "Variable in middle of pipeline"),
        # Classic evasion patterns
        ("split-concat", "a=ba; b=sh; $a$b", True,
         "Split-and-concatenate variable execution"),
        ("assign-in-list", "X=bash; $X", True,
         "Simple assignment then execution via list"),
        # Nested constructs
        ("nested-for-in-if", "if true; then for i in 1; do $CMD; done; fi", True,
         "Nested for inside if"),
        ("nested-if-in-while", "while true; do if true; then $CMD; fi; break; done", True,
         "Nested if inside while"),
        # Function definitions
        ("function-body-var", "f() { $CMD; }", True,
         "Variable as command in function body"),
        # has_assignment bypass
        ("bare-var-no-assign", "$CMD", True,
         "Bare variable as command without visible assignment"),
        ("export-then-exec", "export CMD=bash; $CMD", True,
         "Export as assignment, then variable as command"),
        # Logical operators
        ("and-var-cmd", "true && $CMD", True,
         "Variable as command after &&"),
        ("or-var-cmd", "false || $CMD", True,
         "Variable as command after ||"),
        ("assign-and-var", "CMD=bash; true && $CMD", True,
         "Assignment, then && with variable"),
        # Safe commands (should NOT warn)
        ("echo-safe", "echo hello", False,
         "Simple echo - should not warn"),
        ("ls-safe", "ls -la", False,
         "Simple ls - should not warn"),
        ("pipe-safe", "echo hi | grep hi", False,
         "Simple pipeline - should not warn"),
        ("for-safe", "for i in 1 2 3; do echo $i; done", False,
         "For loop with echo - should not warn"),
    ]

    fn_count = 0
    evade_crash_count = 0
    fp_count = 0

    for name, cmd, should_warn, desc in evasion_tests:
        results.total += 1
        result, elapsed, timed_out = test_fn(cmd)
        parseable, exc = check_parse(cmd)
        warned = result is not None and result.get("action") == "warn"

        if timed_out:
            results.findings.append(Finding(
                "evasion-timeout", "HIGH", cmd,
                "Complete within 5s", f"TIMEOUT {elapsed:.1f}s",
                f"Hang on evasion test: {desc}",
            ))
            print(f"  [TIMEOUT] {name}")
        elif should_warn and not warned:
            if not parseable:
                sev = "CRITICAL" if any(k in cmd.lower() for k in ["bash", "sh", "rm"]) else "HIGH"
                results.findings.append(Finding(
                    "evasion-via-crasher", sev, cmd,
                    "WARN", f"None (crash: {exc[0] if exc else '?'})",
                    f"Evasion via parser crash: {desc}",
                    exc[0] if exc else None, exc[1] if exc else None,
                ))
                evade_crash_count += 1
                print(f"  [EVASION-CRASH] {name}: {desc}")
            else:
                results.findings.append(Finding(
                    "false-negative", "CRITICAL", cmd,
                    "WARN", "None (not detected)",
                    f"AST walker miss: {desc}",
                ))
                fn_count += 1
                print(f"  [FALSE NEGATIVE] {name}: {desc}")
        elif not should_warn and warned:
            results.findings.append(Finding(
                "false-positive", "LOW", cmd,
                "None", f"WARN: {result.get('reason', '?')}",
                f"False alarm: {desc}",
            ))
            fp_count += 1
            print(f"  [FALSE POSITIVE] {name}: {desc}")
        else:
            results.passed += 1
            det = "detected" if warned else "correctly safe"
            print(f"  [OK] {name}: {det}")

    print(f"\n  False negatives: {fn_count}, Crasher evasions: {evade_crash_count}, False positives: {fp_count}")

    # =========================================================================
    # CATEGORY 3: MALICIOUS COMMANDS THAT CRASH BASHLEX
    # =========================================================================
    print("\n" + "=" * 70)
    print("CATEGORY 3: MALICIOUS CRASHER BYPASS")
    print("=" * 70)

    malicious_crashers = {
        "case-assign-exec": "case x in x) X=bash; $X;; esac",
        "heredoc-unclosed-var": "X=bash; $X << 'EOF'",
        "process-sub-var": "X=bash; $X <(echo hello)",
        "array-exec": "arr=(bash); ${arr[0]}",
        "extglob-var": "X=bash; $X +(a|b)",
        "coproc-var": "coproc $X",
        "select-var": "X=bash; select i in a; do $X; done",
        "arith-for-exec": "for ((i=0;i<1;i++)); do X=bash; $X; done",
        "function-alt-exec": "function f { X=bash; $X; }; f",
        "eval-constructed": "X='rm -rf /'; eval $X",
        "source-var": "X=/tmp/malicious.sh; source $X",
        "dot-var": "X=/tmp/malicious.sh; . $X",
        "exec-var": "X=bash; exec $X",
        "compound-cmd-sub": "X=bash; $(${X})",
        "multiline-evasion": "X=bash\n$X",
        "unicode-var-name": "\u0410=bash; $\u0410",
    }

    mc_crash = 0
    mc_evade = 0
    for name, cmd in malicious_crashers.items():
        results.total += 1
        parseable, exc = check_parse(cmd)
        result, elapsed, timed_out = test_fn(cmd)

        if timed_out:
            results.findings.append(Finding(
                "malicious-timeout", "CRITICAL", cmd,
                "WARN or parse", f"TIMEOUT {elapsed:.1f}s",
                f"Malicious command hangs validator: {name}",
            ))
            print(f"  [TIMEOUT] {name}")
        elif not parseable:
            mc_crash += 1
            sev = "CRITICAL" if any(k in cmd for k in ["bash", "rm", "eval"]) else "HIGH"
            results.findings.append(Finding(
                "malicious-crasher", sev, cmd,
                "WARN", f"None (crash: {exc[0] if exc else '?'})",
                f"Malicious bypass via crash: {name}",
                exc[0] if exc else None, exc[1] if exc else None,
            ))
            print(f"  [CRASH-BYPASS] {name}: {exc[0] if exc else '?'}")
        elif result is None:
            mc_evade += 1
            results.findings.append(Finding(
                "malicious-evasion", "CRITICAL", cmd,
                "WARN", "None (parsed but not detected)",
                f"Malicious evasion: {name}",
            ))
            print(f"  [EVASION] {name}")
        else:
            results.passed += 1
            print(f"  [DETECTED] {name}")

    print(f"\n  Crasher bypasses: {mc_crash}, AST evasions: {mc_evade}")

    # =========================================================================
    # CATEGORY 4: PERFORMANCE / HANG
    # =========================================================================
    print("\n" + "=" * 70)
    print("CATEGORY 4: PERFORMANCE")
    print("=" * 70)

    slow_inputs = {
        "1000-semicolons": "; ".join(["echo hi"] * 1000),
        "1000-pipes": " | ".join(["echo hi"] * 1000),
        "many-assignments": "; ".join([f"x{i}=v{i}" for i in range(500)]) + "; $x499",
        "many-and": " && ".join(["echo hi"] * 500),
        "long-var-value": "X=" + "a" * 5000 + "; $X",
    }

    for name, cmd in slow_inputs.items():
        results.total += 1
        result, elapsed, timed_out = test_fn(cmd, timeout=5)
        if timed_out:
            results.findings.append(Finding(
                "performance-hang", "HIGH",
                cmd[:100] + "..." if len(cmd) > 100 else cmd,
                "< 5s", f"TIMEOUT {elapsed:.1f}s",
                f"Hang: {name}",
            ))
            print(f"  [TIMEOUT] {name}: >{elapsed:.1f}s")
        elif elapsed > 1.0:
            results.findings.append(Finding(
                "performance-slow", "MEDIUM",
                cmd[:100] + "..." if len(cmd) > 100 else cmd,
                "< 1s", f"{elapsed:.2f}s",
                f"Slow: {name}",
            ))
            print(f"  [SLOW] {name}: {elapsed:.2f}s")
        else:
            results.passed += 1
            print(f"  [OK] {name}: {elapsed:.3f}s")

    # =========================================================================
    # CATEGORY 5: AST NODE KIND COVERAGE
    # =========================================================================
    print("\n" + "=" * 70)
    print("CATEGORY 5: NODE KIND COVERAGE")
    print("=" * 70)

    node_tests = [
        ("top-level-list", "X=bash; $X", True, "list"),
        ("pipeline", "echo hi | $CMD", True, "pipeline"),
        ("compound-brace", "{ X=bash; $X; }", True, "compound->list"),
        ("compound-subshell", "(X=bash; $X)", True, "compound->list"),
        ("compound-for", "for i in bash; do $i; done", True, "compound->for->list"),
        ("compound-while", "while true; do X=bash; $X; done", True, "compound->while->list"),
        ("compound-if", "if true; then X=bash; $X; fi", True, "compound->if->list"),
        ("compound-until", "X=bash; until $X; do echo; done", True, "compound->until"),
    ]

    for name, cmd, should_warn, path in node_tests:
        results.total += 1
        result, elapsed, timed_out = test_fn(cmd)
        warned = result is not None and result.get("action") == "warn"
        parseable, _ = check_parse(cmd)

        if should_warn and not warned and parseable:
            results.findings.append(Finding(
                "node-kind-gap", "CRITICAL", cmd,
                "WARN", "None",
                f"AST path '{path}' NOT traversed",
            ))
            print(f"  [GAP] {name}: '{path}' NOT COVERED")
        elif should_warn and not warned and not parseable:
            print(f"  [CRASH] {name}: bashlex can't parse")
        elif should_warn and warned:
            results.passed += 1
            print(f"  [COVERED] {name}: '{path}' detected")
        else:
            results.passed += 1
            print(f"  [OK] {name}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total tests: {results.total}")
    print(f"  Passed: {results.passed}")
    print(f"  Findings: {len(results.findings)}")

    by_sev = {}
    by_cat = {}
    for f in results.findings:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
        by_cat[f.category] = by_cat.get(f.category, 0) + 1

    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        if sev in by_sev:
            print(f"    {sev}: {by_sev[sev]}")
    for cat, c in sorted(by_cat.items()):
        print(f"    {cat}: {c}")

    return results


def esc(s):
    return (s.replace("`", "\\`").replace("\x00", "\\x00")
             .replace("\n", "\\n").replace("\r", "\\r")
             .replace("\t", "\\t").replace("\x1b", "\\x1b"))


def generate_report(results):
    lines = []
    lines.append("# Fuzzing Report: `_check_variable_in_command_position()`\n")
    lines.append("## Overview\n")
    lines.append(f"- **Date**: 2026-02-15")
    lines.append(f"- **Target**: `src/aegish/validator.py::_check_variable_in_command_position()`")
    lines.append(f"- **Total tests**: {results.total}")
    lines.append(f"- **Findings**: {len(results.findings)}\n")

    by_sev = {}
    for f in results.findings:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1

    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        if s in by_sev:
            lines.append(f"| {s} | {by_sev[s]} |")
    lines.append("")

    lines.append("## Executive Summary\n")
    lines.append("The `_check_variable_in_command_position()` function has a broad `except Exception` "
                 "handler (line 117) that silently swallows all bashlex parse errors, returning `None` "
                 "(i.e., 'safe'). Any command that crashes bashlex bypasses the static validator.\n")
    lines.append("The AST walker (`_find_var_in_command_position`) only handles: "
                 "`pipeline`, `command`, `list`, and `compound`. Control-flow nodes "
                 "(`for`, `if`, `while`, `until`) inside `compound.list` are iterated "
                 "but silently skipped.\n")

    by_cat = {}
    for f in results.findings:
        by_cat.setdefault(f.category, []).append(f)

    cat_order = [
        ("node-kind-gap", "AST Node Kind Gaps"),
        ("false-negative", "False Negatives (Parsed but Undetected)"),
        ("malicious-evasion", "Malicious Command Evasions"),
        ("malicious-crasher", "Malicious Crasher Bypasses"),
        ("evasion-via-crasher", "Evasion via Parser Crash"),
        ("performance-hang", "Performance Hangs"),
        ("performance-slow", "Performance Issues"),
        ("malicious-timeout", "Malicious Timeouts"),
        ("evasion-timeout", "Evasion Timeouts"),
        ("crasher", "General Parser Crashes"),
        ("timeout", "General Timeouts"),
        ("false-positive", "False Positives"),
    ]

    for key, label in cat_order:
        if key not in by_cat:
            continue
        findings = by_cat[key]
        lines.append(f"## {label}\n")
        lines.append(f"**Count: {len(findings)}**\n")
        for i, f in enumerate(findings, 1):
            lines.append(f"### {i}. [{f.severity}] `{esc(f.input_cmd[:120])}`\n")
            lines.append(f"- **Input**: `{esc(f.input_cmd)}`")
            lines.append(f"- **Expected**: {f.expected}")
            lines.append(f"- **Actual**: {f.actual}")
            lines.append(f"- **Security Impact**: {f.security_impact}")
            if f.exception_type:
                lines.append(f"- **Exception**: `{f.exception_type}: {esc(f.exception_msg or '')}`")
            lines.append("")

    lines.append("## Recommendations\n")
    lines.append("### 1. CRITICAL: Handle `for`, `if`, `while`, `until` in AST walker\n")
    lines.append("```python")
    lines.append("elif node.kind in ('for', 'if', 'while', 'until'):")
    lines.append("    for part in node.parts:")
    lines.append("        if part.kind == 'list':")
    lines.append("            local_assign = has_assignment or any(")
    lines.append("                sub.kind == 'assignment'")
    lines.append("                for p in part.parts if p.kind == 'command'")
    lines.append("                for sub in p.parts)")
    lines.append("            result = _find_var_in_command_position(part.parts, local_assign)")
    lines.append("            if result is not None:")
    lines.append("                return result")
    lines.append("```\n")
    lines.append("### 2. HIGH: Narrow the exception handler\n")
    lines.append("Replace `except Exception` with specific bashlex exceptions.\n")
    lines.append("### 3. MEDIUM: Add generic recursive fallback\n")
    lines.append("```python")
    lines.append("else:")
    lines.append("    for attr in ('parts', 'list'):")
    lines.append("        children = getattr(node, attr, None)")
    lines.append("        if children:")
    lines.append("            result = _find_var_in_command_position(children, has_assignment)")
    lines.append("            if result is not None:")
    lines.append("                return result")
    lines.append("```\n")
    lines.append("### 4. MEDIUM: Remove `has_assignment` requirement for `command` branch\n")
    lines.append("A bare `$CMD` is suspicious regardless of visible assignments.\n")

    return "\n".join(lines)


if __name__ == "__main__":
    results = run_fuzzer()
    report = generate_report(results)
    out = "/home/gbergman/YDKHHICF/SecBASH/docs/security_vulnerabilities/v2/fuzzing/01-check-variable-in-command-position.md"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(report)
    print(f"\nReport written to: {out}")
