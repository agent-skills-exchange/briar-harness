# Checking saved inspection evidence

`ase verify-inspection` and the library function
`agent_skills_exchange.inspection.verify_inspection_evidence` provide an offline
consistency check, not an admission API. They require a package lock, cache,
receipt bytes, report bytes, expected receipt SHA-256 and expected scanner
executable SHA-256. It uses the standard library and performs no network request,
scanner execution, installation or activation.

```sh
ase verify-inspection --lock skill.lock.json --cache ./cache \
  --receipt inspection/receipt.json --report inspection/report.json \
  --expected-receipt-sha256 "$TRUSTED_RECEIPT_SHA256" \
  --expected-scanner-sha256 "$TRUSTED_SCANNER_SHA256"
```

Supply both expected identities from protected operator state. This command
does not discover trusted identities or validate their custody. It prints one
JSON result, returns 0 for consistent passing evidence and 2 for a failed check
or unreadable evidence. It reads each evidence file once; unreadable-file errors
do not echo the path. `briar-harness verify-inspection` is the same command.

Expected hashes must come from independently protected caller state, not be
calculated from whatever receipt a skill supplies and then trusted. The function
cannot verify that protected origin. Its success explicitly leaves
`expected_identity_origin_verified`, `scanner_runtime_verified`,
`receipt_is_authority`, `approval_granted` and `activated` false.

The check verifies the current cached package bytes against the pinned lock,
the exact receipt hash, report hash, package digest, scanner executable digest
and current static-policy identity. It parses and reassesses the report rather
than accepting a saved pass flag. Coverage gaps, blocking findings, altered
assessment fields, mismatched policy/scanner/package, errors or authority flags
deny success. Parsing and hashing use the same supplied bytes; the function
does not reopen evidence files after hashing. It neither modifies evidence nor
generates a baseline or suppression.

This detects inconsistency, not a malicious party who controls the receipt,
report and expected hashes together. A matching executable hash does not bind
its interpreter, imported packages, native libraries or scanner configuration.
Report metadata does not attest scanner execution. Trusted receipt custody,
complete runtime binding, independent review and current authority/revocation
checks are still required before a future activation path can reuse evidence.
Neither the CLI nor any current activation path treats this result as an
admission ticket. No activation command exists.

Scanner and optional format-validator subprocesses run in separate POSIX
sessions. Their process groups are killed on timeout or exceptional exit, and
ordinary descendants left after a successful launcher exit are also cleaned up.
This is not OS sandboxing: a descendant that deliberately changes session/group
can escape it, and termination/reaping can be delayed by the operating system.
An external supervisor is still needed for hostile-process containment and hard
workload deadlines. No network or filesystem isolation is implied by cleanup.

Synthetic tests cover consistent evidence and altered receipt, report, cached
content, package/scanner/policy identities, verdict fields and blocking findings.
They do not prove real scanner runtime identity or independent approval of
Cloudflare's findings. Cloudflare remains blocked; no failed scan was cleared.

Assisted-by: Briar
