# SPDX-License-Identifier: GPL-3.0-or-later
"""Protocol/transport fixtures only; no live PDP, tokens, identity or authority."""

from contextlib import redirect_stdout
from datetime import datetime, timezone
from email.message import Message
import io
import json
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler

from agent_skills_exchange import authzen
from agent_skills_exchange.cli import main
from agent_skills_exchange.dependencies import DependencyError
from test_skill_packages import package_lock


ENDPOINT = "https://pdp.example.test/access/v1/evaluation"
ORIGIN = "https://pdp.example.test"
SCOPE = {"worker": "test-agent", "project": "test-project", "task": "test-task",
         "phase": "test-phase", "requested_until": "2099-01-01T00:00:00Z",
         "revocation_epoch": "test-epoch"}


class AuthzenTests(unittest.TestCase):
    def evaluate(self, reply=b'{"decision":true}', *, status=200,
                 content_type="application/json", **kwargs):
        transport = MagicMock(return_value=(status, content_type, reply))
        result = authzen.evaluate_activation(
            package_lock(), SCOPE, endpoint=ENDPOINT, credential_origin=ORIGIN,
            credential="synthetic-token", socket_timeout=5, transport=transport, **kwargs)
        self.assertEqual(transport.call_count, 1)
        for field in ["approval_granted", "activated", "identity_verified", "scope_claims_verified",
                      "authority_verifier_live", "receipt_is_authority"]:
            self.assertFalse(result[field])
        self.assertNotIn("synthetic-token", json.dumps(result))
        return result, transport

    def test_request_has_standard_entities_and_custom_scope_without_instruction_content(self):
        request = authzen.activation_request(package_lock(), SCOPE)
        self.assertEqual(set(request), {"subject", "action", "resource", "context"})
        self.assertEqual(request["subject"], {"type": "agent", "id": SCOPE["worker"]})
        self.assertEqual(request["action"], {"name": "skill.activate"})
        self.assertEqual(request["resource"]["id"], "sha256:" + package_lock()["ref"]["package_sha256"])
        self.assertEqual(request["context"]["agent_skills_exchange"]["requested_revocation_epoch"],
                         SCOPE["revocation_epoch"])
        self.assertNotIn("Do nothing", json.dumps(request))
        self.assertNotIn("files", request["resource"]["properties"])

    def test_every_scope_binding_changes_the_request(self):
        original = authzen.activation_request(package_lock(), SCOPE)
        for field in SCOPE:
            changed = dict(SCOPE)
            changed[field] = "2099-02-01T00:00:00Z" if field == "requested_until" else "different"
            with self.subTest(field=field):
                self.assertNotEqual(authzen.activation_request(package_lock(), changed), original)

    def test_invalid_scopes_expiry_and_identifiers_fail(self):
        for field in SCOPE:
            scope = dict(SCOPE)
            del scope[field]
            with self.subTest(missing=field), self.assertRaises(DependencyError):
                authzen.activation_request(package_lock(), scope)
        for field, value in [("worker", ""), ("project", "a\nb"), ("task", True),
                             ("phase", "\ud800"), ("requested_until", "2000-01-01T00:00:00Z"),
                             ("requested_until", "2099-02-31T00:00:00Z"),
                             ("requested_until", "2099-01-01T00:00:00+00:00")]:
            scope = dict(SCOPE, **{field: value})
            with self.subTest(field=field), self.assertRaises(DependencyError):
                authzen.activation_request(package_lock(), scope)

    def test_true_and_false_are_policy_evidence_only(self):
        for decision in [True, False]:
            result, transport = self.evaluate(json.dumps({"decision": decision}).encode())
            self.assertTrue(result["valid"])
            self.assertEqual(result["decision"], decision)
            endpoint, body, credential, timeout = transport.call_args.args
            self.assertEqual(endpoint, ENDPOINT)
            self.assertEqual(json.loads(body), authzen.activation_request(package_lock(), SCOPE))

    def test_unknown_top_level_fields_are_ignored_per_authzen(self):
        result, _ = self.evaluate(b'{"decision":true,"future":{"value":"not propagated"}}')
        self.assertTrue(result["valid"])
        self.assertNotIn("not propagated", json.dumps(result))

    def test_unsupported_context_never_triggers_step_up_or_grants(self):
        result, _ = self.evaluate(b'{"decision":true,"context":{"step_up":"untrusted advice"}}')
        self.assertFalse(result["valid"])
        self.assertFalse(result["decision"])
        self.assertEqual(result["error"], "unsupported_pdp_context")
        self.assertNotIn("untrusted advice", json.dumps(result))

    def test_malformed_ambiguous_and_non_ijson_responses_deny(self):
        for reply in [b'[]', b'{"decision":1}', b'{"decision":"true"}', b'{}', b'not-json',
                      b'{"decision":true,"context":null}',
                      b'{"decision":false,"decision":true}',
                      b'{"decision":true,"context":{"x":NaN}}',
                      b'{"decision":true,"future":"\\ud800"}',
                      b'{"decision":true,"future":9007199254740992}',
                      b'{"decision":true,"future":1e1000}', b'\xff']:
            with self.subTest(reply=reply):
                result, _ = self.evaluate(reply)
                self.assertFalse(result["valid"])
                self.assertFalse(result["decision"])

    def test_content_type_status_and_empty_context(self):
        for content_type in ["text/html", "application/json; charset=latin-1"]:
            result, _ = self.evaluate(content_type=content_type)
            self.assertEqual(result["error"], "invalid_pdp_content_type")
        result, _ = self.evaluate(status=201)
        self.assertEqual(result["error"], "pdp_http_error")
        result, _ = self.evaluate(b'{"decision":true,"context":{}}',
                                  content_type="application/json; charset=UTF-8")
        self.assertTrue(result["valid"])

    def test_endpoint_and_credential_binding_fail_before_network(self):
        for endpoint, origin in [("http://pdp.example.test/evaluation", ORIGIN),
                                 (ENDPOINT, "https://other.example.test"),
                                 ("https://user:secret@pdp.example.test/evaluation", ORIGIN),
                                 (ENDPOINT + "?token=private", ORIGIN),
                                 (ENDPOINT + "#fragment", ORIGIN),
                                 ("https://pdp.example.test:0/evaluation", ORIGIN)]:
            transport = MagicMock()
            with self.subTest(endpoint=endpoint), self.assertRaises(DependencyError):
                authzen.evaluate_activation(package_lock(), SCOPE, endpoint=endpoint,
                    credential_origin=origin, credential="synthetic", socket_timeout=5, transport=transport)
            transport.assert_not_called()

    def test_invalid_bearer_or_timeout_never_reaches_transport(self):
        for token, timeout in [("x\r\nInjected: yes", 5), ("", 5),
                               ("synthetic", True), ("synthetic", 0),
                               ("synthetic", float("inf"))]:
            transport = MagicMock()
            with self.subTest(timeout=timeout), self.assertRaises(DependencyError):
                authzen.evaluate_activation(package_lock(), SCOPE, endpoint=ENDPOINT,
                    credential_origin=ORIGIN, credential=token, socket_timeout=timeout, transport=transport)
            transport.assert_not_called()

    def test_expired_response_cannot_extend_scope_by_mutating_input(self):
        scope = dict(SCOPE, requested_until="2026-01-01T00:00:01Z")
        def transport(*args):
            scope["requested_until"] = SCOPE["requested_until"]
            return 200, "application/json", b'{"decision":true}'
        with patch.object(authzen, "_now", side_effect=[
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 0, 0, 2, tzinfo=timezone.utc)]):
            result = authzen.evaluate_activation(package_lock(), scope, endpoint=ENDPOINT,
                credential_origin=ORIGIN, credential="synthetic", socket_timeout=5, transport=transport)
        self.assertFalse(result["decision"])
        self.assertEqual(result["error"], "requested_scope_expired")

    def test_failures_are_value_free_and_not_retried(self):
        for failure, error in [(TimeoutError("synthetic-secret"), "pdp_unavailable"),
                               (DependencyError("pdp_redirect_refused"), "pdp_redirect_refused")]:
            transport = MagicMock(side_effect=failure)
            result = authzen.evaluate_activation(package_lock(), SCOPE, endpoint=ENDPOINT,
                credential_origin=ORIGIN, credential="synthetic-token", socket_timeout=5, transport=transport)
            self.assertEqual(result["error"], error)
            self.assertNotIn("synthetic-secret", json.dumps(result))
            self.assertEqual(transport.call_count, 1)

    def test_authentication_failure_closes_response_without_forwarding_body(self):
        body = io.BytesIO(b"synthetic-private-diagnostic")
        transport = MagicMock(side_effect=HTTPError(ENDPOINT, 401, "private", {}, body))
        result = authzen.evaluate_activation(package_lock(), SCOPE, endpoint=ENDPOINT,
            credential_origin=ORIGIN, credential="synthetic", socket_timeout=5, transport=transport)
        self.assertEqual(result["error"], "pdp_authentication_failed")
        self.assertTrue(body.closed)
        self.assertNotIn("private", json.dumps(result))

    def test_default_transport_uses_tls_no_proxy_and_one_post(self):
        response = MagicMock()
        response.geturl.return_value = ENDPOINT
        response.status = 200
        response.headers = Message()
        response.headers["Content-Type"] = "application/json"
        response.read.return_value = b'{"decision":false}'
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value = response
        with patch.object(authzen, "build_opener", return_value=opener) as build:
            value = authzen._post(ENDPOINT, b'{}', "synthetic", 5)
        self.assertEqual(value[0], 200)
        self.assertEqual(opener.open.call_count, 1)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        handlers = build.call_args.args
        self.assertEqual(next(h for h in handlers if isinstance(h, ProxyHandler)).proxies, {})
        context = next(h for h in handlers if isinstance(h, HTTPSHandler))._context
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        with self.assertRaises(DependencyError):
            next(h for h in handlers if isinstance(h, authzen._NoRedirect)).redirect_request(
                request, None, 302, "redirect", {}, "https://elsewhere.example.test")

    def test_offline_cli_builds_only_metadata_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / "lock.json"
            lock.write_text(json.dumps(package_lock()))
            args = ["authzen-request", "--lock", str(lock)]
            for name, value in SCOPE.items():
                args.extend(["--" + name.replace("_", "-"), value])
            stdout = io.StringIO()
            with patch.object(authzen, "_post") as post, redirect_stdout(stdout):
                status = main(args)
            self.assertEqual(status, 0)
            result = json.loads(stdout.getvalue())
            self.assertFalse(result["approval_granted"])
            self.assertFalse(result["authority_verifier_live"])
            self.assertEqual(result["request"], authzen.activation_request(package_lock(), SCOPE))
            post.assert_not_called()

    def test_offline_import_does_not_require_optional_tls_backend(self):
        source = str(Path(__file__).resolve().parents[1] / "src")
        code = '''
import builtins, sys
original = builtins.__import__
def without_ssl(name, *args, **kwargs):
    if name == "ssl":
        raise ImportError("synthetic missing SSL backend")
    return original(name, *args, **kwargs)
builtins.__import__ = without_ssl
sys.path.insert(0, SOURCE)
import agent_skills_exchange.cli
from agent_skills_exchange.authzen import _post
from agent_skills_exchange.dependencies import DependencyError
try:
    _post("https://pdp.example.test", b"{}", "synthetic", 1)
except DependencyError as exc:
    assert exc.code == "pdp_tls_unavailable"
else:
    raise AssertionError("TLS unavailable must deny")
'''.replace("SOURCE", repr(source))
        process = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code],
                                 stdin=subprocess.DEVNULL, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == "__main__":
    unittest.main()
