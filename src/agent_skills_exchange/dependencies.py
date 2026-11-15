# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline dependency declarations and planning; never installs or grants access."""

from __future__ import annotations

from collections import deque
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit


class DependencyError(ValueError):
    """A stable, value-free error safe for structured command output."""

    def __init__(self, code: str, location: str = "manifest"):
        self.code = code
        self.location = location
        super().__init__(f"{code} at {location}")


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise DependencyError("duplicate_json_key")
        value[key] = item
    return value


def _invalid_constant(_value):
    raise DependencyError("nonfinite_json_number")


def read_json(path: Path) -> Any:
    """Read only the explicitly supplied local metadata, never its linked files."""
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise DependencyError("unreadable_json") from exc


def dependency_schema() -> dict:
    return json.loads(
        files("agent_skills_exchange").joinpath("schemas/dependencies-v1.json")
        .read_text(encoding="utf-8")
    )


def _equal(left, right):
    # Python considers True == 1; JSON Schema does not.
    if type(left) in (int, float) and type(right) in (int, float):
        return left == right
    return type(left) is type(right) and left == right


def _check(value, rule, root, location):
    """Evaluate only the closed JSON Schema vocabulary used by this profile.

    No caller-provided schemas or remote references are accepted. The authoring
    extra's independent JSON Schema implementation checks parity in tests.
    """
    supported = {
        "$schema", "$defs", "$ref", "title", "description", "type", "const",
        "enum", "pattern", "minLength", "required", "properties",
        "additionalProperties", "minItems", "uniqueItems", "items",
        "if", "then", "else", "anyOf",
    }
    if set(rule) - supported:
        raise DependencyError("unsupported_schema_keyword", location)
    if "$ref" in rule:
        ref = rule["$ref"]
        if not ref.startswith("#/$defs/") or ref[8:] not in root["$defs"]:
            raise DependencyError("unsupported_schema_reference", location)
        _check(value, root["$defs"][ref[8:]], root, location)
    if "anyOf" in rule:
        for option in rule["anyOf"]:
            try:
                _check(value, option, root, location)
                break
            except DependencyError:
                pass
        else:
            raise DependencyError("schema_alternatives", location)
    types = {"object": dict, "array": list, "string": str, "boolean": bool}
    if "type" in rule and type(value) is not types[rule["type"]]:
        raise DependencyError("schema_type", location)
    if "const" in rule and not _equal(value, rule["const"]):
        raise DependencyError("schema_const", location)
    if "enum" in rule and not any(_equal(value, item) for item in rule["enum"]):
        raise DependencyError("schema_enum", location)
    if isinstance(value, str):
        if len(value) < rule.get("minLength", 0):
            raise DependencyError("schema_min_length", location)
        if "pattern" in rule and not re.search(rule["pattern"], value):
            raise DependencyError("schema_pattern", location)
    if isinstance(value, dict):
        if set(rule.get("required", [])) - set(value):
            raise DependencyError("schema_required", location)
        properties = rule.get("properties", {})
        if rule.get("additionalProperties") is False and set(value) - set(properties):
            raise DependencyError("schema_unknown_field", location)
        for key in sorted(properties.keys() & value.keys()):
            _check(value[key], properties[key], root, f"{location}.{key}")
    if isinstance(value, list):
        if len(value) < rule.get("minItems", 0):
            raise DependencyError("schema_min_items", location)
        if rule.get("uniqueItems"):
            rendered = [json.dumps(item, sort_keys=True) for item in value]
            if len(set(rendered)) != len(rendered):
                raise DependencyError("schema_unique_items", location)
        if "items" in rule:
            for index, item in enumerate(value):
                _check(item, rule["items"], root, f"{location}[{index}]")
    if "if" in rule:
        try:
            _check(value, rule["if"], root, location)
            branch = "then"
        except DependencyError:
            branch = "else"
        _check(value, rule.get(branch, {}), root, location)


def validate_manifest(manifest: Any) -> dict:
    schema = dependency_schema()
    _check(manifest, schema, schema, "manifest")
    features = set(manifest["features"])
    platform_ids = [entry["id"] for entry in manifest["platforms"]]
    if len(set(platform_ids)) != len(platform_ids):
        raise DependencyError("duplicate_platform_id")
    for category in ("platforms", "hosts", "software", "skills", "network", "credentials", "lockfiles"):
        entries = manifest[category]
        ids = [item["id"] for item in entries if "id" in item]
        if category not in {"software", "skills"} and len(set(ids)) != len(ids):
            raise DependencyError("duplicate_dependency_id", f"manifest.{category}")
        for index, item in enumerate(entries):
            location = f"manifest.{category}[{index}]"
            if not set(item["applies_to"]).issubset(features):
                raise DependencyError("unknown_feature_reference", location)
            if category == "software" and not set(item["platforms"]).issubset(platform_ids):
                raise DependencyError("unknown_platform_reference", location)
            if category == "network":
                try:
                    parsed = urlsplit(item["destination"])
                    _port = parsed.port
                except ValueError as exc:
                    raise DependencyError("invalid_network_destination", location) from exc
                if not parsed.hostname or parsed.username or parsed.password:
                    raise DependencyError("invalid_network_destination", location)
    covered = set().union(*(set(item["applies_to"]) for item in manifest["platforms"]))
    if features - covered:
        raise DependencyError("feature_without_platform")
    for index, left in enumerate(manifest["software"]):
        for right in manifest["software"][index + 1:]:
            if (left["id"] == right["id"]
                    and set(left["platforms"]) & set(right["platforms"])
                    and set(left["applies_to"]) & set(right["applies_to"])):
                raise DependencyError("overlapping_software_dependency")
    for index, left in enumerate(manifest["skills"]):
        for right in manifest["skills"][index + 1:]:
            if left["id"] == right["id"] and set(left["applies_to"]) & set(right["applies_to"]):
                raise DependencyError("overlapping_skill_dependency")
    return manifest


def manifest_digest(manifest: dict) -> str:
    return hashlib.sha256(json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _reference(raw: Any) -> dict:
    rule = dependency_schema()["$defs"]["skill"]
    expected = set(rule["properties"]) - {"required", "applies_to", "features"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise DependencyError("invalid_package_reference")
    combined = {**raw, "required": True, "applies_to": ["reference"], "features": ["reference"]}
    schema = dependency_schema()
    _check(combined, rule, schema, "reference")
    return raw


def _platforms(manifest, features, target):
    matched = []
    unresolved = set()
    for item in manifest["platforms"]:
        if not set(item["applies_to"]) & features:
            continue
        if item["os"] not in ("any", target["os"]):
            continue
        if item["distribution"] not in ("any", target["distribution"]):
            continue
        if "any" not in item["architectures"] and target["architecture"] not in item["architectures"]:
            continue
        version = item["version"]
        if version["scheme"] == "exact":
            if version["constraint"] != target["version"]:
                continue
        elif version["scheme"] != "none":
            unresolved.update(set(item["applies_to"]) & features)
            continue
        matched.append(item)
    covered = set().union(*(set(item["applies_to"]) for item in matched))
    if features - covered:
        if (features - covered) & unresolved:
            raise DependencyError("platform_version_scheme_not_implemented")
        raise DependencyError("unsupported_target_platform")
    return {item["id"] for item in matched}


def plan_dependencies(catalog: Any, skill: str, features: list[str], target: dict,
                      optional: list[str] = ()) -> dict:
    """Plan a local metadata closure. Pins are requests, not verified artifacts.

    Never reads SKILL.md, fetches sources, executes target code, installs
    packages, checks credentials or turns declared requirements into permission.
    """
    if (not isinstance(catalog, dict) or set(catalog) != {"schema_version", "packages"}
            or type(catalog["schema_version"]) is not int or catalog["schema_version"] != 1
            or not isinstance(catalog["packages"], list)):
        raise DependencyError("invalid_catalog")
    if not isinstance(target, dict) or set(target) != {"os", "distribution", "version", "architecture"} or not all(
        isinstance(value, str) and value for value in target.values()
    ):
        raise DependencyError("invalid_target")
    if target["os"] not in {"linux", "macos", "windows", "freebsd"}:
        raise DependencyError("invalid_target")
    if not features or len(set(features)) != len(features) or len(set(optional)) != len(optional):
        raise DependencyError("invalid_selection")
    packages = {}
    for entry in catalog["packages"]:
        if not isinstance(entry, dict) or set(entry) != {"ref", "manifest"}:
            raise DependencyError("invalid_catalog_entry")
        ref = _reference(entry["ref"])
        if ref["id"] in packages:
            raise DependencyError("duplicate_catalog_id")
        packages[ref["id"]] = entry
    requested = {skill: set(features)}
    queue = deque([skill])
    graph = {}
    requirements = {}
    seen_optional = set()
    while queue:
        current = queue.popleft()
        if current not in packages:
            raise DependencyError("missing_package")
        entry = packages[current]
        manifest = validate_manifest(entry["manifest"])
        active = requested[current]
        if not active.issubset(manifest["features"]):
            raise DependencyError("unsupported_requested_feature")
        platforms = _platforms(manifest, active, target)
        graph[current] = set()
        requirements[current] = {
            category: [item for item in manifest[category]
                       if set(item["applies_to"]) & active
                       and (category != "software" or set(item["platforms"]) & platforms)]
            for category in ("hosts", "software", "network", "credentials", "lockfiles")
        }
        for dependency in manifest["skills"]:
            if not set(dependency["applies_to"]) & active:
                continue
            seen_optional.add(dependency["id"])
            if not dependency["required"] and dependency["id"] not in optional:
                continue
            child = dependency["id"]
            if child not in packages:
                raise DependencyError("missing_package")
            if any(packages[child]["ref"][key] != dependency[key] for key in packages[child]["ref"]):
                raise DependencyError("dependency_pin_conflict")
            graph[current].add(child)
            previous = requested.get(child, set())
            expanded = previous | set(dependency["features"])
            if child not in requested or expanded != previous:
                requested[child] = expanded
                queue.append(child)
    if set(optional) - seen_optional:
        raise DependencyError("unknown_optional_selection")
    # Iterative topological ordering avoids Python recursion depth for long chains.
    ordered = []
    pending = {node: set(children) for node, children in graph.items()}
    while pending:
        leaves = sorted(node for node, children in pending.items() if not children)
        if not leaves:
            raise DependencyError("dependency_cycle")
        ordered.extend(leaves)
        for node in leaves:
            del pending[node]
        for children in pending.values():
            children.difference_update(leaves)
    exact_versions = {}
    for node in ordered:
        for item in requirements[node]["software"]:
            if item["required"] and item["version"]["scheme"] == "exact":
                version = item["version"]["constraint"]
                if item["id"] in exact_versions and exact_versions[item["id"]] != version:
                    raise DependencyError("exact_software_version_conflict")
                exact_versions[item["id"]] = version
    return {
        "schema_version": 1, "plan_only": True, "approval_granted": False,
        "artifact_integrity_verified": False, "target": target,
        "packages": [{
            "ref": packages[node]["ref"], "features": sorted(requested[node]),
            "manifest_sha256": manifest_digest(packages[node]["manifest"]),
            "requirements": requirements[node],
        } for node in ordered],
        "unverified": ["package_bytes", "host_support", "installed_prerequisites",
                       "nonexact_software_constraints", "credential_access", "execution_authority"],
    }
