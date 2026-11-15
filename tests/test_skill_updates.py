# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from agent_skills_exchange.dependencies import DependencyError
from agent_skills_exchange.cli import main
from agent_skills_exchange.packages import fetch_package
from agent_skills_exchange.updates import check_deployment, plan_update
from test_skill_packages import BODY, LICENSE, download, fix_digest, package_lock


class UpdatePlanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / "cache"
        self.current = package_lock()
        cached = fetch_package(self.current, self.cache, download=download)
        self.live = self.root / "selected-skill"
        shutil.copytree(cached["content"], self.live)
        self.target = copy.deepcopy(self.current)
        self.target["ref"]["revision"] = "b" * 40
        self.target["files"][0].update(size=len(BODY + b"Updated\n"),
            sha256=hashlib.sha256(BODY + b"Updated\n").hexdigest())
        self.target["files"].pop()
        self.target["files"].append({"path": "references/new.md", "source_path": "skills/fixture/references/new.md",
            "size": 4, "sha256": hashlib.sha256(b"new\n").hexdigest()})
        fix_digest(self.target)
        def target_download(url, size):
            return b"new\n" if url.endswith("/new.md") else BODY + b"Updated\n"
        fetch_package(self.target, self.cache, download=target_download)

    def plan(self):
        return plan_update(self.current, self.target, self.cache, self.live)

    def test_versioned_changes_and_retained_rollback_bytes_without_writes(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            result = self.plan()
        self.assertEqual(result["changes"], [
            {"path": "SKILL.md", "action": "replace"},
            {"path": "UPSTREAM-LICENSE", "action": "remove"},
            {"path": "references/new.md", "action": "add"}])
        self.assertFalse(result["blocked_by_drift"])
        self.assertTrue(result["rollback_cache_verified"])
        self.assertEqual(result["rollback_package_sha256"], self.current["ref"]["package_sha256"])
        for key in ["rollback_execution_tested", "apply_implemented", "writes_performed",
                    "approval_granted", "activated"]:
            self.assertIs(result[key], False)
        self.assertEqual((self.live / "SKILL.md").read_bytes(), BODY)
        self.assertEqual((self.live / "UPSTREAM-LICENSE").read_bytes(), LICENSE)

    def test_modified_and_missing_files_block_without_repair(self):
        (self.live / "SKILL.md").write_bytes(b"local edit")
        (self.live / "UPSTREAM-LICENSE").unlink()
        result = self.plan()
        self.assertTrue(result["blocked_by_drift"])
        self.assertEqual(result["deployment"]["differences"], [
            {"path": "SKILL.md", "state": "modified"},
            {"path": "UPSTREAM-LICENSE", "state": "missing"}])
        self.assertEqual((self.live / "SKILL.md").read_bytes(), b"local edit")

    def test_local_config_is_preserved_not_read_or_reported_by_name(self):
        extra = self.live / "local-only"
        extra.mkdir()
        (extra / "secret.txt").write_text("do-not-read")
        result = self.plan()
        self.assertTrue(result["blocked_by_drift"])
        self.assertEqual(result["deployment"]["unexpected_entries"], 1)
        self.assertNotIn("secret", str(result))
        self.assertEqual((extra / "secret.txt").read_text(), "do-not-read")

    def test_symlinked_directory_or_expected_file_is_rejected(self):
        link = self.root / "linked-skill"
        link.symlink_to(self.live, target_is_directory=True)
        with self.assertRaises(DependencyError):
            check_deployment(self.current, link)
        (self.live / "SKILL.md").unlink()
        (self.live / "SKILL.md").symlink_to(self.live / "UPSTREAM-LICENSE")
        with self.assertRaises(DependencyError):
            self.plan()

    def test_changed_candidate_cache_and_identity_mismatch_fail(self):
        other = copy.deepcopy(self.target)
        other["ref"]["source"] = "https://github.com/example/different"
        with self.assertRaises(DependencyError):
            plan_update(self.current, other, self.cache, self.live)
        target = self.cache / self.target["ref"]["package_sha256"] / "content/SKILL.md"
        target.write_bytes(b"tampered")
        with self.assertRaises(DependencyError):
            self.plan()

    def test_relative_and_missing_deployments_fail(self):
        for directory in [Path("relative"), self.root / "missing"]:
            with self.subTest(directory=directory), self.assertRaises(DependencyError):
                check_deployment(self.current, directory)

    def test_identical_version_plan_has_no_changes(self):
        result = plan_update(self.current, self.current, self.cache, self.live)
        self.assertEqual(result["changes"], [])
        self.assertFalse(result["blocked_by_drift"])

    def test_cli_returns_nonzero_for_drift_without_changing_files(self):
        current, target = self.root / "current.json", self.root / "target.json"
        current.write_text(json.dumps(self.current))
        target.write_text(json.dumps(self.target))
        arguments = ["plan-update", "--current-lock", str(current), "--target-lock", str(target),
                     "--cache", str(self.cache), "--directory", str(self.live)]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(arguments), 0)
        self.assertTrue(json.loads(output.getvalue())["valid"])
        (self.live / "SKILL.md").write_bytes(b"local edit")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(arguments), 2)
        self.assertEqual(json.loads(output.getvalue())["error"], "deployment_drift_detected")
        self.assertEqual((self.live / "SKILL.md").read_bytes(), b"local edit")


if __name__ == "__main__":
    unittest.main()
