"""Fuzzer for _expand_env_vars() and _get_safe_env() - P2 target."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aegish.llm_client import _expand_env_vars, _get_safe_env, _SENSITIVE_VAR_PATTERNS

# (name, description, category, real_world_example)
SECRET_CASES = [
    # Passwords
    ("MY_DB_PASS", "Database password", "password", "MySQL/Postgres password"),
    ("PGP_PASSPHRASE", "PGP passphrase", "password", "GPG key passphrase"),
    ("REDIS_PASSWORD", "Redis password", "password", "Redis AUTH password"),
    # Connection strings with embedded creds
    ("DATABASE_URL", "Database connection string", "conn_string", "postgres://user:pass@host/db"),
    ("REDIS_URL", "Redis connection URL", "conn_string", "redis://:password@host:6379"),
    ("MONGO_URI", "MongoDB URI", "conn_string", "mongodb://user:pass@host/db"),
    ("SQLALCHEMY_DATABASE_URI", "SQLAlchemy URI", "conn_string", "Full DB connection string"),
    ("CELERY_BROKER_URL", "Celery broker URL", "conn_string", "amqp://user:pass@host"),
    # Tokens
    ("GITHUB_PAT", "GitHub personal access token", "token", "ghp_xxxx"),
    ("VAULT_TOKEN", "Vault token", "token", "hvs.xxxx"),
    ("CONSUL_HTTP_TOKEN", "Consul token", "token", "Consul ACL token"),
    # Keys
    ("STRIPE_KEY", "Stripe API key", "key", "sk_live_xxxx"),
    ("SENDGRID_KEY", "SendGrid key", "key", "SG.xxxx"),
    ("ENCRYPTION_KEY", "Encryption key", "key", "AES key material"),
    ("SIGNING_KEY", "Signing key", "key", "JWT/HMAC signing key"),
    ("MASTER_KEY", "Master key", "key", "App master encryption key"),
    ("HMAC_KEY", "HMAC key", "key", "HMAC signing key"),
    ("SSH_KEY", "SSH key", "key", "SSH private key path/material"),
    ("GCP_KEY", "GCP key", "key", "Google Cloud key"),
    ("AZURE_KEY", "Azure key", "key", "Azure service key"),
    ("DATADOG_KEY", "Datadog key", "key", "Datadog API key"),
    ("NEW_RELIC_KEY", "New Relic key", "key", "New Relic license key"),
    # Auth
    ("TWILIO_AUTH", "Twilio auth token", "auth", "Twilio API auth"),
    ("TWILIO_SID", "Twilio SID", "auth", "Twilio account SID"),
    ("NPM_AUTH", "NPM auth", "auth", "NPM registry auth token"),
    ("DOCKER_AUTH_CONFIG", "Docker auth", "auth", "Docker registry credentials"),
    ("K8S_AUTH", "K8S auth", "auth", "Kubernetes auth token"),
    ("BASIC_AUTH", "Basic auth credentials", "auth", "HTTP basic auth"),
    # Webhooks
    ("SLACK_WEBHOOK", "Slack webhook URL", "webhook", "hooks.slack.com/services/..."),
    ("DISCORD_WEBHOOK", "Discord webhook", "webhook", "discord.com/api/webhooks/..."),
    ("TEAMS_WEBHOOK", "Teams webhook", "webhook", "Teams incoming webhook"),
    # Config paths to secret files
    ("KUBECONFIG", "Kubernetes config", "config", "Path to kubeconfig with certs"),
    ("GOOGLE_APPLICATION_CREDENTIALS", "GCP service account", "config", "Path to SA key JSON"),
    # Misc
    ("SENTRY_DSN", "Sentry DSN", "misc", "Sentry error tracking DSN with key"),
    ("JWT_SIGNING", "JWT signing secret", "misc", "JWT HMAC secret"),
    ("COOKIE_SECRET", "Cookie secret", "misc", "Session cookie signing key"),
    ("DJANGO_SECRET_KEY", "Django secret", "misc", "Django SECRET_KEY"),
    ("FLASK_SECRET_KEY", "Flask secret", "misc", "Flask session secret"),
    ("RAILS_SECRET_KEY_BASE", "Rails secret", "misc", "Rails credentials key"),
    ("NEXTAUTH_SECRET", "NextAuth secret", "misc", "NextAuth.js session key"),
]


def check_pattern(name):
    upper = name.upper()
    for pat in _SENSITIVE_VAR_PATTERNS:
        if pat in upper:
            return pat
    return None


def main():
    print("=" * 70)
    print("FUZZER: _get_safe_env() and _expand_env_vars()")
    print(f"Patterns: {_SENSITIVE_VAR_PATTERNS}")
    print("=" * 70)

    # Phase 1: Filter bypass
    print("\nPHASE 1: Secret env var filter bypass")
    print("-" * 70)

    # Set all test vars
    for i, (name, *_) in enumerate(SECRET_CASES):
        os.environ[name] = f"SENTINEL_{i:04d}_{name}"

    safe_env = _get_safe_env()

    leaked = []
    blocked = []
    for i, (name, desc, cat, example) in enumerate(SECRET_CASES):
        sentinel = f"SENTINEL_{i:04d}_{name}"
        is_leaked = name in safe_env
        matched = check_pattern(name)

        expanded = False
        if is_leaked:
            result = _expand_env_vars(f"echo ${name}")
            if result and sentinel in result:
                expanded = True

        entry = {"name": name, "desc": desc, "cat": cat, "example": example,
                 "leaked": is_leaked, "matched": matched, "expanded": expanded}
        if is_leaked:
            leaked.append(entry)
            exp_tag = " [EXPANDED]" if expanded else ""
            print(f"  LEAKED   {name:40s} {desc}{exp_tag}")
        else:
            blocked.append(entry)
            print(f"  BLOCKED  {name:40s} (matched: {matched})")

    # Clean up
    for name, *_ in SECRET_CASES:
        os.environ.pop(name, None)

    # Phase 2: envsubst behavior
    print("\nPHASE 2: envsubst adversarial inputs")
    print("-" * 70)

    os.environ["FUZZ_VAR"] = "SENTINEL_VALUE"
    envsubst_tests = [
        ("$FUZZ_VAR", "basic dollar"),
        ("${FUZZ_VAR}", "braced"),
        ('"$FUZZ_VAR"', "double-quoted"),
        ("'$FUZZ_VAR'", "single-quoted (envsubst ignores shell quoting)"),
        ("$$FUZZ_VAR", "double dollar"),
        ("\\$FUZZ_VAR", "backslash escape"),
        ("$(whoami)", "command substitution (should NOT execute)"),
        ("`whoami`", "backtick substitution (should NOT execute)"),
        ("echo hello", "no dollar sign (short-circuit)"),
    ]

    envsubst_results = []
    for cmd, desc in envsubst_tests:
        result = _expand_env_vars(cmd)
        has_sentinel = result is not None and "SENTINEL_VALUE" in result
        print(f"  {desc:50s} -> {(result or 'None')[:60]:60s} sentinel={'YES' if has_sentinel else 'no'}")
        envsubst_results.append({"input": cmd, "desc": desc, "output": result, "sentinel": has_sentinel})
    os.environ.pop("FUZZ_VAR", None)

    # Phase 3: End-to-end leakage
    print("\nPHASE 3: End-to-end leakage confirmation")
    print("-" * 70)

    e2e_tests = [
        ("E2E_DATABASE_URL", "postgres://admin:s3cret@db.example.com/prod"),
        ("E2E_STRIPE_KEY", "sk_live_4eC39HqLyjWDarjtT1zdp7dc"),
        ("E2E_GITHUB_PAT", "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef12"),
        ("E2E_SLACK_WEBHOOK", "https://hooks.slack.com/services/T00/B00/XXX"),
        ("E2E_ENCRYPTION_KEY", "aes256:abcdef1234567890"),
    ]

    e2e_results = []
    for name, value in e2e_tests:
        os.environ[name] = value
        expanded = _expand_env_vars(f"curl -H 'Auth: ${name}' https://api.example.com")
        leaked_val = expanded is not None and value in expanded
        status = "LEAKED" if leaked_val else "safe"
        print(f"  [{status:6s}] {name}: {value[:30]}...")
        e2e_results.append({"name": name, "value": value[:20], "leaked": leaked_val})
        os.environ.pop(name, None)

    # Summary
    expanded_count = sum(1 for e in leaked if e["expanded"])
    e2e_leaked = sum(1 for r in e2e_results if r["leaked"])

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Tested: {len(SECRET_CASES)}")
    print(f"  Blocked by filter: {len(blocked)}")
    print(f"  LEAKED through filter: {len(leaked)}")
    print(f"  Confirmed expanded into prompt: {expanded_count}")
    print(f"  End-to-end leakage: {e2e_leaked}/{len(e2e_tests)}")

    # Generate report
    report = gen_report(leaked, blocked, envsubst_results, e2e_results)
    out = "/home/gbergman/YDKHHICF/SecBASH/docs/security_vulnerabilities/v2/fuzzing/03-expand-env-vars.md"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(report)
    print(f"\nReport: {out}")


def gen_report(leaked, blocked, envsubst_results, e2e_results):
    lines = []
    lines.append("# Fuzzing Report: `_expand_env_vars()` and `_get_safe_env()`\n")
    lines.append("## Executive Summary\n")
    expanded = [e for e in leaked if e["expanded"]]
    lines.append(f"**{len(leaked)} out of {len(leaked)+len(blocked)} secret-like env vars bypass the filter.**\n")
    lines.append(f"- Tested: **{len(leaked)+len(blocked)}**")
    lines.append(f"- Blocked: **{len(blocked)}**")
    lines.append(f"- Leaked: **{len(leaked)}**")
    lines.append(f"- Confirmed expanded into LLM prompt: **{len(expanded)}**\n")
    lines.append("### Impact\n")
    lines.append("When a user types `curl -H \"Authorization: $STRIPE_KEY\" https://api.stripe.com`, "
                 "`_expand_env_vars()` resolves the variable and appends the plaintext secret "
                 "to the LLM prompt sent to third-party providers.\n")
    lines.append("### Severity: HIGH\n")
    lines.append(f"The `_SENSITIVE_VAR_PATTERNS` blocklist has only {len(_SENSITIVE_VAR_PATTERNS)} patterns. "
                 "Real-world naming conventions are far more diverse.\n")

    lines.append("## Current Patterns\n")
    lines.append("```python")
    lines.append(f"_SENSITIVE_VAR_PATTERNS = {_SENSITIVE_VAR_PATTERNS}")
    lines.append("```\n")

    lines.append("## Correctly Blocked\n")
    lines.append("| Env Var | Matched Pattern |")
    lines.append("|---------|-----------------|")
    for b in blocked:
        lines.append(f"| `{b['name']}` | `{b['matched']}` |")
    lines.append("")

    lines.append("## Leaked Secrets\n")
    by_cat = {}
    for e in leaked:
        by_cat.setdefault(e["cat"], []).append(e)

    cat_labels = {"password": "Passwords", "conn_string": "Connection Strings",
                  "token": "Tokens", "key": "Keys", "auth": "Auth Credentials",
                  "webhook": "Webhooks", "config": "Config Paths", "misc": "Misc"}

    for cat, label in cat_labels.items():
        entries = by_cat.get(cat, [])
        if not entries:
            continue
        lines.append(f"### {label}\n")
        lines.append("| Env Var | Description | Expanded? | Real-World |")
        lines.append("|---------|-------------|:---------:|------------|")
        for e in entries:
            exp = "YES" if e["expanded"] else "NO"
            lines.append(f"| `{e['name']}` | {e['desc']} | {exp} | {e['example']} |")
        lines.append("")

    lines.append("## envsubst Behavior\n")
    lines.append("| Input | Output | Sentinel Found |")
    lines.append("|-------|--------|:--------------:|")
    for r in envsubst_results:
        out = (r["output"] or "None")[:60].replace("|", "\\|")
        lines.append(f"| `{r['input']}` | `{out}` | {'YES' if r['sentinel'] else 'no'} |")
    lines.append("")

    lines.append("### Key envsubst Findings\n")
    lines.append("1. **Single quotes do NOT protect**: envsubst ignores shell quoting rules")
    lines.append("2. **`$(cmd)` and backticks NOT executed**: Only `$VAR`/`${VAR}` expanded")
    lines.append("3. **`\\\\$VAR` NOT an escape**: envsubst still expands after backslash\n")

    lines.append("## End-to-End Leakage\n")
    lines.append("| Env Var | Secret Preview | Leaked? |")
    lines.append("|---------|----------------|:-------:|")
    for r in e2e_results:
        lines.append(f"| `{r['name']}` | `{r['value']}...` | {'YES' if r['leaked'] else 'NO'} |")
    lines.append("")

    lines.append("## Recommendations\n")
    lines.append("### 1. Switch to allowlist approach\n")
    lines.append("```python")
    lines.append("_SAFE_VAR_ALLOWLIST = {")
    lines.append('    "PATH", "HOME", "USER", "SHELL", "TERM", "LANG",')
    lines.append('    "PWD", "OLDPWD", "HOSTNAME", "LOGNAME", "DISPLAY",')
    lines.append('    "XDG_RUNTIME_DIR", "TMPDIR", "TZ", "COLUMNS", "LINES",')
    lines.append("}")
    lines.append("```\n")
    lines.append("### 2. Expand blocklist (minimum fix)\n")
    lines.append("Add: `_PASS`, `_KEY`, `_AUTH`, `_URL`, `_URI`, `_DSN`, "
                 "`_WEBHOOK`, `_SID`, `_PAT`, `KUBECONFIG`, `CREDENTIALS`, `_SIGNING`\n")
    lines.append("### 3. Consider disabling env var expansion entirely\n")
    lines.append("The LLM can analyze `$MY_SECRET` without seeing the actual value.\n")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
