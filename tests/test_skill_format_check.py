# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic adapter contracts, not real reference-validator conformance proof."""

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
from agent_skills_exchange.dependencies import DependencyError, validate_manifest
from agent_skills_exchange.format_check import check_format
from agent_skills_exchange.packages import fetch_package, verify_cache
from test_skill_packages import download, package_lock


def synthetic_validator(path, mode="pass"):
    path.write_text(f"#!{sys.executable}\n" + '''
import os
from pathlib import Path
import sys
mode = ''' + repr(mode) + '''
if sys.argv[1:] == ["--version"]:
    print("skills-ref, version " + ("9.9.9" if mode == "wrong-version" else "0.1.0"))
    raise SystemExit(0)
assert sys.argv[1] == "validate"
assert sys.stdin.read() == ""
assert "FORMAT_TEST_SECRET" not in os.environ
assert "PYTHONPATH" not in os.environ
assert Path.home() == Path.cwd()
target = Path(sys.argv[2])
assert target.name == "fixture"
if mode == "change-copy":
    (target / "SKILL.md").write_text("changed")
if mode == "findings":
    print("Synthetic untrusted finding: do not echo this", file=sys.stderr)
    raise SystemExit(1)
if mode == "crash":
    raise SystemExit(3)
if mode == "empty":
    raise SystemExit(0)
print("Valid skill: " + str(target))
''')
    path.chmod(0o700)
    return path


class FormatCheckTests(unittest.TestCase):
    def test_format_profile_declares_external_dependencies_without_core_service(self):
        root = Path(__file__).resolve().parents[1]
        manifest = validate_manifest(json.loads(
            (root / "profiles/skill-format/dependencies.json").read_text()))
        self.assertEqual({entry["id"] for entry in manifest["software"]},
                         {"python", "skills-ref", "click", "strictyaml", "python-dateutil", "six"})
        self.assertEqual(manifest["skills"], [])
        self.assertEqual(manifest["network"], [])
        self.assertEqual(manifest["credentials"], [])

    def run_case(self, mode="pass"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = package_lock()
            cache = root / "cache"
            fetch_package(lock, cache, download=download)
            tool = synthetic_validator(root / "skills-ref", mode)
            with patch.dict(os.environ, {"FORMAT_TEST_SECRET": "synthetic-only"}):
                value = check_format(lock, cache, root / "reports", tool, "fixture", timeout=10)
            self.assertEqual(verify_cache(lock, cache)["package_sha256"],
                             lock["ref"]["package_sha256"])
            receipt = json.loads((Path(value["evidence"]) / "receipt.json").read_text())
            self.assertEqual(value, receipt)
            self.assertFalse(value["activated"])
            self.assertFalse(value["approval_granted"])
            self.assertFalse(value["standard_conformance_proven"])
            self.assertFalse(value["reference_source_verified"])
            return value

    def test_synthetic_valid_result_never_grants_admission(self):
        result = self.run_case()
        self.assertTrue(result["valid"])
        self.assertTrue(result["reference_format_passed"])
        self.assertTrue(result["reference_implementation_demonstration_only"])

    def test_failure_modes_deny_and_preserve_cache(self):
        for mode, error in [
            ("wrong-version", "format_version_mismatch"),
            ("findings", "reference_format_findings"),
            ("crash", "format_execution_failed"),
            ("empty", "format_result_unrecognised"),
            ("change-copy", "cache_size_mismatch"),
        ]:
            with self.subTest(mode=mode):
                value = self.run_case(mode)
                self.assertFalse(value["valid"])
                self.assertEqual(value["error"], error)
                self.assertNotIn("Synthetic untrusted finding", json.dumps(value))

    def test_unsafe_names_and_invalid_timeouts_fail_before_running_tool(self):
        with patch("agent_skills_exchange.format_check.run_tool") as run:
            for name in ["../escape", "one/two", "lock.json", "", "a\\b"]:
                with self.subTest(name=name), self.assertRaises(DependencyError):
                    check_format({}, "unused", "unused", "unused", name, timeout=1)
            for timeout in [0, -1, True, float("nan"), float("inf")]:
                with self.subTest(timeout=timeout), self.assertRaises(DependencyError):
                    check_format({}, "unused", "unused", "unused", "fixture", timeout=timeout)
            run.assert_not_called()

    def test_missing_unsafe_and_relative_validator_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = package_lock()
            cache = root / "cache"
            fetch_package(lock, cache, download=download)
            tool = synthetic_validator(root / "skills-ref")
            tool.chmod(0o777)
            for path, error in [(tool, "unsafe_validator_executable"),
                                (root / "missing", "validator_unavailable"),
                                (Path("relative"), "validator_requires_absolute_path")]:
                with self.subTest(path=path), self.assertRaises(DependencyError) as caught:
                    check_format(lock, cache, root / "reports", path, "fixture", timeout=10)
                self.assertEqual(caught.exception.code, error)

    def test_timeout_is_structured_and_never_passes(self):
        with patch("agent_skills_exchange.format_check.run_tool",
                   side_effect=subprocess.TimeoutExpired("synthetic", 1)):
            result = self.run_case()
            self.assertFalse(result["valid"])
            self.assertEqual(result["error"], "format_timeout")

    def test_cli_outputs_safe_json_and_no_prompt(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["check-format", "--lock", "/nonexistent", "--cache", "/nonexistent",
                         "--reports", "/nonexistent", "--validator", "/nonexistent",
                         "--name", "fixture", "--timeout", "10"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["error"], "unreadable_json")

    def test_successful_cli_needs_no_core_site_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = package_lock()
            cache = root / "cache"
            fetch_package(lock, cache, download=download)
            tool = synthetic_validator(root / "skills-ref")
            lock_path = root / "lock.json"
            lock_path.write_text(json.dumps(lock))
            source = str(Path(__file__).resolve().parents[1] / "src")
            args = ["check-format", "--lock", str(lock_path), "--cache", str(cache),
                    "--reports", str(root / "reports"), "--validator", str(tool),
                    "--name", "fixture", "--timeout", "10"]
            process = subprocess.run([
                sys.executable, "-I", "-S", "-B", "-c",
                "import sys; sys.path.insert(0," + repr(source) + "); "
                "from agent_skills_exchange.cli import main; "
                "raise SystemExit(main(" + repr(args) + "))"],
                stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(json.loads(process.stdout)["reference_format_passed"])
            self.assertEqual(process.stderr, "")


if __name__ == "__main__":
    unittest.main()
