# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline project-local onboarding plans; no discovery-path writes or admission."""

from pathlib import Path
import re

from .dependencies import DependencyError


_HOSTS = {
    "codex": (".agents/skills", "https://learn.chatgpt.com/docs/build-skills"),
    "claude": (".claude/skills", "https://code.claude.com/docs/en/skills"),
    "cursor": (".cursor/skills", "https://cursor.com/docs/skills"),
}
_RESERVED = {"con", "prn", "aux", "nul"} | {
    prefix + str(number) for prefix in ("com", "lpt") for number in range(1, 10)
}


def onboarding_plan(host, project, skill_name):
    """Describe native paths without reading/writing the project or skills.

    Project paths use the operating system running this command. Existence,
    symlinks, conflicts, installed host versions and live loading are not checked.
    """
    if not isinstance(host, str) or host not in _HOSTS:
        raise DependencyError("unsupported_host")
    if (not isinstance(skill_name, str) or len(skill_name) > 64
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_name)
            or skill_name in _RESERVED):
        raise DependencyError("invalid_skill_name")
    if (not isinstance(project, str) or not project
            or any(ord(c) < 32 or ord(c) == 127 for c in project)):
        raise DependencyError("invalid_project_path")
    root = Path(project)
    if not root.is_absolute() or ".." in root.parts:
        raise DependencyError("project_requires_absolute_path")
    directory, source = _HOSTS[host]
    destination = root / directory / skill_name
    return {
        "valid": True, "host": host, "project": str(root),
        "skill_name": skill_name, "scope": "project",
        "skill_directory": str(destination),
        "instruction_file": str(destination / "SKILL.md"),
        "documentation": source, "documentation_checked": "2026-11-15",
        "steps": [
            "resolve pinned package and explicit dependency closure",
            "verify exact cached bytes outside host discovery directories",
            "require bound static SkillSpector inspection without unresolved blockers",
            "verify workload authority, scope, lifetime and current revocation",
            "check destination conflicts and preserve existing project content",
            "only after admission expose selected skill through the native host path",
            "verify discovery and invocation in the actual host version",
        ],
        "writes_performed": False, "host_runtime_tested": False,
        "destination_checked": False, "admission_implemented": False,
        "approval_granted": False, "activated": False,
        "removal_unloads_existing_context": False,
    }
