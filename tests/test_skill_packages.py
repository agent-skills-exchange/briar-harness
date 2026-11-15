# SPDX-License-Identifier: GPL-3.0-or-later
"""Pinned acquisition tests with synthetic bytes, no remote code execution."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_skills_exchange.dependencies import DependencyError
from agent_skills_exchange.packages import (
    _NoRedirect, fetch_package, package_digest, validate_lock, verify_cache,
)


BODY = b"---\nname: fixture\ndescription: Synthetic test only\n---\nDo nothing.\n"
LICENSE = b"Synthetic licence fixture, not an upstream licence.\n"


def package_lock():
    records = [
        {"path": "SKILL.md", "source_path": "skills/fixture/SKILL.md",
         "size": len(BODY), "sha256": hashlib.sha256(BODY).hexdigest()},
        {"path": "UPSTREAM-LICENSE", "source_path": "LICENSE",
         "size": len(LICENSE), "sha256": hashlib.sha256(LICENSE).hexdigest()},
    ]
    return {"schema_version": 1, "ref": {
        "id": "fixture", "source": "https://github.com/example/fixture",
        "revision": "a" * 40, "path": "skills/fixture",
        "package_sha256": package_digest(records)}, "files": records}


def fix_digest(lock):
    lock["ref"]["package_sha256"] = package_digest(lock["files"])
    return lock


def download(url, size):
    if url.endswith("/skills/fixture/SKILL.md"):
        return BODY
    if url.endswith("/LICENSE"):
        return LICENSE
    raise AssertionError("unexpected source request")


class PackageTests(unittest.TestCase):
    def assert_code(self, code, call):
        with self.assertRaises(DependencyError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_fetch_and_cache_hit_verify_bytes_without_refetch(self):
        lock = package_lock()
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache"
            result = fetch_package(lock, cache, download=download)
            self.assertTrue(result["artifact_integrity_verified"])
            self.assertFalse(result["cache_hit"])
            self.assertFalse(result["approval_granted"])
            self.assertFalse(result["activated"])
            self.assertEqual((Path(result["content"]) / "UPSTREAM-LICENSE").read_bytes(), LICENSE)
            def forbidden(*_args):
                self.fail("cached package was downloaded again")
            result = fetch_package(lock, cache, download=forbidden)
            self.assertTrue(result["cache_hit"])
            self.assertEqual(len(list(cache.iterdir())), 1)

    def test_wrong_body_hash_never_publishes_partial_cache(self):
        lock = package_lock()
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache"
            def wrong(url, size):
                return b"x" * size
            self.assert_code("package_digest_mismatch", lambda: fetch_package(lock, cache, download=wrong))
            self.assertEqual(list(cache.iterdir()), [])

    def test_oversize_body_rejected_using_reviewed_size(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache"
            self.assert_code("package_size_mismatch", lambda: fetch_package(
                package_lock(), cache, download=lambda url, size: download(url, size) + b"x"))
            self.assertEqual(list(cache.iterdir()), [])

    def test_corrupt_cache_is_rejected_without_overwrite_or_network(self):
        lock = package_lock()
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache"
            result = fetch_package(lock, cache, download=download)
            skill = Path(result["content"]) / "SKILL.md"
            corrupt = b"x" * len(BODY)
            skill.write_bytes(corrupt)
            self.assert_code("cache_digest_mismatch", lambda: fetch_package(
                lock, cache, download=lambda *_args: self.fail("network on corrupt cache")))
            self.assertEqual(skill.read_bytes(), corrupt)

    def test_cache_file_set_and_empty_directory_injection_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = package_lock()
            cache = Path(directory) / "cache"
            result = fetch_package(lock, cache, download=download)
            tree = Path(result["content"])
            injected = tree / "injected"
            injected.mkdir()
            self.assert_code("cache_directory_set_mismatch", lambda: verify_cache(lock, cache))
            injected.rmdir()
            (tree / "extra.txt").write_text("extra")
            self.assert_code("cache_file_set_mismatch", lambda: verify_cache(lock, cache))

    def test_symlink_cache_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = package_lock()
            cache = Path(directory) / "cache"
            result = fetch_package(lock, cache, download=download)
            skill = Path(result["content"]) / "SKILL.md"
            skill.unlink()
            skill.symlink_to(Path(result["content"]) / "UPSTREAM-LICENSE")
            self.assert_code("unsafe_cache_content", lambda: verify_cache(lock, cache))

    def test_symlink_root_or_slot_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            real = base / "real"
            real.mkdir(mode=0o700)
            linked = base / "linked"
            linked.symlink_to(real, target_is_directory=True)
            self.assert_code("unsafe_cache_root", lambda: fetch_package(package_lock(), linked, download=download))
            slot = real / package_lock()["ref"]["package_sha256"]
            slot.symlink_to(base, target_is_directory=True)
            self.assert_code("unsafe_cache_slot", lambda: verify_cache(package_lock(), real))

    def test_cache_receipt_is_not_trusted_as_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = package_lock()
            cache = Path(directory) / "cache"
            result = fetch_package(lock, cache, download=download)
            receipt = Path(result["content"]).parent / "lock.json"
            receipt.write_text('{"verified":true}')
            self.assert_code("cache_lock_mismatch", lambda: verify_cache(lock, cache))

    def test_traversal_windows_devices_and_case_aliases_rejected(self):
        for path in ["../outside", "/outside", "a/../../outside", "a\\b", "C:/outside", "file:stream", "NUL", "con.txt", "a/.", "a//b", "a."]:
            with self.subTest(path=path):
                lock = package_lock()
                lock["files"][1]["path"] = path
                fix_digest(lock)
                self.assert_code("unsafe_package_path", lambda: validate_lock(lock))
        lock = package_lock()
        lock["files"].append({**lock["files"][0], "path": "skill.md"})
        fix_digest(lock)
        self.assert_code("duplicate_package_path", lambda: validate_lock(lock))

    def test_file_directory_collision_rejected(self):
        lock = package_lock()
        lock["files"][1]["path"] = "SKILL.md/child"
        fix_digest(lock)
        self.assert_code("package_path_collision", lambda: validate_lock(lock))

    def test_source_and_lock_drift_rejected(self):
        lock = package_lock()
        lock["files"][0]["size"] += 1
        self.assert_code("package_lock_digest_mismatch", lambda: validate_lock(lock))
        lock = package_lock()
        lock["ref"]["source"] = "https://untrusted.example/repository"
        self.assert_code("unsupported_package_source", lambda: validate_lock(lock))
        lock = package_lock()
        lock["files"][0]["size"] = True
        self.assert_code("invalid_package_file_record", lambda: validate_lock(lock))

    def test_redirect_is_rejected_before_following(self):
        self.assert_code("unexpected_package_redirect", lambda: _NoRedirect().redirect_request(
            None, None, 302, "redirect", {}, "http://127.0.0.1/private"))

    def test_offline_verification_cannot_open_network(self):
        lock = package_lock()
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache"
            fetch_package(lock, cache, download=download)
            with patch("socket.socket", side_effect=AssertionError("network forbidden")):
                self.assertTrue(verify_cache(lock, cache)["valid"])


if __name__ == "__main__":
    unittest.main()
