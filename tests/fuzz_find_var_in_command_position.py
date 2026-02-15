"""Fuzzer for _find_var_in_command_position() - P3 target."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import bashlex
from aegish.validator import (
    _check_variable_in_command_position,
    _find_var_in_command_position,
)


def dump_ast(node, indent=0):
    """Recursively dump a bashlex AST node."""
    prefix = "  " * indent
    kind = getattr(node, "kind", "?")
    word = getattr(node, "word", None)
    line = f"{prefix}{kind}"
    if word:
        line += f" [{word}]"
    lines = [line]
    for attr in ("parts", "list"):
        children = getattr(node, attr, None)
        if children:
            for child in children:
                lines.extend(dump_ast(child, indent + 1).splitlines())
    if hasattr(node, "body"):
        lines.extend(dump_ast(node.body, indent + 1).splitlines())
    return "\n".join(lines)


def collect_kinds(node, kinds=None):
    if kinds is None:
        kinds = set()
    kinds.add(getattr(node, "kind", "?"))
    for attr in ("parts", "list"):
        children = getattr(node, attr, None)
        if children:
            for child in children:
                collect_kinds(child, kinds)
    if hasattr(node, "body"):
        collect_kinds(node.body, kinds)
    return kinds


def test_case(test_id, category, command, expected_detect, notes):
    """Run a single test case."""
    result = _check_variable_in_command_position(command)
    detected = result is not None and result.get("action") == "warn"

    # Check if parseable
    parse_error = None
    ast_dump = ""
    node_kinds = set()
    try:
        parts = bashlex.parse(command)
        ast_dump = "\n".join(dump_ast(p) for p in parts)
        for p in parts:
            collect_kinds(p, node_kinds)
    except Exception as e:
        parse_error = f"{type(e).__name__}: {str(e)[:100]}"

    is_evasion = expected_detect and not detected and parse_error is None
    is_fp = not expected_detect and detected

    return {
        "id": test_id, "category": category, "command": command,
        "expected": expected_detect, "detected": detected,
        "is_evasion": is_evasion, "is_fp": is_fp,
        "parse_error": parse_error, "ast_dump": ast_dump,
        "node_kinds": node_kinds, "notes": notes,
        "result": result,
    }


def get_tests():
    """All test cases: (id, category, command, should_detect, notes)"""
    cases = []

    # For loops
    cases.extend([
        ("FOR-01", "for_loop", "for i in bash; do $i; done", True,
         "Variable from for-loop var used as command"),
        ("FOR-02", "for_loop", "CMD=bash; for i in 1; do $CMD; done", True,
         "Assignment + for loop execution"),
        ("FOR-03", "for_loop", "for i in 1 2 3; do echo $i; done", False,
         "Echo arg, not command position"),
    ])

    # If statements
    cases.extend([
        ("IF-01", "if_stmt", "if true; then $CMD; fi", True,
         "Variable as command in then-branch"),
        ("IF-02", "if_stmt", "if false; then echo ok; else $CMD; fi", True,
         "Variable as command in else-branch"),
        ("IF-03", "if_stmt", "CMD=bash; if true; then $CMD; fi", True,
         "Assignment + if execution"),
        ("IF-04", "if_stmt", "if true; then echo ok; fi", False,
         "Safe if statement"),
    ])

    # While/until
    cases.extend([
        ("WHILE-01", "while_loop", "while true; do $CMD; break; done", True,
         "Variable as command in while body"),
        ("UNTIL-01", "until_loop", "until false; do $CMD; break; done", True,
         "Variable as command in until body"),
    ])

    # Subshells and brace groups
    cases.extend([
        ("SUB-01", "subshell", "(CMD=bash; $CMD)", True,
         "Assignment + execution in subshell"),
        ("BRACE-01", "brace_group", "{ CMD=bash; $CMD; }", True,
         "Assignment + execution in brace group"),
    ])

    # Pipelines (no has_assignment needed)
    cases.extend([
        ("PIPE-01", "pipeline", "echo hi | $CMD", True,
         "Variable in second pipeline command"),
        ("PIPE-02", "pipeline", "$CMD | grep foo", True,
         "Variable in first pipeline command"),
        ("PIPE-03", "pipeline", "echo | $CMD | grep", True,
         "Variable in middle of pipeline"),
    ])

    # Classic patterns
    cases.extend([
        ("CLASSIC-01", "classic", "a=ba; b=sh; $a$b", True,
         "Split-and-concatenate"),
        ("CLASSIC-02", "classic", "X=bash; $X", True,
         "Simple assignment + execution"),
    ])

    # has_assignment bypass
    cases.extend([
        ("ASSIGN-01", "has_assignment", "$CMD", True,
         "Bare variable as command, no visible assignment"),
        ("ASSIGN-02", "has_assignment", "export CMD=bash; $CMD", True,
         "Export + execution"),
    ])

    # Logical operators
    cases.extend([
        ("LOGIC-01", "logical_ops", "true && $CMD", True,
         "Variable after &&"),
        ("LOGIC-02", "logical_ops", "false || $CMD", True,
         "Variable after ||"),
        ("LOGIC-03", "logical_ops", "CMD=bash; true && $CMD", True,
         "Assignment + && + variable"),
    ])

    # Nested constructs
    cases.extend([
        ("NEST-01", "nested", "for i in 1; do for j in 1; do $CMD; done; done", True,
         "Nested for loops"),
        ("NEST-02", "nested", "if true; then for i in 1; do $CMD; done; fi", True,
         "If wrapping for"),
        ("NEST-03", "nested", "{ for i in 1; do $CMD; done; }", True,
         "Brace wrapping for"),
        ("NEST-04", "nested", "(if true; then $CMD; fi)", True,
         "Subshell wrapping if"),
    ])

    # Evasion techniques
    cases.extend([
        ("EVADE-01", "evasion", "CMD=bash; eval $CMD", True,
         "eval with variable arg"),
        ("EVADE-02", "evasion", "CMD=bash; exec $CMD", True,
         "exec with variable arg"),
    ])

    # Function definitions
    cases.extend([
        ("FUNC-01", "function", "f() { $CMD; }", True,
         "Variable in function body"),
    ])

    # Safe commands
    cases.extend([
        ("SAFE-01", "safe", "echo hello", False, "Simple echo"),
        ("SAFE-02", "safe", "ls -la /home", False, "Simple ls"),
        ("SAFE-03", "safe", "cat /etc/hostname", False, "Simple cat"),
        ("SAFE-04", "safe", "echo $HOME", False, "Variable as argument, not command"),
        ("SAFE-05", "safe", "X=hello; echo $X", False, "Variable as echo argument"),
    ])

    # Crasher constructs
    cases.extend([
        ("CRASH-01", "crasher", "arr=(bash); ${arr[0]}", True,
         "Array execution (bashlex may crash)"),
        ("CRASH-02", "crasher", "X=bash; $X <(echo hi)", True,
         "Process substitution (bashlex may crash)"),
        ("CRASH-03", "crasher", "case x in x) $CMD;; esac", True,
         "Case statement (bashlex may crash)"),
        ("CRASH-04", "crasher", "select i in a; do $CMD; done", True,
         "Select statement (bashlex may crash)"),
        ("CRASH-05", "crasher", "for ((i=0;i<1;i++)); do $CMD; done", True,
         "C-style for (bashlex may crash)"),
    ])

    return cases


def main():
    print("=" * 70)
    print("FUZZER: _find_var_in_command_position()")
    print("=" * 70)

    cases = get_tests()
    results = []
    for test_id, cat, cmd, expected, notes in cases:
        r = test_case(test_id, cat, cmd, expected, notes)
        results.append(r)

    # Print results
    evasions = [r for r in results if r["is_evasion"]]
    parse_errors = [r for r in results if r["parse_error"]]
    false_positives = [r for r in results if r["is_fp"]]

    print(f"\nTotal: {len(results)}")
    print(f"Detected: {sum(1 for r in results if r['detected'])}")
    print(f"Evasions: {len(evasions)}")
    print(f"Parse errors: {len(parse_errors)}")
    print(f"False positives: {len(false_positives)}")

    # Category breakdown
    cats = {}
    for r in results:
        cats.setdefault(r["category"], []).append(r)

    print(f"\n{'Category':<20} {'Total':>6} {'Det':>5} {'Evade':>6} {'Parse':>6}")
    print("-" * 50)
    for cat, rs in cats.items():
        t = len(rs)
        d = sum(1 for r in rs if r["detected"])
        e = sum(1 for r in rs if r["is_evasion"])
        p = sum(1 for r in rs if r["parse_error"])
        marker = " <<<" if e > 0 else ""
        print(f"{cat:<20} {t:>6} {d:>5} {e:>6} {p:>6}{marker}")

    if evasions:
        print("\n" + "=" * 70)
        print("EVASION DETAILS")
        print("=" * 70)
        for r in evasions:
            print(f"\n--- {r['id']} [{r['category']}] ---")
            print(f"  Command:   {r['command']!r}")
            print(f"  Kinds:     {sorted(r['node_kinds'])}")
            print(f"  Notes:     {r['notes']}")
            print(f"  AST:")
            for line in r["ast_dump"].splitlines():
                print(f"    {line}")

    if parse_errors:
        print("\n" + "=" * 70)
        print("PARSE ERRORS")
        print("=" * 70)
        for r in parse_errors:
            expected_tag = " [EXPECTED DETECT]" if r["expected"] else ""
            print(f"  {r['id']}: {r['command']!r} -> {r['parse_error']}{expected_tag}")

    # All results table
    print("\n" + "=" * 70)
    print("ALL RESULTS")
    print("=" * 70)
    print(f"{'ID':<12} {'Cat':<20} {'Exp':>4} {'Act':>5} {'Result':<10} Command")
    print("-" * 95)
    for r in results:
        exp = "DET" if r["expected"] else "OK"
        if r["parse_error"]:
            act = "ERR"
            res = "PARSE_ERR"
        elif r["detected"]:
            act = "DET"
            res = "PASS" if r["expected"] else "FALSE_POS"
        else:
            act = "NONE"
            res = "EVASION" if r["expected"] else "PASS"
        cmd_short = r["command"][:50] + ("..." if len(r["command"]) > 50 else "")
        print(f"{r['id']:<12} {r['category']:<20} {exp:>4} {act:>5} {res:<10} {cmd_short}")

    # Generate report
    report = gen_report(results, evasions, parse_errors, false_positives, cats)
    out = "/home/gbergman/YDKHHICF/SecBASH/docs/security_vulnerabilities/v2/fuzzing/04-find-var-in-command-position.md"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(report)
    print(f"\nReport: {out}")

    if evasions:
        print(f"\nWARNING: {len(evasions)} evasion(s) found!")
        sys.exit(1)


def gen_report(results, evasions, parse_errors, false_positives, cats):
    lines = []
    lines.append("# Fuzzing Report: `_find_var_in_command_position()`\n")
    lines.append("## Summary\n")
    lines.append(f"- **Total tests**: {len(results)}")
    lines.append(f"- **Detected**: {sum(1 for r in results if r['detected'])}")
    lines.append(f"- **Evasions**: {len(evasions)}")
    lines.append(f"- **Parse errors**: {len(parse_errors)}")
    lines.append(f"- **False positives**: {len(false_positives)}\n")

    lines.append("The function only handles `pipeline`, `command`, `list`, and `compound` node kinds. "
                 "Control-flow nodes (`for`, `if`, `while`, `until`) are silently ignored.\n")

    lines.append("## Category Breakdown\n")
    lines.append("| Category | Total | Detected | Evasions | Parse Errors |")
    lines.append("|----------|-------|----------|----------|--------------|")
    for cat, rs in cats.items():
        t = len(rs)
        d = sum(1 for r in rs if r["detected"])
        e = sum(1 for r in rs if r["is_evasion"])
        p = sum(1 for r in rs if r["parse_error"])
        lines.append(f"| {cat} | {t} | {d} | {e} | {p} |")
    lines.append("")

    if evasions:
        lines.append("## Evasion Details\n")
        lines.append(f"**{len(evasions)} commands evade detection.**\n")
        for r in evasions:
            cmd_esc = r["command"].replace("|", "\\|").replace("$", "\\$")
            lines.append(f"### {r['id']}: `{cmd_esc}`\n")
            lines.append(f"- **Category**: {r['category']}")
            lines.append(f"- **Expected**: Detected")
            lines.append(f"- **Actual**: Not detected (evasion)")
            lines.append(f"- **AST kinds**: {', '.join(sorted(r['node_kinds']))}")
            lines.append(f"- **Notes**: {r['notes']}")
            lines.append(f"- **Security impact**: Attacker can execute arbitrary commands via this construct\n")
            lines.append("```")
            lines.append(r["ast_dump"])
            lines.append("```\n")

    lines.append("## Root Cause Analysis\n")
    lines.append("### Unhandled Node Kinds\n")
    unhandled = set()
    for r in evasions:
        unhandled |= r["node_kinds"] - {"pipeline", "command", "list", "compound",
                                         "word", "parameter", "assignment", "operator",
                                         "redirect", "heredoc", "reservedword"}
    for k in sorted(unhandled):
        lines.append(f"- `{k}`")
    lines.append("")

    lines.append("### The `has_assignment` Asymmetry\n")
    lines.append("- **`pipeline` branch**: No `has_assignment` required")
    lines.append("- **`command` branch**: Requires `has_assignment=True`")
    lines.append("- A bare `$CMD` is not flagged, but `echo | $CMD` is.\n")

    if parse_errors:
        lines.append("## Parse Errors\n")
        for r in parse_errors:
            expected_tag = " (SHOULD DETECT)" if r["expected"] else ""
            lines.append(f"- `{r['command']}`: `{r['parse_error']}`{expected_tag}")
        lines.append("")

    lines.append("## Recommendations\n")
    lines.append("### 1. Handle all control-flow node kinds\n")
    lines.append("```python")
    lines.append('elif node.kind in ("for", "if", "while", "until"):')
    lines.append("    for part in node.parts:")
    lines.append('        if part.kind == "list":')
    lines.append("            result = _find_var_in_command_position(part.parts, has_assignment)")
    lines.append("            if result is not None:")
    lines.append("                return result")
    lines.append("```\n")
    lines.append("### 2. Add generic recursive fallback\n")
    lines.append("### 3. Remove `has_assignment` requirement\n")
    lines.append("### 4. Handle parse failures conservatively\n")

    lines.append("\n## Full Results\n")
    lines.append("| ID | Category | Command | Expected | Actual | Result |")
    lines.append("|---|---|---|---|---|---|")
    for r in results:
        exp = "Detect" if r["expected"] else "Safe"
        if r["parse_error"]:
            act, res = "Error", "PARSE_ERR"
        elif r["detected"]:
            act = "Detected"
            res = "PASS" if r["expected"] else "FALSE_POS"
        else:
            act = "None"
            res = "**EVASION**" if r["expected"] else "PASS"
        cmd = r["command"].replace("|", "\\|").replace("$", "\\$")[:60]
        lines.append(f"| {r['id']} | {r['category']} | `{cmd}` | {exp} | {act} | {res} |")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
