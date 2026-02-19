# aegish

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

LLM-powered shell with security validation. aegish validates every command against an LLM before execution, blocking dangerous commands and warning about risky operations.

## Features

- **Security validation** - Every command is validated by an LLM before execution
- **Provider fallback** - Supports OpenAI and Anthropic with automatic failover
- **Command history** - Persistent history with up/down arrow navigation
- **Exit code preservation** - Maintains `$?` semantics for scripting

## Installation

### Prerequisites

- Python 3.10 or higher
- At least one LLM API key (OpenAI or Anthropic)

### Install with uv (recommended)

```bash
# Clone the repository
git clone https://github.com/GuidoBergman/aegish.git
cd aegish

# Install with uv
uv sync

# Run aegish
uv run aegish
```

### Install with pip

```bash
# Clone the repository
git clone https://github.com/GuidoBergman/aegish.git
cd aegish

# Install in editable mode
pip install -e .

# Run aegish
aegish
```

### Install from source

```bash
# Clone the repository
git clone https://github.com/GuidoBergman/aegish.git
cd aegish

# Install build dependencies
pip install hatchling

# Build and install
pip install .

# Run aegish
aegish
```

### Run with Docker

This starts two containers — one per role (default and sysadmin):

```bash
# Clone the repository
git clone https://github.com/GuidoBergman/aegish.git
cd aegish

# Build and start both containers
docker compose up -d

# Connect via SSH (default password: aegish)
ssh -p 2222 aegish@localhost   # default role
ssh -p 2223 aegish@localhost   # sysadmin role
```

To set a custom password:

```bash
# Via environment variable
AEGISH_USER_PASSWORD=mysecurepass docker compose up -d --build

# Or add to your .env file
echo 'AEGISH_USER_PASSWORD=mysecurepass' >> .env
docker compose up -d --build
```

Sudo requires the user's password, matching production behavior:

```
aegish> sudo apt update
[sudo] password for aegish: ********
```

## Quick Start

1. Set up an API key:
   ```bash
   export OPENAI_API_KEY="your-key-here"
   ```

2. Launch aegish:
   ```bash
   aegish
   ```

3. Try some commands:
   ```
   aegish> ls -la
   aegish> echo "Hello, World!"
   aegish> exit
   ```

## Configuration

### API Keys

aegish requires at least one LLM API key. The quickest way to get started is to copy the example env file:

```bash
cp .env.example .env
# Edit .env and fill in your keys, then load them:
export $(grep -v '^#' .env | xargs)
```

Or set the environment variables directly:

```bash
# OpenAI (primary)
export OPENAI_API_KEY="your-key-here"        # https://platform.openai.com/api-keys

# Anthropic (fallback)
export ANTHROPIC_API_KEY="your-key-here"     # https://console.anthropic.com/
```

Add these to your `~/.bashrc` or `~/.zshrc` for persistence:

```bash
# Add to ~/.bashrc or ~/.zshrc
export OPENAI_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"   # optional
```

### Model Configuration

By default, aegish uses GPT-4 for security validation with Claude as a fallback. You can customize which models are used:

```bash
# Primary model for command validation
export AEGISH_PRIMARY_MODEL="openai/gpt-4"

# Fallback models (comma-separated, tried in order if primary fails)
export AEGISH_FALLBACK_MODELS="anthropic/claude-3-haiku-20240307"
```

#### Default Configuration

If no model environment variables are set, aegish uses these defaults:

| Variable | Default Value |
|----------|---------------|
| `AEGISH_PRIMARY_MODEL` | `openai/gpt-4` |
| `AEGISH_FALLBACK_MODELS` | `anthropic/claude-3-haiku-20240307` |

#### Model String Format

Model strings follow LiteLLM format: `provider/model-name`

Valid examples:
- `openai/gpt-4`
- `openai/gpt-4-turbo`
- `anthropic/claude-3-haiku-20240307`
- `anthropic/claude-3-opus-20240229`

#### Common Configurations

**Single provider (no fallbacks):**
```bash
export AEGISH_PRIMARY_MODEL="anthropic/claude-3-haiku-20240307"
export AEGISH_FALLBACK_MODELS=""  # Empty = no fallbacks
```

**Custom model chain:**
```bash
export AEGISH_PRIMARY_MODEL="openai/gpt-4-turbo"
export AEGISH_FALLBACK_MODELS="anthropic/claude-3-opus-20240229"
```

#### API Key Requirements

Each model requires its provider's API key:
- `openai/*` models require `OPENAI_API_KEY`
- `anthropic/*` models require `ANTHROPIC_API_KEY`

Models without a configured API key are skipped automatically.

### Provider Priority

Providers are tried in this order (based on model chain):

1. **OpenAI** - GPT-4 primary
2. **Anthropic** - Claude fallback

The startup message shows which models are active:

```
aegish - LLM-powered shell with security validation
Model chain: openai/gpt-4 (active) > anthropic/claude-3-haiku-20240307 (active)
Type 'exit' or press Ctrl+D to quit.
```

## Setting aegish as Login Shell

> **Warning**: Changing your login shell can lock you out of your system if something goes wrong. Read and follow ALL safety precautions below.

### Prerequisites

Before setting aegish as your login shell, verify:

- [ ] aegish is installed and runs without errors
- [ ] At least one LLM API key is configured and tested
- [ ] API key is set in a file that login shells source (e.g., `~/.profile`, `~/.bash_profile`)
- [ ] You have root or sudo access
- [ ] You know the absolute path to aegish (`which aegish`)

### Installation Steps

1. **Find aegish installation path:**
   ```bash
   which aegish
   # Example output: /home/user/.local/bin/aegish
   ```

2. **Verify aegish starts correctly:**
   ```bash
   /full/path/to/aegish
   # Should show startup message
   # Type 'exit' to return to your current shell
   ```

3. **Add aegish to /etc/shells (requires root):**
   ```bash
   echo "/full/path/to/aegish" | sudo tee -a /etc/shells
   ```

4. **Change your login shell:**
   ```bash
   chsh -s /full/path/to/aegish
   ```

5. **Verify the change:**
   ```bash
   grep $USER /etc/passwd | cut -d: -f7
   # Should show: /full/path/to/aegish
   ```

### Safety Precautions

> **Warning**: ALWAYS follow these safety steps to avoid being locked out.

1. **Test in a separate terminal first** - Don't change your login shell until aegish works reliably

2. **Keep a root terminal open** - Before logging out, open a root shell:
   ```bash
   sudo -i
   # Keep this terminal open until you've verified login works
   ```

3. **Test with su before logging out:**
   ```bash
   su - $USER
   # This simulates a login shell session
   # If it fails, you can fix it from your current terminal
   ```

4. **Ensure API keys load on login** - API keys must be set in `~/.profile` or `~/.bash_profile`, not just `~/.bashrc`:
   ```bash
   # Add to ~/.profile (read by login shells)
   export OPENAI_API_KEY="your-key-here"
   ```

5. **Have a backup shell available** - Know how to access root via single-user mode or recovery console

### Recovery Instructions

If aegish fails as your login shell:

**Option 1: Via root terminal (if you kept one open)**
```bash
sudo chsh -s /bin/bash your-username
```

**Option 2: Via SSH with forced command**
```bash
ssh user@host /bin/bash -c 'chsh -s /bin/bash'
```

**Option 3: Via single-user mode**
1. Reboot and edit GRUB (press `e` at boot menu)
2. Add `init=/bin/bash` to the linux line
3. Boot and remount filesystem:
   ```bash
   mount -o remount,rw /
   ```
4. Edit /etc/passwd and change your shell to `/bin/bash`
5. Reboot normally

**Option 4: Via live USB/recovery console**
1. Boot from live USB
2. Mount your root filesystem
3. Edit /etc/passwd on the mounted filesystem
4. Reboot

## Usage

### Basic Commands

aegish executes commands through bash, so standard shell commands work:

```
aegish> ls -la
aegish> cd /var/log
aegish> cat syslog | grep error
aegish> echo $?
```

### Security Responses

When you enter a command, aegish validates it and responds with one of:

- **Allow** - Command executes normally
- **Warn** - Shows warning and asks for confirmation (`Proceed anyway? [y/N]`)
- **Block** - Command is blocked with explanation

Example warning:

```
aegish> rm -rf /tmp/*

WARNING: This command recursively deletes all files in /tmp
Proceed anyway? [y/N]: n
Command cancelled.
```

### Command History

- **Up/Down arrows** - Navigate command history
- **History file** - `~/.aegish_history` (persists across sessions)
- **History length** - 1000 commands (default)

## Known Limitations

- **Network required** - LLM validation requires network connectivity
- **Latency** - Each command incurs LLM API latency
- **Not a full shell** - Some advanced shell features may not work as expected
- **Single API key per provider** - Cannot configure multiple keys for the same provider

## Troubleshooting

### History file permission errors

If you see `PermissionError` related to `~/.aegish_history`, check file permissions:

```bash
ls -la ~/.aegish_history
# Fix permissions if needed:
chmod 600 ~/.aegish_history
```

### Verifying installation

Check your aegish version and configured providers:

```bash
aegish --version
# Expected: aegish version 0.1.0
```

## Running Benchmarks

aegish includes an [Inspect AI](https://inspect.aisi.org.uk/) evaluation harness for benchmarking LLM classifiers against the GTFOBins (malicious) and harmless command datasets.

### API Keys for Benchmarks

Inspect uses the **same standard environment variables** as each provider's SDK. You only need keys for the models you want to evaluate:

| Provider | Environment Variable | Signup |
|----------|---------------------|--------|
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| Anthropic | `ANTHROPIC_API_KEY` | https://console.anthropic.com/ |
| Google | `GOOGLE_API_KEY` | https://aistudio.google.com/apikey |
| OpenRouter | `OPENROUTER_API_KEY` | https://openrouter.ai/ |
| HuggingFace | `HF_TOKEN` | https://huggingface.co/settings/tokens |

All of these are listed in `.env.example`.

### Running a Single Evaluation

```bash
# Evaluate a model against the GTFOBins dataset
uv run inspect eval benchmark/tasks/aegish_eval.py@aegish_gtfobins --model openai/gpt-4o-mini

# Evaluate against the harmless dataset
uv run inspect eval benchmark/tasks/aegish_eval.py@aegish_harmless --model openai/gpt-4o-mini

# Enable Chain-of-Thought scaffolding
uv run inspect eval benchmark/tasks/aegish_eval.py@aegish_gtfobins --model openai/gpt-4o-mini -T cot=true

# View results in the Inspect web UI
uv run inspect view
```

### Multi-Model Comparison

```bash
# Compare all default models (needs keys for each)
uv run -m benchmark.compare

# Compare specific models
uv run -m benchmark.compare --models openai/gpt-4o-mini,anthropic/claude-3-haiku-20240307

# Generate a report from the latest evaluation
uv run -m benchmark.report --latest
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes with tests
4. Run the test suite (`uv run pytest`)
5. Submit a pull request

## License

MIT
