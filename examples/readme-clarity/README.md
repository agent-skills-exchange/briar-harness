# Standalone skill starter

This is a small instruction-only Agent Skills example named `readme-clarity`.
Use it as the starting content for **one independent skill repository**, not as
a dependency on Briar. It reviews text supplied by the user and needs no tools,
network, credentials, additional software or other skills.

The example is kept outside host discovery directories. Including it in a source
archive does not install, activate or admit it. It is not the planned second
external game-testing integration and does not displace Cloudflare as the first.

## Make a skill repository

1. Start an otherwise empty repository. Copy this directory's contents to its
   root and include the Briar core's GPLv3 `LICENSE` text. Original contributions
   are GPL-3.0-or-later; retain that grant in SKILL.md and your repository docs.
   Preserve all upstream notices if you introduce third-party material.
2. Change the standard `name` and `description` fields and write the focused
   instructions. Use the [Agent Skills specification](https://agentskills.io/specification).
   Do not put unrelated private operational history in the new repository.
3. Update `dependencies.json` for the skill's actual scope. Explicitly declare
   operating systems/distributions/versions, architecture, runtimes, tools,
   system packages, services, installation steps, network, credentials and skill
   dependencies. Record transitive software locks/SBOMs where applicable. Keep
   required, optional, feature-specific and platform-specific needs distinct.
4. Add focused behaviour tests for scripts, if any. State declared versus tested
   support; do not claim every host works because metadata parses.
5. Validate the dependency declaration, check the standard format, run isolated
   static SkillSpector inspection, and complete required independent review/CI.
   Pin the reviewed source/content identity before referencing it from a project.

The dependency companion is an Agent Skills Exchange extension linked through
a standard string metadata field. An arbitrary Agent Skills host may ignore it;
do not claim that host enforces dependencies or permissions. No Briar import,
service or proprietary metadata is needed to read the skill itself.

For contributors using the optional core checks, run `ase validate
/path/to/skill/dependencies.json`. Optional format diagnostics and required
core-managed SkillSpector intake are documented in the core's contributor guide.
Tools are separately provisioned, never installed by this example. Keep the
source outside native discovery paths until the intended installation is admitted.

Do not add credentials to a manifest. A dependency declaration or successful
scan grants no permission to install software, disclose source or publish.
Changes to this example's instructions must be scanned again; do not reuse a
previous inspection result after changing package, scanner or policy inputs.

Assisted-by: Briar
