"""
Directory scanner — walks configured directories, parses SKILL.md
frontmatter, and produces a structured inventory.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from . import config as cfg
from .models import (
    MODALITY_CALL_TYPE,
    SUBDIR_MODALITY,
    ScanDir,
    ScanReport,
    SkillMeta,
    parse_frontmatter,
)

SKIP_FILES = {
    "readme.md", "license", "license.md", "changelog.md",
    "contributing.md", "code_of_conduct.md", "security.md",
    "support.md", "authors.md",
}


def _build_invocation(meta: SkillMeta) -> str:
    """Construct a JSON invocation descriptor based on modality."""
    if meta.modality == "skill-cc":
        cmd = f"/{meta.name}"
        invocation = json.dumps({
            "type": MODALITY_CALL_TYPE.get(meta.modality, "unknown"),
            "command": cmd,
            "args_hint": meta.aliases,
        }, ensure_ascii=False)
    elif meta.modality == "agent-sub":
        invocation = json.dumps({
            "type": "agent-call",
            "agent_name": meta.name,
        }, ensure_ascii=False)
    elif meta.modality == "cli-command":
        invocation = json.dumps({
            "type": "cli-command",
            "command": "",
        }, ensure_ascii=False)
    else:
        invocation = ""
    return invocation


def scan_directory(
    scan_dir: ScanDir,
) -> list[SkillMeta]:
    """Walk one directory tree and return all skill entries found.

    Looks for ``SKILL.md``, ``AGENTS.md``, or ``.md`` files with
    valid YAML frontmatter.
    """
    discovered: list[SkillMeta] = []
    root = scan_dir.path
    if not root.exists():
        return discovered

    for entry in sorted(root.rglob("*")):
        if entry.is_dir():
            continue
        if entry.name.lower() in SKIP_FILES:
            continue
        if entry.name not in ("SKILL.md", "AGENTS.md") and entry.suffix != ".md":
            continue

        fm, _, body = parse_frontmatter(entry.read_text(encoding="utf-8", errors="replace"))

        # Skip files without frontmatter outside known subdirs
        if not fm:
            try:
                rel = entry.relative_to(root)
                in_known = any(p.lower() in SUBDIR_MODALITY for p in rel.parts[:-1])
            except ValueError:
                in_known = False
            if not in_known:
                continue

        name = fm.get("name", "")
        if not name:
            name = entry.parent.name if entry.name in ("SKILL.md", "AGENTS.md") else entry.stem

        description = fm.get("description", "")
        if not description:
            body_lines = [l.strip() for l in body.split("\n") if l.strip() and not l.startswith("#")]
            description = body_lines[0] if body_lines else ""

        aliases_raw = fm.get("aliases", "")
        aliases: str = (
            aliases_raw
            if isinstance(aliases_raw, str)
            else ",".join(aliases_raw) if isinstance(aliases_raw, list)
            else ""
        )

        triggers = ""
        auto_activate = fm.get("auto_activate", [])
        if isinstance(auto_activate, list) and auto_activate:
            triggers = ",".join(auto_activate)

        is_user_invocable = str(fm.get("user-invocable", "")).lower() in ("true", "yes", "1")

        # Modality inference
        modality = scan_dir.modality
        try:
            rel = entry.relative_to(root)
            for part in rel.parts[:-1]:
                if part.lower() in SUBDIR_MODALITY:
                    modality = SUBDIR_MODALITY[part.lower()]
                    break
        except ValueError:
            pass

        if entry.name == "SKILL.md":
            modality = "skill-cc" if is_user_invocable else "doc-reference"
        elif entry.name == "AGENTS.md":
            modality = "agent-sub"

        meta = SkillMeta(
            name=name,
            description=description[:500],
            modality=modality,
            path=str(entry),
            aliases=aliases,
            triggers=triggers,
            source_url=scan_dir.source_url,
            is_user_invocable=is_user_invocable,
        )
        meta.invocation = _build_invocation(meta)
        discovered.append(meta)

    return discovered


def scan_all(scan_dirs: Optional[list[ScanDir]] = None) -> list[SkillMeta]:
    """Scan all configured directories and return a deduplicated list.

    Deduplication is by *path* — the first occurrence wins.
    """
    if scan_dirs is None:
        conf = cfg.get_config()
        scan_dirs = [
            ScanDir(path=Path(d["path"]).expanduser(), modality=d.get("type", "doc-reference"))
            for d in conf.get("scan_dirs", [])
        ]

    all_skills: list[SkillMeta] = []
    seen: set[str] = set()

    for sd in scan_dirs:
        for skill in scan_directory(sd):
            if skill.path not in seen:
                seen.add(skill.path)
                all_skills.append(skill)
    return all_skills


def diff_against_index(
    discovered: list[SkillMeta],
    index: list[dict],
) -> ScanReport:
    """Compare discovered skills against an existing Excel/JSON index.

    Returns a ``ScanReport`` describing what would be added, updated,
    or is healthy.
    """
    report = ScanReport()
    index_by_path: dict[str, dict] = {}
    index_by_name_mod: dict[str, list[dict]] = {}

    for row in index:
        p = str(row.get("路径", row.get("path", "")))
        if p:
            index_by_path[p] = row
        key = f"{row.get('名称', row.get('name', ''))}|{row.get('技能形态 (Modality)', row.get('modality', ''))}"
        index_by_name_mod.setdefault(key, []).append(row)

    seen_names: set[str] = set()

    for skill in discovered:
        if skill.name in seen_names:
            report.skipped += 1
            continue
        seen_names.add(skill.name)

        existing = index_by_path.get(skill.path)
        if existing is None:
            # Try name+modality match
            key = f"{skill.name}|{skill.modality}"
            candidates = index_by_name_mod.get(key, [])
            if candidates:
                existing = candidates[0]

        if existing is None:
            report.added.append(skill)
        else:
            needs_update = False
            # Check if fields differ
            for field, attr in [("名称", "name"), ("描述（英文）", "description"),
                                 ("技能形态 (Modality)", "modality"), ("aliases", "aliases")]:
                old = str(existing.get(field, ""))
                new = str(getattr(skill, attr, ""))
                if old != new and new:
                    needs_update = True
                    break
            existing_path = str(existing.get("路径", existing.get("path", "")))
            if existing_path != skill.path:
                needs_update = True
                report.path_fixed += 1

            if needs_update:
                report.updated.append(skill)
            else:
                report.healthy += 1

    return report


def health_check(index: list[dict]) -> int:
    """Mark entries whose paths no longer exist as missing_path.

    Returns the count of entries marked.
    """
    count = 0
    for row in index:
        p = str(row.get("路径", row.get("path", "")))
        if p and not os.path.exists(Path(p)):
            row["health"] = "missing_path"
            count += 1
    return count
