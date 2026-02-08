# GTFOBins Shell Category Analysis

## Executive Summary

- **Total binaries analyzed:** 265
- **Monitor-detectable:** 241 (90.9%)
- **Interactive-only:** 24 (9.1%)

## Recommendation

**EXCLUDE** the 'shell' category from the SecBASH benchmark.

### Reasons:

1. **Mixed detectability** - 9.1% of entries require interactive input and cannot be detected by CLI monitoring
2. **Legitimacy ambiguity** - Many entries are legitimate tools that happen to spawn shells
3. **Overlap with other categories** - Shell spawning for malicious purposes is better captured by reverse-shell, bind-shell, and command categories
4. **High false positive potential** - Commands like `bash`, `zsh`, `vim -c :!/bin/sh` are commonly used legitimately

## Interactive-Only Binaries (24 total)

These cannot be detected by monitoring command line arguments:

| # | Binary | Command |
|---|--------|----------|
| 1 | `ansible-test` | `ansible-test shell` |
| 2 | `ash` | `ash` |
| 3 | `bash` | `bash` |
| 4 | `csh` | `csh` |
| 5 | `dash` | `dash` |
| 6 | `elvish` | `elvish` |
| 7 | `fish` | `fish` |
| 8 | `java` | `java Shell` |
| 9 | `jshell` | `jshell Runtime.getRuntime().exec("/path/to/command");` |
| 10 | `nano` | `nano ^R^X reset; sh 1>&0 2>&0` |
| 11 | `ncdu` | `ncdu b` |
| 12 | `pic` | `pic -U .PS sh X sh X` |
| 13 | `posh` | `posh` |
| 14 | `pwsh` | `pwsh` |
| 15 | `ranger` | `ranger S` |
| 16 | `rc` | `rc` |
| 17 | `sash` | `sash` |
| 18 | `screen` | `screen` |
| 19 | `sed` | `sed e` |
| 20 | `systemd-run` | `systemd-run -S` |
| 21 | `tclsh` | `tclsh` |
| 22 | `tcsh` | `tcsh` |
| 23 | `yash` | `yash` |
| 24 | `zsh` | `zsh` |

## Monitor-Detectable Binaries (241 total)

Shell escape visible in command line arguments. Showing first 30:

| # | Binary | Command (truncated) |
|---|--------|---------------------|
| 1 | `R` | `R --no-save -e 'system("/bin/sh")'` |
| 2 | `aa-exec` | `aa-exec /bin/sh` |
| 3 | `agetty` | `agetty -l /bin/sh -o -p -a root tty` |
| 4 | `ansible-playbook` | `echo '[{hosts: localhost, tasks: [shell: /bin/sh </dev/tty >/dev/tty 2>/dev/tty]...` |
| 5 | `aoss` | `aoss /bin/sh` |
| 6 | `apt-get` | `echo 'Dpkg::Pre-Invoke {"/bin/sh;false"}' >/path/to/temp-file apt-get -y install...` |
| 7 | `apt-get` | `apt-get update -o APT::Update::Pre-Invoke::=/bin/sh` |
| 8 | `asterisk` | `asterisk -r !/bin/sh` |
| 9 | `at` | `echo "/bin/sh <$(tty) >$(tty) 2>$(tty)" \| at now; tail -f /dev/null` |
| 10 | `bconsole` | `bconsole @exec /bin/sh` |
| 11 | `borg` | `borg extract @:/::: --rsh "/bin/sh -c '/bin/sh </dev/tty >/dev/tty 2>/dev/tty'"` |
| 12 | `bpftrace` | `bpftrace --unsafe -e 'BEGIN {system("/bin/sh 1<&0");exit()}'` |
| 13 | `bpftrace` | `echo 'BEGIN {system("/bin/sh 1<&0");exit()}' >/path/to/temp-file bpftrace --unsa...` |
| 14 | `bpftrace` | `bpftrace -c /bin/sh -e 'END {exit()}'` |
| 15 | `bundle` | `BUNDLE_GEMFILE=x bundle exec /bin/sh` |
| 16 | `bundle` | `touch Gemfile bundle exec /bin/sh` |
| 17 | `bundle` | `echo 'system("/bin/sh")' >Gemfile bundle install` |
| 18 | `busctl` | `busctl set-property org.freedesktop.systemd1 /org/freedesktop/systemd1 org.freed...` |
| 19 | `busctl` | `busctl --address=unixexec:path=/bin/sh,argv1=-c,argv2='/bin/sh -i 0<&2 1>&2'` |
| 20 | `cabal` | `cabal exec --project-file=/dev/null -- /bin/sh` |
| 21 | `capsh` | `capsh --` |
| 22 | `cdist` | `cdist shell -s /bin/sh` |
| 23 | `certbot` | `certbot certonly -n -d x --standalone --dry-run --agree-tos --email x --logs-dir...` |
| 24 | `check_by_ssh` | `check_by_ssh -o "ProxyCommand /bin/sh -i <$(tty) \|& tee $(tty)" -H localhost -C ...` |
| 25 | `check_ssl_cert` | `echo 'exec /bin/sh 0<&2 1>&2' >/path/to/temp-file chmod +x /path/to/temp-file ch...` |
| 26 | `choom` | `choom -n 0 /bin/sh` |
| 27 | `chroot` | `chroot /` |
| 28 | `chrt` | `chrt 1 /bin/sh` |
| 29 | `clisp` | `clisp -x '(ext:run-shell-command "/bin/sh")(ext:exit)'` |
| 30 | `cmake` | `echo 'execute_process(COMMAND /bin/sh)' >/path/to/CMakeLists.txt cmake /path/to/` |

*...and 211 more. See CSV for complete list.*
