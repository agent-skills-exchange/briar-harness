# Briar harness

A small starting point for selecting and inspecting independent
[Agent Skills](https://agentskills.io/specification). Skills can live in their
own repositories or stay upstream; they do not need Briar's communications
stack, LXC, Telegram or a particular model provider.

This is a local development candidate for Agent Skills Exchange, not a published
release or a deployed replacement for an existing harness.

## Start without installing anything

Python 3.12 or newer is required. From this checkout:

```sh
PYTHONPATH=src python3 -m agent_skills_exchange --help
PYTHONPATH=src python3 -m agent_skills_exchange validate \
  integrations/cloudflare-security-audit/dependencies.guidance.json
PYTHONPATH=src python3 -m agent_skills_exchange plan \
  --lock integrations/cloudflare-security-audit/package-lock.json \
  --manifest integrations/cloudflare-security-audit/dependencies.guidance.json \
  --skill cloudflare-security-audit --feature guidance \
  --os linux --distribution ubuntu --os-version 24.04 --architecture x86_64
```

An installed package exposes both `briar-harness` and `ase` for the same command
interface. The default package has no third-party runtime dependencies. JSON
results and nonzero failures are non-interactive; no desktop or hardware-key
approval is built into the product. Installing or changing an existing host
environment remains the operator's decision.

## Current boundary

`validate` checks structured dependency declarations. `plan` resolves selected
features and pinned skill dependencies from local metadata. `fetch` acquires
exact reviewed bytes into an inactive cache; `verify-cache` checks them without
network access. `inspect` requires separately provisioned SkillSpector 2.8.2 and
produces static inspection evidence on an isolated copy, without LLM calls.
A headless `verify-inspection` [saved-evidence check](docs/INSPECTION-EVIDENCE.md) can detect
package/report/scanner/policy mismatches; it cannot establish trusted origin,
scanner runtime identity or admission.

The optional [skill-management profile](profiles/skill-management/README.md)
records scanner/runtime prerequisites and an exact installed-package inventory.
It exposes remaining native-library, reproducible-install and environment-binding
gaps explicitly; it is not yet a supported clean-host scanner installer.

`check-format` optionally invokes the separately provisioned Python Agent Skills
reference validator on an isolated package copy. The [format profile](profiles/skill-format/README.md)
declares its prerequisites and demonstration-only limits; passing this diagnostic
does not establish production conformance, security inspection or admission.

None of these commands activates a skill, installs its prerequisites or grants
permission to execute. Cloudflare's first pinned package remains blocked by
inspection; its guidance profile is metadata for a strict instruction-only
subset, not a claim the full audit or host integrations have passed.

`authzen-request` constructs an offline AuthZEN evaluation request from pinned
package metadata and explicitly unverified worker/task claims. The optional
library client can query an operator-configured HTTPS policy service once;
neither path verifies identity or grants activation. See the
[AuthZEN client boundary](docs/AUTHZEN.md) for prerequisites and remaining gates.

Host onboarding for Claude/Cursor/Codex, trusted admission/result reuse,
unattended workload credentials, full-audit integration and versioned local
sync/rollback remain implementation work. Do not replace a live installation
with this candidate yet.

`onboarding-plan` describes native project-local paths for Codex, Claude Code
and Cursor without reading/writing the project or exposing skill instructions.
See [host onboarding](docs/HOST-ONBOARDING.md) for commands, vendor sources and
the distinction between an offline plan and a tested admitted installation.

See [commands and limits](docs/SKILL-COMMANDS.md),
[product requirements](docs/PRODUCT-REQUIREMENTS.md),
[Cloudflare intake](integrations/cloudflare-security-audit/README.md) and
[contributing](CONTRIBUTING.md).

For an existing selected skill, `plan-update` verifies both pinned cached
versions and checks deployment drift without applying changes. See
[update planning](docs/UPDATE-PLANNING.md); cached rollback bytes are not proof
of an executed rollback or permission to migrate the live harness.

## Licence

Original work is GPL-3.0-or-later; see [LICENSE](LICENSE). Upstream material
keeps its own licence and notices. Cloudflare's pinned package includes its
MIT licence; SkillSpector is a separate Apache-2.0 tool, not vendored here.

Assisted-by: Briar
