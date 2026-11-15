# AuthZEN client boundary

The core includes an AuthZEN single-access-evaluation request builder and an
optional library client. This is not a live authority verifier, an identity
provider, or an activation implementation. No policy service is configured.
The [prerequisite profile](../profiles/authzen/README.md) separates the schema-valid
offline declaration from structured, explicitly unbound HTTPS requirements.

The protocol source is OpenID AuthZEN's `api/authorization-api-1_0.md` at
[revision a2467098d070e98032100e6574c4499cf916d844](https://github.com/openid/authzen/blob/a2467098d070e98032100e6574c4499cf916d844/api/authorization-api-1_0.md).
Our `agent`, `agent-skill`, `skill.activate` and `agent_skills_exchange` vocabulary
is an application profile, not identity or authority claims defined by AuthZEN.

## Offline request

From a checkout with Python 3.12 or newer:

```sh
PYTHONPATH=src python3 -m agent_skills_exchange authzen-request \
  --lock integrations/cloudflare-security-audit/package-lock.json \
  --worker example-worker --project example-project --task example-task \
  --phase review --requested-until 2030-01-01T00:00:00Z \
  --revocation-epoch example-epoch
```

Replace the example identifiers and future UTC expiry with the intended scope.
The request binds the skill digest, source revision/path, worker, project, task,
phase, requested expiry and claimed revocation epoch. All scope claims remain
unverified. The command does not fetch content, inspect a skill, read credentials
or contact a service. Its JSON explicitly reports that authority is not verified.

## Optional host-adapter client

`agent_skills_exchange.authzen.evaluate_activation` accepts a lock, scope,
explicit HTTPS endpoint, credential origin, bearer credential and positive
socket timeout. Only trusted operator configuration may supply the destination
and credential; never take either from remote skill instructions or manifests.
The endpoint must match the credential's HTTPS origin. Configure its evaluation
path explicitly; there is no endpoint discovery or implicit network permission.

The client needs Python's SSL backend and an operator-maintained CA trust store,
plus explicitly authorised HTTPS egress to that endpoint. It uses the standard
library only and does not install software or provision/retrieve credentials.
Offline commands do not require a working SSL backend. No operating system's
live policy-service integration has been proven by the synthetic tests.

The client makes one JSON POST, with TLS verification and no redirects,
inherited proxies, cookies, retries, interactive authentication or decision
cache. The timeout is socket inactivity, not an overall execution deadline;
the host runner must enforce a workload wall-clock deadline. A malformed reply,
non-200 status, non-boolean decision, unsupported decision context or expired
request fails closed. Unknown top-level reply fields are ignored as AuthZEN
requires. Errors do not include credentials or raw response content.

Even a valid `decision: true` result leaves `approval_granted`, `activated`,
`identity_verified`, `scope_claims_verified`, `authority_verifier_live` and
`receipt_is_authority` false. A request/response hash is diagnostic evidence,
not a signed or reusable admission ticket. There is deliberately no network
evaluation CLI or command-line credential option.

## Before activation can exist

The host still needs verified workload identity and root delegation; trustworthy
task/resource bindings; current expiry/revocation enforcement; defined PDP
policy semantics and protected configuration; and a reviewed activation path.
That path must independently enforce package provenance, dependency/platform
checks and mandatory SkillSpector inspection bound to exact package, scanner
and policy identities. A policy decision never waives those checks.

No live service, credential, admission, host onboarding or migration is proved
by this client. Synthetic transport and offline tests are author checks, not
independent security review or standards certification.

Assisted-by: Briar
