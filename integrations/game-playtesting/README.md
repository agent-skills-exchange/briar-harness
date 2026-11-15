# Game/app playtesting intake candidate

Alex confirmed `DynamicDevices/game-playtesting-skill` as the second ASE example.
Cloudflare remains first. This integration selects the standard upstream
`app-playtesting` skill at `skills/app-playtesting`, not its repository's review
infrastructure or a running Briar service.

After manual review and merge of PRs #7, #8 and #9, this lock pins accepted main
commit `79347af51d4e6d28ae3cfdcd49adfab64649ddd9`. It contains 21 files/127779 bytes;
package digest:
`d272ad2de97ecc5a314838ca54ee5b4bc27d4e09077cb35ddefa743049fef739`.
`UPSTREAM-LICENSE` preserves the repository's MIT licence. ASE's original
integration code/docs are GPL-3.0-or-later; they do not relicense the skill.
The upstream instructions, scripts and existing baseline are unchanged here.

## State and boundaries

The exact package has been verified into an inactive cache from native Git
objects, without another network download. Cache integrity is not admission,
inspection approval or permission to drive an app. No skill instruction or
script has been activated or executed by this intake candidate.

Repository-level manual integration passed 40 offline app tests, 126 offline
review-integration tests and template validation. Final PR/main CI passed and
the merged main tree matched the combined reviewed candidate. These are source
and synthetic checks, not a real Unity, Android, browser, game or editor-host
acceptance result.

The source repository's static scan passes using its previously reviewed
fingerprint baseline, refreshed for unchanged findings after the route fix.
That does **not** satisfy ASE's separate no-baseline intake policy. A skill's
own baseline is bundled as source data, not trusted authority or an approved
exception. The core's installed scanner-executable safety check also remains
unresolved; earlier inspection stopped before scanning. Do not bypass it or
describe the standalone baseline-backed scan as core admission.

## Dependencies still to declare

Upstream does not yet declare ASE's structured companion dependency extension.
There is intentionally no installable ASE dependency profile for this skill
yet: absence of that profile does not mean no dependencies.

The method requires authorised app access, actual screenshot inspection and an
appropriate input mechanism. Android/ADB and Unity/editor automation are
optional adapters, not requirements for everyone. Upstream declares Python 3.9+
for the optional session validator; Unity helpers, the optional adviser/SDK,
platform-specific credential access and target-specific tools need separate
feature-scoped declarations with their complete transitive dependencies.
The selected host, OS/architecture, actual app/build, credentials and adapter
requirements remain to be bound and verified. Do not infer supported platforms
or install software from the existence of instructions or scripts.

No Briar runtime, LXC, communications stack or repository review service is an
implicit skill dependency. Host-provider credentials belong to the chosen host;
loading this package does not request them or grant purchases, app/device access,
publication rights or permission to run experiments.

Next: complete those structured declarations, resolve exact-package core
inspection and authority, then demonstrate this second example only after the
Cloudflare integration. No live harness synchronization or cut-over is implied.

Assisted-by: Briar
