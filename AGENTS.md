# Work on Briar's reusable core

Read `docs/PRODUCT-REQUIREMENTS.md` and `CONTRIBUTING.md` before changing the
package format, dependencies, inspection, authentication or onboarding.

Keep the default Python runtime standard-library-only. Skills are independent
Agent Skills packages, not plugins that require a running Briar service.
Declare dependencies explicitly; pin source and content identities. Loading
instructions never grants authority, installs software or broadens access.

Require static SkillSpector intake for core-managed additions and updates before
activation. Scan isolated exact bytes; missing, failed or incomplete inspection
and unresolved blocking findings deny activation. A cache or inspection receipt
is not an authority token. No activation command is implemented yet.

All product operations must be scriptable without prompts, YubiKey gestures or
per-action human sign-off. Keep scoped credentials, expiry, revocation and
deterministic permission checks. Do not disable a host's existing safeguards.

Use focused tests and retain independent review and CI for the actual risk.
Do not claim runtime host support, publication or migration from local tests.
Do not copy private deployment records, credentials or legacy history here.

Assisted-by: Briar
