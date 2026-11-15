# SPDX-License-Identifier: GPL-3.0-or-later
"""Draft dependency structure tests, not package admission or host execution."""

import copy
from importlib.resources import files
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator
from agent_skills_exchange.dependencies import DependencyError, validate_manifest


SCHEMA = json.loads(
    files("agent_skills_exchange").joinpath("schemas/dependencies-v1.json")
    .read_text(encoding="utf-8")
)


def minimal():
    """Synthetic instruction-only skill; makes no runtime compatibility claim."""
    return {
        "schema_version": 1,
        "features": ["guidance"],
        "platforms": [{
            "id": "portable", "os": "any", "distribution": "any",
            "version": {"scheme": "none", "constraint": ""},
            "architectures": ["any"], "applies_to": ["guidance"],
            "support": {"status": "declared", "evidence": []},
        }],
        "hosts": [], "software": [], "skills": [], "network": [],
        "credentials": [], "lockfiles": [],
    }


class SkillDependencySchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Draft202012Validator.check_schema(SCHEMA)
        cls.validator = Draft202012Validator(SCHEMA)

    def assert_invalid(self, manifest):
        self.assertTrue(list(self.validator.iter_errors(manifest)))

    def test_instruction_only_skill_needs_no_briar_or_tools(self):
        self.validator.validate(minimal())

    def test_stdlib_runtime_matches_reference_validator_on_structural_cases(self):
        cases = [minimal()]
        for field in minimal():
            value = minimal()
            del value[field]
            cases.append(value)
        for field, content in [("schema_version", True), ("schema_version", 1.0),
                               ("features", []), ("platforms", []),
                               ("software", ["not-an-object"]), ("extra", True)]:
            value = minimal()
            value[field] = content
            cases.append(value)
        for index, value in enumerate(cases):
            with self.subTest(case=index):
                expected = self.validator.is_valid(value)
                try:
                    validate_manifest(value)
                    actual = True
                except DependencyError:
                    actual = False
                self.assertEqual(actual, expected)

    def test_every_dependency_category_must_be_explicit(self):
        for field in minimal():
            with self.subTest(field=field):
                candidate = minimal()
                del candidate[field]
                self.assert_invalid(candidate)

    def test_unknown_fields_and_empty_platforms_are_rejected(self):
        for field, value in [("install_automatically", True), ("platforms", [])]:
            candidate = minimal()
            candidate[field] = value
            self.assert_invalid(candidate)

    def test_tested_support_requires_evidence(self):
        candidate = minimal()
        candidate["platforms"][0]["support"]["status"] = "tested"
        self.assert_invalid(candidate)
        candidate["platforms"][0]["support"]["evidence"] = ["tests/platform-result.json"]
        self.validator.validate(candidate)

    def test_installation_is_structured_and_required(self):
        candidate = minimal()
        candidate["software"] = [{
            "id": "python", "kind": "runtime", "required": True,
            "version": {"scheme": "pep440", "constraint": ">=3.12"},
            "applies_to": ["guidance"], "platforms": ["portable"],
            "installation": {
                "method": "manual", "package": "python",
                "source": "https://www.python.org/downloads/",
                "instructions": "references/setup.md",
            },
        }]
        self.validator.validate(candidate)
        del candidate["software"][0]["installation"]
        self.assert_invalid(candidate)

    def test_skill_requires_immutable_revision_and_package_digest(self):
        candidate = minimal()
        candidate["skills"] = [{
            "id": "external-example", "source": "https://example.org/skill",
            "revision": "a" * 40, "path": "skills/example",
            "package_sha256": "b" * 64, "required": False,
            "applies_to": ["guidance"], "features": ["guidance"],
        }]
        self.validator.validate(candidate)
        for field, value in [("revision", "main"), ("package_sha256", "")]:
            changed = copy.deepcopy(candidate)
            changed["skills"][0][field] = value
            self.assert_invalid(changed)

    def test_paths_cannot_escape_package(self):
        for path in ["../outside", "a/../../outside", "/etc/passwd", "C:/private", "a\\b"]:
            with self.subTest(path=path):
                candidate = minimal()
                candidate["lockfiles"] = [{
                    "path": path, "sha256": "a" * 64, "format": "example",
                    "applies_to": ["guidance"],
                }]
                self.assert_invalid(candidate)

    def test_credentials_accept_requirements_not_secret_values(self):
        candidate = minimal()
        candidate["credentials"] = [{
            "id": "example-api", "purpose": "Read synthetic data",
            "permissions": ["read"], "provisioning": "references/credentials.md",
            "required": False, "applies_to": ["guidance"],
        }]
        self.validator.validate(candidate)
        candidate["credentials"][0]["value"] = "synthetic-not-a-real-secret"
        self.assert_invalid(candidate)

    def test_network_destination_cannot_embed_credentials_or_queries(self):
        for url in ["https://user:password@example.org", "https://example.org/?token=fake", "ftp://example.org"]:
            candidate = minimal()
            candidate["network"] = [{
                "id": "example-api", "destination": url, "purpose": "Read fixtures",
                "required": False, "applies_to": ["guidance"],
            }]
            self.assert_invalid(candidate)

    def test_local_game_testing_network_and_native_architecture_are_representable(self):
        candidate = minimal()
        candidate["platforms"][0]["architectures"] = ["x86_64", "aarch64"]
        for destination in ["http://127.0.0.1:3000", "ws://localhost:3000", "tcp://127.0.0.1:9000"]:
            candidate["network"] = [{
                "id": "local-fixture", "destination": destination,
                "purpose": "Local game test fixture", "required": True,
                "applies_to": ["guidance"],
            }]
            self.validator.validate(candidate)

    def test_versions_require_declared_scheme_and_constraint(self):
        for version in [{"scheme": "pep440", "constraint": ""}, {"scheme": "none", "constraint": ">=1"}, {"scheme": "custom", "constraint": "1"}]:
            candidate = minimal()
            candidate["platforms"][0]["version"] = version
            self.assert_invalid(candidate)


if __name__ == "__main__":
    unittest.main()
