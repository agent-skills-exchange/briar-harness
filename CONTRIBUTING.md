# Contributing

Keep contributions small enough to review and useful without a production Briar
deployment. Read [the product contract](docs/PRODUCT-REQUIREMENTS.md).

## Skills

Each skill belongs in its own repository or remains upstream. Conform to the
[Agent Skills specification](https://agentskills.io/specification); Briar is
not an implicit dependency. Use standard SKILL.md frontmatter and progressive
disclosure. Reference the structured companion dependency declaration with:

```yaml
metadata:
  agent-skills-exchange-dependencies: dependencies.json
```

Start with the [standalone skill example](examples/readme-clarity/README.md)
for a small instruction-only package, explicit dependency declaration and
repository setup steps. It is not installed or loaded automatically.

The dependency profile is our extension, not an upstream resolver standard.
The draft schema is packaged at
`src/agent_skills_exchange/schemas/dependencies-v1.json`. Explicitly declare
OS/distribution/version/architecture, software and installation requirements,
other skills, services, network, credentials and transitive locks/SBOMs. Separate
required, optional and feature/platform-specific needs. Empty lists mean none
for the declared scope, not unexamined dependencies. Label declared versus
tested support; preserve the evidence for tested claims.

Core-managed skill additions and updates require static SkillSpector inspection
of isolated exact package bytes before activation. Retain findings and package,
scanner and policy identities. Missing/failed/incomplete checks and unresolved
blocking findings deny activation. Do not generate suppressions to clear a
failure. No LLM enrichment or running Briar service is required.

## Code and tests

Keep runtime imports standard-library-only and commands headless. Add positive
and negative tests. Never call fixture identities or editable receipts authority.
Preserve the separation between provenance, inspection, workload identity and
permission. No background polling, eager catalogue loading or silent installers.

The optional `skill-validation` development extra supplies the independent
JSON Schema checker. In a provisioned development environment, run:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_skill*.py'
PYTHONPATH=src python3 -m unittest discover -s tests -p test_product_packaging.py
```

Tests do not download or execute external skill code. Name actual host versions
when testing Claude/Cursor/Codex; format compliance is not runtime integration.
Describe behaviour, dependencies, evidence and limits in a focused PR. Retain
risk-appropriate independent review and CI; maintainers own merges/releases.
The [core CI candidate](docs/CI-BOOTSTRAP.md) documents pinned actions, locked
test dependencies, read-only permissions and the still-required real Actions run.

## Rights and confidentiality

Offer original contributions under GPL-3.0-or-later and confirm you have the
rights to do so. No copyright assignment is required. Preserve third-party
licences, notices and attribution; do not relicense upstream by assertion.
Never submit credentials, private deployment history, customer material or
source you cannot redistribute. Disclose agent assistance accurately; use
`Assisted-by: Briar` when applicable without implying human review occurred.

Assisted-by: Briar
