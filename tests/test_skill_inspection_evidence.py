# SPDX-License-Identifier: GPL-3.0-or-later
"""Consistency of supplied evidence is not proof of its trusted origin."""

import copy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from agent_skills_exchange.dependencies import DependencyError
from agent_skills_exchange.cli import main
from agent_skills_exchange.inspection import (
    POLICY, _canonical, assess_report, verify_inspection_evidence,
)
from agent_skills_exchange.packages import fetch_package
from test_skill_inspection import report_fixture
from test_skill_packages import download, package_lock


class InspectionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cache = Path(self.temporary.name) / "cache"
        self.lock = package_lock()
        fetch_package(self.lock, self.cache, download=download)
        self.report = report_fixture(self.lock)
        self.scanner_digest = "b" * 64
        self.receipt = {
            "valid": True, "activated": False, "approval_granted": False,
            "receipt_is_authority": False, "artifact_integrity_verified": True,
            "package_sha256": self.lock["ref"]["package_sha256"],
            "policy": copy.deepcopy(POLICY),
            "policy_sha256": hashlib.sha256(_canonical(POLICY)).hexdigest(),
            "scanner_executable_sha256": self.scanner_digest,
            "report_sha256": hashlib.sha256(_canonical(self.report)).hexdigest(),
            **assess_report(self.report, self.lock),
        }

    def check(self, *, receipt_bytes=None, report_bytes=None, expected=None):
        receipt_bytes = _canonical(self.receipt) if receipt_bytes is None else receipt_bytes
        report_bytes = _canonical(self.report) if report_bytes is None else report_bytes
        return verify_inspection_evidence(
            self.lock, self.cache, receipt_bytes, report_bytes,
            expected_receipt_sha256=expected or hashlib.sha256(receipt_bytes).hexdigest(),
            expected_scanner_sha256=self.scanner_digest)

    def test_consistent_synthetic_evidence_never_proves_origin_runtime_or_authority(self):
        result = self.check()
        self.assertTrue(result["evidence_consistent"])
        for key in ["expected_identity_origin_verified", "scanner_runtime_verified",
                    "receipt_is_authority", "approval_granted", "activated"]:
            self.assertIs(result[key], False)

    def test_tampered_receipt_or_report_fails(self):
        original = hashlib.sha256(_canonical(self.receipt)).hexdigest()
        self.receipt["score"] = 1
        with self.assertRaises(DependencyError):
            self.check(expected=original)
        with self.assertRaises(DependencyError):
            self.check(report_bytes=_canonical(self.report) + b" ")

    def test_package_scanner_and_policy_mismatch_fail(self):
        for field, value in [("package_sha256", "c" * 64),
                             ("scanner_executable_sha256", "c" * 64),
                             ("policy_sha256", "c" * 64),
                             ("policy", {**POLICY, "maximum_score": 100})]:
            with self.subTest(field=field):
                original = self.receipt[field]
                self.receipt[field] = value
                with self.assertRaises(DependencyError):
                    self.check()
                self.receipt[field] = original

    def test_forged_passing_assessment_and_authority_flags_fail(self):
        for field, value in [("score", 1), ("valid", 1), ("activated", True),
                             ("receipt_is_authority", True), ("approval_granted", True),
                             ("static_coverage_verified", 1),
                             ("artifact_integrity_verified", 1)]:
            with self.subTest(field=field):
                original = self.receipt[field]
                self.receipt[field] = value
                with self.assertRaises(DependencyError):
                    self.check()
                self.receipt[field] = original

    def test_changed_cached_bytes_fail(self):
        content = self.cache / self.lock["ref"]["package_sha256"] / "content/SKILL.md"
        content.write_bytes(b"changed")
        with self.assertRaises(DependencyError):
            self.check()

    def test_blocking_report_cannot_be_reused(self):
        self.report["risk_assessment"] = {"score": 76, "severity": "HIGH"}
        self.receipt.update(assess_report(self.report, self.lock))
        self.receipt.update(valid=False, error="inspection_findings_blocked",
                            report_sha256=hashlib.sha256(_canonical(self.report)).hexdigest())
        with self.assertRaises(DependencyError):
            self.check()

    def test_bad_json_and_missing_fields_fail(self):
        for raw in [b"[]", b"{}", b'{"valid":true,"valid":false}', b"\xff"]:
            with self.subTest(raw=raw), self.assertRaises(DependencyError):
                self.check(receipt_bytes=raw)


    def run_cli(self, *, receipt_bytes=None, report_bytes=None, overrides=None):
        root = Path(self.temporary.name)
        (root / "lock.json").write_text(json.dumps(self.lock), encoding="utf-8")
        receipt_bytes = _canonical(self.receipt) if receipt_bytes is None else receipt_bytes
        report_bytes = _canonical(self.report) if report_bytes is None else report_bytes
        (root / "receipt.json").write_bytes(receipt_bytes)
        (root / "report.json").write_bytes(report_bytes)
        options = {
            "lock": str(root / "lock.json"), "cache": str(self.cache),
            "receipt": str(root / "receipt.json"), "report": str(root / "report.json"),
            "expected-receipt-sha256": hashlib.sha256(receipt_bytes).hexdigest(),
            "expected-scanner-sha256": self.scanner_digest,
        }
        options.update(overrides or {})
        argv = ["verify-inspection"]
        for key, value in options.items():
            argv.extend(["--" + key, value])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(argv)
        return status, json.loads(output.getvalue())

    def test_cli_consistent_evidence_is_not_admission(self):
        status, result = self.run_cli()
        self.assertEqual(status, 0)
        self.assertIs(result["evidence_consistent"], True)
        for field in ["expected_identity_origin_verified", "scanner_runtime_verified",
                      "receipt_is_authority", "approval_granted", "activated"]:
            self.assertIs(result[field], False)

    def test_cli_rejects_mismatched_expected_hashes_and_malformed_binding(self):
        for field, value, error in [
            ("expected-receipt-sha256", "c" * 64, "inspection_receipt_digest_mismatch"),
            ("expected-scanner-sha256", "c" * 64, "inspection_binding_mismatch"),
            ("expected-scanner-sha256", "private-invalid-value", "invalid_inspection_binding"),
        ]:
            with self.subTest(field=field, value=value):
                status, result = self.run_cli(overrides={field: value})
                self.assertEqual(status, 2)
                self.assertEqual(result["error"], error)
                self.assertNotIn("private-invalid-value", json.dumps(result))

    def test_cli_unreadable_evidence_returns_json_without_path(self):
        for field in ["receipt", "report"]:
            with self.subTest(field=field):
                status, result = self.run_cli(
                    overrides={field: str(Path(self.temporary.name) / "private-missing-file")})
                self.assertEqual(status, 2)
                self.assertEqual(result["error"], "inspection_evidence_unreadable")
                self.assertNotIn("private-missing-file", json.dumps(result))

    def test_cli_rejects_changed_report_and_malformed_json(self):
        for raw, error in [(b"{}", "inspection_binding_mismatch"),
                           (b"\xff", "invalid_inspection_report")]:
            with self.subTest(raw=raw):
                status, result = self.run_cli(report_bytes=raw)
                self.assertEqual(status, 2)
                self.assertEqual(result["error"], error)

    def test_cli_rejects_changed_cache(self):
        content = self.cache / self.lock["ref"]["package_sha256"] / "content/SKILL.md"
        content.write_bytes(b"changed")
        status, result = self.run_cli()
        self.assertEqual(status, 2)
        self.assertIs(result["valid"], False)

    def test_cli_blocking_report_stays_blocked(self):
        self.report["risk_assessment"] = {"score": 76, "severity": "HIGH"}
        self.receipt.update(assess_report(self.report, self.lock))
        self.receipt.update(valid=False, error="inspection_findings_blocked",
                            report_sha256=hashlib.sha256(_canonical(self.report)).hexdigest())
        status, result = self.run_cli()
        self.assertEqual(status, 2)
        self.assertEqual(result["error"], "inspection_findings_blocked")


if __name__ == "__main__":
    unittest.main()
