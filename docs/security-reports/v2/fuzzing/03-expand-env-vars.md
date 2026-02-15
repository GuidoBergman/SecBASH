# Fuzzing Report: `_expand_env_vars()` and `_get_safe_env()`

## Executive Summary

**31 out of 40 secret-like env vars bypass the filter.**

- Tested: **40**
- Blocked: **9**
- Leaked: **31**
- Confirmed expanded into LLM prompt: **31**

### Impact

When a user types `curl -H "Authorization: $STRIPE_KEY" https://api.stripe.com`, `_expand_env_vars()` resolves the variable and appends the plaintext secret to the LLM prompt sent to third-party providers.

### Severity: HIGH

The `_SENSITIVE_VAR_PATTERNS` blocklist has only 9 patterns. Real-world naming conventions are far more diverse.

## Current Patterns

```python
_SENSITIVE_VAR_PATTERNS = ('_API_KEY', '_SECRET', '_PASSWORD', '_TOKEN', '_CREDENTIAL', '_PRIVATE_KEY', 'API_KEY', 'SECRET_KEY', 'ACCESS_KEY')
```

## Correctly Blocked

| Env Var | Matched Pattern |
|---------|-----------------|
| `REDIS_PASSWORD` | `_PASSWORD` |
| `VAULT_TOKEN` | `_TOKEN` |
| `CONSUL_HTTP_TOKEN` | `_TOKEN` |
| `GOOGLE_APPLICATION_CREDENTIALS` | `_CREDENTIAL` |
| `COOKIE_SECRET` | `_SECRET` |
| `DJANGO_SECRET_KEY` | `_SECRET` |
| `FLASK_SECRET_KEY` | `_SECRET` |
| `RAILS_SECRET_KEY_BASE` | `_SECRET` |
| `NEXTAUTH_SECRET` | `_SECRET` |

## Leaked Secrets

### Passwords

| Env Var | Description | Expanded? | Real-World |
|---------|-------------|:---------:|------------|
| `MY_DB_PASS` | Database password | YES | MySQL/Postgres password |
| `PGP_PASSPHRASE` | PGP passphrase | YES | GPG key passphrase |

### Connection Strings

| Env Var | Description | Expanded? | Real-World |
|---------|-------------|:---------:|------------|
| `DATABASE_URL` | Database connection string | YES | postgres://user:pass@host/db |
| `REDIS_URL` | Redis connection URL | YES | redis://:password@host:6379 |
| `MONGO_URI` | MongoDB URI | YES | mongodb://user:pass@host/db |
| `SQLALCHEMY_DATABASE_URI` | SQLAlchemy URI | YES | Full DB connection string |
| `CELERY_BROKER_URL` | Celery broker URL | YES | amqp://user:pass@host |

### Tokens

| Env Var | Description | Expanded? | Real-World |
|---------|-------------|:---------:|------------|
| `GITHUB_PAT` | GitHub personal access token | YES | ghp_xxxx |

### Keys

| Env Var | Description | Expanded? | Real-World |
|---------|-------------|:---------:|------------|
| `STRIPE_KEY` | Stripe API key | YES | sk_live_xxxx |
| `SENDGRID_KEY` | SendGrid key | YES | SG.xxxx |
| `ENCRYPTION_KEY` | Encryption key | YES | AES key material |
| `SIGNING_KEY` | Signing key | YES | JWT/HMAC signing key |
| `MASTER_KEY` | Master key | YES | App master encryption key |
| `HMAC_KEY` | HMAC key | YES | HMAC signing key |
| `SSH_KEY` | SSH key | YES | SSH private key path/material |
| `GCP_KEY` | GCP key | YES | Google Cloud key |
| `AZURE_KEY` | Azure key | YES | Azure service key |
| `DATADOG_KEY` | Datadog key | YES | Datadog API key |
| `NEW_RELIC_KEY` | New Relic key | YES | New Relic license key |

### Auth Credentials

| Env Var | Description | Expanded? | Real-World |
|---------|-------------|:---------:|------------|
| `TWILIO_AUTH` | Twilio auth token | YES | Twilio API auth |
| `TWILIO_SID` | Twilio SID | YES | Twilio account SID |
| `NPM_AUTH` | NPM auth | YES | NPM registry auth token |
| `DOCKER_AUTH_CONFIG` | Docker auth | YES | Docker registry credentials |
| `K8S_AUTH` | K8S auth | YES | Kubernetes auth token |
| `BASIC_AUTH` | Basic auth credentials | YES | HTTP basic auth |

### Webhooks

| Env Var | Description | Expanded? | Real-World |
|---------|-------------|:---------:|------------|
| `SLACK_WEBHOOK` | Slack webhook URL | YES | hooks.slack.com/services/... |
| `DISCORD_WEBHOOK` | Discord webhook | YES | discord.com/api/webhooks/... |
| `TEAMS_WEBHOOK` | Teams webhook | YES | Teams incoming webhook |

### Config Paths

| Env Var | Description | Expanded? | Real-World |
|---------|-------------|:---------:|------------|
| `KUBECONFIG` | Kubernetes config | YES | Path to kubeconfig with certs |

### Misc

| Env Var | Description | Expanded? | Real-World |
|---------|-------------|:---------:|------------|
| `SENTRY_DSN` | Sentry DSN | YES | Sentry error tracking DSN with key |
| `JWT_SIGNING` | JWT signing secret | YES | JWT HMAC secret |

## envsubst Behavior

| Input | Output | Sentinel Found |
|-------|--------|:--------------:|
| `$FUZZ_VAR` | `SENTINEL_VALUE` | YES |
| `${FUZZ_VAR}` | `SENTINEL_VALUE` | YES |
| `"$FUZZ_VAR"` | `"SENTINEL_VALUE"` | YES |
| `'$FUZZ_VAR'` | `'SENTINEL_VALUE'` | YES |
| `$$FUZZ_VAR` | `$SENTINEL_VALUE` | YES |
| `\$FUZZ_VAR` | `\SENTINEL_VALUE` | YES |
| `$(whoami)` | `$(whoami)` | no |
| ``whoami`` | ``whoami`` | no |
| `echo hello` | `echo hello` | no |

### Key envsubst Findings

1. **Single quotes do NOT protect**: envsubst ignores shell quoting rules
2. **`$(cmd)` and backticks NOT executed**: Only `$VAR`/`${VAR}` expanded
3. **`\\$VAR` NOT an escape**: envsubst still expands after backslash

## End-to-End Leakage

| Env Var | Secret Preview | Leaked? |
|---------|----------------|:-------:|
| `E2E_DATABASE_URL` | `postgres://admin:s3c...` | YES |
| `E2E_STRIPE_KEY` | `sk_live_4eC39HqLyjWD...` | YES |
| `E2E_GITHUB_PAT` | `ghp_ABCDEFGHIJKLMNOP...` | YES |
| `E2E_SLACK_WEBHOOK` | `https://hooks.slack....` | YES |
| `E2E_ENCRYPTION_KEY` | `aes256:abcdef1234567...` | YES |

## Recommendations

### 1. Switch to allowlist approach

```python
_SAFE_VAR_ALLOWLIST = {
    "PATH", "HOME", "USER", "SHELL", "TERM", "LANG",
    "PWD", "OLDPWD", "HOSTNAME", "LOGNAME", "DISPLAY",
    "XDG_RUNTIME_DIR", "TMPDIR", "TZ", "COLUMNS", "LINES",
}
```

### 2. Expand blocklist (minimum fix)

Add: `_PASS`, `_KEY`, `_AUTH`, `_URL`, `_URI`, `_DSN`, `_WEBHOOK`, `_SID`, `_PAT`, `KUBECONFIG`, `CREDENTIALS`, `_SIGNING`

### 3. Consider disabling env var expansion entirely

The LLM can analyze `$MY_SECRET` without seeing the actual value.
