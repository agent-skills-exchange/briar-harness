# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only single-skill drift/update planning, never live synchronisation."""

import hashlib
import os
from pathlib import Path
import stat

from .dependencies import DependencyError
from .packages import validate_lock, verify_cache


def check_deployment(lock, directory):
    """Check a selected skill tree without reading unexpected file contents.

    Extra files/directories are conflicts, not candidates for deletion. A local
    filesystem is assumed trusted against concurrent hostile namespace changes;
    this observation is not an atomic snapshot or an activation authorisation.
    """
    validate_lock(lock)
    root = Path(directory)
    if not root.is_absolute() or ".." in root.parts:
        raise DependencyError("deployment_requires_absolute_path")
    records = {item["path"]: item for item in lock["files"]}
    expected_dirs = {parent.as_posix() for name in records for parent in Path(name).parents
                     if parent != Path(".")}
    differences = []
    unknown_entries = 0
    try:
        # Do not follow an installed-directory symlink (including its ancestors).
        for parent in [root, *root.parents]:
            if not stat.S_ISDIR(parent.lstat().st_mode):
                raise DependencyError("unsafe_deployment_directory")
        pending = [root]
        found_files, found_dirs = set(), set()
        while pending:
            current = pending.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    relative = path.relative_to(root).as_posix()
                    if relative in expected_dirs:
                        if not entry.is_dir(follow_symlinks=False):
                            raise DependencyError("unsafe_deployment_entry")
                        found_dirs.add(relative)
                        pending.append(path)
                    elif relative in records:
                        if not entry.is_file(follow_symlinks=False):
                            raise DependencyError("unsafe_deployment_entry")
                        found_files.add(relative)
                    else:
                        # No descent into unrelated trees and no contents read.
                        unknown_entries += 1
        for name in sorted(records):
            if name not in found_files:
                differences.append({"path": name, "state": "missing"})
                continue
            record = records[name]
            descriptor = os.open(root / name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                                 | getattr(os, "O_NONBLOCK", 0))
            with os.fdopen(descriptor, "rb") as source:
                metadata = os.fstat(source.fileno())
                if not stat.S_ISREG(metadata.st_mode):
                    raise DependencyError("unsafe_deployment_entry")
                same_size = metadata.st_size == record["size"]
                body = source.read(record["size"] + 1) if same_size else b""
            if (not same_size or len(body) != record["size"]
                    or hashlib.sha256(body).hexdigest() != record["sha256"]):
                differences.append({"path": name, "state": "modified"})
        matches = not differences and unknown_entries == 0 and found_dirs == expected_dirs
        return {"valid": True, "matches_pinned_version": matches,
                "differences": differences, "unexpected_entries": unknown_entries,
                "writes_performed": False, "approval_granted": False, "activated": False}
    except OSError as exc:
        raise DependencyError("deployment_observation_failed") from exc


def plan_update(current_lock, target_lock, cache, directory):
    """Verify both cached versions and observe drift; never fetch or change files."""
    for lock in (current_lock, target_lock):
        validate_lock(lock)
    for field in ("id", "source", "path"):
        if current_lock["ref"][field] != target_lock["ref"][field]:
            raise DependencyError("update_skill_identity_mismatch")
    current = verify_cache(current_lock, cache)
    target = verify_cache(target_lock, cache)
    observation = check_deployment(current_lock, directory)
    old = {item["path"]: item for item in current_lock["files"]}
    new = {item["path"]: item for item in target_lock["files"]}
    changes = []
    for name in sorted(old.keys() | new.keys()):
        if name not in old:
            changes.append({"path": name, "action": "add"})
        elif name not in new:
            changes.append({"path": name, "action": "remove"})
        elif (old[name]["sha256"], old[name]["size"]) != (new[name]["sha256"], new[name]["size"]):
            changes.append({"path": name, "action": "replace"})
    result = {
        "valid": observation["matches_pinned_version"], "changes": changes, "deployment": observation,
        "current_package_sha256": current["package_sha256"],
        "target_package_sha256": target["package_sha256"],
        "rollback_package_sha256": current["package_sha256"],
        "rollback_cache_verified": True, "rollback_execution_tested": False,
        "blocked_by_drift": not observation["matches_pinned_version"],
        "admission_required": True, "apply_implemented": False,
        "writes_performed": False, "approval_granted": False, "activated": False,
    }
    if result["blocked_by_drift"]:
        result["error"] = "deployment_drift_detected"
    return result
