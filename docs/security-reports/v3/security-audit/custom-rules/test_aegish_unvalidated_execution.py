# Test file for aegish-unvalidated-execution rule

import subprocess
import os


# --- TRUE POSITIVES (should be detected) ---

def dangerous_direct_execution(command):
    # ruleid: aegish-unvalidated-execution
    subprocess.run(command, shell=True)


def dangerous_popen(command):
    # ruleid: aegish-unvalidated-execution
    subprocess.Popen(command, shell=True)


def dangerous_os_system(command):
    # ruleid: aegish-unvalidated-execution
    os.system(command)


def dangerous_os_popen(command):
    # ruleid: aegish-unvalidated-execution
    os.popen(command)


def dangerous_check_output(command):
    # ruleid: aegish-unvalidated-execution
    subprocess.check_output(command, shell=True)


def dangerous_subprocess_call(command):
    # ruleid: aegish-unvalidated-execution
    subprocess.call(command, shell=True)


# --- TRUE NEGATIVES (should NOT be detected) ---

# ok: aegish-unvalidated-execution
def safe_call_through_executor():
    from aegish.executor import execute_command
    execute_command("ls -la")


# ok: aegish-unvalidated-execution
def safe_variable_usage():
    result = {"action": "allow"}
    print(result)
