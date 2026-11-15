# Cloudflare security-audit intake

Upstream: <https://github.com/cloudflare/security-audit-skill>.
Skill: `skills/security-audit` at commit
`c1c8a8c1471069fb0e188eeaff69b8e8db6564a8`.

The adjacent package lock selects 21 files, 315748 bytes, including the root MIT
licence as `UPSTREAM-LICENSE`. The original upstream licence is preserved; GPL
terms for our integration work do not relicense Cloudflare's work. Upstream
instructions are unchanged. Package digest:
`36af2ef2ddabeca0bb9c033f0a4a01703f561556bb556e6dbe8f6b3f8d961cb2`.

## Current result

Fetched and verified locally; **not activated**. Static SkillSpector 2.8.2
inspection reports 12 findings, score 76, HIGH, without suppressions. The core
adapter reproduces that blocking verdict and verifies static file coverage.
The gate remains closed; contextual triage below is not an approved exception
or a suppression baseline.

| Source | Finding context | Initial assessment |
| --- | --- | --- |
| `SKILL.md:14` | “Do not automatically run” the full audit | Negated instruction, not an automatic-execution request |
| `DESKTOP-MOBILE-AND-LOCAL-IPC.md:44` | IPC accepting peers “without checking” credentials | Describes a vulnerability to investigate |
| `UPSTREAM-LICENSE:16` | MIT warranty text “NOT LIMITED TO” | Licence wording, not a permission request |
| `AI-AND-LLM.md:29` | Review who can create, update and “delete memory” | Threat-model checklist, not an instruction to delete memory |
| `ATTACK-CLASSES.md:114` | Skipped permission checks | Vulnerability checklist |
| `ATTACK-CLASSES.md:118` | Checked-in `credentials.json` | Secret-exposure checklist, not credential harvesting |
| `DESKTOP-MOBILE-AND-LOCAL-IPC.md:15,67` | Keychain ACLs and lower-trust readers | Credential-boundary assessment guidance |
| `validate-coverage-ledger.test.cjs:495` | `/etc/passwd` input | Unsafe-path rejection fixture |
| `validate-findings.test.cjs:320,606` | `/etc/passwd` input | Unsafe-path rejection fixtures |
| `DESKTOP-MOBILE-AND-LOCAL-IPC.md:53` | World-writable IPC endpoints | Vulnerability checklist |

These local observations explain likely context-insensitive pattern matches;
they are not a complete source review or a claim the skill is safe. Do not
generate a baseline merely to make it pass. Any future reviewed exception
mechanism must bind exact findings, package bytes, scanner and policy and remain
separate from permission to execute.

## Remaining integration work

Upstream has not declared our structured dependency extension. Our guidance
profile below is a separate, attributed declaration, not a modification of
upstream or a claim of conformance it has not declared. A complete full-audit
profile remains to be built. Guidance and full-audit modes have
different needs. Ordinary questions must not silently start the full workflow,
delegate a complete audit or create report files.

`full-audit-prerequisites.json` records source-bound full-audit requirements and
unresolved choices as structured data. It is deliberately not an installable
dependency manifest: no execution platform, Node version, target toolchain,
sandbox or artifact-promotion implementation is yet verified. Unknown versions,
resource limits and target inventories remain null, not invented defaults.
The requirements come from the pinned upstream, not a new Briar service
dependency. The core must not treat the record as an available profile or an
admission ticket. Target-specific tools and transitive locks must be resolved
before a complete full-audit dependency declaration can be offered. Source-only
inspection does not permit target execution, and static scanner process-group
cleanup does not provide the sandbox or race-safe evidence retention required
here. The existing guidance-only manifest remains unchanged.

`dependencies.guidance.json` is our attributed companion declaration for a
strict instruction-only subset: reading selected methodology and checklists.
It does not enable delegation, target execution, report generation or the full
audit. For this subset there are no tool/runtime, Briar, skill, service, network
or credential dependencies and no software lockfile is needed. Reading text
does not depend on a particular OS/architecture or a host-specific API. Platform
support is declared, not tested Claude/Cursor/Codex integration. An agent host's
own inference credentials are provisioned by that host, not requested by this
skill. Fetching and inspecting the package are separate core operations with
their own dependencies; the empty arrays do not waive those gates.

Plan it without creating a catalogue or reading the upstream instruction body:

```sh
ase plan --lock integrations/cloudflare-security-audit/package-lock.json \
  --manifest integrations/cloudflare-security-audit/dependencies.guidance.json \
  --skill cloudflare-security-audit --feature guidance \
  --os linux --distribution ubuntu --os-version 24.04 --architecture x86_64
```

The planner rejects `--feature full-audit`; it is deliberately not declared
until its prerequisites and sandbox capabilities can be represented completely.
This does not reduce the integration's intended final scope. The complete pinned
upstream package stays intact and blocked by inspection, even when planning the
instruction-only subset. Successful planning is not skill activation or proof
of host compatibility. No source files are hidden from inspection.

Full audit requires host delegation capabilities, Node-based validators and
an OS-enforced validation sandbox. Establish actual runtime versions and
platform evidence before declaring support. Target execution requires no
network, an empty/allowlisted environment, scratch-only writes, read-only target
and tools, and bounded resources/time. Do not disable host protections to obtain
a test result. Without the required sandbox, executable validation remains
`needs_validation`.

Standalone guidance use, full dependency completeness, upstream format checks,
independent review and Claude/Cursor/Codex behaviour evidence are not yet proven.

Assisted-by: Briar
