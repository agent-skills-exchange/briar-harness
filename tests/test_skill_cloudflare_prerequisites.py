# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep unavailable full-audit requirements distinct from executable profiles."""

import json
from pathlib import Path
import unittest

from agent_skills_exchange.dependencies import DependencyError, validate_manifest


class CloudflarePrerequisiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        integration = root / "integrations/cloudflare-security-audit"
        cls.requirements = json.loads((integration / "full-audit-prerequisites.json").read_text())
        cls.lock = json.loads((integration / "package-lock.json").read_text())
        cls.guidance = json.loads((integration / "dependencies.guidance.json").read_text())

    def test_requirements_bind_the_pinned_package_not_a_floating_branch(self):
        upstream, ref = self.requirements["upstream"], self.lock["ref"]
        self.assertEqual(upstream["repository"], ref["source"])
        self.assertEqual(upstream["revision"], ref["revision"])
        self.assertEqual(upstream["package_sha256"], ref["package_sha256"])
        self.assertEqual(upstream["licence"], "MIT")

    def test_unresolved_requirements_are_not_an_installable_or_available_profile(self):
        self.assertIs(self.requirements["available"], False)
        self.assertIs(self.requirements["installable_dependency_manifest"], False)
        self.assertIs(self.requirements["activation_granted"], False)
        with self.assertRaises(DependencyError):
            validate_manifest(self.requirements)
        self.assertEqual(validate_manifest(self.guidance)["features"], ["guidance"])

    def test_execution_and_promotion_need_actual_enforcement_not_just_metadata(self):
        execution = self.requirements["target_execution"]
        self.assertIs(execution["enabled"], False)
        self.assertIs(execution["external_network_allowed"], False)
        self.assertEqual(execution["environment"]["initial"], "empty")
        self.assertIsNone(execution["resource_limits"]["selected_values"])
        self.assertIs(execution["resource_limits"]["enforcement_verified"], False)
        promotion = self.requirements["artifact_promotion"]
        self.assertIs(promotion["implementation_verified"], False)
        self.assertIs(promotion["all_sandbox_processes_terminated_first"], True)
        self.assertIs(promotion["descriptor_relative_no_follow_traversal_required"], True)
        self.assertIsNone(promotion["selected_byte_limits"])
        self.assertIs(self.requirements["software"]["target_toolchain"]["resolved_inventory"], None)
        self.assertEqual(self.requirements["platforms"]["supported_execution_profiles"], [])


if __name__ == "__main__":
    unittest.main()
