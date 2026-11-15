# SPDX-License-Identifier: GPL-3.0-or-later
"""The clean core must not ship or depend on the legacy service."""

from pathlib import Path
import subprocess
import sys
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CleanPackagingTests(unittest.TestCase):
    def test_lightweight_distribution_and_entry_points(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        self.assertEqual(project["name"], "briar-harness")
        self.assertEqual(project["dependencies"], [])
        self.assertEqual(project["license"], "GPL-3.0-or-later")
        self.assertEqual(project["optional-dependencies"], {
            "skill-validation": ["jsonschema==4.19.2"]})
        self.assertEqual(project["scripts"], {
            "briar-harness": "agent_skills_exchange.cli:main",
            "ase": "agent_skills_exchange.cli:main"})
        self.assertFalse((ROOT / "src/briar_harness").exists())
        self.assertFalse((ROOT / "config").exists())
        self.assertFalse((ROOT / "docs/DEPLOYMENT-STATE.md").exists())

    def test_core_imports_without_site_packages_or_legacy_service(self):
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-c",
             "import sys; sys.path.insert(0," + repr(str(ROOT / "src")) + "); "
             "import agent_skills_exchange.cli; "
             "assert 'telegram' not in sys.modules; "
             "assert 'jsonschema' not in sys.modules; "
             "assert 'briar_harness' not in sys.modules"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_distribution_declares_test_profiles_and_docs_without_private_config(self):
        manifest = (ROOT / "MANIFEST.in").read_text()
        for directory in ["profiles", "docs", "integrations", "tests"]:
            self.assertIn("recursive-include " + directory + " ", manifest)
        self.assertIn("global-exclude *.py[cod]", manifest)
        self.assertNotIn("graft", manifest)
        self.assertNotIn("config", manifest)


if __name__ == "__main__":
    unittest.main()
