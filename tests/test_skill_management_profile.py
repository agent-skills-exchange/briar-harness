# SPDX-License-Identifier: GPL-3.0-or-later
"""Observed scanner inventory is not a trusted installation or scan receipt."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_skills_exchange.dependencies import validate_manifest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "scanner_snapshot", ROOT / "profiles/skill-management/snapshot_environment.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def records():
    return [{"name": "SkillSpector", "version": "2.8.2",
             "requires_dist": ["example>=1; python_version >= '3.12'"],
             "requires_python": ">=3.12,<3.15", "metadata_sha256": "a" * 64,
             "origin": {"url": MODULE.SOURCE,
                        "vcs_info": {"commit_id": MODULE.REVISION}}},
            {"name": "example", "version": "1.2.3", "requires_dist": [],
             "requires_python": ">=3.12", "metadata_sha256": "b" * 64,
             "origin": {}}]


class ScannerProfileTests(unittest.TestCase):
    def test_checked_in_profile_binds_inventory_and_exposes_remaining_setup_work(self):
        profile = ROOT / "profiles/skill-management"
        manifest = validate_manifest(json.loads((profile / "dependencies.json").read_text()))
        inventory = profile / manifest["lockfiles"][0]["path"]
        self.assertEqual(hashlib.sha256(inventory.read_bytes()).hexdigest(),
                         manifest["lockfiles"][0]["sha256"])
        readiness = json.loads((profile / "readiness.json").read_text())
        self.assertFalse(readiness["installable_profile_ready"])
        self.assertEqual(len(json.loads(inventory.read_text())["components"]),
                         readiness["environment"]["inventory_components"])
        self.assertEqual(manifest["network"], [])
        self.assertEqual(manifest["credentials"], [])
        for software in manifest["software"]:
            self.assertEqual(software["installation"]["method"], "preinstalled")

    def test_inventory_preserves_exact_versions_and_requirements_without_claiming_installation(self):
        value = MODULE.snapshot(records(), {"os": "linux"})
        self.assertEqual(value["bomFormat"], "CycloneDX")
        props = {item["name"]: item["value"] for item in value["metadata"]["properties"]}
        self.assertEqual(props["ase:installation-reproducible"], "false")
        self.assertEqual(props["ase:approval-granted"], "false")
        components = {item["name"]: item for item in value["components"]}
        self.assertNotIn("purl", components["skillspector"])
        self.assertEqual(components["example"]["version"], "1.2.3")
        scanner = {item["name"]: item["value"] for item in components["skillspector"]["properties"]}
        self.assertEqual(json.loads(scanner["ase:requires-dist"]), records()[0]["requires_dist"])

    def test_wrong_scanner_identity_and_missing_scanner_fail(self):
        for field, value in [("version", "9.0"), ("origin", {})]:
            source = records()
            source[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                MODULE.snapshot(source, {})
        with self.assertRaises(ValueError):
            MODULE.snapshot(records()[1:], {})

    def test_private_sources_and_duplicate_names_fail_without_export(self):
        for mutate in [
            lambda rows: rows[1].update(origin={"url": "file:///private/source"}),
            lambda rows: rows[1].update(requires_dist=["other @ https://user:secret@example.org/pkg"]),
            lambda rows: rows.append(copy.deepcopy(rows[1])),
        ]:
            source = records()
            mutate(source)
            with self.assertRaises(ValueError):
                MODULE.snapshot(source, {})

    def test_refresh_never_overwrites_existing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "existing.json"
            target.write_text("reviewed evidence")
            with patch.object(MODULE.importlib.metadata, "distributions", return_value=[]), \
                    patch.object(MODULE, "snapshot", return_value={}), \
                    patch.object(MODULE.sys, "argv", ["snapshot", "--output", str(target)]), \
                    self.assertRaises(FileExistsError):
                MODULE.main()
            self.assertEqual(target.read_text(), "reviewed evidence")


if __name__ == "__main__":
    unittest.main()
