# Optional Agent Skills reference-format diagnostic

`ase check-format` runs a separately provisioned Python `skills-ref` validator on
an isolated copy of exact cached skill bytes. It never installs dependencies,
executes skill scripts, performs SkillSpector inspection, activates instructions
or grants permission. It is optional for unrelated core commands and standalone
skill use; the default core still imports standard-library modules only.

The chosen reference is [agentskills/agentskills](https://github.com/agentskills/agentskills/tree/f130f348f502d9804278a617f86929846896d2e9/skills-ref),
version 0.1.0, commit `f130f348f502d9804278a617f86929846896d2e9`, Apache-2.0.
The upstream README explicitly says **demonstration purposes only, not for
production**. We use its CLI as a diagnostic and do not fork its YAML parsing or
claim it establishes production conformance. A passing result reports
`reference_format_passed`, but always reports `standard_conformance_proven: false`,
`reference_source_verified: false` and `approval_granted: false`.

The preinstalled-runtime manifest declares an initial Linux x86-64 profile with
CPython3.13.9 and the Python runtime package versions from that pinned upstream
lock: click8.3.1, strictyaml1.7.3, python-dateutil2.9.0.post0 and six1.17.0.
Upstream development extras and Windows-only colorama are not required by this
Linux diagnostic profile. These are declared prerequisites, not a provisioned
environment, clean-host test, native OS-library inventory or complete reviewed
artifact/build lock. A reproducible isolated install, its build dependencies,
source/artifact integrity and runtime identity still require proof. No installer
command or production-conformance gate is advertised here.

Provide an absolute path to an explicitly trusted executable named `skills-ref`
with an absolute interpreter in its launcher. Its version output must match the
Python reference CLI. The resolved executable must be owner/root-owned and not
group/other writable. Do not substitute an npm package or another implementation
merely because it has the same command/version name. The adapter records the
launcher SHA-256 and checks it for changes; that does not attest its interpreter,
dependencies or upstream origin. It is trusted local software, not OS-sandboxed.
Its environment excludes inherited credentials/configuration, but no OS-enforced
network isolation is claimed.

```sh
ase check-format --lock /absolute/package-lock.json --cache /absolute/cache \
  --reports /absolute/private/reports --validator /absolute/trusted/skills-ref \
  --name security-audit --timeout SECONDS
```

`--name` is the intended skill directory name, not necessarily its catalogue ID.
The reference validator checks frontmatter/name compatibility in that directory;
the command never reads the body into a model context. Set the workload timeout
explicitly. Version mismatch, launch/timeout, changed copy/cache/launcher,
unrecognised success output and validator findings do not pass. Exit0 means
only the named reference-format diagnostic passed; failure is exit2 with JSON.
Raw diagnostics and a value-free summary receipt stay in the private reports
directory rather than being forwarded to the agent. Those diagnostics can contain
untrusted skill text; never treat them as instructions or authority.

The implementation is presently covered by synthetic adapter tests only. The
installed same-name npm tool was not substituted or executed. Cloudflare's real
Python-reference diagnostic and its independent SkillSpector findings disposition
remain outstanding. Format validation cannot waive the security gate.

Source package/runtime choices follow the open-standard reuse decision: a small
adapter to the published reference, no custom YAML dialect, optional provisioning,
and explicit demonstration-only limitations. Preserve upstream Apache-2.0 and
dependency licences when separately provisioning; no upstream code is vendored.
Our adapter/profile is GPL-3.0-or-later.

Assisted-by: Briar
