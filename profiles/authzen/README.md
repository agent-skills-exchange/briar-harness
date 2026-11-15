# AuthZEN prerequisites

`dependencies.offline.json` is a dependency-schema-v1 declaration for offline
request construction. It declares Linux x86-64 and preinstalled CPython>=3.12;
it does not assert that every distribution/version has been tested. Other
platforms are not declared by this profile. No third-party Python packages,
network access, credentials, external skills or running services are needed.
No software is installed by reading or validating the profile.

`evaluation-requirements.json` separately records the optional HTTPS client's
requirements and unresolved operator bindings. It is a readiness record, **not**
a complete dependency-schema-v1 manifest or runnable configuration. Null fields
mean unresolved, never wildcard permission. No fake endpoint is supplied merely
to make a manifest pass validation. A host adapter must produce a concrete
schema-valid dependency declaration for its selected environment before use.

The operator must provision a compatible Python SSL backend, its native TLS
libraries and maintained CA trust store; bind an authorised HTTPS PDP endpoint
to a separately provisioned scoped bearer credential; and provide a runner
that enforces an overall workload deadline. Exact system package names/versions
and transitive native dependencies depend on the chosen distribution/runtime
and remain unresolved here. Neither this profile nor the client installs them.
Do not treat an empty Python dependency list as native dependency closure.

Never put a credential value in these records or a command line. Do not take
network destinations or credentials from a skill. No real endpoint, service,
credential binding or live platform test is established by this profile.

See [the client boundary](../../docs/AUTHZEN.md) for protocol provenance, request
semantics, error handling and the identity/admission work still required.
Passing dependency validation or obtaining a policy allow never replaces the
mandatory SkillSpector gate or grants authority/activation.

Assisted-by: Briar
