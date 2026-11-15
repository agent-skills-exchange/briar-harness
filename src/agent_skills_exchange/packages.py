# SPDX-License-Identifier: GPL-3.0-or-later
"""Pinned, content-only GitHub package acquisition. Never executes skill code."""

from __future__ import annotations

import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .dependencies import DependencyError, _reference, read_json


_HEX = re.compile(r"^[a-f0-9]{64}$")
_RESERVED = {"con", "prn", "aux", "nul"} | {
    prefix + str(number) for prefix in ("com", "lpt") for number in range(1, 10)
}


def _relative(value):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or any(ord(character) < 32 or ord(character) == 127
                   or 0xD800 <= ord(character) <= 0xDFFF for character in value)):
        raise DependencyError("unsafe_package_path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} or part.endswith((".", " "))
           or part.split(".")[0].casefold() in _RESERVED for part in parts):
        raise DependencyError("unsafe_package_path")
    return value


def package_digest(records):
    """Content identity covers canonical relative paths, source paths and bytes."""
    canonical = json.dumps(sorted(records, key=lambda item: item["path"]),
                           sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                           allow_nan=False).encode("utf-8")
    return hashlib.sha256(b"agent-skills-exchange-package-v1\0" + canonical).hexdigest()


def _repository(source):
    try:
        parsed = urlsplit(source)
    except ValueError as exc:
        raise DependencyError("unsupported_package_source") from exc
    parts = parsed.path.strip("/").split("/")
    if (parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query
            or parsed.fragment or len(parts) != 2
            or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) or part in {".", ".."} for part in parts)):
        raise DependencyError("unsupported_package_source")
    return parts


def validate_lock(lock):
    if (not isinstance(lock, dict) or set(lock) != {"schema_version", "ref", "files"}
            or type(lock["schema_version"]) is not int or lock["schema_version"] != 1
            or not isinstance(lock["files"], list) or not lock["files"]):
        raise DependencyError("invalid_package_lock")
    ref = _reference(lock["ref"])
    _repository(ref["source"])
    if ref["path"] != ".":
        _relative(ref["path"])
    paths = set()
    folded = set()
    for record in lock["files"]:
        if (not isinstance(record, dict) or set(record) != {"path", "source_path", "size", "sha256"}
                or type(record["size"]) is not int or record["size"] < 0
                or not isinstance(record["sha256"], str) or not _HEX.fullmatch(record["sha256"])):
            raise DependencyError("invalid_package_file_record")
        path = _relative(record["path"])
        _relative(record["source_path"])
        if path in paths or path.casefold() in folded:
            raise DependencyError("duplicate_package_path")
        paths.add(path)
        folded.add(path.casefold())
    if "SKILL.md" not in paths:
        raise DependencyError("package_missing_skill")
    # A file cannot also be a directory, including case aliases on Windows/macOS.
    for path in paths:
        parts = path.split("/")
        if any("/".join(parts[:index]).casefold() in folded for index in range(1, len(parts))):
            raise DependencyError("package_path_collision")
    if package_digest(lock["files"]) != ref["package_sha256"]:
        raise DependencyError("package_lock_digest_mismatch")
    return lock


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        raise DependencyError("unexpected_package_redirect")


def _download(url, expected_size):
    request = Request(url, headers={"User-Agent": "agent-skills-exchange/0.1",
                                    "Accept-Encoding": "identity"})
    try:
        # Thirty seconds is the per-file network idle timeout, not an authority
        # lifetime. Body size is bound to the reviewed file record, not a quota.
        with build_opener(_NoRedirect()).open(request, timeout=30) as response:
            if response.status != 200:
                raise DependencyError("package_http_error")
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdecimal() or int(length) != expected_size):
                raise DependencyError("package_size_mismatch")
            return response.read(expected_size + 1)
    except (OSError, HTTPError, URLError, HTTPException) as exc:
        raise DependencyError("package_download_failed") from exc


def _root(cache, *, create):
    cache = Path(cache)
    try:
        if create:
            cache.mkdir(mode=0o700, parents=True, exist_ok=True)
        metadata = cache.lstat()
    except (OSError, ValueError) as exc:
        raise DependencyError("cache_unavailable") from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise DependencyError("unsafe_cache_root")
    if os.name == "posix" and (metadata.st_uid != os.getuid() or metadata.st_mode & 0o022):
        raise DependencyError("unsafe_cache_root")
    return cache


def _verify_content(slot, lock):
    if slot.is_symlink() or not slot.is_dir():
        raise DependencyError("unsafe_cache_slot")
    if {path.name for path in slot.iterdir()} != {"content", "lock.json"}:
        raise DependencyError("cache_entry_set_mismatch")
    receipt = slot / "lock.json"
    if receipt.is_symlink() or not receipt.is_file() or read_json(receipt) != lock:
        raise DependencyError("cache_lock_mismatch")
    tree = slot / "content"
    if tree.is_symlink() or not tree.is_dir():
        raise DependencyError("unsafe_cache_content")
    observed = set()
    observed_dirs = set()
    for directory, dirs, names in os.walk(tree, followlinks=False):
        base = Path(directory)
        for name in dirs:
            if not stat.S_ISDIR((base / name).lstat().st_mode):
                raise DependencyError("unsafe_cache_content")
            observed_dirs.add((base / name).relative_to(tree).as_posix())
        for name in names:
            path = base / name
            if not stat.S_ISREG(path.lstat().st_mode):
                raise DependencyError("unsafe_cache_content")
            observed.add(path.relative_to(tree).as_posix())
    if observed != {record["path"] for record in lock["files"]}:
        raise DependencyError("cache_file_set_mismatch")
    expected_dirs = {parent.as_posix() for record in lock["files"]
                     for parent in Path(record["path"]).parents if parent != Path(".")}
    if observed_dirs != expected_dirs:
        raise DependencyError("cache_directory_set_mismatch")
    for record in lock["files"]:
        path = tree / record["path"]
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != record["size"]:
                raise DependencyError("cache_size_mismatch")
            body = source.read(record["size"] + 1)
        if len(body) != record["size"] or hashlib.sha256(body).hexdigest() != record["sha256"]:
            raise DependencyError("cache_digest_mismatch")


def verify_cache(lock, cache):
    validate_lock(lock)
    root = _root(cache, create=False)
    slot = root / lock["ref"]["package_sha256"]
    try:
        _verify_content(slot, lock)
    except OSError as exc:
        raise DependencyError("cache_verification_failed") from exc
    return {"valid": True, "cache_hit": True, "artifact_integrity_verified": True,
            "approval_granted": False, "activated": False,
            "package_sha256": lock["ref"]["package_sha256"],
            "content": str(slot / "content"), "files": len(lock["files"])}


def fetch_package(lock, cache, *, download=None):
    validate_lock(lock)
    root = _root(cache, create=True)
    slot = root / lock["ref"]["package_sha256"]
    if slot.exists() or slot.is_symlink():
        return verify_cache(lock, root)
    download = download or _download
    owner, repository = _repository(lock["ref"]["source"])
    staging = Path(tempfile.mkdtemp(prefix=".stage-", dir=root))
    try:
        tree = staging / "content"
        tree.mkdir()
        for record in sorted(lock["files"], key=lambda item: item["path"]):
            url = "https://raw.githubusercontent.com/" + "/".join(
                quote(value, safe="") for value in (owner, repository, lock["ref"]["revision"])
            ) + "/" + quote(record["source_path"], safe="/")
            body = download(url, record["size"])
            if not isinstance(body, bytes) or len(body) != record["size"]:
                raise DependencyError("package_size_mismatch")
            if hashlib.sha256(body).hexdigest() != record["sha256"]:
                raise DependencyError("package_digest_mismatch")
            destination = tree / record["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                output.write(body)
        with (staging / "lock.json").open("x", encoding="utf-8") as output:
            json.dump(lock, output, sort_keys=True, ensure_ascii=True)
        _verify_content(staging, lock)
        try:
            staging.rename(slot)
        except OSError:
            # Another fetch may have won. Never replace an existing cache entry.
            if not slot.exists():
                raise
            verify_cache(lock, root)
        result = verify_cache(lock, root)
        result["cache_hit"] = False
        return result
    except OSError as exc:
        raise DependencyError("cache_write_failed") from exc
    finally:
        # Only this call's freshly created staging directory is ever removed.
        if staging.exists():
            shutil.rmtree(staging)
