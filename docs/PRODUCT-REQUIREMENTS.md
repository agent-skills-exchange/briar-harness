# Agent Skills Exchange requirements

This document defines the reusable product contract. It is not a claim that
every requirement is implemented. See the README for current capabilities.

## Public home and licensing

The public entry point is `agent-skills-exchange/briar-harness`: a clean,
lightweight core with no inherited private operational history. Preserve private
source records and their reviews separately; do not publish them as part of this
project. Under Alex's instruction, verified public repositories are assumed
cleared for public sharing; do not impose a redundant confidentiality gate on
that work. This does not include private operational history, credentials or
local-only configuration imported from elsewhere, and does not waive separate
publication/execution authority. Our original code, documentation and skills are GPL-3.0-or-later.
Retain third-party licences/notices; do not relicense upstream work by assertion.

## Independent skills

Every skill is a standard [Agent Skills](https://agentskills.io/specification)
package in its own repository, or an immutable reference to an external one.
It must be usable without the Briar runtime unless its function actually needs
that runtime. Neither LXC, Telegram, one model provider nor one editor is an
implicit dependency. No special hosted registry or running Briar service is
required simply to read and use a skill.

Use standard SKILL.md fields and progressive disclosure. Extra structured
requirements belong in a companion manifest referenced by a namespaced string
in standard metadata. Our dependency profile is an extension, not a claim that
upstream Agent Skills defines dependency resolution or admission.

All supported operating systems/distributions/versions, architectures, tools,
runtimes, libraries, system packages, services, other skills, network access,
credentials and installation requirements must be explicit and structured.
Separate required, optional, feature-specific and platform-specific needs.
Record resolved transitive software dependencies in pinned lockfiles or SBOMs.
An empty list means none declared, not that analysis was skipped. Distinguish
declared platform support from support actually tested, with evidence.

Dependencies use immutable revisions/content identities. Check closure,
conflicts, cycles and compatibility before activation. A declaration is not
permission to install software, run a script, disclose data or obtain credentials.
Authorised installation can be automated without prompts; never execute an
unreviewed installer merely because a remote manifest requests it.

## Agent-friendly entry point

The `briar-harness` repository is the onboarding entry point for people and
agents. Provide documented, scriptable commands for project setup, selecting
Claude/Cursor/Codex, adding a pinned skill, checking prerequisites and syncing
approved versions. Commands must offer non-interactive operation, structured
results and meaningful exit codes; missing access produces a useful error,
not a hidden prompt or an interactive fallback.

Keep default runtime dependencies small. Transport, LXC, review providers and
host-specific integrations are optional. A user selecting skill support must
not install the complete live communications stack. The existing service
deployment lock stays with its separate legacy/full-service project, not in
the default standalone-skills install or the clean core repository.

Host adapters must use each host's supported integration mechanism and state
reload limits honestly. Do not claim that changing files unloads instructions
from an existing model context or hot-loads tools into a running chat.

## Required skill inspection

Skills inspection is a core requirement wherever the harness handles skills. Use
[NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector), the existing
inspection tool, for this requirement.

The core's skill intake and update path must require static SkillSpector
inspection before activation. Inspect the exact pinned package, including its
scripts and references, on an isolated copy so inspection cannot change the
verified cache. Bind the result to the package digest, scanner version and scan
policy; reuse it only while those inputs remain unchanged. A missing scanner,
failed/incomplete scan or unresolved blocking findings prevents activation,
with a structured non-interactive error. Fetching into quarantine, inspecting
metadata and planning do not imply admission.

Use static, no-LLM scanning by default. Declare the scanner and its installation,
platform and runtime requirements explicitly in the skill-management profile;
do not silently install it or make it a prerequisite for unrelated core commands.
Standalone skills remain usable without Briar or a running inspection service.
Do not suppress findings or generate a baseline merely to clear a failed gate.
Passing inspection does not grant execution rights or replace provenance,
sandboxing, dependency checks, independent review or runtime authorisation.

## Unattended authentication and permission checks

The new product must not require YubiKey authentication, hardware-key gestures,
GUI approval, or per-action human sign-off. Do not add a YubiKey integration
to the new core. Support unattended operation using explicitly provisioned,
scoped machine/workload credentials, expiry, revocation and deterministic
policy enforcement. Initial operator configuration is distinct from approving
every agent operation; CI/headless use cannot depend on a desktop prompt.

Separate package provenance, workload identity, and permission for a particular
operation. A signed package is not permission; a valid token is not a request
to perform every action it can technically reach. The policy must bind the
worker, selected task/project, resources, operations and lifetime. Skills cannot
grant rights, admit other workers or broaden that policy.

Reuse supported OAuth/MCP mechanisms as appropriate and model admission around
AuthZEN subject/action/resource/context. Keep AAuth compatibility as a design
direction while its drafts evolve; do not make an unfinished standard or a new
identity infrastructure stack a prerequisite for ordinary skill use. Evaluate
SPIFFE or supply-chain signing/update systems only for demonstrated needs.

This unattended design does not promise survival of arbitrary host or credential
compromise. Exfiltrated machine credentials or a compromised policy authority
remain risks; containment and least privilege limit their reach. Missing,
expired, revoked, mismatched or unavailable required verification denies the
operation without asking the model to invent an exception.

These requirements do not disable safeguards in an existing installation or
grant permission to publish, administer credentials or deploy. Do not transplant
an author's personal hardware-key gates into the shipped product.

## Tokens, bandwidth and lifetime

Do not load all skill bodies or a large remote catalogue at startup. Discover
from small local/project metadata and load only selected instructions and
needed references. Cache exact reviewed package bytes; do not redownload
unchanged packages or perform background update checks. Resolve dependencies,
validate signatures and evaluate policy with code, not paid model calls.

Scope availability by project, task/phase and worker, with explicit lifetime
and revocation. Keep cached packages distinct from active instructions and
credentials. No routine polling, mandatory usage accounting or invented token
quotas. Measure before claiming token, bandwidth or billing savings.

## Contributions and migration

Make a skill's setup, tests, dependency declaration, licence and contribution
path understandable without reading the harness internals. Provide reusable
checks and examples; do not require the full production stack to contribute.
Run required independent review and CI for the risk of the actual change.

The first external integration is Cloudflare security-audit, pinned to upstream
with its MIT licence retained. The second is the game-testing skill, once its
source is identified. Demonstrate standalone use and distinguish each host's
observed behaviour from generic format compliance.

Use one canonical shared source and versioned, reviewable deployment to the
local environment. Preserve local-only secrets/configuration and detect drift;
do not create silent bidirectional overwrites. Prove updates, rollback and
representative work before any approved live cut-over. Deprecate cursor-skills
only after the replacement is accepted; do not delete or disable it now.

Assisted-by: Briar
