# SPDX-License-Identifier: GPL-3.0-or-later
"""Inventory a provisioned scanner environment; never install or import its code.

Run with that environment's Python using -I -B. Output is an observed CycloneDX
inventory, not an install lock, source attestation, scan result or authority.
"""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote


SOURCE = "https://github.com/NVIDIA/skillspector.git"
REVISION = "2bc641fd0639550a1cae9557491f483e30520afb"


def snapshot(records, runtime):
    components = []
    seen = set()
    for record in sorted(records, key=lambda row: row["name"].lower()):
        name = re.sub(r"[-_.]+", "-", record["name"]).lower()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or name in seen:
            raise ValueError("invalid_or_duplicate_distribution")
        seen.add(name)
        # Direct references may contain credentials or local paths. Refuse
        # them rather than exporting those values into a shareable inventory.
        requirements = record["requires_dist"]
        if any("@" in item or "://" in item for item in requirements):
            raise ValueError("direct_dependency_requires_separate_review")
        props = [
            {"name": "ase:requires-dist", "value": json.dumps(requirements)},
            {"name": "ase:requires-python", "value": record["requires_python"]},
            {"name": "ase:metadata-sha256", "value": record["metadata_sha256"]},
        ]
        component = {
            "type": "library", "bom-ref": name, "name": name,
            "version": record["version"],
            "purl": "pkg:pypi/" + name + "@" + quote(record["version"], safe=""),
            "properties": props,
        }
        if name == "skillspector":
            origin = record["origin"]
            if (record["version"] != "2.8.2" or origin.get("url") != SOURCE
                    or origin.get("vcs_info", {}).get("commit_id") != REVISION):
                raise ValueError("scanner_identity_mismatch")
            component.pop("purl")  # Git install is not a verified PyPI artifact.
            component["externalReferences"] = [{"type": "vcs", "url": SOURCE}]
            props.append({"name": "ase:installed-vcs-commit", "value": REVISION})
        elif record["origin"]:
            raise ValueError("nonregistry_dependency_requires_separate_review")
        components.append(component)
    if "skillspector" not in seen:
        raise ValueError("scanner_missing")
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "metadata": {"properties": [
            {"name": "ase:evidence-kind", "value": "observed-installed-environment"},
            {"name": "ase:runtime", "value": json.dumps(runtime, sort_keys=True)},
            {"name": "ase:dependency-graph", "value": "not-resolved; declarations retained including extras and markers"},
            {"name": "ase:installation-reproducible", "value": "false"},
            {"name": "ase:approval-granted", "value": "false"},
        ]},
        "components": components,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = []
    for dist in importlib.metadata.distributions():
        metadata = dist.read_text("METADATA")
        if metadata is None:
            raise ValueError("distribution_metadata_missing")
        records.append({
            "name": dist.metadata["Name"], "version": dist.version,
            "requires_dist": dist.requires or [],
            "requires_python": dist.metadata.get("Requires-Python", ""),
            "metadata_sha256": hashlib.sha256(metadata.encode()).hexdigest(),
            "origin": json.loads(dist.read_text("direct_url.json") or "{}"),
        })
    import platform
    result = snapshot(records, {"python": platform.python_version(),
                               "os": sys.platform, "architecture": platform.machine()})
    # Exclusive creation prevents replacing a previously reviewed snapshot.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"written": True, "components": len(result["components"]),
                      "installation_reproducible": False, "approval_granted": False}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError):
        raise SystemExit("Snapshot failed; no installation or fallback attempted.") from None
