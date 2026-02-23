# Test file for aegish-missing-sandbox rules

import subprocess
import os


def _sandbox_kwargs():
    return {}


def _build_safe_env():
    return {}


sandbox_kw = {}


# --- TRUE POSITIVES ---

def dangerous_no_sandbox(command):
    # ruleid: aegish-subprocess-missing-sandbox-kwargs
    subprocess.run(
        ["/bin/bash", "-c", command],
        env=_build_safe_env(),
    )


def dangerous_raw_environ(command):
    # ruleid: aegish-subprocess-missing-safe-env
    subprocess.run(
        ["/bin/bash", "-c", command],
        env=os.environ,
        preexec_fn=lambda: None,
    )


def safe_env_but_no_sandbox(command):
    # ok: aegish-subprocess-missing-safe-env
    # ruleid: aegish-subprocess-missing-sandbox-kwargs
    subprocess.run(
        ["/bin/bash", "-c", command],
        env=_build_safe_env(),
    )


# --- TRUE NEGATIVES ---

def safe_with_sandbox_kwargs(command):
    # ok: aegish-subprocess-missing-sandbox-kwargs
    subprocess.run(
        ["/bin/bash", "-c", command],
        env=_build_safe_env(),
        **_sandbox_kwargs(),
    )


def safe_with_sandbox_kw(command):
    # ok: aegish-subprocess-missing-sandbox-kwargs
    subprocess.run(
        ["/bin/bash", "-c", command],
        env=_build_safe_env(),
        **sandbox_kw,
    )


def safe_with_preexec(command):
    # ok: aegish-subprocess-missing-sandbox-kwargs
    subprocess.run(
        ["/bin/bash", "-c", command],
        env=_build_safe_env(),
        preexec_fn=lambda: None,
    )
