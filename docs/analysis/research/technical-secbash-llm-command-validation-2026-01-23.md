---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'aegish - LLM-based shell command validation'
research_goals: 'Understand existing shell security solutions, LLM-based security tools, command interception techniques, threat models for dangerous commands, and user experience patterns'
user_name: 'guido'
date: '2026-01-23'
web_research_enabled: true
source_verification: true
---

# Technical Research: aegish - LLM-based Shell Command Validation

## Technical Research Scope Confirmation

**Research Topic:** aegish - LLM-based shell command validation

**Research Goals:** Understand existing shell security solutions, LLM-based security tools, command interception techniques, threat models for dangerous commands, and user experience patterns

**Technical Research Scope:**

- Architecture Analysis - design patterns, frameworks, system architecture
- Implementation Approaches - development methodologies, coding patterns
- Technology Stack - languages, frameworks, tools, platforms
- Integration Patterns - APIs, protocols, interoperability
- Performance Considerations - scalability, optimization, patterns

**Research Methodology:**

- Current web data with rigorous source verification
- Multi-source validation for critical technical claims
- Confidence level framework for uncertain information
- Comprehensive technical coverage with architecture-specific insights

**Scope Confirmed:** 2026-01-23

---

## Technology Stack Analysis

### Command Interception Technologies

#### Bash Preexec Hooks [High Confidence]

The most mature approach for intercepting commands before execution in Bash uses the **bash-preexec** library, which provides Zsh-style `preexec` and `precmd` hook functions for Bash 3.1+.

| Approach | Bash Version | Complexity | Production Use |
|----------|--------------|------------|----------------|
| **bash-preexec library** | 3.1+ | Low | Bashhub, iTerm2, Ghostty |
| **DEBUG trap + PROMPT_COMMAND** | 3.0+ | Medium | Custom solutions |
| **PS0 variable** | 4.4+ | Low | Limited |
| **Native preexec** | 5.3+ | Low | Emerging |

The bash-preexec approach combines the DEBUG trap and PROMPT_COMMAND to execute code right before and right after a command runs. It's currently used in production by Bashhub, iTerm2, and Ghostty.

_Source: [bash-preexec GitHub](https://github.com/rcaloras/bash-preexec), [Native Bash Preexec](https://posix.nexus/posts/native-bash-preexec/)_

#### ptrace System Call Interception [High Confidence]

For deeper system-level interception, the **ptrace()** system call allows a tracer process to observe and control another process's execution, including:

- Intercepting and mutating system call arguments
- Blocking certain system calls entirely
- Monitoring all shell input/output

Facebook's **Reverie** framework provides an "ergonomic and safe syscall interception framework for Linux" using ptrace.

_Source: [ptrace manual](https://man7.org/linux/man-pages/man2/ptrace.2.html), [Reverie GitHub](https://github.com/facebookexperimental/reverie), [Intercepting syscalls with ptrace](https://notes.eatonphil.com/2023-10-01-intercepting-and-modifying-linux-system-calls-with-ptrace.html)_

### Programming Languages & Frameworks

#### Recommended Stack for aegish

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Shell Integration** | Bash + bash-preexec | Mature, production-tested, minimal dependencies |
| **Core Logic** | Python 3.10+ | Rich LLM client libraries, readline integration |
| **Alternative** | Rust | Performance-critical path, safer memory handling |
| **LLM Integration** | OpenAI/Anthropic SDKs | Official clients with streaming support |

#### Python Shell Libraries

- **readline module** (stdlib) - GNU readline interface for command-line editing and history
- **gnureadline** (PyPI) - Statically linked GNU readline for cross-platform compatibility
- **rlwrap** - Wrapper providing readline capabilities with filter plugins in Python/Perl
- **cmd module** - Built-in framework for interactive command interpreters

_Source: [Python readline docs](https://docs.python.org/3/library/readline.html), [gnureadline PyPI](https://pypi.org/project/gnureadline/), [rlwrap GitHub](https://github.com/hanslub42/rlwrap)_

### LLM Security Tools & Frameworks

#### Enterprise Platforms [High Confidence]

| Tool | Focus | Latency | Key Feature |
|------|-------|---------|-------------|
| **Lakera Guard** | Prompt injection prevention | <50ms | Real-time LLM protection |
| **Mindgard** | AI red teaming | Varies | MITRE ATLAS alignment |
| **LLM Guard (Protect AI)** | Input/output filtering | Low | Data leakage prevention |

#### Open-Source Frameworks [High Confidence]

| Framework | Purpose | Language |
|-----------|---------|----------|
| **Guardrails AI** | Output validation & correction | Python |
| **AgentFence** | AI agent security testing | Python |
| **Adversarial Robustness Toolbox (ART)** | ML model security | Python |

These tools address prompt injection, jailbreaks, and unsafe model behavior - patterns directly applicable to aegish's command validation.

_Source: [Mindgard](https://mindgard.ai/blog/best-ai-security-tools-for-llm-and-genai), [LLM Security Tools 2026](https://www.deepchecks.com/top-llm-security-tools-frameworks/), [Guardrails AI](https://research.aimultiple.com/llm-security-tools/)_

### Existing Shell Security Solutions

#### Restricted Shells & Sudo Mechanisms [High Confidence]

| Mechanism | Protection Level | Bypass Risk |
|-----------|-----------------|-------------|
| **rbash (restricted bash)** | Medium | Well-documented escapes |
| **sudoers NOEXEC** | Medium-High | Prevents shell escapes from allowed binaries |
| **chroot/containers** | High | Requires careful configuration |
| **SELinux/AppArmor** | High | Policy complexity |

Key sudo security features:
- **NOEXEC tag** - Prevents dynamically-linked executables from spawning further commands
- **Environment restrictions** - LESSSECURE=1 to disable shell escapes in tools like `less`
- **Absolute paths** - Requiring full paths prevents PATH manipulation attacks

_Source: [sudoers manual](https://linux.die.net/man/5/sudoers), [Dangerous Sudoers Entries](https://blog.compass-security.com/2012/10/dangerous-sudoer-entries-part-1-command-execution/), [CISA Command Injection Guide](https://www.cisa.gov/resources-tools/resources/secure-design-alert-eliminating-os-command-injection-vulnerabilities)_

#### Security Auditing Tools

| Tool | Purpose |
|------|---------|
| **SUDO_KILLER** | Identifies sudo privilege escalation vulnerabilities |
| **LinPEAS** | Linux privilege escalation enumeration |
| **LinEnum** | Privilege escalation path discovery |

_Source: [SUDO_KILLER GitHub](https://github.com/TH3xACE/SUDO_KILLER)_

### Dangerous Command Categories

Based on security research, commands aegish should flag include:

| Category | Examples | Risk Level |
|----------|----------|------------|
| **Destructive** | `rm -rf /`, `mkfs`, `dd if=/dev/zero` | Critical |
| **Privilege Escalation** | `sudo`, `su`, `chmod 777` | High |
| **Shell Escapes** | `!` in less/vim, `:shell` | High |
| **Data Exfiltration** | `curl`, `wget`, `nc` with sensitive paths | Medium-High |
| **Persistence** | `crontab`, `.bashrc` modifications | Medium |
| **Reconnaissance** | `cat /etc/passwd`, `ps aux` | Low-Medium |

_Source: [8 Risky Unix Commands - Proofpoint](https://www.proofpoint.com/us/blog/insider-threat-management/8-risky-commands-unix), [Dangerous Linux Commands](https://phoenixnap.com/kb/dangerous-linux-terminal-commands)_

---

## Integration Patterns Analysis

### LLM API Integration Patterns

#### Streaming vs Batch Responses [High Confidence]

For aegish's command validation, **streaming is not recommended** - you need the complete validation decision before allowing command execution. However, streaming architecture concepts inform the design:

| Pattern | Use Case for aegish | Recommendation |
|---------|---------------------|----------------|
| **Synchronous (blocking)** | Command validation | **Primary** - wait for full response |
| **Streaming** | User feedback during long analysis | Optional UX enhancement |
| **Async batch** | Background learning/analysis | Deferred processing |

The transition from batch to streaming LLM interactions represents a fundamental architectural shift. For aegish, the key insight is that streaming enables **early termination** - stop generating when you have enough information to make a decision.

_Source: [Streaming LLM Responses](https://dataa.dev/2025/02/18/streaming-llm-responses-building-real-time-ai-applications/), [Streaming LLMs Reshaping API Design](https://nitishagar.medium.com/the-streaming-llms-reshaping-api-design-a9102db9b8ef)_

#### Server-Sent Events (SSE) Standard

SSE is the de facto standard for LLM streaming, used by OpenAI, Anthropic, and most LLM APIs natively. For aegish, if implementing streaming feedback:

```
User types command → aegish intercepts → LLM validates (SSE stream) → Decision rendered → Execute or block
```

_Source: [Complete Guide to Streaming LLM](https://dev.to/hobbada/the-complete-guide-to-streaming-llm-responses-in-web-applications-from-sse-to-real-time-ui-3534)_

### Latency Optimization Strategies

#### Critical for aegish UX [High Confidence]

Command validation must be **fast** to avoid frustrating users. Key optimization strategies:

| Strategy | Latency Impact | Implementation Complexity |
|----------|---------------|---------------------------|
| **Prompt Caching** | Up to 80% reduction | Low |
| **Token Optimization** | 20-40% reduction | Medium |
| **Streaming (early termination)** | Variable | Medium |
| **Parallel validation** | Near-linear speedup | High |
| **Local model fallback** | Eliminates API latency | High |

#### Prompt Caching [High Confidence]

Prompt caching gives the model a "head start," resulting in faster responses and notable reduction in Time To First Token (TTFT). Research shows up to **80% latency improvement** and **90% cost reduction** without affecting output quality.

For aegish, cache the system prompt and dangerous command patterns - only the user's specific command changes per request.

_Source: [Claude Reducing Latency](https://docs.anthropic.com/claude/docs/reducing-latency), [Georgian AI Latency Guide](https://georgian.io/reduce-llm-costs-and-latency-guide/)_

#### Token Minimization

Minimize tokens in both input prompt and expected output. For aegish:
- Use structured JSON output (safer decision: true/false)
- Keep system prompts concise
- Request only essential reasoning

_Source: [Claude Latency Optimization](https://claude-ai.chat/blog/latency-optimization-in-claude/), [SigNoz Claude API Latency](https://signoz.io/guides/claude-api-latency/)_

### Caching Strategies

#### Semantic vs Exact Caching [High Confidence]

| Caching Type | Description | aegish Application |
|--------------|-------------|---------------------|
| **Exact match** | Identical query lookup | Same command = cached decision |
| **Semantic caching** | Similar query matching via embeddings | Similar commands share validation |

GPTCache uses semantic caching because exact match is less effective for LLM queries. For aegish, consider:
- **Exact cache**: `rm -rf /home/user` → cached as dangerous
- **Semantic cache**: `rm -rf /home/*` → matches similar dangerous pattern

#### Recommended Tools

| Tool | Purpose | Key Feature |
|------|---------|-------------|
| **LiteLLM** | Caching + proxy | Stores and reuses LLM responses |
| **GPTCache** | Semantic caching | Claims 10x cost reduction, 100x speed |
| **Redis** | Fast memory cache | Quick responses for frequent queries |

_Source: [GPTCache GitHub](https://github.com/zilliztech/GPTCache), [LiteLLM Caching](https://docs.litellm.ai/docs/proxy/caching), [Ultimate Guide to LLM Caching](https://latitude-blog.ghost.io/blog/ultimate-guide-to-llm-caching-for-low-latency-ai/)_

### Offline Fallback Architecture

#### Critical for Reliability [High Confidence]

aegish must work when the network is unavailable. Strategies:

| Approach | Pros | Cons |
|----------|------|------|
| **Local LLM (Ollama)** | Full functionality offline | Requires GPU/resources |
| **Rule-based fallback** | Fast, reliable | Limited to known patterns |
| **Cached decisions** | Zero latency | Only covers seen commands |
| **Fail-open (allow)** | No user friction | Security gap |
| **Fail-closed (block)** | Maximum security | User friction |

#### Ollama for Offline Operation

Ollama uses a local model library that works offline once models are pulled. Set environment variables:
- `HF_DATASETS_OFFLINE=1`
- `TRANSFORMERS_OFFLINE=1`
- `HF_HUB_OFFLINE=1`

Maintain multiple tool chains (llama.cpp, Ollama, transformers) so one missing dependency doesn't halt all operations.

_Source: [How to Run LLMs Offline](https://mljourney.com/how-to-run-llms-offline-complete-guide/), [LiteLLM Load Balancing](https://www.tanyongsheng.com/note/litellm-proxy-for-high-availability-llm-services-load-balancing-techniques/)_

### Validation Pipeline Architecture

#### aegish Pipeline Design [High Confidence]

Based on DevSecOps pipeline patterns and the Pipeline Pattern for data processing:

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│ Command     │───▶│ Local Rules  │───▶│ LLM         │───▶│ Decision     │
│ Intercept   │    │ (fast path)  │    │ Validation  │    │ Enforcement  │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
                          │                   │
                          ▼                   ▼
                   ┌──────────────┐    ┌─────────────┐
                   │ Cache Check  │    │ Offline     │
                   │              │    │ Fallback    │
                   └──────────────┘    └─────────────┘
```

#### Pipeline Stages

1. **Command Intercept** - bash-preexec captures command before execution
2. **Local Rules (fast path)** - Known dangerous patterns blocked immediately
3. **Cache Check** - Return cached decision if available
4. **LLM Validation** - Query LLM for uncertain commands
5. **Offline Fallback** - Local model or rule-based if API unavailable
6. **Decision Enforcement** - Allow, block, or prompt user

The Pipeline Pattern organizes processing into discrete stages where each stage transforms data and passes it to the next - ideal for aegish's validation flow.

_Source: [Pipeline Pattern](https://dev.to/wallacefreitas/the-pipeline-pattern-streamlining-data-processing-in-software-architecture-44hn), [OWASP SPVS](https://owasp.org/www-project-spvs/)_

### Real-Time Validation with Guardrails AI

#### Streaming Validation Pattern [Medium Confidence]

Guardrails AI enables streaming validation - validating each valid fragment as the LLM returns it. For JSON responses, it defines a "valid fragment" as a chunk that lints as fully-formed JSON, then performs sub-schema validation.

For aegish, this means:
- Define a strict JSON schema for validation responses
- Validate incrementally as tokens arrive
- Make decision as soon as schema is satisfied

_Source: [Guardrails AI Real-Time Validation](https://www.guardrailsai.com/blog/validate-llm-responses-real-time)_

### Structured Output for Reliable Decisions

#### JSON Schema Validation [High Confidence]

Both Guardrails AI and native LLM structured outputs follow the pattern:
1. Define data structure (Pydantic model)
2. Generate JSON schema
3. Send schema to LLM as formatting instructions
4. Validate response against original model

For aegish, define a strict decision schema:

```python
class ValidationDecision(BaseModel):
    safe: bool
    risk_level: Literal["none", "low", "medium", "high", "critical"]
    reason: str
    suggested_alternative: Optional[str]
```

_Source: [Structured Outputs Guide](https://agenta.ai/blog/the-guide-to-structured-outputs-and-function-calling-with-llms), [API Design for LLM Apps](https://www.gravitee.io/blog/designing-apis-for-llm-apps)_

---

## Architectural Patterns and Design

### Core Architecture Pattern: Interceptor + Chain of Responsibility

aegish's architecture combines two foundational patterns:

#### Interceptor Pattern [High Confidence]

The Interceptor pattern is ideal for aegish because:
- **Transparency** - The change is transparent; the rest of the system (shell) works as before
- **Non-intrusive** - Allows extension without modifying the shell or application code
- **Configurable** - Interceptors can be registered dynamically at runtime or via config

The pattern uses a predefined interface for extension and a dispatching mechanism where interceptors are registered. Context objects provide access to the framework's internal state.

Functions added through interceptors include: monitoring, logging/measurement, **security**, caching, and load balancing.

_Source: [Interceptor Pattern Wikipedia](https://en.wikipedia.org/wiki/Interceptor_pattern), [Introduction to Interceptor Pattern](https://medium.com/@octaviantuchila14/introduction-to-the-interceptor-pattern-899218598852)_

#### Chain of Responsibility Pattern [High Confidence]

The Chain of Responsibility pattern allows passing requests along a chain of handlers. Each handler decides to process or pass to the next handler.

| Benefit | Application to aegish |
|---------|----------------------|
| **Separation of concerns** | Each validation rule is a standalone handler |
| **Modular code** | Add/remove validations without touching others |
| **Runtime flexibility** | Insert, remove, or reorder handlers dynamically |
| **Testability** | Individual handlers tested in isolation |

This pattern eliminates brittle if-else chains that violate the Open/Closed Principle.

_Source: [Chain of Responsibility](https://refactoring.guru/design-patterns/chain-of-responsibility), [Validation Pipeline with CoR](https://zeeshan01.medium.com/implement-pipeline-pattern-with-simple-password-validation-2b061995f31e)_

### aegish Handler Chain Design

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Command Validation Chain                        │
├─────────────┬─────────────┬─────────────┬─────────────┬───────────────┤
│  Whitelist  │  Blacklist  │   Cache     │    LLM      │   Decision    │
│   Handler   │   Handler   │   Handler   │   Handler   │   Handler     │
│             │             │             │             │               │
│ Known-safe  │ Known-bad   │ Previously  │ AI-based    │ Final allow/  │
│ commands    │ patterns    │ validated   │ analysis    │ deny/prompt   │
└─────────────┴─────────────┴─────────────┴─────────────┴───────────────┘
       ↓             ↓             ↓             ↓              ↓
    ALLOW         BLOCK        RETURN       VALIDATE        ENFORCE
                            cached result
```

Each handler can:
- **Process** the request and return a decision
- **Pass** to the next handler in the chain
- **Short-circuit** the chain (e.g., whitelist allows immediately)

_Source: [Chain of Responsibility Pattern](https://algomaster.io/learn/lld/chain-of-responsibility), [Handling Validations Elegantly](https://medium.com/sahibinden-technology/implementing-the-chain-of-responsibility-pattern-to-handle-validations-in-an-elegant-manner-fc3703cd5052)_

### Security Proxy Pattern [High Confidence]

aegish acts as a **Protection Proxy** for shell command execution:

| Proxy Type | Description | aegish Application |
|------------|-------------|---------------------|
| **Protection Proxy** | Controls access based on rights | Validate before execution |
| **Virtual Proxy** | Placeholder for expensive objects | Lazy-load LLM connection |
| **Firewall Proxy** | Filters inconsistent requests | Block dangerous commands |

The proxy implements the same interface as the real object (shell) but adds security checks before calling the actual command execution.

_Source: [Proxy Pattern Wikipedia](https://en.wikipedia.org/wiki/Proxy_pattern), [Proxy Design Pattern](https://www.digitalocean.com/community/tutorials/proxy-design-pattern)_

### Guardrails Architecture Pattern [High Confidence]

LLM guardrails span five layers - aegish primarily operates at the **application** and **runtime** layers:

| Layer | aegish Implementation |
|-------|----------------------|
| **Application** | Input validation before LLM call |
| **API** | Structured output enforcement |
| **Runtime** | Command execution control |

#### Guardrail Types for aegish

| Type | Purpose | Implementation |
|------|---------|----------------|
| **Safety guardrails** | Prevent dangerous output | Block destructive commands |
| **Security guardrails** | Detect attacks | Prevent prompt injection in commands |

#### Guardrail Approaches

| Approach | Speed | Flexibility | aegish Use |
|----------|-------|-------------|-------------|
| **Rule-based** | Fast (μs) | Limited | Known patterns (rm -rf /) |
| **Neural** | Medium (ms) | High | Novel threats |
| **Hybrid** | Balanced | Balanced | **Recommended** |

_Source: [Safeguarding LLMs with Guardrails](https://medium.com/data-science/safeguarding-llms-with-guardrails-4f5d9f57cff2), [LLM Guardrails Best Practices](https://www.datadoghq.com/blog/llm-guardrails-best-practices/), [Guardrails AI GitHub](https://github.com/guardrails-ai/guardrails)_

### Fail-Safe Architecture Decisions

#### Fail-Closed vs Fail-Open [High Confidence]

| Mode | Behavior When Unavailable | Use Case |
|------|--------------------------|----------|
| **Fail-closed** | Deny all commands | High-security environments |
| **Fail-open** | Allow all commands | Development/convenience |
| **Fail-safe (hybrid)** | Use local rules, prompt user | **Recommended default** |

The critical implementation detail: the circuit breaker MUST fail CLOSED when the validation service is down - deny everything, not allow everything.

_Source: [Secure-by-Design Middleware 2025](https://blog.devsecopsguides.com/p/secure-by-design-access-control-middleware)_

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         aegish Shell                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Command   │  │  Validation │  │      LLM Service        │ │
│  │ Interceptor │─▶│   Pipeline  │─▶│  ┌─────┐ ┌──────────┐  │ │
│  │             │  │             │  │  │Cache│ │API Client│  │ │
│  │ bash-preexec│  │ Chain of    │  │  └─────┘ └──────────┘  │ │
│  │             │  │ Handlers    │  │         ↓              │ │
│  └─────────────┘  └─────────────┘  │  ┌──────────────────┐  │ │
│         │               │          │  │ Offline Fallback │  │ │
│         │               │          │  │    (Ollama)      │  │ │
│         │               │          │  └──────────────────┘  │ │
│         │               │          └─────────────────────────┘ │
│         │               ↓                                      │
│         │        ┌─────────────┐                               │
│         │        │  Decision   │                               │
│         │        │  Enforcer   │                               │
│         │        └─────────────┘                               │
│         │               │                                      │
│         ▼               ▼                                      │
│  ┌─────────────────────────────────────────┐                   │
│  │           Shell Execution Layer          │                   │
│  │  ALLOW → execute | BLOCK → deny | PROMPT │                   │
│  └─────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles

#### Separation of Concerns

| Component | Responsibility |
|-----------|---------------|
| **Interceptor** | Capture commands only |
| **Pipeline** | Orchestrate validation flow |
| **Handlers** | Individual validation rules |
| **LLM Service** | AI-based analysis |
| **Enforcer** | Execute decisions |

#### Open/Closed Principle

The Chain of Responsibility enables adding new validation rules without modifying existing code - essential for evolving threat detection.

#### Single Responsibility

Each handler has ONE job:
- WhitelistHandler: Check known-safe commands
- BlacklistHandler: Check known-dangerous patterns
- CacheHandler: Return cached decisions
- LLMHandler: Query AI for analysis
- DecisionHandler: Enforce final verdict

_Source: [Security Patterns in Practice](https://www.amazon.com/Security-Patterns-Practice-Designing-Architectures/dp/1119998948), [Azure Security Design Patterns](https://learn.microsoft.com/en-us/azure/well-architected/security/design-patterns)_

---

## Implementation Summary

### Quick Start Stack

| Component | Tool | Install |
|-----------|------|---------|
| Shell hook | bash-preexec | `curl -o ~/.bash-preexec.sh https://raw.githubusercontent.com/rcaloras/bash-preexec/master/bash-preexec.sh` |
| Core logic | Python 3.10+ + Click/Typer | `pip install typer openai anthropic` |
| LLM client | OpenAI/Anthropic SDK | Built-in |
| Cache | GPTCache or Redis | `pip install gptcache` |
| Offline | Ollama | `curl -fsSL https://ollama.com/install.sh \| sh` |

### Testing Strategy

| Type | Tool | Purpose |
|------|------|---------|
| Unit tests | pytest + unittest.mock | Mock LLM responses |
| Integration | vcrpy/pytest-recording | Record/replay API calls |
| E2E | Fake LLM backend | Full flow without API costs |

_Source: [bash-preexec GitHub](https://github.com/rcaloras/bash-preexec), [Mock LLM API Calls](https://markaicode.com/mock-llm-api-calls-unit-testing/), [LangChain Testing](https://docs.langchain.com/oss/python/langchain/test)_

---

## Research Conclusions

### Recommended Approach

1. **Start with bash-preexec** - Production-proven, used by iTerm2/Ghostty
2. **Python + Typer for CLI** - Fast development, rich LLM ecosystem
3. **Chain of Responsibility** - Pluggable validation handlers
4. **Hybrid validation** - Fast rules first, LLM for uncertain cases
5. **GPTCache for semantic caching** - Reduce latency and costs
6. **Ollama fallback** - Offline capability essential

### Key Metrics to Target

| Metric | Target |
|--------|--------|
| Validation latency (cached) | <50ms |
| Validation latency (LLM) | <500ms |
| Cache hit rate | >70% |
| False positive rate | <5% |

---

**Research Complete: 2026-01-23**

