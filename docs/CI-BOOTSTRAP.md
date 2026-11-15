# Core test workflow candidate

`.github/workflows/core-tests.yml` is a locally prepared workflow, not an enabled
GitHub integration or a passed Actions result. Publishing/enabling it needs the
repository bootstrap authority and any necessary scoped workflow-write permission.
Do not widen the existing App's permissions or manufacture a check status.

The candidate runs on pull requests and pushes to main, using disposable GitHub
`ubuntu-24.04` runners and Python3.12/3.14. Minor-series selection intentionally
uses the current patch supplied by setup-python; the job prints the actual
runtime version. Other OS/architectures and actual hosted execution are unproved.

Actions are pinned to commits resolved from their official repositories on
15 November2026: checkout v6, setup-python v6 and setup-uv v7. The setup-uv v7
annotated tag was dereferenced to its commit, not mistaken for a commit hash.
uv is pinned to0.9.10, matching the locally checked lock parser. Cache is disabled.
The job explicitly provisions only its disposable test environment: it does not
change a user's host or install skill prerequisites. `uv sync --frozen` consumes
the existing `uv.lock` and the declared `skill-validation` extra; source builds,
automatic Python downloads by uv and installation of the project are disabled.
The setup-python action explicitly supplies the selected interpreter first.
All test-package versions and artifact hashes are in the lock. Native-library
and runner-image closure are not claimed by that Python lock.

The token is contents-read only, checkout does not persist credentials, and the
workflow uses no repository secrets, deployment environments or privileged
pull_request_target event. It performs no paid review, source publication,
credential operation, SkillSpector activation, service deployment or live sync.
Unit tests use synthetic packages/processes; this is not a real Cloudflare audit.

Focused source assertions and offline lock checking are author checks. They are
not a complete YAML/Actions validation or a real hosted result. Once bootstrap is
authorised, verify the actual check for the exact PR/head/base and retain any
failures before correcting the candidate. Exact-candidate independent review and
other required comprehensive checks remain separate.

Assisted-by: Briar
