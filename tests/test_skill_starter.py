# SPDX-License-Identifier: GPL-3.0-or-later
"""Starter metadata checks, not full standards conformance or host proof."""

import json
from pathlib import Path
import unittest

from agent_skills_exchange.dependencies import validate_manifest


ROOT = Path(__file__).resolve().parents[1]


class StandaloneStarterTests(unittest.TestCase):
    def test_starter_declares_instruction_only_scope_without_briar_dependencies(self):
        directory = ROOT / "examples/readme-clarity"
        manifest = validate_manifest(json.loads((directory / "dependencies.json").read_text()))
        self.assertEqual(manifest["features"], ["text-review"])
        for field in ["hosts", "software", "skills", "network", "credentials", "lockfiles"]:
            self.assertEqual(manifest[field], [])
        self.assertEqual(manifest["platforms"][0]["support"], {"status": "declared", "evidence": []})
        skill = (directory / "SKILL.md").read_text()
        self.assertTrue(skill.startswith("---\nname: readme-clarity\n"))
        self.assertEqual(directory.name, "readme-clarity")
        self.assertIn("license: GPL-3.0-or-later\n", skill)
        self.assertIn("  agent-skills-exchange-dependencies: dependencies.json\n", skill)
        self.assertIn("recursive-include examples *.md *.json", (ROOT / "MANIFEST.in").read_text())


if __name__ == "__main__":
    unittest.main()
