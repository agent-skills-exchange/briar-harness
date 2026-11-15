# SPDX-License-Identifier: GPL-3.0-or-later
"""Accepted-source selection is not activation or host compatibility proof."""

from pathlib import Path
import unittest

from agent_skills_exchange.dependencies import read_json
from agent_skills_exchange.packages import validate_lock


class GameIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.lock = read_json(root / "integrations/game-playtesting/package-lock.json")

    def test_lock_selects_the_accepted_merged_skill(self):
        lock = validate_lock(self.lock)
        self.assertEqual(lock["ref"]["source"],
                         "https://github.com/DynamicDevices/game-playtesting-skill")
        # This integration intentionally pins the accepted three-PR merge.
        self.assertEqual(lock["ref"]["revision"],
                         "79347af51d4e6d28ae3cfdcd49adfab64649ddd9")
        self.assertEqual(lock["ref"]["path"], "skills/app-playtesting")

    def test_root_licence_retained_without_review_infrastructure(self):
        files = {entry["path"]: entry for entry in self.lock["files"]}
        self.assertEqual(files["UPSTREAM-LICENSE"]["source_path"], "LICENSE")
        self.assertEqual(files["SKILL.md"]["source_path"], "skills/app-playtesting/SKILL.md")
        for entry in self.lock["files"]:
            if entry["path"] == "UPSTREAM-LICENSE":
                continue
            self.assertEqual(entry["source_path"], "skills/app-playtesting/" + entry["path"])
            self.assertFalse(entry["source_path"].startswith(".github/"))

    def test_upstream_baseline_stays_bundled_data_not_an_admission_claim(self):
        self.assertIn(".skillspector-baseline.yaml", {entry["path"] for entry in self.lock["files"]})
        self.assertEqual(set(self.lock), {"schema_version", "ref", "files"})


if __name__ == "__main__":
    unittest.main()
