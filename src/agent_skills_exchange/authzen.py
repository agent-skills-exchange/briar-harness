# SPDX-License-Identifier: GPL-3.0-or-later
"""AuthZEN single-evaluation client, not identity verification or an activation gate.

Endpoint/credential binding must come from trusted operator configuration, never
from a skill. This module neither provisions nor retrieves credentials. Results
are per-call policy evidence, not authority tokens or reusable admission tickets.
"""

from datetime import datetime, timezone
from email.message import Message
import hashlib
from http.client import HTTPException
import json
import math
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .dependencies import DependencyError, _invalid_constant, _unique_object
from .packages import validate_lock


SPEC_REVISION = "a2467098d070e98032100e6574c4499cf916d844"
_SCOPE_KEYS = {"worker", "project", "task", "phase", "requested_until", "revocation_epoch"}


def _now():
    return datetime.now(timezone.utc)


def _text(value):
    if (not isinstance(value, str) or not value.strip()
            or any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise DependencyError("invalid_policy_identifier")
    return value


def _expiry(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value):
        raise DependencyError("invalid_requested_expiry")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DependencyError("invalid_requested_expiry") from exc
    if instant <= _now():
        raise DependencyError("requested_scope_expired")
    return value


def activation_request(lock, scope):
    """Construct a single evaluation request from metadata and unverified claims.

    The namespace's phase, lifetime and epoch meanings are our application
    profile, not AuthZEN-defined claims or evidence those claims are true.
    """
    validate_lock(lock)
    if not isinstance(scope, dict) or set(scope) != _SCOPE_KEYS:
        raise DependencyError("invalid_policy_scope")
    for value in scope.values():
        _text(value)
    _expiry(scope["requested_until"])
    ref = lock["ref"]
    return {
        "subject": {"type": "agent", "id": scope["worker"]},
        "action": {"name": "skill.activate"},
        "resource": {
            "type": "agent-skill", "id": "sha256:" + ref["package_sha256"],
            "properties": {"source": ref["source"], "revision": ref["revision"], "path": ref["path"]},
        },
        "context": {"agent_skills_exchange": {
            "project": scope["project"], "task": scope["task"], "phase": scope["phase"],
            "requested_until": scope["requested_until"],
            "requested_revocation_epoch": scope["revocation_epoch"],
        }},
    }


def _endpoint(value, *, origin_only=False):
    if (not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value)
            or "\\" in value):
        raise DependencyError("invalid_pdp_endpoint")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise DependencyError("invalid_pdp_endpoint") from exc
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment or port == 0
            or (origin_only and parsed.path not in {"", "/"})):
        raise DependencyError("invalid_pdp_endpoint")
    return (parsed.scheme, parsed.hostname.lower(), 443 if port is None else port)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DependencyError("pdp_redirect_refused")


def _post(endpoint, body, credential, timeout):
    # No inherited proxy, cookies, metadata discovery, retry or interactive auth.
    try:
        import ssl
        from urllib.request import HTTPSHandler
    except ImportError as exc:
        raise DependencyError("pdp_tls_unavailable") from exc
    context = ssl.create_default_context()
    opener = build_opener(ProxyHandler({}), _NoRedirect(), HTTPSHandler(context=context))
    request = Request(endpoint, data=body, method="POST", headers={
        "Authorization": "Bearer " + credential,
        "Content-Type": "application/json", "Accept": "application/json",
    })
    with opener.open(request, timeout=timeout) as response:
        if response.geturl() != endpoint:
            raise DependencyError("pdp_endpoint_changed")
        types = response.headers.get_all("Content-Type", [])
        if len(types) != 1:
            raise DependencyError("invalid_pdp_content_type")
        return response.status, types[0], response.read()


def _ijson(value):
    # AuthZEN recommends I-JSON: unique keys, valid Unicode, interoperable numbers.
    if isinstance(value, str):
        if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise DependencyError("invalid_pdp_json")
    elif type(value) is int and abs(value) > (2 ** 53 - 1):
        raise DependencyError("invalid_pdp_json")
    elif type(value) is float and not math.isfinite(value):
        raise DependencyError("invalid_pdp_json")
    elif isinstance(value, list):
        for item in value:
            _ijson(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            _ijson(key)
            _ijson(item)


def _decision(content_type, body):
    headers = Message()
    headers["Content-Type"] = content_type
    if (headers.get_content_type() != "application/json"
            or headers.get_content_charset() not in {None, "utf-8"}):
        raise DependencyError("invalid_pdp_content_type")
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=_invalid_constant)
        _ijson(value)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise DependencyError("invalid_pdp_json") from exc
    if not isinstance(value, dict) or type(value.get("decision")) is not bool:
        raise DependencyError("invalid_pdp_decision")
    if "context" in value:
        if not isinstance(value["context"], dict):
            raise DependencyError("invalid_pdp_decision")
        if value["context"]:
            # AuthZEN permits rejecting conditions the PEP cannot understand.
            # Never turn obligations or step-up advice into an implicit prompt.
            raise DependencyError("unsupported_pdp_context")
    # Unknown top-level fields are ignored as required by AuthZEN 1.0.
    return value["decision"]


def evaluate_activation(lock, scope, *, endpoint, credential_origin, credential,
                        socket_timeout, transport=None):
    """Query an explicitly bound PDP once. Never activate or cache a decision.

    Identity/claim truth and root delegation are not verified here. The caller
    must enforce a workload wall deadline; urllib's timeout is socket inactivity,
    not a total request deadline. No real PDP is configured by this package.
    """
    request = activation_request(lock, scope)
    if _endpoint(endpoint) != _endpoint(credential_origin, origin_only=True):
        raise DependencyError("pdp_credential_origin_mismatch")
    if (not isinstance(credential, str)
            or not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", credential)):
        raise DependencyError("invalid_pdp_credential")
    if type(socket_timeout) not in {int, float} or not math.isfinite(socket_timeout) or socket_timeout <= 0:
        raise DependencyError("invalid_pdp_timeout")
    body = json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    result = {
        "valid": False, "decision": False, "approval_granted": False,
        "activated": False, "identity_verified": False, "scope_claims_verified": False,
        "authority_verifier_live": False, "receipt_is_authority": False,
        "request_sha256": hashlib.sha256(body).hexdigest(),
    }
    try:
        status, content_type, reply = (transport or _post)(endpoint, body, credential, socket_timeout)
        if type(status) is not int or status != 200:
            raise DependencyError("pdp_http_error")
        decision = _decision(content_type, reply)
        _expiry(request["context"]["agent_skills_exchange"]["requested_until"])
        result.update(valid=True, decision=decision, response_sha256=hashlib.sha256(reply).hexdigest())
    except HTTPError as exc:
        exc.close()
        result["error"] = "pdp_authentication_failed" if exc.code in {401, 403} else "pdp_http_error"
    except (DependencyError, OSError, URLError, HTTPException, ValueError,
            TypeError, AttributeError, RecursionError) as exc:
        result["error"] = exc.code if isinstance(exc, DependencyError) else "pdp_unavailable"
    return result
