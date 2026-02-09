# Related Work: Threat Databases, Detection Frameworks, and Benchmarks

This document surveys tools, projects, and academic work related to GTFOBins, LOLBAS, and detection frameworks relevant to aegish's benchmark methodology.

---

## 1. GTFOBins

### What It Is
GTFOBins ("Get The F*** Out Binaries") is a curated, community-maintained list of Unix/Linux binaries that can be exploited to bypass local security restrictions in misconfigured systems. Each entry documents how a legitimate binary can be abused for: shell spawning, reverse shells, bind shells, file read/write, SUID/sudo exploitation, and capability abuse.

### Relevance to aegish
GTFOBins is the primary source for aegish's malicious command benchmark dataset. aegish extracts 676 commands across 389 binaries from GTFOBins categories (shell, reverse-shell, bind-shell, file-read, file-write, upload, download, command). The benchmark measures whether the LLM correctly classifies these as BLOCK.

### How aegish Uses GTFOBins Differently
Most tools reference GTFOBins as a static threat intelligence source -- writing Sigma rules or Falco rules to detect specific patterns. aegish's approach is fundamentally different: rather than encoding GTFOBins patterns as rules, aegish tests whether the LLM can *generalize* from its training data to recognize these attack patterns without explicit programming. This tests semantic understanding rather than pattern matching.

- **Source**: https://gtfobins.github.io/, https://github.com/GTFOBins/GTFOBins.github.io

---

## 2. LOLBAS (Living Off The Land Binaries And Scripts)

### What It Is
The Windows equivalent of GTFOBins. Catalogs Windows binaries, scripts, and libraries that can be used for malicious purposes: execution, lateral movement, persistence, credential theft. Maintained by the community at lolbas-project.github.io.

### Relevance to aegish
LOLBAS validates the generality of the "Living off the Land" threat model that aegish addresses. If aegish were extended to Windows (PowerShell), LOLBAS would serve the same role as GTFOBins in the benchmark. The existence of both GTFOBins and LOLBAS demonstrates that dual-use binary abuse is a cross-platform problem requiring semantic understanding.

### How aegish Differs
LOLBAS is a reference database; aegish is an enforcement mechanism. Tools that consume LOLBAS (e.g., Sigma rules, EDR detections) encode known patterns. aegish aims to detect the *class* of attack (binary abuse for unintended purposes) through semantic understanding.

- **Source**: https://lolbas-project.github.io/

---

## 3. LOLDrivers

### What It Is
Catalog of Windows drivers that can be exploited for kernel-level attacks. Documents signed drivers with known vulnerabilities that attackers use for privilege escalation and defense evasion.

### Relevance to aegish
Demonstrates the breadth of "Living off the Land" attacks beyond user-space binaries. While aegish currently focuses on shell commands, the driver abuse pattern shows that semantic analysis could extend to other system configuration commands (e.g., `insmod`, `modprobe` on Linux).

- **Source**: https://www.loldrivers.io/

---

## 4. MITRE ATT&CK Framework

### What It Is
A globally-accessible knowledge base of adversary tactics, techniques, and procedures (TTPs) based on real-world observations. Organized into 14 tactics (Reconnaissance through Impact) with hundreds of techniques. Version 18 (October 2025) is current as of early 2026.

### Relevance to aegish
aegish's threat model maps directly to multiple ATT&CK techniques:
- **T1059** (Command and Scripting Interpreter) -- aegish's primary detection target
- **T1059.004** (Unix Shell) -- Bash-specific command abuse
- **T1048** (Exfiltration Over Alternative Protocol) -- Data exfiltration via curl, wget
- **T1071** (Application Layer Protocol) -- Reverse shells over HTTP/HTTPS
- **T1053** (Scheduled Task/Job) -- Crontab manipulation
- **T1548** (Abuse Elevation Control Mechanism) -- sudo/SUID abuse
- **T1222** (File and Directory Permissions Modification) -- chmod attacks

### How aegish Differs from ATT&CK-Based Detection
ATT&CK-based detection (Sigma rules, EDR detections) encodes specific technique patterns. aegish's LLM can potentially recognize ATT&CK techniques it was trained on without explicit encoding, and may generalize to new sub-techniques. ATT&CK provides the taxonomy; aegish provides the detection mechanism.

- **Source**: https://attack.mitre.org/

---

## 5. Atomic Red Team

### What It Is
A library of simple, focused tests mapped to MITRE ATT&CK techniques. Each "atomic test" is a small script or command that exercises a specific technique. Used for detection validation and red team testing.

### Relevance to aegish
Atomic Red Team tests could serve as an additional benchmark dataset for aegish beyond GTFOBins. The Linux atomics for T1059.004 (Unix Shell), T1548.003 (SUID/SGID abuse), T1222.002 (Linux file permissions), etc., provide real-world attack command samples that could validate aegish's detection coverage.

### How aegish Differs
Atomic Red Team is a testing framework for validating detection capabilities. aegish is a prevention mechanism. Atomic Red Team executes attacks to test if they're detected; aegish would prevent those attacks from executing in the first place. Using Atomic Red Team commands as a benchmark would test aegish in a detection-before-execution scenario.

- **Source**: https://github.com/redcanaryco/atomic-red-team

---

## 6. Sigma Rules

### What It Is
A generic, open signature format for writing detection rules for SIEM systems. Over 3,000 rules covering Windows, Linux, and cloud environments. Rules can be converted to Splunk, Elastic, QRadar, and other SIEM query languages.

### Relevance to aegish
Sigma rules for Linux process creation (e.g., `proc_creation_lnx_reverse_shell.yml`, `proc_creation_lnx_susp_command.yml`) detect many of the same threats aegish targets. They represent the state-of-the-art in rule-based command detection.

### How aegish Differs
- **Timing**: Sigma rules detect commands *after* they execute (from process creation logs). aegish blocks *before* execution.
- **Approach**: Sigma uses regex/string patterns; aegish uses LLM semantic analysis.
- **Maintenance**: Sigma requires manual rule updates for new techniques; aegish's LLM may generalize to novel attacks.
- **False positives**: Sigma rules are tuned for specific environments; aegish's LLM makes context-dependent judgments.
- **Complementary**: Sigma rules can validate aegish's coverage -- commands matching Sigma Linux rules should also be caught by aegish.

- **Source**: https://github.com/SigmaHQ/sigma

---

## 7. YARA Rules

### What It Is
Pattern-matching tool for malware identification. YARA rules define byte patterns, strings, and conditions for classifying files as malicious.

### Relevance to aegish
YARA operates on file content (binary patterns, strings); aegish operates on command text. YARA could potentially be applied to command strings but would require manual rule creation for each pattern. The comparison highlights aegish's advantage: LLMs understand command semantics without requiring explicit pattern rules.

- **Source**: https://virustotal.github.io/yara/

---

## 8. Falco -- Runtime Security

### What It Is
CNCF graduated project for cloud-native runtime security. Uses eBPF or kernel modules to intercept system calls and apply detection rules. Default rules include: shell spawning in containers, reverse shell detection, unexpected process execution, sensitive file access.

### Relevance to aegish
Falco detects many of the same threats as aegish: reverse shells, shell escapes, suspicious commands. Falco has specific rules for GTFOBins detection patterns.

### How aegish Differs
- **Timing**: Falco detects *during/after* execution (monitors system calls); aegish blocks *before* execution.
- **Layer**: Falco operates at kernel level (system call interception); aegish operates at shell level (command string analysis).
- **Approach**: Falco uses rule-based pattern matching on system call parameters; aegish uses LLM semantic analysis on command text.
- **Environment**: Falco is designed for containerized/cloud-native environments; aegish works on any system with shell access.
- **Complementary**: aegish prevents commands before they generate system calls for Falco to analyze.

- **Source**: https://falco.org/, https://github.com/falcosecurity/falco

---

## 9. osquery

### What It Is
SQL-powered framework (originally from Meta/Facebook) for OS instrumentation and analytics. Exposes the OS as a relational database, allowing SQL queries to explore running processes, installed packages, logged-in users, and security events.

### Relevance to aegish
osquery can monitor process creation events including command-line arguments. Query like `SELECT * FROM process_events WHERE cmdline LIKE '%/dev/tcp%'` detects reverse shell patterns.

### How aegish Differs
- **Timing**: osquery queries historical/current state (post-execution); aegish evaluates commands pre-execution.
- **Approach**: osquery uses SQL pattern matching on OS state; aegish uses LLM semantic analysis.
- **Mode**: osquery is monitoring/analytics; aegish is prevention.

- **Source**: https://github.com/osquery/osquery

---

## 10. Security Datasets and Benchmarks

### 10.1 Schonlau Masquerade Detection Dataset
- 15,000 Unix commands per user across 50 users (750,000 total); foundational benchmark for command-based masquerade detection.
- **Relevance**: Earliest labeled dataset of Unix commands for security. Different task (user identification vs. command safety) but same domain.
- **Source**: https://www.schonlau.net/intrusion.html

### 10.2 ADFA-LD (Australian Defence Force Academy Linux Dataset)
- System call traces for normal and attack scenarios on Linux.
- **Relevance**: Benchmark for system-call-based IDS. Different abstraction level (syscalls vs. commands) but related problem.

### 10.3 NL2Bash Corpus
- Approximately 10,000 bash one-liner / natural language pairs from Lin et al. (2018, LREC; arXiv:1802.08979).
- **Relevance**: Demonstrates NLP understanding of bash commands. Could inform aegish's approach to command comprehension. Different task (NL-to-bash translation vs. safety classification).
- **Source**: https://github.com/TellinaTool/nl2bash

### 10.4 OTRF / Mordor Security Datasets
- Pre-recorded security events from attack simulations mapped to ATT&CK techniques.
- **Relevance**: Includes command-line data from simulated attacks. Could provide additional benchmark commands for aegish.
- **Source**: https://github.com/OTRF/Security-Datasets

### 10.5 LANL Unified Host and Network Dataset
- Los Alamos National Laboratory dataset including process creation events with command-line data.
- **Relevance**: Large-scale real-world command-line data for security research.

### 10.6 HuggingFace Bash Commands Dataset
- Source for aegish's harmless command benchmark (aelhalili/bash-commands-dataset). 840 original commands filtered to 290 safe commands, then extended with 206 LLM-generated commands covering additional developer workflows for a total of 496 harmless benchmark commands.
- **Relevance**: Direct component of aegish's evaluation methodology.

---

## 11. Key Observations

### aegish's Benchmark Contribution
aegish's benchmark methodology is itself a contribution: combining GTFOBins (malicious ground truth) with filtered harmless commands to create a balanced evaluation for command safety classifiers. This paired benchmark (malicious + benign) is not available elsewhere for shell command security evaluation.

### Gap in Existing Detection
Existing detection frameworks (Sigma, Falco, YARA, osquery) all operate *after* commands execute. They analyze logs, system calls, or process creation events. aegish fills a gap by operating *before* execution -- the only tool in this survey that prevents rather than detects.

### Semantic vs. Syntactic Detection
The fundamental distinction: GTFOBins documents hundreds of ways to abuse legitimate binaries. Encoding each as a detection rule (Sigma/Falco approach) creates a maintenance burden and misses novel variations. aegish's LLM approach aims to detect the *class* of abuse (shell escape, reverse shell, data exfiltration) regardless of the specific binary or syntax used.
