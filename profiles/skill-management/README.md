# Skill-management prerequisites (draft)

This optional profile describes a separately provisioned static scanner. It is
not a skill, a Briar runtime extra, an installer or an activation mechanism.
Ordinary metadata/planning/cache commands do not need this environment.

`dependencies.json` uses the same dependency schema as skill companion
manifests. Its scope is **already-provisioned runtime operation**, not setup:
Linux x86-64, scanner CPython 3.13.9 and SkillSpector 2.8.2 at upstream commit
`2bc641fd0639550a1cae9557491f483e30520afb`. This captures the environment used,
not the scanner's entire supported Python/platform range. The platform entry is
declared, not a claim of clean-host installation or every-distribution testing.

The inventory `environment.cdx.json` records 101 installed distributions with
exact versions, their `Requires-Dist` declarations (including extras and markers)
and SHA-256 of their UTF-8 distribution metadata. It is an observed CycloneDX
1.5 inventory, **not a reproducible install lock**. Metadata hashes are not wheel
hashes. Root Git provenance is recorded from installed metadata, not independently
attested. The dependency graph, native OS-library prerequisites and installation
artifact/build closure remain unresolved; `readiness.json` exposes these gaps.
Do not infer that all installed packages are required by a static scan.

## Inspection and setup boundary

Once the scanner is separately provisioned and trusted, `ase inspect` checks its
version and executable permissions, scans an isolated copy without LLM calls or
baseline suppressions, and retains its evidence. The executable must be owned
by the operator or root and not group/other writable. A launcher hash alone does
not pin its Python interpreter or libraries. This profile does not change that
adapter into an OS sandbox or bind its entire environment to an admission token.
No activation command or trusted scan-result reuse exists yet.

The runtime profile needs no provider credential, MCP server, Briar service or
declared network access. The existing adapter removes inherited credentials and
tracing settings but does not enforce network isolation at OS level. Package
provisioning would need separately declared network/build/artifact requirements;
the empty runtime network list is not permission for installer access.

An offline no-build lock attempt lacked cached dependencies. An online no-build
attempt also failed on upstream LangGraph in-memory server dependencies and
wheel availability across the requested Python range. No upstream build script
was enabled to get past that failure, and no scanner was installed or upgraded.
There is deliberately no advertised unattended installation command until its
complete dependency/build profile has been reviewed and proven. The scanner's
upstream Python declaration is not proof its transitive stack installs on all
those versions. Completing that setup remains required work.

## Refresh an inventory without installing

Use the already provisioned scanner environment's absolute Python path. This
command reads distribution metadata without importing scanner code or fetching
packages, and exclusively creates a new output; do not overwrite a reviewed
snapshot:

```sh
/absolute/scanner/environment/bin/python -I -B snapshot_environment.py \
  --output /absolute/private/output/new-environment.cdx.json
```

It refuses a mismatched scanner source/version, duplicate names, direct
dependency URLs and non-registry dependencies needing separate review. Review
any replacement inventory and update the manifest's digest explicitly. A new
inventory is not a passing scan, independent review, installation approval or
authority to reuse old inspection results. Preserve Apache-2.0 for SkillSpector
and the licences of its dependencies; this profile does not redistribute their
code or relicense them. Our profile/generator is GPL-3.0-or-later.

Assisted-by: Briar
