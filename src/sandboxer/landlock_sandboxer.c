/*
 * landlock_sandboxer.c -- LD_PRELOAD library that applies Landlock
 * restrictions inside the bash process, denying execution of all
 * shell binaries listed in DENIED_SHELLS.
 *
 * Loaded via LD_PRELOAD in the subprocess environment.
 * Constructor runs before bash main(), so restrictions are in place
 * before any user command is evaluated.
 *
 * Exit behavior:
 *   On failure, calls _exit(126) to abort the process before bash
 *   can run any user commands. This is fail-safe.
 *
 * prctl(PR_SET_NO_NEW_PRIVS) is called here to make the library
 * self-sufficient. For the normal path, Python's preexec_fn already
 * set it (idempotent). For the sudo path, no preexec_fn runs, so
 * the library must set it before landlock_restrict_self().
 */

#define _GNU_SOURCE
#include <dirent.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/landlock.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>

/*
 * Must match DENIED_SHELLS in sandbox.py.
 * Known limitation: path-based denylist; copy/rename bypasses it.
 */
static const char *DENIED_SHELLS[] = {
    "/bin/bash",      "/usr/bin/bash",
    "/bin/sh",        "/usr/bin/sh",
    "/bin/dash",      "/usr/bin/dash",
    "/bin/zsh",       "/usr/bin/zsh",
    "/bin/fish",      "/usr/bin/fish",
    "/bin/ksh",       "/usr/bin/ksh",
    "/bin/csh",       "/usr/bin/csh",
    "/bin/tcsh",      "/usr/bin/tcsh",
    "/bin/ash",       "/usr/bin/ash",
    "/bin/busybox",   "/usr/bin/busybox",
    "/bin/mksh",      "/usr/bin/mksh",
    "/bin/rbash",     "/usr/bin/rbash",
    "/bin/elvish",    "/usr/bin/elvish",
    "/bin/nu",        "/usr/bin/nu",
    "/bin/pwsh",      "/usr/bin/pwsh",
    "/bin/xonsh",     "/usr/bin/xonsh",
    NULL
};

/*
 * Check if a path (or its resolved form) matches a denied shell.
 */
static int is_denied(const char *path, const char *resolved) {
    for (const char **s = DENIED_SHELLS; *s != NULL; s++) {
        if (strcmp(path, *s) == 0 || strcmp(resolved, *s) == 0)
            return 1;
    }
    return 0;
}

/*
 * Add an EXECUTE rule for a single file path to the Landlock ruleset.
 */
static int add_exec_rule(int ruleset_fd, const char *path) {
    int fd = open(path, O_PATH | O_CLOEXEC);
    if (fd < 0) return -1;

    struct landlock_path_beneath_attr rule = {
        .allowed_access = LANDLOCK_ACCESS_FS_EXECUTE,
        .parent_fd = fd,
    };
    int ret = (int)syscall(SYS_landlock_add_rule, ruleset_fd,
                           LANDLOCK_RULE_PATH_BENEATH, &rule, 0);
    close(fd);
    return ret;
}

__attribute__((constructor))
static void apply_sandbox(void) {
    /* 1. Create Landlock ruleset for EXECUTE access */
    struct landlock_ruleset_attr attr = {
        .handled_access_fs = LANDLOCK_ACCESS_FS_EXECUTE,
    };
    int ruleset_fd = (int)syscall(SYS_landlock_create_ruleset,
                                  &attr, sizeof(attr), 0);
    if (ruleset_fd < 0) {
        /* Landlock not supported -- fail safe, don't allow unprotected execution */
        perror("landlock_sandboxer: create_ruleset");
        _exit(126);
    }

    /* 2. Enumerate PATH directories and add rules for allowed executables */
    const char *path_env = getenv("PATH");
    if (!path_env || !*path_env) {
        close(ruleset_fd);
        fprintf(stderr, "landlock_sandboxer: PATH is empty\n");
        _exit(126);
    }

    char *path_copy = strdup(path_env);
    if (!path_copy) { close(ruleset_fd); _exit(126); }

    char *saveptr = NULL;
    for (char *dir = strtok_r(path_copy, ":", &saveptr);
         dir != NULL;
         dir = strtok_r(NULL, ":", &saveptr))
    {
        DIR *d = opendir(dir);
        if (!d) continue;

        struct dirent *ent;
        while ((ent = readdir(d)) != NULL) {
            char fullpath[PATH_MAX];
            int n = snprintf(fullpath, sizeof(fullpath), "%s/%s", dir, ent->d_name);
            if (n < 0 || (size_t)n >= sizeof(fullpath)) continue;

            struct stat st;
            if (stat(fullpath, &st) != 0)      continue;
            if (!S_ISREG(st.st_mode))           continue;
            if (!(st.st_mode & (S_IXUSR | S_IXGRP | S_IXOTH))) continue;

            char resolved[PATH_MAX];
            if (!realpath(fullpath, resolved)) continue;

            if (is_denied(fullpath, resolved))
                continue;

            add_exec_rule(ruleset_fd, fullpath);
        }
        closedir(d);
    }
    free(path_copy);

    /* 3. Ensure NO_NEW_PRIVS is set (required by landlock_restrict_self).
     *    Idempotent: harmless if already set by Python preexec_fn.
     *    Essential for the sudo path where no preexec_fn runs. */
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        perror("landlock_sandboxer: prctl(NO_NEW_PRIVS)");
        close(ruleset_fd);
        _exit(126);
    }

    /* 4. Activate Landlock */
    if (syscall(SYS_landlock_restrict_self, ruleset_fd, 0) != 0) {
        perror("landlock_sandboxer: restrict_self");
        close(ruleset_fd);
        _exit(126);
    }

    close(ruleset_fd);
    /* Constructor returns, bash main() proceeds under Landlock */
}
