# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic inspection contracts; no skill code is executed."""

import copy
from contextlib import redirect_stdout
import io
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agent_skills_exchange.cli import main
from agent_skills_exchange.dependencies import DependencyError
from agent_skills_exchange.inspection import (
    SCANNER_VERSION, _APPLICABLE, _OTHER, _SEMANTIC, _STATIC,
    assess_report, inspect_package,
)
from agent_skills_exchange.packages import fetch_package
from test_skill_packages import download, fix_digest, package_lock


def report_fixture(lock):
    count = len(lock["files"])
    statuses = []
    for name in sorted(_STATIC | _APPLICABLE | _OTHER | _SEMANTIC):
        planned = count if name in _STATIC else (1 if name in _OTHER else 0)
        status = "disabled" if name in _SEMANTIC else (
            "not_applicable" if name in _APPLICABLE else "completed")
        statuses.append({"analyzer_id": name, "status": status,
                         "planned_work": planned, "completed": planned,
                         "skipped": 0, "failed": 0, "unaccounted": 0})
    return {"execution_successful": True,
            "metadata": {"skillspector_version": SCANNER_VERSION, "llm_requested": False,
                         "meta_analysis_applied": False, "inference_usage": []},
            "suppressed_count": 0, "suppressed": [], "issues": [],
            "components": [{"path": item["path"], "size_bytes": item["size"]}
                           for item in lock["files"]],
            "risk_assessment": {"score": 0, "severity": "LOW"},
            "analysis_completeness": {
                "execution_successful": True, "is_complete": False,
                "total_components": count, "scanned_components": count,
                "fully_inspected_files": count, "coverage_percent": 100.0,
                "partially_inspected_files": 0, "entirely_uninspected_files": 0,
                "ledger_exceptions": [], "scope_exclusions": [],
                "findings_before_filtering": 0, "findings_after_filtering": 0,
                "analyzer_statuses": statuses}}


class InspectionTests(unittest.TestCase):
    def assert_code(self, code, call):
        with self.assertRaises(DependencyError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_static_completion_does_not_require_disabled_llm_work(self):
        lock = package_lock()
        result = assess_report(report_fixture(lock), lock)
        self.assertTrue(result["inspection_passed"])
        self.assertTrue(result["static_coverage_verified"])

    def test_no_findings_meta_analyzer_can_be_not_applicable(self):
        lock = package_lock()
        report = report_fixture(lock)
        item = next(item for item in report["analysis_completeness"]["analyzer_statuses"]
                    if item["analyzer_id"] == "meta_analyzer")
        item.update(status="not_applicable", reason_code="no_applicable_files")
        self.assertTrue(assess_report(report, lock)["inspection_passed"])
        report["issues"] = [{"severity": "LOW", "location": {"file": "SKILL.md"}}]
        self.assert_code("inspection_not_static", lambda: assess_report(report, lock))
        report = report_fixture(lock)
        item = next(item for item in report["analysis_completeness"]["analyzer_statuses"]
                    if item["analyzer_id"] == "semantic_security_discovery")
        item.update(status="not_applicable", reason_code="no_applicable_files")
        self.assert_code("inspection_not_static", lambda: assess_report(report, lock))

    def test_missing_or_duplicate_analyzers_are_rejected(self):
        lock = package_lock()
        for duplicate in (False, True):
            report = report_fixture(lock)
            items = report["analysis_completeness"]["analyzer_statuses"]
            items.pop()
            if duplicate:
                items.append(copy.deepcopy(items[0]))
            self.assert_code("inspection_analyzer_set_mismatch",
                             lambda: assess_report(report, lock))

    def test_skipped_or_disabled_static_analysis_fails(self):
        lock = package_lock()
        for field, value in (("status", "disabled"), ("skipped", 1),
                             ("failed", 1), ("unaccounted", 1), ("completed", 0)):
            report = report_fixture(lock)
            item = next(item for item in report["analysis_completeness"]["analyzer_statuses"]
                        if item["analyzer_id"] in _STATIC)
            item[field] = value
            self.assert_code("inspection_incomplete", lambda: assess_report(report, lock))

    def test_missing_file_or_wrong_size_is_rejected(self):
        lock = package_lock()
        for change in ("remove", "size", "duplicate"):
            report = report_fixture(lock)
            if change == "remove":
                report["components"].pop()
            elif change == "size":
                report["components"][0]["size_bytes"] += 1
            else:
                report["components"][1] = report["components"][0]
            self.assert_code("inspection_file_coverage_mismatch",
                             lambda: assess_report(report, lock))

    def test_unknown_version_llm_use_and_suppression_fail(self):
        lock = package_lock()
        for field, value, error in (
                ("skillspector_version", "future", "inspection_version_mismatch"),
                ("llm_requested", True, "inspection_not_static"),
                ("meta_analysis_applied", True, "inspection_not_static"),
                ("inference_usage", [{}], "inspection_not_static")):
            report = report_fixture(lock)
            report["metadata"][field] = value
            self.assert_code(error, lambda: assess_report(report, lock))
        report = report_fixture(lock)
        report["suppressed_count"] = 1
        self.assert_code("inspection_suppressed_findings", lambda: assess_report(report, lock))

    def test_hidden_filtering_and_exclusions_fail(self):
        lock = package_lock()
        for field, value, error in (
                ("findings_before_filtering", 1, "inspection_filtered_findings"),
                ("scope_exclusions", ["SKILL.md"], "inspection_incomplete"),
                ("ledger_exceptions", ["failed"], "inspection_incomplete")):
            report = report_fixture(lock)
            report["analysis_completeness"][field] = value
            self.assert_code(error, lambda: assess_report(report, lock))

    def test_either_high_finding_or_score_above_existing_gate_blocks(self):
        lock = package_lock()
        report = report_fixture(lock)
        report["risk_assessment"]["score"] = 51
        self.assertFalse(assess_report(report, lock)["inspection_passed"])
        report["risk_assessment"]["score"] = 50
        self.assertTrue(assess_report(report, lock)["inspection_passed"])
        report["issues"] = [{"severity": "HIGH", "location": {"file": "SKILL.md"}}]
        report["analysis_completeness"].update(
            findings_before_filtering=1, findings_after_filtering=1)
        self.assertFalse(assess_report(report, lock)["inspection_passed"])

    def test_malformed_reports_fail_with_stable_error(self):
        lock = package_lock()
        for report in ({}, [], None):
            self.assert_code("invalid_inspection_report", lambda: assess_report(report, lock))
        for value in (float("nan"), float("inf"), True, "0"):
            report = report_fixture(lock)
            report["risk_assessment"]["score"] = value
            self.assert_code("invalid_inspection_report", lambda: assess_report(report, lock))

    def fixture(self, directory):
        lock = package_lock()
        cache = Path(directory) / "cache"
        fetched = fetch_package(lock, cache, download=download)
        return lock, cache, Path(fetched["content"])

    def runner(self, lock, *, score=0, mutate=False, exit_code=0):
        def execute(arguments, **kwargs):
            self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
            self.assertFalse(kwargs["check"])
            self.assertNotIn("shell", kwargs)
            self.assertNotIn("OPENAI_API_KEY", kwargs["env"])
            self.assertNotIn("PYTHONPATH", kwargs["env"])
            if arguments[1] == "--version":
                kwargs["stdout"].write(("SkillSpector v" + SCANNER_VERSION + "\n").encode())
                return subprocess.CompletedProcess(arguments, 0)
            self.assertIn("--no-llm", arguments)
            self.assertNotIn("--baseline", arguments)
            content = Path(arguments[2])
            report = report_fixture(lock)
            report["skill"] = {"source": str(content)}
            report["risk_assessment"]["score"] = score
            Path(arguments[-1]).write_text(json.dumps(report))
            if mutate:
                (content / "SKILL.md").write_text("changed by scanner")
            return subprocess.CompletedProcess(arguments, exit_code)
        return execute

    def test_inspection_copies_bytes_preserves_cache_and_retains_bound_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            lock, cache, content = self.fixture(directory)
            before = (content / "SKILL.md").read_bytes()
            with patch("agent_skills_exchange.inspection.run_tool", self.runner(lock)):
                result = inspect_package(lock, cache, Path(directory) / "reports",
                                         sys.executable, timeout=30)
            self.assertTrue(result["inspection_passed"])
            self.assertTrue(result["valid"])
            self.assertFalse(result["activated"])
            self.assertFalse(result["approval_granted"])
            self.assertFalse(result["receipt_is_authority"])
            self.assertEqual(result["package_sha256"], lock["ref"]["package_sha256"])
            self.assertEqual((content / "SKILL.md").read_bytes(), before)
            evidence = Path(result["evidence"])
            self.assertEqual(json.loads((evidence / "receipt.json").read_text()), result)
            report = json.loads((evidence / "report.json").read_text())
            self.assertNotEqual(report["skill"]["source"], str(content))
            self.assertFalse(Path(report["skill"]["source"]).exists())

    def test_high_score_retains_report_and_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            lock, cache, _content = self.fixture(directory)
            with patch("agent_skills_exchange.inspection.run_tool",
                       self.runner(lock, score=76, exit_code=1)):
                result = inspect_package(lock, cache, Path(directory) / "reports",
                                         sys.executable, timeout=30)
            self.assertFalse(result["valid"])
            self.assertEqual(result["error"], "inspection_findings_blocked")
            self.assertTrue((Path(result["evidence"]) / "report.json").is_file())

    def test_assessment_and_digest_use_one_report_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            lock, cache, _content = self.fixture(directory)
            read_bytes = Path.read_bytes
            snapshots = []
            def observe(path):
                data = read_bytes(path)
                if path.name == "report.json":
                    snapshots.append(data)
                    # Simulate a concurrent change after the observation. The
                    # receipt must still hash the bytes actually assessed.
                    path.write_bytes(b"changed after read")
                return data
            with patch("agent_skills_exchange.inspection.run_tool", self.runner(lock)), \
                    patch.object(Path, "read_bytes", observe):
                result = inspect_package(lock, cache, Path(directory) / "reports",
                                         sys.executable, timeout=30)
            self.assertTrue(result["valid"])
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(result["report_sha256"], hashlib.sha256(snapshots[0]).hexdigest())
            self.assertNotEqual(result["report_sha256"], hashlib.sha256(b"changed after read").hexdigest())

    def test_invalid_report_encoding_duplicate_keys_and_nonfinite_json_fail(self):
        for body in [b"\xff", b'{"execution_successful":true,"execution_successful":false}',
                     b'{"score": NaN}']:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                lock, cache, _content = self.fixture(directory)
                runner = self.runner(lock)
                def execute(arguments, **kwargs):
                    result = runner(arguments, **kwargs)
                    if arguments[1] != "--version":
                        Path(arguments[-1]).write_bytes(body)
                    return result
                with patch("agent_skills_exchange.inspection.run_tool", execute):
                    result = inspect_package(lock, cache, Path(directory) / "reports",
                                             sys.executable, timeout=30)
                self.assertFalse(result["valid"])
                self.assertFalse(result["activated"])
                self.assertIn("error", result)

    def test_scanner_mutation_is_not_accepted_and_cache_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            lock, cache, content = self.fixture(directory)
            before = (content / "SKILL.md").read_bytes()
            with patch("agent_skills_exchange.inspection.run_tool",
                       self.runner(lock, mutate=True)):
                result = inspect_package(lock, cache, Path(directory) / "reports",
                                         sys.executable, timeout=30)
            self.assertFalse(result["valid"])
            self.assertEqual(result["error"], "cache_size_mismatch")
            self.assertEqual((content / "SKILL.md").read_bytes(), before)

    def test_timeout_is_reported_without_prompt_or_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            lock, cache, _content = self.fixture(directory)
            with patch("agent_skills_exchange.inspection.run_tool",
                       side_effect=subprocess.TimeoutExpired("scanner", 0.01)) as run:
                result = inspect_package(lock, cache, Path(directory) / "reports",
                                         sys.executable, timeout=0.01)
            self.assertEqual(result["error"], "inspection_timeout")
            self.assertEqual(run.call_count, 1)

    def test_missing_scanner_bad_timeout_and_relative_executable_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            lock, cache, _content = self.fixture(directory)
            for timeout in (0, -1, float("nan"), float("inf")):
                self.assert_code("invalid_inspection_timeout", lambda: inspect_package(
                    lock, cache, Path(directory) / "reports", sys.executable, timeout=timeout))
            self.assert_code("scanner_requires_absolute_path", lambda: inspect_package(
                lock, cache, Path(directory) / "reports", "skillspector", timeout=30))
            self.assert_code("inspection_unavailable", lambda: inspect_package(
                lock, cache, Path(directory) / "reports", "/absent/skillspector", timeout=30))

    def test_bytecode_package_is_rejected_not_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = package_lock()
            lock["files"][1]["path"] = "__pycache__/fixture.pyc"
            fix_digest(lock)
            cache = Path(directory) / "cache"
            fetched = fetch_package(lock, cache, download=download)
            with patch("agent_skills_exchange.inspection.run_tool") as run:
                self.assert_code("inspection_bytecode_not_supported", lambda: inspect_package(
                    lock, cache, Path(directory) / "reports", sys.executable, timeout=30))
                run.assert_not_called()
            self.assertTrue((Path(fetched["content"]) / "__pycache__/fixture.pyc").exists())

    def test_execution_error_is_not_overruled_by_a_passing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            lock, cache, _content = self.fixture(directory)
            with patch("agent_skills_exchange.inspection.run_tool",
                       self.runner(lock, exit_code=2)):
                result = inspect_package(lock, cache, Path(directory) / "reports",
                                         sys.executable, timeout=30)
            self.assertEqual(result["error"], "inspection_execution_failed")
            self.assertFalse(result["inspection_passed"])

    def test_cli_returns_nonzero_for_blocked_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            lock, cache, _content = self.fixture(directory)
            lockfile = Path(directory) / "lock.json"
            lockfile.write_text(json.dumps(lock))
            output = io.StringIO()
            with patch("agent_skills_exchange.inspection.run_tool",
                       self.runner(lock, score=76)), redirect_stdout(output):
                status = main(["inspect", "--lock", str(lockfile), "--cache", str(cache),
                               "--reports", str(Path(directory) / "reports"),
                               "--scanner", sys.executable, "--timeout", "30"])
            self.assertEqual(status, 2)
            result = json.loads(output.getvalue())
            self.assertFalse(result["inspection_passed"])
            self.assertFalse(result["approval_granted"])


if __name__ == "__main__":
    unittest.main()
