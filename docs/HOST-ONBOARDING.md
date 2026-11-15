# Native host onboarding

The core can produce an offline setup plan for Codex, Claude Code and Cursor:

```sh
PYTHONPATH=src python3 -m agent_skills_exchange onboarding-plan \
  --host codex --project /absolute/path/to/project --name example-skill
```

Choose `codex`, `claude` (meaning **Claude Code**, not every Claude product),
or `cursor`. JSON describes the intended project-local path and prerequisites.
The project path must be absolute using the command's current operating-system
syntax. The command does not require that path to exist, read project contents,
resolve symlinks, inspect conflicts, contact a service or write anything.
It cannot certify a safe destination or successful host loading.

## Native locations

| Host | Planned project-local skill path | Official documentation |
| --- | --- | --- |
| Codex | `.agents/skills/<name>/SKILL.md` | [Build skills](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code | `.claude/skills/<name>/SKILL.md` | [Skills](https://code.claude.com/docs/en/skills) |
| Cursor | `.cursor/skills/<name>/SKILL.md` | [Skills](https://cursor.com/docs/skills) |

These conventions were checked against the fetched vendor documentation on
15 November 2026; actual runtime versions have not been tested. Cursor also
documents `.agents/skills`; the planner chooses its host-specific path to avoid
silently changing another host's project discovery. Do not duplicate the same
skill into multiple discovery paths merely to improve its chance of loading.
Codex scans applicable ancestor `.agents/skills` directories; duplicate names
are not necessarily merged. Existing installations must be checked before use.

Skills use the standard Agent Skills package, not a Briar service or LXC plugin.
Do not add a full Briar runtime dependency unless the skill's function needs it.
The plan itself needs only the core's Python>=3.12 runtime. It invokes no host
binary and installs no host or additional packages. Host software versions,
credentials and per-skill prerequisites must be declared and tested separately
before claiming an operational integration.

## Keep inactive bytes out of discovery

A future admitted-install path must keep fetched/quarantined skills outside
all host discovery directories. Copying an unadmitted SKILL.md into one of these
paths can expose instructions even without a Briar activation command. The plan
therefore never creates directories or links. An installation path still needs
verified pinned content, explicit dependency/platform checks, bound mandatory
SkillSpector inspection, current workload authority/revocation, destination
conflict handling and a tested rollback before exposing selected content.

Native discovery is not a security boundary or a mechanism for enforcing task
expiry. Keep remote catalogues and inactive skill bodies out of startup context;
expose only admitted selections. Removing a directory does not remove instructions
already seen by a running model. Codex documents automatic discovery and restart
as a fallback; other loading behaviour and all actual invocations need observation
in the selected host version. Do not promise hot-unload or immediate revocation
of context. Runtime permission enforcement must remain outside skill text.

Cloudflare remains the first intended external integration but is still blocked
by inspection. This planner does not bypass that blocker or prove standalone
audit execution, host support, automatic setup or local migration. No live
harness or existing skill directory is changed.

Assisted-by: Briar
