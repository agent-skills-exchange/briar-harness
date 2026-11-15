# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline planner tests; no target execution, network, credentials or prompts."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agent_skills_exchange.dependencies import (
    DependencyError, manifest_digest, plan_dependencies, read_json,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
TARGET = {"os": "linux", "distribution": "ubuntu", "version": "24.04", "architecture": "x86_64"}


def manifest(features=("guidance",)):
    return {
        "schema_version": 1, "features": list(features),
        "platforms": [{"id": "portable", "os": "any", "distribution": "any",
                       "version": {"scheme": "none", "constraint": ""},
                       "architectures": ["any"], "applies_to": list(features),
                       "support": {"status": "declared", "evidence": []}}],
        "hosts": [], "software": [], "skills": [], "network": [],
        "credentials": [], "lockfiles": [],
    }


def ref(name):
    return {"id": name, "source": "https://example.org/" + name,
            "revision": "a" * 40, "path": ".",
            "package_sha256": hashlib.sha256(name.encode()).hexdigest()}


def entry(name, features=("guidance",)):
    return {"ref": ref(name), "manifest": manifest(features)}


def dependency(name, *, required=True, applies=("guidance",), features=("guidance",)):
    return {**ref(name), "required": required, "applies_to": list(applies), "features": list(features)}


def software(version):
    return {"id": "example-runtime", "kind": "runtime", "required": True,
            "version": {"scheme": "exact", "constraint": version},
            "applies_to": ["guidance"], "platforms": ["portable"],
            "installation": {"method": "manual", "package": "example-runtime",
                             "source": "https://example.org/runtime",
                             "instructions": "references/setup.md"}}


def catalog(*entries):
    return {"schema_version": 1, "packages": list(entries)}


def plan(value, features=("guidance",), optional=(), target=None):
    return plan_dependencies(value, "root", list(features), target or TARGET, list(optional))


class ErrorAssertions:
    def assert_code(self, expected, action):
        with self.assertRaises(DependencyError) as caught:
            action()
        self.assertEqual(caught.exception.code, expected)


class SemanticManifestTests(ErrorAssertions, unittest.TestCase):
    def test_valid_manifest_and_canonical_digest(self):
        value = manifest()
        self.assertEqual(validate_manifest(value), value)
        self.assertEqual(manifest_digest(value), manifest_digest(dict(reversed(list(value.items())))))

    def test_bool_is_not_schema_version_one(self):
        value = manifest()
        value["schema_version"] = True
        self.assert_code("schema_const", lambda: validate_manifest(value))

    def test_unknown_feature_and_platform_references(self):
        value = manifest()
        value["software"] = [software("1")]
        value["software"][0]["applies_to"] = ["undeclared"]
        self.assert_code("unknown_feature_reference", lambda: validate_manifest(value))
        value["software"][0]["applies_to"] = ["guidance"]
        value["software"][0]["platforms"] = ["undeclared"]
        self.assert_code("unknown_platform_reference", lambda: validate_manifest(value))

    def test_duplicate_platform_and_overlapping_software(self):
        value = manifest()
        value["platforms"] *= 2
        self.assert_code("duplicate_platform_id", lambda: validate_manifest(value))
        value = manifest()
        value["software"] = [software("1"), software("2")]
        self.assert_code("overlapping_software_dependency", lambda: validate_manifest(value))

    def test_platform_specific_versions_can_differ(self):
        value = manifest()
        another = copy.deepcopy(value["platforms"][0])
        another["id"] = "other-platform"
        value["platforms"].append(another)
        value["software"] = [software("1"), software("2")]
        value["software"][1]["platforms"] = ["other-platform"]
        validate_manifest(value)

    def test_every_feature_needs_a_platform_declaration(self):
        value = manifest()
        value["features"].append("full-audit")
        self.assert_code("feature_without_platform", lambda: validate_manifest(value))

    def test_bad_url_has_value_free_error(self):
        value = manifest()
        value["network"] = [{"id": "fixture", "destination": "http://[invalid",
                             "purpose": "test", "required": True, "applies_to": ["guidance"]}]
        self.assert_code("invalid_network_destination", lambda: validate_manifest(value))

    def test_json_rejects_duplicates_and_nonfinite_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for text, code in [('{' + '"key":1,"key":2}', "duplicate_json_key"),
                               ('{"key":NaN}', "nonfinite_json_number")]:
                path.write_text(text)
                self.assert_code(code, lambda: read_json(path))


class PlannerTests(ErrorAssertions, unittest.TestCase):
    def test_standalone_skill_is_offline_and_not_permission(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            result = plan(catalog(entry("root")))
        self.assertEqual([p["ref"]["id"] for p in result["packages"]], ["root"])
        self.assertTrue(result["plan_only"])
        self.assertFalse(result["approval_granted"])
        self.assertFalse(result["artifact_integrity_verified"])

    def test_required_dependency_is_before_parent(self):
        parent, child = entry("root"), entry("child")
        parent["manifest"]["skills"] = [dependency("child")]
        result = plan(catalog(parent, child))
        self.assertEqual([p["ref"]["id"] for p in result["packages"]], ["child", "root"])

    def test_optional_dependency_is_not_selected_implicitly(self):
        parent, child = entry("root"), entry("child")
        parent["manifest"]["skills"] = [dependency("child", required=False)]
        self.assertEqual(len(plan(catalog(parent, child))["packages"]), 1)
        self.assertEqual(len(plan(catalog(parent, child), optional=["child"])["packages"]), 2)
        self.assert_code("unknown_optional_selection", lambda: plan(catalog(parent), optional=["typo"]))

    def test_feature_specific_dependency_does_not_affect_guidance(self):
        parent = entry("root", ("guidance", "full-audit"))
        parent["manifest"]["skills"] = [dependency("child", applies=("full-audit",))]
        self.assertEqual(len(plan(catalog(parent))["packages"]), 1)
        self.assert_code("missing_package", lambda: plan(catalog(parent), features=["full-audit"]))

    def test_dependency_pin_conflict(self):
        parent, child = entry("root"), entry("child")
        parent["manifest"]["skills"] = [dependency("child")]
        child["ref"]["revision"] = "b" * 40
        self.assert_code("dependency_pin_conflict", lambda: plan(catalog(parent, child)))

    def test_cycle_rejected_without_recursion(self):
        parent, child = entry("root"), entry("child")
        parent["manifest"]["skills"] = [dependency("child")]
        child["manifest"]["skills"] = [dependency("root")]
        self.assert_code("dependency_cycle", lambda: plan(catalog(parent, child)))

    def test_diamond_merges_requested_child_features(self):
        root, left, right = entry("root"), entry("left"), entry("right")
        child = entry("child", ("guidance", "full-audit"))
        root["manifest"]["skills"] = [dependency("left"), dependency("right")]
        left["manifest"]["skills"] = [dependency("child")]
        right["manifest"]["skills"] = [dependency("child", features=("full-audit",))]
        result = plan(catalog(root, left, right, child))
        node = next(p for p in result["packages"] if p["ref"]["id"] == "child")
        self.assertEqual(node["features"], ["full-audit", "guidance"])
        self.assertEqual(len(result["packages"]), 4)

    def test_same_child_can_have_disjoint_parent_feature_requirements(self):
        root = entry("root", ("guidance", "full-audit"))
        child = entry("child", ("guidance", "full-audit"))
        root["manifest"]["skills"] = [
            dependency("child"),
            dependency("child", applies=("full-audit",), features=("full-audit",)),
        ]
        result = plan(catalog(root, child))
        self.assertEqual(result["packages"][0]["features"], ["guidance"])
        result = plan(catalog(root, child), features=["full-audit"])
        self.assertEqual(result["packages"][0]["features"], ["full-audit"])
        root["manifest"]["skills"][1]["applies_to"] = ["guidance"]
        self.assert_code("overlapping_skill_dependency", lambda: plan(catalog(root, child)))

    def test_exact_software_version_conflict(self):
        root, child = entry("root"), entry("child")
        root["manifest"]["skills"] = [dependency("child")]
        root["manifest"]["software"] = [software("1")]
        child["manifest"]["software"] = [software("2")]
        self.assert_code("exact_software_version_conflict", lambda: plan(catalog(root, child)))

    def test_target_platform_and_unsupported_version_scheme(self):
        root = entry("root")
        platform = root["manifest"]["platforms"][0]
        platform.update(os="linux", distribution="ubuntu", architectures=["aarch64"])
        self.assert_code("unsupported_target_platform", lambda: plan(catalog(root)))
        platform["architectures"] = ["x86_64"]
        platform["version"] = {"scheme": "exact", "constraint": "24.04"}
        plan(catalog(root))
        platform["version"] = {"scheme": "system", "constraint": ">=24"}
        self.assert_code("platform_version_scheme_not_implemented", lambda: plan(catalog(root)))

    def test_unknown_feature_and_duplicate_catalog_id(self):
        self.assert_code("unsupported_requested_feature", lambda: plan(catalog(entry("root")), features=["absent"]))
        self.assert_code("duplicate_catalog_id", lambda: plan(catalog(entry("root"), entry("root"))))


class CliTests(unittest.TestCase):
    def command(self, *args):
        # No site packages, stdin or display: no hidden GUI/hardware fallback.
        environment = {key: value for key, value in os.environ.items()
                       if key not in {"DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"}}
        return subprocess.run(
            [sys.executable, "-I", "-S", "-c",
             "import sys; sys.path.insert(0," + repr(str(ROOT / "src")) + "); "
             "from agent_skills_exchange.cli import main; raise SystemExit(main())", *args],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            env=environment, timeout=10, check=False,
        )

    def test_validate_and_plan_are_noninteractive_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json"
            path.write_text(json.dumps(manifest()))
            result = self.command("validate", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["valid"])
            path.write_text(json.dumps(catalog(entry("root"))))
            result = self.command("plan", "--catalog", str(path), "--skill", "root",
                                  "--feature", "guidance", "--os", "linux",
                                  "--distribution", "ubuntu", "--os-version", "24.04",
                                  "--architecture", "x86_64")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["plan_only"])

    def test_bad_arguments_and_bad_metadata_do_not_echo_values(self):
        marker = "synthetic-private-value"
        result = self.command("not-a-command", marker)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(marker, result.stdout + result.stderr)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json"
            path.write_text('{"unexpected":"' + marker + '"}')
            result = self.command("validate", str(path))
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(marker, result.stdout + result.stderr)
            self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
