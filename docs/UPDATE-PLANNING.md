# Read-only update and drift planning

Use `plan-update` for one explicitly selected, already deployed skill directory:

```sh
ase plan-update --current-lock /absolute/current-lock.json \
  --target-lock /absolute/target-lock.json --cache /absolute/inactive-cache \
  --directory /absolute/project/.agents/skills/example-skill
```

This observes the named directory; it does not discover a deployment, fetch
packages, install dependencies, write files, execute skill code or activate
anything. The default core Python runtime is sufficient; no additional packages,
services, credentials or network are required. Paths use the running operating
system's syntax. The deployed directory must be absolute and not symlinked,
including its ancestors. No real host platform integration is proved here.

Both pinned versions must already be available in the verified inactive cache.
The same skill ID, source and package path are required: silently changing
upstream or substituting a different skill is not an update. Cache verification
requires the exact recorded locks; this command does not rewrite a cache record
to alias a different source revision with identical content.

The plan lists added, replaced and removed package paths, verifies retained
current-version bytes as the rollback source, and checks deployed content against
the current lock. Missing or modified expected files and unexpected entries block
the plan with exit2 and `deployment_drift_detected`. A consistent plan returns
exit0 but still has no permission or apply capability. Missing/unsafe directories,
symlinks, corrupted caches or mismatched identities also fail with structured
errors. An unchanged target produces no content changes.

Unexpected files and directories are counted, not reported by name, read for
content, traversed or deleted. This preserves local configuration and prevents a
secret-containing extra directory from becoming an accidental read target.
Expected package files are read only to their pinned size plus one byte after
regular-file checks. Treat local edits and extras as conflicts for explicit
reconciliation, not permission to reset or overwrite the directory.

This is a bounded observation, not a filesystem lock or atomic snapshot against
a hostile concurrent writer. The future write path must recheck drift and live
admission at its transaction boundary. Mandatory exact-byte SkillSpector
inspection, dependency/platform checks, verified authority and current revocation
are not evaluated by this planner. No result is an admission ticket.

`rollback_cache_verified` means previous bytes remain available and verified;
`rollback_execution_tested` remains false. Actual atomic installation, rollback,
host invocation and interrupted-update recovery are not implemented/proved.
Do not point a future installer at the whole live harness or copy local secrets
and deployment history into this public core. Live migration and cursor-skills
retirement require separate approval and representative acceptance evidence.

Assisted-by: Briar
