# SPDX-License-Identifier: GPL-3.0-or-later
"""Pinned integration metadata checks; not external skill activation."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agent_skills_exchange.cli import main
from agent_skills_exchange.dependencies import read_json, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "integrations/cloudflare-security-audit"
LOCK = INTEGRATION / "package-lock.json"
MANIFEST = INTEGRATION / "dependencies.guidance.json"
TARGET = ["--os", "linux", "--distribution", "ubuntu", "--os-version", "24.04",
          "--architecture", "x86_64"]


class CloudflareProfileTests(unittest.TestCase):
    def command(self, *arguments):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["plan", *arguments, "--skill", "cloudflare-security-audit",
                           "--feature", "guidance", *TARGET])
        return status, json.loads(output.getvalue())

    def test_instruction_only_profile_is_structurally_valid_and_standalone(self):
        manifest = validate_manifest(read_json(MANIFEST))
        self.assertEqual(manifest["features"], ["guidance"])
        for key in ("hosts", "software", "skills", "network", "credentials", "lockfiles"):
            self.assertEqual(manifest[key], [])
        self.assertEqual(manifest["platforms"][0]["support"]["status"], "declared")

    def test_direct_plan_reads_only_lock_and_manifest_without_fetching_or_scanning(self):
        with patch("agent_skills_exchange.cli.read_json", wraps=read_json) as read, \
                patch("agent_skills_exchange.cli.fetch_package") as fetch, \
                patch("agent_skills_exchange.cli.inspect_package") as inspect:
            status, result = self.command("--lock", str(LOCK), "--manifest", str(MANIFEST))
        self.assertEqual(status, 0)
        self.assertEqual([call.args[0] for call in read.call_args_list], [LOCK, MANIFEST])
        fetch.assert_not_called()
        inspect.assert_not_called()
        self.assertTrue(result["plan_only"])
        self.assertFalse(result["artifact_integrity_verified"])
        self.assertFalse(result["approval_granted"])
        self.assertEqual(len(result["packages"]), 1)
        package = result["packages"][0]
        self.assertEqual(package["ref"], read_json(LOCK)["ref"])
        self.assertEqual(package["features"], ["guidance"])
        self.assertTrue(all(value == [] for value in package["requirements"].values()))

    def test_direct_and_catalog_forms_have_identical_plan_output(self):
        status, direct = self.command("--lock", str(LOCK), "--manifest", str(MANIFEST))
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "catalog.json"
            catalog.write_text(json.dumps({"schema_version": 1, "packages": [{
                "ref": read_json(LOCK)["ref"], "manifest": read_json(MANIFEST)}]}))
            other_status, other = self.command("--catalog", str(catalog))
        self.assertEqual((status, other_status), (0, 0))
        self.assertEqual(direct, other)

    def test_full_audit_is_not_advertised_as_ready(self):
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(["plan", "--lock", str(LOCK), "--manifest", str(MANIFEST),
                           "--skill", "cloudflare-security-audit", "--feature", "full-audit",
                           *TARGET])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(output.getvalue())["error"], "unsupported_requested_feature")

    def test_missing_or_ambiguous_input_is_rejected_without_echoing_paths(self):
        for arguments in (("--lock", str(LOCK)),
                          ("--catalog", "private-catalog", "--manifest", str(MANIFEST)),
                          ("--catalog", "private-catalog", "--lock", str(LOCK))):
            status, result = self.command(*arguments)
            self.assertEqual(status, 2)
            self.assertEqual(result["error"], "invalid_arguments")
            self.assertNotIn("private-catalog", json.dumps(result))

    def test_direct_plan_validates_package_lock_instead_of_trusting_ref_only(self):
        with tempfile.TemporaryDirectory() as directory:
            lockfile = Path(directory) / "lock.json"
            lock = read_json(LOCK)
            lock["files"][0]["size"] += 1
            lockfile.write_text(json.dumps(lock))
            status, result = self.command("--lock", str(lockfile), "--manifest", str(MANIFEST))
        self.assertEqual(status, 2)
        self.assertEqual(result["error"], "package_lock_digest_mismatch")

    def test_guidance_plan_is_headless_and_stdlib_only(self):
        environment = {key: value for key, value in os.environ.items()
                       if key not in {"DISPLAY", "WAYLAND_DISPLAY", "PYTHONPATH"}}
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-c",
             "import sys; sys.path.insert(0," + repr(str(ROOT / "src")) + "); "
             "from agent_skills_exchange.cli import main; raise SystemExit(main())",
             "plan", "--lock", str(LOCK), "--manifest", str(MANIFEST),
             "--skill", "cloudflare-security-audit", "--feature", "guidance", *TARGET],
            env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["plan_only"])


if __name__ == "__main__":
    unittest.main()
