# SPDX-License-Identifier: GPL-3.0-or-later
"""Static inspection evidence, not skill activation or runtime authority."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time

from .dependencies import DependencyError, _invalid_constant, _unique_object
from .packages import _root, _verify_content, verify_cache
from .processes import run_tool


# Adapter contract: do not silently accept an unknown report/analyzer version.
SCANNER_VERSION = "2.8.2"
POLICY = {
    "id": "ase-skillspector-static-v1",
    "scanner_version": SCANNER_VERSION,
    "llm": False,
    "baseline": False,
    # Existing Briar SkillSpector gate, not a model-generated risk budget.
    "maximum_score": 50,
    "blocking_severities": ["HIGH", "CRITICAL"],
}
_PATTERNS = (
    "agent_snooping", "anti_refusal", "data_exfiltration", "excessive_agency",
    "harmful_content", "memory_poisoning", "output_handling",
    "privilege_escalation", "prompt_injection", "rogue_agent", "ssrf",
    "supply_chain", "system_prompt_leakage", "tool_misuse",
)
_STATIC = {"static_patterns_" + name for name in _PATTERNS} | {"static_yara"}
_APPLICABLE = {"behavioral_ast", "behavioral_taint_tracking", "mcp_least_privilege"}
_OTHER = {"mcp_rug_pull", "mcp_tool_poisoning"}
_SEMANTIC = {"meta_analyzer", "semantic_developer_intent", "semantic_quality_policy",
             "semantic_security_discovery"}
_SEVERITIES = {"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _parse_report_bytes(raw):
    """Parse the exact bytes whose digest is retained, without reopening a path."""
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, DependencyError):
            raise
        raise DependencyError("invalid_inspection_report") from exc


def verify_inspection_evidence(lock, cache, receipt_bytes, report_bytes, *,
                               expected_receipt_sha256, expected_scanner_sha256):
    """Check saved evidence against independently supplied expected identities.

    Bytes are supplied rather than reopened after hashing. Expected hashes must
    come from protected caller state, not from the receipt being checked. This
    function cannot establish that origin, scanner runtime closure or authority.
    It never activates a skill, signs evidence or treats a receipt as permission.
    """
    for value in (expected_receipt_sha256, expected_scanner_sha256):
        if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
            raise DependencyError("invalid_inspection_binding")
    if type(receipt_bytes) is not bytes or type(report_bytes) is not bytes:
        raise DependencyError("invalid_inspection_evidence")
    if hashlib.sha256(receipt_bytes).hexdigest() != expected_receipt_sha256:
        raise DependencyError("inspection_receipt_digest_mismatch")
    verified = verify_cache(lock, cache)
    try:
        receipt, report = _parse_report_bytes(receipt_bytes), _parse_report_bytes(report_bytes)
        if not isinstance(receipt, dict) or not isinstance(report, dict):
            raise DependencyError("invalid_inspection_evidence")
        if (receipt["package_sha256"] != lock["ref"]["package_sha256"]
                or receipt["scanner_executable_sha256"] != expected_scanner_sha256
                or _canonical(receipt["policy"]) != _canonical(POLICY)
                or receipt["policy_sha256"] != hashlib.sha256(_canonical(POLICY)).hexdigest()
                or receipt["report_sha256"] != hashlib.sha256(report_bytes).hexdigest()):
            raise DependencyError("inspection_binding_mismatch")
        assessment = assess_report(report, lock)
        for field in ("activated", "approval_granted", "receipt_is_authority"):
            if receipt[field] is not False:
                raise DependencyError("invalid_inspection_evidence")
        if receipt["artifact_integrity_verified"] is not True:
            raise DependencyError("invalid_inspection_evidence")
        for field, value in assessment.items():
            if type(receipt[field]) is not type(value) or receipt[field] != value:
                raise DependencyError("inspection_assessment_mismatch")
        if receipt["valid"] is not assessment["inspection_passed"]:
            raise DependencyError("inspection_assessment_mismatch")
        if not assessment["inspection_passed"] or "error" in receipt:
            raise DependencyError("inspection_findings_blocked")
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, DependencyError):
            raise
        raise DependencyError("invalid_inspection_evidence") from exc
    return {
        "valid": True, "evidence_consistent": True,
        "package_sha256": verified["package_sha256"],
        "receipt_sha256": expected_receipt_sha256,
        "scanner_executable_sha256": expected_scanner_sha256,
        "expected_identity_origin_verified": False,
        "scanner_runtime_verified": False, "receipt_is_authority": False,
        "approval_granted": False, "activated": False,
    }


def assess_report(report, lock):
    """Reject missing coverage, unknown schemas, suppression and LLM execution.

    A caller-supplied report alone is never evidence that a scan actually ran.
    inspect_package binds locally generated evidence to the verified package.
    """
    try:
        if report["execution_successful"] is not True:
            raise DependencyError("inspection_execution_failed")
        metadata = report["metadata"]
        if metadata["skillspector_version"] != SCANNER_VERSION:
            raise DependencyError("inspection_version_mismatch")
        if (metadata["llm_requested"] is not False
                or metadata["meta_analysis_applied"] is not False
                or metadata["inference_usage"] != []):
            raise DependencyError("inspection_not_static")
        if report["suppressed_count"] != 0 or report["suppressed"] != []:
            raise DependencyError("inspection_suppressed_findings")
        components = report["components"]
        expected = {item["path"]: item["size"] for item in lock["files"]}
        if (not isinstance(components, list) or len(components) != len(expected)
                or {item["path"]: item["size_bytes"] for item in components} != expected):
            raise DependencyError("inspection_file_coverage_mismatch")
        coverage = report["analysis_completeness"]
        for field in ("total_components", "scanned_components", "fully_inspected_files"):
            if type(coverage[field]) is not int or coverage[field] != len(expected):
                raise DependencyError("inspection_incomplete")
        if (coverage["execution_successful"] is not True
                or coverage["coverage_percent"] != 100
                or coverage["partially_inspected_files"] != 0
                or coverage["entirely_uninspected_files"] != 0
                or coverage["ledger_exceptions"] != [] or coverage["scope_exclusions"] != []):
            raise DependencyError("inspection_incomplete")
        statuses = coverage["analyzer_statuses"]
        expected_ids = _STATIC | _APPLICABLE | _OTHER | _SEMANTIC
        if (len(statuses) != len(expected_ids)
                or {item["analyzer_id"] for item in statuses} != expected_ids):
            raise DependencyError("inspection_analyzer_set_mismatch")
        for item in statuses:
            name, status = item["analyzer_id"], item["status"]
            counts = [item[field] for field in
                      ("planned_work", "completed", "skipped", "failed", "unaccounted")]
            if (any(type(value) is not int or value < 0 for value in counts)
                    or counts[2:] != [0, 0, 0] or counts[0] != counts[1]):
                raise DependencyError("inspection_incomplete")
            if name in _SEMANTIC:
                # Overall is_complete is false in no-LLM mode. Only these named
                # semantic checks may be disabled; all static work is required.
                empty_meta = (name == "meta_analyzer" and status == "not_applicable"
                              and item.get("reason_code") == "no_applicable_files"
                              and report["issues"] == [])
                if (status != "disabled" and not empty_meta) or counts != [0] * 5:
                    raise DependencyError("inspection_not_static")
            elif name in _APPLICABLE and status == "not_applicable":
                if counts != [0] * 5:
                    raise DependencyError("inspection_incomplete")
            elif status != "completed" or not counts[0]:
                raise DependencyError("inspection_incomplete")
            if name in _STATIC and counts[0] != len(expected):
                raise DependencyError("inspection_incomplete")
        issues = report["issues"]
        if not isinstance(issues, list):
            raise DependencyError("invalid_inspection_report")
        if (coverage["findings_before_filtering"] != len(issues)
                or coverage["findings_after_filtering"] != len(issues)):
            raise DependencyError("inspection_filtered_findings")
        for issue in issues:
            if issue["severity"] not in _SEVERITIES or issue["location"]["file"] not in expected:
                raise DependencyError("invalid_inspection_report")
        risk = report["risk_assessment"]
        score, severity = risk["score"], risk["severity"]
        if (type(score) not in {int, float} or not math.isfinite(score)
                or not 0 <= score <= 100 or severity not in _SEVERITIES):
            raise DependencyError("invalid_inspection_report")
        blocked = (score > POLICY["maximum_score"]
                   or severity in POLICY["blocking_severities"]
                   or any(item["severity"] in POLICY["blocking_severities"] for item in issues))
        return {"inspection_passed": not blocked, "score": score, "severity": severity,
                "finding_count": len(issues), "static_coverage_verified": True}
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, DependencyError):
            raise
        raise DependencyError("invalid_inspection_report") from exc


def inspect_package(lock, cache, reports, scanner, *, timeout):
    """Run a trusted operator-provisioned scanner against a private copy.

    The scanner is trusted local software, not sandboxed here. No target code
    is intentionally executed. Receipts are local evidence, not signed admission
    tokens, and this command never activates skills or reuses old scan results.
    """
    if type(timeout) not in {int, float} or not math.isfinite(timeout) or timeout <= 0:
        raise DependencyError("invalid_inspection_timeout")
    verified = verify_cache(lock, cache)
    if any(record["path"].endswith((".pyc", ".pyo"))
           or "__pycache__" in record["path"].split("/") for record in lock["files"]):
        # Never clean selected package bytes to obtain a different scan target.
        raise DependencyError("inspection_bytecode_not_supported")
    try:
        scanner = Path(scanner)
        if not scanner.is_absolute():
            raise DependencyError("scanner_requires_absolute_path")
        scanner = scanner.resolve(strict=True)
        metadata = scanner.stat()
        if not stat.S_ISREG(metadata.st_mode) or not os.access(scanner, os.X_OK):
            raise DependencyError("scanner_unavailable")
        if os.name != "posix":
            raise DependencyError("inspection_platform_not_supported")
        if metadata.st_uid not in {0, os.getuid()} or metadata.st_mode & 0o022:
            raise DependencyError("unsafe_scanner_executable")
        executable_hash = hashlib.sha256(scanner.read_bytes()).hexdigest()
        root = _root(reports, create=True).resolve()
        evidence = Path(tempfile.mkdtemp(prefix="inspection-", dir=root))
        started = time.monotonic()
        result = {"valid": False, "activated": False, "approval_granted": False,
                  "inspection_passed": False, "artifact_integrity_verified": True,
                  "package_sha256": lock["ref"]["package_sha256"],
                  "policy": POLICY, "policy_sha256": hashlib.sha256(_canonical(POLICY)).hexdigest(),
                  "scanner": str(scanner), "scanner_executable_sha256": executable_hash,
                  "evidence": str(evidence), "receipt_is_authority": False}
        # Empty credential/config environment: no inherited provider tokens or
        # tracing configuration. This is not OS-enforced network containment.
        with tempfile.TemporaryDirectory(prefix="ase-inspect-") as temporary:
            scratch = Path(temporary)
            home = scratch / "home"
            home.mkdir()
            environment = {"PATH": os.defpath, "HOME": str(home),
                           "XDG_CONFIG_HOME": str(home), "PYTHONNOUSERSITE": "1",
                           "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8",
                           "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"}
            slot = scratch / "package"
            slot.mkdir()
            shutil.copytree(verified["content"], slot / "content", symlinks=True)
            (slot / "lock.json").write_bytes(_canonical(lock))
            _verify_content(slot, lock)

            def run(arguments, name):
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(arguments, timeout)
                with (evidence / (name + ".stdout")).open("xb") as out, \
                        (evidence / (name + ".stderr")).open("xb") as err:
                    return run_tool([str(scanner), *arguments], cwd=home,
                                          env=environment, stdin=subprocess.DEVNULL,
                                          stdout=out, stderr=err, timeout=remaining,
                                          check=False).returncode

            try:
                code = run(["--version"], "version")
                if (code != 0 or (evidence / "version.stdout").read_text().strip()
                        != "SkillSpector v" + SCANNER_VERSION):
                    raise DependencyError("inspection_version_mismatch")
                report_path = evidence / "report.json"
                code = run(["scan", str(slot / "content"), "--no-llm", "--format", "json",
                            "--output", str(report_path)], "scan")
                # SkillSpector returns 1 for an elevated risk verdict; other
                # nonzero statuses are execution failures even with a report.
                if code not in {0, 1}:
                    raise DependencyError("inspection_execution_failed")
                _verify_content(slot, lock)
                verify_cache(lock, cache)
                if hashlib.sha256(scanner.read_bytes()).hexdigest() != executable_hash:
                    raise DependencyError("scanner_changed_during_inspection")
                report_bytes = report_path.read_bytes()
                report = _parse_report_bytes(report_bytes)
                if report["skill"]["source"] != str(slot / "content"):
                    raise DependencyError("inspection_source_mismatch")
                result.update(assess_report(report, lock))
                result["report_sha256"] = hashlib.sha256(report_bytes).hexdigest()
                result["valid"] = result["inspection_passed"]
                if not result["inspection_passed"]:
                    result["error"] = "inspection_findings_blocked"
            except subprocess.TimeoutExpired:
                result["error"] = "inspection_timeout"
            except (DependencyError, KeyError, TypeError, OSError, UnicodeError) as exc:
                result["error"] = getattr(exc, "code", "inspection_execution_failed")
        (evidence / "receipt.json").write_bytes(_canonical(result))
        return result
    except (OSError, ValueError) as exc:
        if isinstance(exc, DependencyError):
            raise
        raise DependencyError("inspection_unavailable") from exc
