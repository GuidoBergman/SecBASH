---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - docs/prd.md
  - docs/architecture.md
workflowType: 'epics-stories'
status: 'complete'
completedAt: '2026-01-28'
lastRevised: '2026-01-31'
revisionNote: 'Added Story 3.6: Configurable LLM Models'
project_name: 'SecBASH'
user_name: 'guido'
---

# SecBASH - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for SecBASH, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

- FR1: User can run interactive commands exactly as in bash
- FR2: User can execute shell scripts (.sh files) transparently
- FR3: User can use pipes, redirects, and command chaining
- FR4: User can access command history and recall previous commands (should-have)
- FR5: System preserves bash exit codes for script compatibility
- FR6: System intercepts every command before execution
- FR7: System sends command to LLM for security analysis
- FR8: System receives risk assessment from LLM (safe/warn/block)
- FR9: System can detect basic dangerous commands (rm -rf /, fork bombs)
- FR10: System can detect GTFOBins patterns (should-have)
- FR11: System blocks commands classified as dangerous
- FR12: System warns user about risky commands with explanation
- FR13: System allows safe commands to execute immediately
- FR14: User receives plain text explanation when command is blocked/warned
- FR15: User can override warnings and proceed (with confirmation)
- FR16: User can configure LLM API credentials
- FR17: User can set SecBASH as login shell
- FR18: System works with minimal configuration (sensible defaults)

### NonFunctional Requirements

- NFR1: Command validation completes within 2 seconds for interactive use
- NFR2: Cached command decisions return within 100ms
- NFR3: Shell startup time adds no more than 5 seconds to bash startup
- NFR4: LLM API credentials stored securely (not in plain text)
- NFR5: No command data sent to external services beyond configured LLM API
- NFR6: Tool should not be easily bypassed to run commands directly (should-have)
- NFR7: LLM prompt should resist jailbreak attempts (out of scope for MVP)

### Additional Requirements

**From Architecture - Project Initialization:**
- Greenfield project using Python 3.10+, uv package manager, Typer CLI framework
- Dependencies: typer, litellm
- Project structure: src/secbash/ with 6 modules (main.py, shell.py, validator.py, llm_client.py, executor.py, config.py)

**From Architecture - LLM Integration:**
- LLM abstraction: LiteLLM (unified API, built-in caching/fallbacks)
- LLM provider fallback chain: OpenRouter (LlamaGuard) → OpenAI → Anthropic
- Environment variables for credentials: OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY
- LLM response format must be: {action: "allow"|"warn"|"block", reason: string, confidence: 0.0-1.0}
- Built-in caching for repeated command validation (reduces latency and API costs)
- Error handling: LiteLLM handles retries/fallbacks, then fail-open (allow execution)

**From Architecture - Code Standards:**
- PEP 8 naming conventions (snake_case functions, PascalCase classes)
- Standard Python exceptions (ValueError, ConnectionError, TimeoutError)
- Standard Python logging module

**Deferred from MVP (documented for future epics):**
- Latency optimization / semantic caching
- Local model fallback (Ollama)
- GTFOBins benchmark targeting beyond basic detection
- Enterprise features (logging, audit trails)

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 1 | Interactive commands like bash |
| FR2 | Epic 1 | Shell script execution |
| FR3 | Epic 1 | Pipes, redirects, chaining |
| FR4 | Epic 3 | Command history (should-have) |
| FR5 | Epic 1 | Exit code preservation |
| FR6 | Epic 2 | Command interception |
| FR7 | Epic 2 | LLM security analysis |
| FR8 | Epic 2 | Risk assessment (safe/warn/block) |
| FR9 | Epic 2 | Basic dangerous command detection |
| FR10 | Epic 2 | GTFOBins detection (should-have) |
| FR11 | Epic 2 | Block dangerous commands |
| FR12 | Epic 2 | Warn with explanation |
| FR13 | Epic 2 | Allow safe commands |
| FR14 | Epic 2 | Plain text explanations |
| FR15 | Epic 3 | Override warnings |
| FR16 | Epic 3 | API credential configuration |
| FR17 | Epic 3 | Login shell setup |
| FR18 | Epic 3 | Sensible defaults |

## Epic List

### Epic 1: Working Shell Foundation
User can launch SecBASH and execute commands exactly like bash. This epic delivers the foundational shell experience.

**FRs covered:** FR1, FR2, FR3, FR5
**Additional:** Project initialization from Architecture (Python/uv/Typer setup)

### Epic 2: LLM Security Validation
User's commands are validated by AI for security threats before execution. Every command gets analyzed, and the user receives appropriate security responses.

**FRs covered:** FR6, FR7, FR8, FR9, FR10, FR11, FR12, FR13, FR14
**Additional:** LiteLLM integration with provider fallback chain, built-in caching, response format from Architecture

### Epic 3: User Control & Configuration
User can configure SecBASH, override warnings when needed, and use it as their daily shell.

**FRs covered:** FR4, FR15, FR16, FR17, FR18
**NFRs addressed:** NFR4 (secure credential storage)

## Epic 1: Working Shell Foundation

User can launch SecBASH and execute commands exactly like bash. This epic delivers the foundational shell experience.

### Story 1.1: Initialize Project Structure

As a **developer**,
I want **the SecBASH project initialized with proper Python structure**,
So that **I have a foundation to build the shell functionality**.

**Acceptance Criteria:**

**Given** a fresh directory
**When** the project is initialized
**Then** the following structure exists:
- `pyproject.toml` with project metadata
- `src/secbash/` directory with `__init__.py`
- Empty module files: `main.py`, `shell.py`, `validator.py`, `llm_client.py`, `executor.py`, `config.py`
**And** dependencies are installable via `uv sync`
**And** the project follows the Architecture specification

### Story 1.2: Basic Interactive Shell Loop

As a **sysadmin**,
I want **to launch SecBASH and run simple commands interactively**,
So that **I can use it as my command-line interface**.

**Acceptance Criteria:**

**Given** SecBASH is installed and launched
**When** I type a command like `ls` or `pwd`
**Then** the command executes and output is displayed
**And** a new prompt appears for the next command
**And** I can exit with `exit` or Ctrl+D

**Given** SecBASH is running
**When** I press Ctrl+C
**Then** the current input is cancelled without exiting the shell

### Story 1.3: Command Execution with Pipes and Redirects

As a **sysadmin**,
I want **to use pipes, redirects, and command chaining**,
So that **I can perform complex shell operations**.

**Acceptance Criteria:**

**Given** SecBASH is running
**When** I enter a piped command like `ls -la | grep txt`
**Then** the full pipeline executes correctly

**Given** SecBASH is running
**When** I use output redirection like `echo "test" > file.txt`
**Then** the file is created with the content

**Given** SecBASH is running
**When** I chain commands with `&&` or `;`
**Then** commands execute in sequence with proper short-circuit behavior

### Story 1.4: Shell Script Execution

As a **sysadmin**,
I want **to execute shell scripts through SecBASH**,
So that **my existing automation and .sh files work transparently**.

**Acceptance Criteria:**

**Given** a valid shell script `test.sh` exists
**When** I run `./test.sh` or `bash test.sh` through SecBASH
**Then** the script executes completely

**Given** a script with arguments
**When** I run `./script.sh arg1 arg2`
**Then** arguments are passed correctly to the script

### Story 1.5: Exit Code Preservation

As a **sysadmin**,
I want **SecBASH to preserve bash exit codes**,
So that **my scripts and conditional logic work correctly**.

**Acceptance Criteria:**

**Given** a command that succeeds (e.g., `true`)
**When** I check `$?` or use `&&`
**Then** exit code 0 is returned

**Given** a command that fails (e.g., `false` or `ls nonexistent`)
**When** I check `$?`
**Then** the appropriate non-zero exit code is returned

**Given** SecBASH is used in a script with `set -e`
**When** a command fails
**Then** the script exits as expected

## Epic 2: LLM Security Validation

<<<<<<< HEAD
User's commands are validated by AI for security threats before execution. Every command gets analyzed, and the user receives appropriate security responses.

### Story 2.1: LLM Client with Provider Fallback
=======
User's commands are validated by AI for security threats before execution. Every command gets analyzed, and the user receives appropriate security responses. Uses LiteLLM for unified provider access with built-in caching and fallbacks.

### Story 2.1: LLM Client with LiteLLM Integration
>>>>>>> 61055ce (first commit)

As a **sysadmin**,
I want **SecBASH to connect to LLM providers reliably**,
So that **command validation works even if one provider is unavailable**.

**Acceptance Criteria:**

**Given** LiteLLM is configured with provider fallback chain
**When** a validation request is made
**Then** the request goes to OpenRouter (LlamaGuard) first

**Given** OpenRouter fails or times out
**When** fallback providers are configured
**Then** LiteLLM automatically falls back to OpenAI, then Anthropic

**Given** all providers fail after LiteLLM's built-in retries
**When** retries are exhausted
**Then** the system fails open (allows the command) with a warning message

**Given** the same or similar command was recently validated
**When** a validation request is made
**Then** LiteLLM returns cached response (faster, no API call)

**Implementation Notes:**
- Use LiteLLM's `completion()` with `fallbacks` parameter
- Enable LiteLLM caching for repeated commands
- Configure via environment variables: OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY

### Story 2.2: Command Validation Integration

As a **sysadmin**,
I want **every command validated before execution**,
So that **dangerous commands are caught before they can cause harm**.

**Acceptance Criteria:**

**Given** SecBASH is running with LLM configured
**When** I enter any command
**Then** the command is sent to the LLM for security analysis before execution

**Given** a command is sent to the LLM
**When** the LLM responds
**Then** the response is parsed as `{action: "allow"|"warn"|"block", reason: string, confidence: 0.0-1.0}`

**Given** validation is in progress
**When** the user waits
**Then** validation completes *(should-have: target <2 seconds)*

### Story 2.3: Security Response Actions

As a **sysadmin**,
I want **appropriate responses based on command risk level**,
So that **I'm protected from dangerous commands while safe commands run smoothly**.

**Acceptance Criteria:**

**Given** the LLM returns `action: "allow"`
**When** validation completes
**Then** the command executes immediately without additional prompts

**Given** the LLM returns `action: "block"`
**When** validation completes
**Then** the command is NOT executed
**And** a plain text explanation is displayed showing the reason

**Given** the LLM returns `action: "warn"`
**When** validation completes
**Then** the command is NOT executed immediately
**And** a plain text warning with the reason is displayed
**And** the user sees the risk explanation before any further action

### Story 2.4: Dangerous Command Detection

As a **sysadmin**,
I want **SecBASH to detect known dangerous commands**,
So that **common destructive patterns are caught reliably**.

**Acceptance Criteria:**

**Given** a command like `rm -rf /` or `rm -rf /*`
**When** validated
**Then** the command is blocked with an explanation

**Given** a fork bomb like `:(){ :|:& };:`
**When** validated
**Then** the command is blocked with an explanation

**Given** a command that downloads and executes remote code (e.g., `curl ... | bash`)
**When** validated
**Then** the command is flagged as risky (warn or block)

**Given** a GTFOBins escape pattern (e.g., `vim -c ':!bash'`) *(should-have)*
**When** validated
**Then** the command is flagged with a warning

## Epic 3: User Control & Configuration

User can configure SecBASH, override warnings when needed, and use it as their daily shell.

### Story 3.1: API Credential Configuration

As a **sysadmin**,
I want **to configure LLM API credentials securely**,
So that **SecBASH can validate my commands**.

**Acceptance Criteria:**

**Given** environment variables are set (OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY)
**When** SecBASH starts
**Then** credentials are loaded from environment variables

**Given** no API keys are configured
**When** SecBASH starts
**Then** a clear error message explains how to configure credentials

**Given** API keys are configured
**When** I inspect running processes or environment
**Then** credentials are not exposed in plain text in logs or error messages

### Story 3.2: Warning Override

As a **sysadmin**,
I want **to override warnings and proceed with risky commands**,
So that **I can execute commands I understand are risky but necessary**.

**Acceptance Criteria:**

**Given** a command receives a "warn" response
**When** the warning is displayed
**Then** I am prompted to confirm or cancel (e.g., "Proceed anyway? [y/N]")

**Given** I confirm the warning
**When** I enter "y" or "yes"
**Then** the command executes

**Given** I decline or cancel
**When** I enter "n", "no", or press Enter
**Then** the command is NOT executed and I return to the prompt

### Story 3.3: Sensible Defaults

As a **sysadmin**,
I want **SecBASH to work with minimal configuration**,
So that **I can start using it quickly without complex setup**.

**Acceptance Criteria:**

**Given** at least one API key is configured
**When** SecBASH starts
**Then** it works without additional configuration files

**Given** default settings are in use
**When** I use SecBASH
**Then** reasonable defaults are applied (e.g., default shell is bash, standard prompt)

### Story 3.4: Command History *(could-have/optional)*

As a **sysadmin**,
I want **to access command history and recall previous commands**,
So that **I can work efficiently like in a normal shell**.

**Acceptance Criteria:**

**Given** SecBASH is running
**When** I press the up arrow
**Then** previous commands are recalled

**Given** I have entered multiple commands
**When** I use history navigation (up/down arrows)
**Then** I can browse through my command history

**Given** SecBASH is restarted
**When** I press up arrow
**Then** history from previous sessions is available *(optional enhancement)*

### Story 3.5: Login Shell Setup Documentation *(could-have/optional)*

As a **sysadmin**,
I want **documentation on setting SecBASH as my login shell**,
So that **I can use it as my default shell on servers**.

**Acceptance Criteria:**

**Given** SecBASH is installed
**When** I follow the documentation
**Then** I can add SecBASH to `/etc/shells`

**Given** SecBASH is in `/etc/shells`
**When** I run `chsh -s /path/to/secbash`
**Then** SecBASH becomes my login shell

**Given** documentation exists
**When** I read it
**Then** it includes warnings about testing before setting as login shell

### Story 3.6: Configurable LLM Models

As a **sysadmin**,
I want **to configure which LLM models SecBASH uses for validation**,
So that **I can choose models based on my provider access, cost preferences, or performance needs**.

**Acceptance Criteria:**

**Given** environment variables for model configuration are set (e.g., SECBASH_PRIMARY_MODEL, SECBASH_FALLBACK_MODELS)
**When** SecBASH starts
**Then** the configured models are used instead of the hardcoded defaults

**Given** no model configuration environment variables are set
**When** SecBASH starts
**Then** sensible defaults are used (OpenRouter LlamaGuard → OpenAI → Anthropic)

**Given** an invalid model string is configured
**When** SecBASH attempts to use it
**Then** a clear error message is displayed and fallback behavior applies

**Given** I want to use only a specific provider (e.g., only Anthropic)
**When** I configure SECBASH_PRIMARY_MODEL and leave fallbacks empty
**Then** only that model is used for validation

**Implementation Notes:**
- Environment variables: SECBASH_PRIMARY_MODEL, SECBASH_FALLBACK_MODELS (comma-separated)
- Defaults remain: openrouter/meta-llama/llama-guard-3-8b with openai/gpt-4 and anthropic/claude-3-haiku-20240307 fallbacks
- Model strings follow LiteLLM format (provider/model-name)
