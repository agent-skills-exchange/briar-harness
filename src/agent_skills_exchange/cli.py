# SPDX-License-Identifier: GPL-3.0-or-later
"""Non-interactive, JSON-output skill commands. No transport SDK imports."""

import argparse
import json
from pathlib import Path

from .dependencies import DependencyError, plan_dependencies, read_json, validate_manifest
from .packages import fetch_package, validate_lock, verify_cache
from .inspection import inspect_package, verify_inspection_evidence
from .format_check import check_format
from .authzen import activation_request
from .hosts import onboarding_plan
from .updates import plan_update


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # Do not echo possibly sensitive malformed values from arguments.
        raise DependencyError("invalid_arguments", "arguments")


def _read_inspection_evidence(path):
    try:
        return path.read_bytes()
    except OSError as exc:
        # File names and OS errors may contain private caller information.
        raise DependencyError("inspection_evidence_unreadable", "inspection_evidence") from exc


def main(argv=None) -> int:
    parser = Parser(prog="ase", description="Agent Skills Exchange package tools")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    validate = commands.add_parser("validate", help="Check a structured dependency manifest")
    validate.add_argument("manifest", type=Path)
    plan = commands.add_parser("plan", help="Plan pinned skill dependencies from local metadata")
    plan_source = plan.add_mutually_exclusive_group(required=True)
    plan_source.add_argument("--catalog", type=Path)
    plan_source.add_argument("--lock", type=Path)
    plan.add_argument("--manifest", type=Path)
    plan.add_argument("--skill", required=True)
    plan.add_argument("--feature", action="append", required=True)
    plan.add_argument("--optional", action="append", default=[])
    plan.add_argument("--os", required=True)
    plan.add_argument("--distribution", required=True)
    plan.add_argument("--os-version", required=True)
    plan.add_argument("--architecture", required=True)
    fetch = commands.add_parser("fetch", help="Fetch and verify a reviewed pinned package")
    fetch.add_argument("--lock", type=Path, required=True)
    fetch.add_argument("--cache", type=Path, required=True)
    verify = commands.add_parser("verify-cache", help="Verify cached package bytes without network")
    verify.add_argument("--lock", type=Path, required=True)
    verify.add_argument("--cache", type=Path, required=True)
    inspect = commands.add_parser("inspect", help="Static SkillSpector inspection; never activates")
    inspect.add_argument("--lock", type=Path, required=True)
    inspect.add_argument("--cache", type=Path, required=True)
    inspect.add_argument("--reports", type=Path, required=True)
    inspect.add_argument("--scanner", type=Path, required=True)
    inspect.add_argument("--timeout", type=float, required=True)
    evidence = commands.add_parser(
        "verify-inspection", help="Offline saved-evidence consistency check; never admits or activates")
    for field in ["lock", "cache", "receipt", "report"]:
        evidence.add_argument("--" + field, type=Path, required=True)
    evidence.add_argument("--expected-receipt-sha256", required=True)
    evidence.add_argument("--expected-scanner-sha256", required=True)
    format_check = commands.add_parser("check-format", help="Optional reference-format diagnostic; never admits")
    format_check.add_argument("--lock", type=Path, required=True)
    format_check.add_argument("--cache", type=Path, required=True)
    format_check.add_argument("--reports", type=Path, required=True)
    format_check.add_argument("--validator", type=Path, required=True)
    format_check.add_argument("--name", required=True)
    format_check.add_argument("--timeout", type=float, required=True)
    policy_request = commands.add_parser("authzen-request", help="Build an offline policy request; never grants authority")
    policy_request.add_argument("--lock", type=Path, required=True)
    for field in ["worker", "project", "task", "phase", "requested-until", "revocation-epoch"]:
        policy_request.add_argument("--" + field, required=True)
    onboard = commands.add_parser("onboarding-plan", help="Offline native host setup plan; never writes or activates")
    onboard.add_argument("--host", required=True)
    onboard.add_argument("--project", required=True)
    onboard.add_argument("--name", required=True)
    update = commands.add_parser("plan-update", help="Read-only drift/update/rollback-cache plan; never applies")
    update.add_argument("--current-lock", type=Path, required=True)
    update.add_argument("--target-lock", type=Path, required=True)
    update.add_argument("--cache", type=Path, required=True)
    update.add_argument("--directory", type=Path, required=True)
    try:
        args = parser.parse_args(argv)
        if args.command == "validate":
            manifest = validate_manifest(read_json(args.manifest))
            result = {"valid": True, "features": manifest["features"], "approval_granted": False}
        elif args.command == "onboarding-plan":
            result = onboarding_plan(args.host, args.project, args.name)
        elif args.command == "plan-update":
            result = plan_update(read_json(args.current_lock), read_json(args.target_lock),
                                 args.cache, args.directory)
        elif args.command == "plan":
            if args.catalog is not None:
                if args.manifest is not None:
                    raise DependencyError("invalid_arguments", "arguments")
                catalog = read_json(args.catalog)
            else:
                if args.manifest is None:
                    raise DependencyError("invalid_arguments", "arguments")
                lock = validate_lock(read_json(args.lock))
                catalog = {"schema_version": 1, "packages": [
                    {"ref": lock["ref"], "manifest": read_json(args.manifest)}]}
            result = plan_dependencies(
                catalog, args.skill, args.feature,
                {"os": args.os, "distribution": args.distribution,
                 "version": args.os_version, "architecture": args.architecture},
                args.optional,
            )
        elif args.command == "fetch":
            result = fetch_package(read_json(args.lock), args.cache)
        elif args.command == "verify-cache":
            result = verify_cache(read_json(args.lock), args.cache)
        elif args.command == "inspect":
            result = inspect_package(read_json(args.lock), args.cache, args.reports,
                                     args.scanner, timeout=args.timeout)
        elif args.command == "verify-inspection":
            result = verify_inspection_evidence(
                read_json(args.lock), args.cache,
                _read_inspection_evidence(args.receipt),
                _read_inspection_evidence(args.report),
                expected_receipt_sha256=args.expected_receipt_sha256,
                expected_scanner_sha256=args.expected_scanner_sha256)
        elif args.command == "check-format":
            result = check_format(read_json(args.lock), args.cache, args.reports,
                                  args.validator, args.name, timeout=args.timeout)
        else:
            scope = {field: getattr(args, field) for field in
                     ["worker", "project", "task", "phase", "requested_until", "revocation_epoch"]}
            result = {"valid": True, "request": activation_request(read_json(args.lock), scope),
                      "identity_verified": False, "scope_claims_verified": False,
                      "approval_granted": False, "activated": False,
                      "authority_verifier_live": False}
    except (DependencyError, RecursionError) as exc:
        result = {"valid": False, "error": getattr(exc, "code", "metadata_too_deep"),
                  "location": getattr(exc, "location", "manifest"), "approval_granted": False}
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("valid", True) else 2
