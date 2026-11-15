# SPDX-License-Identifier: GPL-3.0-or-later
"""Focused workflow assertions, not a GitHub Actions execution or YAML parser."""

from pathlib import Path
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/core-tests.yml"


class CoreCiContractTests(unittest.TestCase):
    def test_ci_has_no_writer_token_secrets_or_privileged_pr_trigger(self):
        text = WORKFLOW.read_text()
        self.assertIn("permissions:\n  contents: read\n", text)
        self.assertIn("persist-credentials: false", text)
        self.assertNotIn("pull_request_target", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("write", text)

    def test_actions_are_commit_pinned_and_test_dependencies_locked_without_builds(self):
        text = WORKFLOW.read_text()
        actions = re.findall(r"uses: ([^\s]+)", text)
        self.assertEqual(len(actions), 3)
        for action in actions:
            self.assertRegex(action, r"^[A-Za-z0-9_-]+/[A-Za-z0-9_-]+@[a-f0-9]{40}$")
        self.assertIn("version: '0.9.10'", text)
        self.assertIn("enable-cache: false", text)
        self.assertIn("--frozen --extra skill-validation", text)
        self.assertIn("--no-default-groups --no-install-project --no-build", text)
        self.assertIn("UV_PYTHON_DOWNLOADS: never", text)
        self.assertIn(".venv/bin/python -B -m unittest discover -s tests -q", text)

    def test_workflow_is_shipped_and_lock_matches_declared_validation_extra(self):
        text = WORKFLOW.read_text()
        self.assertIn("runs-on: ubuntu-24.04", text)
        self.assertIn("python: ['3.12', '3.14']", text)
        self.assertIn("recursive-include .github/workflows *.yml", (ROOT / "MANIFEST.in").read_text())
        lock = tomllib.loads((ROOT / "uv.lock").read_text())
        packages = {item["name"]: item for item in lock["package"]}
        self.assertEqual(packages["jsonschema"]["version"], "4.19.2")
        for name, package in packages.items():
            if name == "briar-harness":
                continue
            self.assertEqual(package["source"], {"registry": "https://pypi.org/simple"})
            self.assertTrue(package.get("wheels"), name)
            for wheel in package["wheels"]:
                self.assertRegex(wheel["hash"], r"^sha256:[a-f0-9]{64}$")


if __name__ == "__main__":
    unittest.main()
