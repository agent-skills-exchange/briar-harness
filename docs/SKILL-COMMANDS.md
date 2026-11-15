# Skill package commands

These commands are initial package tools, not a completed installer or an
authentication service. Metadata validation, planning and cache verification
require only Python 3.12+ and the default package: no Telegram SDK, model account,
GUI, YubiKey or third-party Python runtime library. Fetching needs HTTPS access;
inspection needs an explicitly provisioned SkillSpector executable. No command
installs optional validators: `check-format` needs the separately provisioned
Python `skills-ref` reference implementation. See the
[format profile](../profiles/skill-format/README.md) for its exact source/runtime
declarations, command and demonstration-only limitations. A passing diagnostic
is not production conformance or permission to use a skill. No command
installs dependencies, activates skills or grants access. Fetching reads bytes;
inspection scans instruction bodies and source but does not run skill code.
External scanner/format tools run in separate POSIX sessions with process-group
cleanup on timeout and launcher exit; this is not containment of descendants
that deliberately detach. Host sandboxing/supervision remains separate.

From a source checkout:

```sh
PYTHONPATH=src python3 -m agent_skills_exchange --help
PYTHONPATH=src python3 -m agent_skills_exchange validate /path/to/skill/dependencies.json
```

An installed package exposes the same commands as `ase`. JSON results go to
stdout; invalid input returns exit code 2 without echoing malformed argument or
manifest values. Help is ordinary text. The commands are always non-interactive:
there is no prompt to disable and no hidden interactive fallback.

## Dependency declarations

`ase plan-update` observes one selected deployed skill and compares verified
cached versions without writes. Local drift blocks with exit2. See
[update planning](UPDATE-PLANNING.md) for arguments, preserved local content
and rollback/admission limits.

For an offline native host setup plan, use `ase onboarding-plan --host codex
--project /absolute/project --name example-skill` (also `claude` for Claude Code,
or `cursor`). It returns intended paths only: no project reads, writes, network,
admission or activation. See [host onboarding](HOST-ONBOARDING.md).

The canonical draft schema ships in the package at
`agent_skills_exchange/schemas/dependencies-v1.json`. `ase validate` checks its
structure plus unique identifiers, feature references, platform references and
overlapping software declarations. It reads only the named manifest. It does
not verify referenced files, evidence, lockfile bytes or installed prerequisites.

Software dependencies explicitly identify the applicable platform IDs. A skill
dependency's `applies_to` selects parent features; its `features` requests child
features. A dependency on a repository-root skill uses `path: "."`. Empty
dependency lists mean none declared; they are not proof that analysis is complete.

## Planning selected packages

A local catalogue is JSON with `schema_version: 1` and a `packages` list. Each
entry has exactly `ref` and `manifest`. `ref` contains `id`, HTTPS repository
`source`, immutable `revision`, package-relative `path` and `package_sha256`.
`manifest` is the companion dependency declaration, not the instruction body.

```sh
ase plan --catalog /path/to/project/skills-catalog.json \
  --skill selected-skill --feature guidance \
  --os linux --distribution ubuntu --os-version 24.04 --architecture x86_64
```

Only active required skill dependencies are included. Select an active optional
skill with `--optional its-id`; dependencies are ordered before their consumers.
Shared dependencies merge requested features. Cycles, pin conflicts, unknown
features, missing packages and conflicting exact required software versions
fail. The planner does not download the catalogue or package content.

For a single package, use `--lock PACKAGE_LOCK --manifest DEPENDENCIES` instead
of `--catalog`. This avoids maintaining a duplicate catalogue for standalone
intake. Both inputs are local metadata; the lock's structure and declared digest
are checked, but package bytes are not read or verified. This form cannot supply
missing transitive skill packages; use a catalogue when the closure needs them.
`--manifest` without `--lock`, or combining both source forms, is an error.

Platform selection currently supports exact and unconstrained (`none`) version
requirements. Other advertised platform version schemes return a specific
not-implemented error when needed, rather than being guessed. Software range
requirements remain explicit in the plan but are not yet solved or checked
against installed versions. No tool silently claims general version resolution.

Every plan says `plan_only: true`, `approval_granted: false` and
`artifact_integrity_verified: false`, and lists remaining verification. A pin in
untrusted metadata is a requested identity, not proof of the package bytes. The
reported manifest hash uses UTF-8 canonical JSON with sorted keys, ASCII escapes,
compact separators and no non-finite numbers. Package byte hashing, fetching,
cache admission and host projection are separate work, not provided by `plan`.

## Pinned acquisition and offline verification

```sh
ase fetch --lock integrations/cloudflare-security-audit/package-lock.json \
  --cache /path/to/private/cache
ase verify-cache --lock integrations/cloudflare-security-audit/package-lock.json \
  --cache /path/to/private/cache
```

A reviewed lock declares each package-relative path, exact upstream source path,
size and SHA-256, plus a repository revision and package digest. The package
digest is SHA-256 of `agent-skills-exchange-package-v1` followed by a NUL byte
and canonical JSON of file records sorted by `path`. Object keys are sorted,
ASCII escapes are enabled and separators are compact. The lock is a locally
selected identity, not an upstream signature or a trust decision.

Acquisition currently supports GitHub HTTPS sources only, using exact revision
paths on raw.githubusercontent.com. It rejects redirects and verifies every
body before publishing an inactive cache slot. No archives or remote installers
are executed. Cache hits check every file and expected directory without network
access. Corrupt caches fail rather than being silently deleted or redownloaded.
Cache roots must be caller-owned and not group/other writable on POSIX. These
checks do not provide resistance to arbitrary host compromise or concurrent
malicious mutation by the same OS account.

## Required static inspection

```sh
ase inspect --lock integrations/cloudflare-security-audit/package-lock.json \
  --cache /path/to/private/cache --reports /path/to/private/reports \
  --scanner /absolute/path/to/skillspector --timeout 60
```

SkillSpector is required for core-managed skill intake and updates, not for
unrelated metadata commands or standalone consumption outside Briar. Provision
the scanner separately; this command never installs or upgrades it. The initial
adapter supports SkillSpector 2.8.2 on POSIX only, exercised on Linux. Other
platforms and a complete pinned scanner installation profile remain work to do.

The scanner path is an operator-selected, trusted local executable. It must be
regular, executable, owned by the caller or root and not group/other writable.
Its version and launcher hash are recorded. This does not pin its interpreter,
imported libraries or rules: a launcher hash is not a complete software supply
chain identity. Do not treat this initial receipt as permission or reusable
admission evidence. The implementation always performs a fresh inspection;
trusted result caching is not implemented yet.

`--timeout` is a caller-selected process deadline in seconds; 60 above is an
example for a small static scan, not a universal policy. It bounds the direct
scanner process, not an OS-enforced process tree or network sandbox. The scanner
is trusted software, runs from a fresh home/config directory, receives no stdin
or inherited provider tokens/tracing settings, and scans an isolated copy of
verified package bytes. Bytecode-containing packages fail instead of being
cleaned into a different package. The copy and cache are checked after scanning.

No baseline is passed. Policy `ase-skillspector-static-v1` retains the existing
Briar gate: HIGH/CRITICAL findings or score above 50 fail. It also rejects failed
execution, suppression, filtered findings, missing files and missing/incomplete
static analyzers. Overall `is_complete` is not used as a shortcut: version 2.8.2
reports false when semantic/LLM analyzers are disabled. Only those four named
semantic analyzers may be disabled (the meta-analyzer may instead report no
applicable work when there are no findings); every required static analyzer
must account for all applicable work. No LLM call is requested.

Each invocation retains its raw report, stdout/stderr and JSON receipt in a new
private evidence directory. Output contains paths and summary fields, not raw
findings or logs. A blocked inspection returns exit code 2 with
`inspection_passed: false`, `activated: false` and `approval_granted: false`.
A pass still does not activate a skill, grant authority, prove the completeness
of dependencies or replace independent review and an execution sandbox.

## Development checks

The optional `skill-validation` extra contains the independent JSON Schema
validator used to check the profile. It is not a dependency of the command.
Run affected tests with:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_skill*.py'
PYTHONPATH=src python3 -m unittest discover -s tests -p test_product_packaging.py
```

No dependency installation or remote skill execution occurs during those tests.

Assisted-by: Briar
