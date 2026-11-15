# SPDX-License-Identifier: GPL-3.0-or-later
"""POSIX tool process-group cleanup; not a hostile-code sandbox."""

import os
import signal
import subprocess


def run_tool(arguments, *, cwd, env, stdin, stdout, stderr, timeout, check=False):
    """Run a trusted provisioned tool in its own session and clean up its group.

    A child that deliberately changes session/process group can escape this
    cleanup. Hostile-code containment needs an external sandbox/supervisor.
    stdout/stderr are caller-owned files, not inherited pipe lifetimes.
    """
    if os.name != "posix" or check is not False:
        raise ValueError("unsupported_tool_process_contract")
    with subprocess.Popen(arguments, cwd=cwd, env=env, stdin=stdin,
                          stdout=stdout, stderr=stderr, start_new_session=True) as process:
        def stop_group():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            stop_group()
            process.wait()
            raise
        # Also stop ordinary descendants left behind after the launcher exits.
        stop_group()
    return subprocess.CompletedProcess(arguments, code)
