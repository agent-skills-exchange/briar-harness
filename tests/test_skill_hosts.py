# SPDX-License-Identifier: GPL-3.0-or-later
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_skills_exchange.cli import main
from agent_skills_exchange.dependencies import DependencyError
from agent_skills_exchange.hosts import onboarding_plan


class HostPlanTests(unittest.TestCase):
    def test_native_paths_and_no_activation_for_each_host(self):
        root = str(Path(tempfile.gettempdir()) / "not-created-briar-example")
        for host, directory in [("codex", ".agents"), ("claude", ".claude"), ("cursor", ".cursor")]:
            with self.subTest(host=host):
                result = onboarding_plan(host, root, "example-skill")
                self.assertEqual(result["instruction_file"], str(Path(root) / directory / "skills/example-skill/SKILL.md"))
                for key in ["writes_performed", "activated", "approval_granted",
                            "host_runtime_tested", "destination_checked", "admission_implemented",
                            "removal_unloads_existing_context"]:
                    self.assertIs(result[key], False)

    def test_invalid_host_names_and_traversal_fail(self):
        root = str(Path(tempfile.gettempdir()))
        for host, name in [("unknown", "safe"), ("codex", "../escape"),
                           ("cursor", "two--hyphens"), ("claude", "CON"),
                           ("codex", "con"), ("codex", "a" * 65),
                           ("codex", "slash/name"), ("codex", "")]:
            with self.subTest(host=host, name=name), self.assertRaises(DependencyError):
                onboarding_plan(host, root, name)

    def test_invalid_project_paths_fail(self):
        for project in ["relative", "/tmp/../escape", "/tmp/new\nline", None]:
            with self.subTest(project=project), self.assertRaises(DependencyError):
                onboarding_plan("codex", project, "safe")

    def test_cli_is_offline_and_does_not_touch_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "not-created"
            output = io.StringIO()
            with patch("socket.socket", side_effect=AssertionError("network forbidden")), contextlib.redirect_stdout(output):
                code = main(["onboarding-plan", "--host", "codex", "--project", str(root), "--name", "safe"])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(output.getvalue())["valid"])
            self.assertFalse(root.exists())

    def test_cli_errors_do_not_echo_untrusted_values(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["onboarding-plan", "--host", "secret-invalid-host", "--project", "/tmp", "--name", "safe"])
        self.assertEqual(code, 2)
        self.assertNotIn("secret-invalid-host", output.getvalue())


if __name__ == "__main__":
    unittest.main()
