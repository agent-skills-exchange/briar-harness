# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline requirements must not imply a configured network/identity service."""

import json
from pathlib import Path
import unittest

from agent_skills_exchange.dependencies import DependencyError, validate_manifest


PROFILE = Path(__file__).resolve().parents[1] / "profiles/authzen"


class AuthzenProfileTests(unittest.TestCase):
    def test_offline_manifest_has_no_network_or_service_requirement(self):
        value = validate_manifest(json.loads((PROFILE / "dependencies.offline.json").read_text()))
        self.assertEqual(value["features"], ["offline-request"])
        for field in ["hosts", "skills", "network", "credentials", "lockfiles"]:
            self.assertEqual(value[field], [])
        self.assertEqual(len(value["software"]), 1)
        python = value["software"][0]
        self.assertEqual(python["version"], {"scheme": "pep440", "constraint": ">=3.12"})
        self.assertEqual(python["installation"]["method"], "preinstalled")
        self.assertTrue((PROFILE / python["installation"]["instructions"]).is_file())
        self.assertEqual(value["platforms"][0]["support"], {"status": "declared", "evidence": []})

    def test_network_record_is_explicitly_unbound_and_not_an_executable_manifest(self):
        value = json.loads((PROFILE / "evaluation-requirements.json").read_text())
        for field in ["ready", "dependency_manifest_complete", "live_integration_tested",
                      "approval_granted", "activated"]:
            self.assertIs(value[field], False)
        self.assertIsNone(value["network"][0]["destination"])
        self.assertIsNone(value["services"][0]["endpoint"])
        self.assertIsNone(value["credentials"][0]["origin"])
        self.assertIs(value["credentials"][0]["value_in_profile"], False)
        self.assertIs(value["installation"]["automatic"], False)
        self.assertTrue(value["unresolved"])
        with self.assertRaises(DependencyError):
            validate_manifest(value)


if __name__ == "__main__":
    unittest.main()
