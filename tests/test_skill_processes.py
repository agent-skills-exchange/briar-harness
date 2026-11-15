# SPDX-License-Identifier: GPL-3.0-or-later
"""Disposable local processes only; never execute target skill code."""

import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from agent_skills_exchange.processes import run_tool


@unittest.skipUnless(os.name == "posix", "POSIX tool adapter")
class ToolProcessTests(unittest.TestCase):
    def test_new_session_and_group_cleanup_on_normal_exit(self):
        process = MagicMock()
        process.pid = 12345
        process.wait.return_value = 0
        process.__enter__.return_value = process
        with patch("agent_skills_exchange.processes.subprocess.Popen", return_value=process) as launch, \
                patch("agent_skills_exchange.processes.os.killpg") as kill:
            result = run_tool(["synthetic"], cwd="/tmp", env={}, stdin=subprocess.DEVNULL,
                              stdout=None, stderr=None, timeout=1)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(launch.call_args.kwargs["start_new_session"])
        self.assertNotIn("shell", launch.call_args.kwargs)
        kill.assert_called_once_with(12345, signal.SIGKILL)

    def test_timeout_preserved_after_group_cleanup(self):
        process = MagicMock()
        process.pid = 12345
        process.__enter__.return_value = process
        process.wait.side_effect = [subprocess.TimeoutExpired("synthetic", 1), -9]
        with patch("agent_skills_exchange.processes.subprocess.Popen", return_value=process), \
                patch("agent_skills_exchange.processes.os.killpg") as kill, \
                self.assertRaises(subprocess.TimeoutExpired):
            run_tool(["synthetic"], cwd="/tmp", env={}, stdin=subprocess.DEVNULL,
                     stdout=None, stderr=None, timeout=1)
        kill.assert_called_once_with(12345, signal.SIGKILL)
        self.assertEqual(process.wait.call_count, 2)

    @unittest.skipUnless(hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"),
                         "Linux pidfd termination observation")
    def test_real_descendant_stops_on_timeout_and_after_launcher_exit(self):
        for parent_waits in [True, False]:
            with self.subTest(parent_waits=parent_waits), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "stdout"
                code = (
                    "import subprocess,sys,time; "
                    "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                    "print(child.pid,flush=True); " + ("time.sleep(30)" if parent_waits else "pass")
                )
                with output.open("wb") as out, (Path(directory) / "stderr").open("wb") as err:
                    try:
                        result = run_tool([sys.executable, "-I", "-S", "-c", code], cwd=directory,
                                          env={"PATH": os.defpath}, stdin=subprocess.DEVNULL,
                                          stdout=out, stderr=err, timeout=1)
                    except subprocess.TimeoutExpired:
                        self.assertTrue(parent_waits)
                    else:
                        self.assertFalse(parent_waits)
                        self.assertEqual(result.returncode, 0)
                pid = int(output.read_text().strip())
                try:
                    descriptor = os.pidfd_open(pid)
                except ProcessLookupError:
                    continue
                try:
                    observer = select.poll()
                    observer.register(descriptor, select.POLLIN)
                    # Kernel event wait, not a loop or sleep-based observation.
                    self.assertTrue(observer.poll(1000), "descendant survived cleanup")
                finally:
                    try:
                        signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    os.close(descriptor)


if __name__ == "__main__":
    unittest.main()
