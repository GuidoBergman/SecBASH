# Related Work: AI/LLM-Powered Security Tools and Shell Assistants

This document surveys existing tools and projects that use AI/LLM/ML for command-line security, shell safety, or command validation.

---

## 1. Command Understanding and Safety Tools

### 1.1 ExplainShell

- **What it does**: Web-based tool that parses shell commands and provides man-page-sourced explanations for each component. Uses static analysis of man pages, not AI.
- **How it relates**: Focuses on command understanding/explanation but without security classification.
- **How aegish differs**: aegish performs security classification (safe/warn/block), not just explanation. aegish uses LLM reasoning rather than static man-page parsing, enabling understanding of novel or combined commands.
- **Source**: https://explainshell.com/

---

## 2. AI Coding Assistants with Shell Execution

### 2.1 Claude Code (Anthropic)

- **What it does**: Anthropic's CLI tool for AI-assisted coding. Includes a tiered permission model for command execution: some commands run automatically, some require user approval. Uses an internal safety classifier.
- **How it relates**: Validates AI-generated commands before execution using a permission model.
- **How aegish differs**: Claude Code validates commands that *it generates*; aegish validates commands that *users type*. Claude Code's safety model is embedded in the agent; aegish is a standalone shell replacement. aegish focuses exclusively on security classification; Claude Code's safety is one aspect of a broader coding assistant.
- **Source**: https://docs.anthropic.com/en/docs/claude-code

### 2.2 GitHub Copilot CLI

- **What it does**: Translates natural language to shell commands. Shows the generated command and asks for user confirmation before execution.
- **How it relates**: Pre-execution confirmation model for AI-generated commands.
- **How aegish differs**: Copilot CLI relies on *human* judgment at the confirmation step; aegish adds *AI* judgment. Copilot only covers commands it generates; aegish covers all commands. Copilot has no security classification -- it shows the command and the user decides.
- **Source**: https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-in-the-command-line

### 2.3 Amazon Q Developer CLI (formerly Fig/CodeWhisperer CLI)

- **What it does**: AI-powered CLI completions and natural-language-to-shell translation. Generates and explains commands.
- **How it relates**: AI-driven shell assistance with command generation.
- **How aegish differs**: Amazon Q focuses on command generation and productivity; aegish focuses on command safety. Q does not perform security classification of user-typed commands.
- **Source**: https://aws.amazon.com/q/developer/

### 2.4 Open Interpreter

- **What it does**: Runs LLM-generated code (Python, shell, JavaScript) with a safe mode that requires user confirmation. Sandboxes Docker execution.
- **How it relates**: Includes a safety layer (user confirmation) for LLM-generated commands.
- **How aegish differs**: Open Interpreter's safety is binary (confirm/deny by the human); aegish provides AI-driven classification with explanations. Open Interpreter is an LLM agent; aegish is a security-focused shell.
- **Source**: https://github.com/OpenInterpreter/open-interpreter

### 2.5 ShellGPT / AI Shell

- **What it does**: CLI tools that use LLMs to generate shell commands from natural language. ShellGPT (TheR1D/shell_gpt) supports multiple modes including shell command generation. AI Shell (BuilderIO/ai-shell) is similar.
- **How it relates**: LLM + shell integration, but for command *generation* not *validation*.
- **How aegish differs**: These tools *create* commands; aegish *evaluates* commands. They have no security validation layer -- generated commands execute without safety analysis.
- **Sources**: https://github.com/TheR1D/shell_gpt, https://github.com/BuilderIO/ai-shell

---

## 3. Enterprise AI Security Copilots

### 3.1 Microsoft Security Copilot

- **What it does**: GPT-4 based SOC assistant for Microsoft's security ecosystem. Helps analysts investigate incidents, analyze logs, correlate alerts, and generate incident reports.
- **How it relates**: Uses LLMs for security analysis, including understanding command-line activity in logs.
- **How aegish differs**: Security Copilot is post-incident analysis (helping analysts after events occur); aegish is pre-execution prevention (blocking commands before they run). Security Copilot is enterprise-grade infrastructure; aegish is a lightweight shell replacement. Different timing (post vs. pre), scope (enterprise SOC vs. individual shell), and use case (analysis vs. enforcement).

### 3.2 Google Security AI Workbench (Sec-PaLM / Gemini)

- **What it does**: Google's AI security platform, announced at RSA 2023 with the Sec-PaLM model and later transitioned to Gemini. Provides threat intelligence, malware analysis, and security operations assistance integrated with Mandiant and VirusTotal.
- **How it relates**: LLM-powered security analysis at enterprise scale.
- **How aegish differs**: Same distinction as Security Copilot -- post-hoc analysis vs. real-time pre-execution enforcement.

### 3.3 CrowdStrike Charlotte AI

- **What it does**: AI assistant built into the CrowdStrike Falcon platform. Helps threat hunters query their telemetry using natural language, correlate events, and generate reports.
- **How it relates**: Uses LLMs to understand and analyze endpoint security data, including command-line activity.
- **How aegish differs**: Charlotte AI operates on collected telemetry (post-execution data); aegish intercepts commands before they generate any telemetry. Charlotte AI helps analysts; aegish helps end users.

### 3.4 SentinelOne Purple AI

- **What it does**: AI-powered threat hunting and investigation assistant in the Singularity platform. Translates natural language queries into endpoint data searches.
- **How it relates**: Another enterprise LLM + security combination.
- **How aegish differs**: Same pattern -- post-hoc analysis vs. real-time prevention.

### 3.5 VirusTotal Code Insight

- **What it does**: Uses Gemini to analyze uploaded scripts (PowerShell, shell scripts, batch files) and explain their behavior, including identifying malicious patterns.
- **How it relates**: Closest enterprise tool to aegish's approach -- LLM analyzing script/command content for security.
- **How aegish differs**: VirusTotal is batch analysis of uploaded files; aegish is real-time analysis of individual commands. VirusTotal provides analysis; aegish enforces decisions (block/warn/allow).

---

## 4. Modern Shell Replacements with AI Features

### 4.1 Warp Terminal

- **What it does**: Modern terminal with AI built in. Warp AI helps users run, understand, and fix commands via natural language interaction. Features include command generation, explanation, and error debugging.
- **How it relates**: AI integrated into the terminal experience, including command understanding.
- **How aegish differs**: Warp's AI is for productivity (suggestions, explanations, debugging); aegish's AI is for security (safety classification). Warp's AI is opt-in assistance; aegish intercepts every command. aegish could theoretically be a safety layer within Warp.

### 4.2 Nushell

- **What it does**: Modern shell with structured data, strong types, and pipelines that understand data formats. Treats output as tables rather than text streams.
- **How it relates**: Safety through language design (type system prevents certain error classes).
- **How aegish differs**: Nushell provides implicit safety through types; aegish provides explicit security classification. They address different aspects of shell safety -- Nushell prevents bugs; aegish prevents attacks.

---

## 5. LLM Agent Sandboxing and Tool Safety Frameworks

### 5.1 E2B (Secure Sandboxes for AI Agents)

- **What it does**: Provides secure cloud sandboxes (microVMs) for AI agents. Each sandbox has its own isolated filesystem, processes, and network.
- **How it relates**: Addresses the same problem (safe code/command execution) through environmental isolation rather than command analysis.
- **How aegish differs**: aegish validates commands semantically on the user's real system; E2B runs code in disposable cloud sandboxes. aegish is preventive analysis; E2B is containment. Complementary approaches.
- **Source**: https://e2b.dev/

### 5.2 NVIDIA NeMo Guardrails

- **What it does**: Toolkit for adding programmable guardrails to LLM applications -- topical rails, safety rails, and security rails (prompt injection prevention).
- **How it relates**: Addresses LLM safety at the output level. Relevant to hardening aegish itself against adversarial inputs.
- **How aegish differs**: NeMo Guardrails protects LLM outputs generally; aegish uses LLMs specifically for command safety. However, NeMo Guardrails' prompt injection defenses are relevant to hardening aegish against adversarial command inputs.
- **Source**: https://github.com/NVIDIA/NeMo-Guardrails

### 5.3 LangChain Tool Safety / Guardrails AI

- **What it does**: LangChain provides security frameworks for AI agents including sandboxing tool execution and human-in-the-loop approval. Guardrails AI provides LLM output validation.
- **How it relates**: Tool-level safety for AI agents executing commands.
- **How aegish differs**: These frameworks target AI agent workflows (agent proposes, framework validates); aegish targets human shell sessions (user types, LLM validates). aegish provides semantic analysis rather than whitelist-based filtering.

### 5.4 ChatGPT Code Interpreter / OpenAI Sandbox

- **What it does**: Sandboxed Python environment for running AI-generated code. Restricted network access, filesystem isolation, resource limits.
- **How it relates**: Sandbox approach to code execution safety.
- **How aegish differs**: aegish runs on the user's real system with a safety layer; Code Interpreter runs in a separate disposable sandbox. Different tradeoff: aegish allows normal workflow with guardrails; Code Interpreter requires moving to an isolated environment.

### 5.5 sudo_pair (Square)

- **What it does**: Sudo plugin requiring another human to approve and monitor privileged sudo sessions. Implements a "two-person rule" for dangerous operations.
- **How it relates**: Pre-execution approval for dangerous commands -- same concept as aegish's WARN classification, but with human rather than AI review.
- **How aegish differs**: aegish uses an LLM as reviewer (immediately available, no second person needed). sudo_pair only covers `sudo` commands; aegish covers all commands.
- **Source**: https://github.com/square/sudo_pair

---

## 6. Static Analysis and Rule-Based Shell Safety

### 6.1 ShellCheck

- **What it does**: Static analysis linter for shell scripts. Identifies bugs, syntax issues, and potential problems using hand-crafted rules. Widely used in CI/CD pipelines.
- **How it relates**: Pre-execution analysis of shell code, but focused on correctness rather than security.
- **How aegish differs**: ShellCheck operates on shell scripts (batch, pre-commit); aegish operates on individual commands (interactive, real-time). ShellCheck catches bugs; aegish catches attacks. ShellCheck uses fixed rules; aegish uses LLM reasoning.
- **Source**: https://github.com/koalaman/shellcheck

### 6.2 Shellharden

- **What it does**: Corrective shell syntax hardener that rewrites shell code to be safer (e.g., quoting variables, preventing word splitting).
- **How it relates**: Shell safety through syntax transformation.
- **How aegish differs**: Shellharden makes shell code syntactically safer; aegish evaluates whether code is semantically malicious. Different problems -- shellharden prevents bugs from unquoted variables; aegish prevents intentional attacks.
- **Source**: https://github.com/anordal/shellharden

### 6.3 safe-rm / trash-cli / Molly-Guard

- **What they do**: Single-purpose safety wrappers. `safe-rm` prevents accidental deletion of critical paths. `trash-cli` moves files to trash instead of deleting. `Molly-Guard` asks for hostname confirmation before shutdown/reboot.
- **How they relate**: Pre-execution safety checks for specific dangerous commands.
- **How aegish differs**: These tools protect against one command or category; aegish evaluates *all* commands. They use hard-coded rules; aegish uses semantic understanding. aegish could subsume all their protections and extend to novel threats.

---

## 7. Summary Comparison Matrix

| Tool / Category | Approach | Scope | Timing | AI/ML | Explains Decisions |
|---|---|---|---|---|---|
| **aegish** | LLM semantic analysis | All shell commands | Pre-execution | Yes (LLM) | Yes (NL reasons) |
| Claude Code | Permission model | AI-generated commands | Pre-execution | Yes (built-in) | No |
| Copilot CLI | User confirmation | AI-suggested commands | Pre-execution | No (human decides) | No |
| Open Interpreter | User confirmation + sandbox | AI-generated code | Pre-execution | No (human decides) | No |
| ShellGPT / AI Shell | Command generation | AI-suggested commands | N/A (no validation) | Yes (generation only) | No |
| Warp Terminal | AI assistance | Command suggestions | N/A (productivity) | Yes (assistance only) | No |
| ShellCheck | Static rules | Shell scripts (batch) | Pre-execution (lint) | No | Yes (rule codes) |
| safe-rm / Molly-Guard | Hard-coded rules | Specific commands only | Pre-execution | No | Minimal |
| MS Security Copilot | LLM analysis | Enterprise SOC | Post-incident | Yes (LLM) | Yes |
| CrowdStrike Charlotte AI | LLM + telemetry | Enterprise EDR | Post-execution | Yes (LLM) | Yes |
| E2B | Cloud microVM sandbox | AI agent code | Runtime (containment) | No | No |
| NeMo Guardrails | Programmable rails | LLM outputs | Runtime | Yes (LLM) | Limited |
| sudo_pair | Human approval | sudo commands only | Pre-execution | No (human reviewer) | No |
