# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional reference-format diagnostics; never security inspection or admission."""

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time

from .dependencies import DependencyError
from .packages import _relative, _root, _verify_content, verify_cache
from .processes import run_tool


REFERENCE_VERSION = "0.1.0"
REFERENCE_REVISION = "f130f348f502d9804278a617f86929846896d2e9"


def check_format(lock, cache, reports, validator, name, *, timeout):
    """Run separately provisioned skills-ref in an isolated scratch directory.

    The validator is trusted local software, not OS-sandboxed here. Its upstream
    reference implementation is demonstration-only. Launcher integrity/version
    checks do not attest its interpreter/libraries or upstream source revision.
    """
    if type(timeout) not in {int, float} or not math.isfinite(timeout) or timeout <= 0:
        raise DependencyError("invalid_format_timeout")
    _relative(name)
    if "/" in name or name == "lock.json":
        raise DependencyError("invalid_skill_directory_name")
    verified = verify_cache(lock, cache)
    try:
        validator = Path(validator)
        if not validator.is_absolute():
            raise DependencyError("validator_requires_absolute_path")
        validator = validator.resolve(strict=True)
        metadata = validator.stat()
        if not stat.S_ISREG(metadata.st_mode) or not os.access(validator, os.X_OK):
            raise DependencyError("validator_unavailable")
        if os.name != "posix":
            raise DependencyError("format_platform_not_supported")
        if metadata.st_uid not in {0, os.getuid()} or metadata.st_mode & 0o022:
            raise DependencyError("unsafe_validator_executable")
        executable_hash = hashlib.sha256(validator.read_bytes()).hexdigest()
        root = _root(reports, create=True).resolve()
        evidence = Path(tempfile.mkdtemp(prefix="format-", dir=root))
        result = {
            "valid": False, "reference_format_passed": False,
            "activated": False, "approval_granted": False,
            "standard_conformance_proven": False, "reference_source_verified": False,
            "reference_implementation_demonstration_only": True,
            "expected_reference_version": REFERENCE_VERSION,
            "documented_reference_revision": REFERENCE_REVISION,
            "validator_executable_sha256": executable_hash,
            "package_sha256": lock["ref"]["package_sha256"],
            "skill_directory_name": name, "evidence": str(evidence),
            "receipt_is_authority": False,
        }
        with tempfile.TemporaryDirectory(prefix="ase-format-") as directory:
            scratch = Path(directory)
            home = scratch / "home"
            home.mkdir()
            environment = {"PATH": os.defpath, "HOME": str(home),
                           "XDG_CONFIG_HOME": str(home), "LANG": "C.UTF-8",
                           "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
            slot = scratch / "package"
            slot.mkdir()
            content = slot / "content"
            shutil.copytree(verified["content"], content, symlinks=True)
            (slot / "lock.json").write_text(json.dumps(lock), encoding="utf-8")
            _verify_content(slot, lock)
            started = time.monotonic()

            def run(arguments, label):
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(arguments, timeout)
                with (evidence / (label + ".stdout")).open("xb") as out, \
                        (evidence / (label + ".stderr")).open("xb") as err:
                    return run_tool([str(validator), *arguments], cwd=home,
                                          env=environment, stdin=subprocess.DEVNULL,
                                          stdout=out, stderr=err, timeout=remaining,
                                          check=False).returncode

            try:
                code = run(["--version"], "version")
                if (code != 0 or (evidence / "version.stdout").read_text().strip()
                        != "skills-ref, version " + REFERENCE_VERSION):
                    raise DependencyError("format_version_mismatch")
                target = slot / name
                if target != content:
                    content.rename(target)
                code = run(["validate", str(target)], "validate")
                if target != content:
                    if os.path.lexists(content):
                        raise DependencyError("format_copy_changed")
                    target.rename(content)
                _verify_content(slot, lock)
                verify_cache(lock, cache)
                if hashlib.sha256(validator.read_bytes()).hexdigest() != executable_hash:
                    raise DependencyError("validator_changed_during_check")
                if code == 1:
                    result["error"] = "reference_format_findings"
                elif code != 0:
                    raise DependencyError("format_execution_failed")
                elif ((evidence / "validate.stdout").read_text()
                      != f"Valid skill: {target}\n"
                      or (evidence / "validate.stderr").stat().st_size != 0):
                    raise DependencyError("format_result_unrecognised")
                else:
                    result.update(valid=True, reference_format_passed=True)
            except subprocess.TimeoutExpired:
                result["error"] = "format_timeout"
            except (DependencyError, OSError, UnicodeError) as exc:
                result["error"] = getattr(exc, "code", "format_execution_failed")
        (evidence / "receipt.json").write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
        return result
    except (OSError, ValueError) as exc:
        if isinstance(exc, DependencyError):
            raise
        raise DependencyError("validator_unavailable") from exc
