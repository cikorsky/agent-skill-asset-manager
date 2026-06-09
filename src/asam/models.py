"""
Data models and SKILL.md frontmatter parsing for AIM.

Provides a lightweight YAML frontmatter extractor that does **not**
require the ``pyyaml`` package, plus typed dataclasses for skill
metadata, scan results, and search results.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ──────────────────────────────────────────────
#  Frontmatter parser (zero-dependency)
# ──────────────────────────────────────────────


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str, str]:
    """Extract YAML frontmatter and body from a markdown string.

    Returns ``(frontmatter_dict, raw_yaml_string, body_string)``.
    If no frontmatter is found the first two elements are empty.
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", text, re.DOTALL)
    if not m:
        return {}, "", text

    yaml_raw = m.group(1)
    body = m.group(2)
    return _parse_simple_yaml(yaml_raw), yaml_raw, body


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML parser for flat + shallow nested keys.

    Supports:
      - Key-value: ``key: value``
      - List items: ``- item``
      - Quoted values (single/double stripped)
      - Inline lists: ``[a, b, c]``

    Does **not** support nested mappings or multi-line strings.
    """
    result: dict[str, Any] = {}
    current_key: Optional[str] = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Inline list  [a, b, c]
        if stripped.startswith("[") and stripped.endswith("]"):
            if current_key:
                items = [x.strip().strip("\"'") for x in stripped[1:-1].split(",") if x.strip()]
                result[current_key] = items
            continue

        # List item  - item
        list_m = re.match(r"^-\s+(.*)", stripped)
        if list_m:
            item = list_m.group(1).strip().strip("\"'")
            if current_key:
                result.setdefault(current_key, [])
                if isinstance(result[current_key], list):
                    result[current_key].append(item)
            continue

        # Key-value  key: value  (if no value, just set current_key for list items)
        kv_m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*(.*)", stripped)
        if kv_m:
            current_key = kv_m.group(1).strip()
            val = kv_m.group(2).strip().strip("\"'")
            if val:
                result[current_key] = val
            # If val is empty, don't set result — list items below will populate it
            continue

    return result


# ──────────────────────────────────────────────
#  Data models
# ──────────────────────────────────────────────

@dataclass
class SkillMeta:
    """Metadata extracted from a single skill directory."""

    name: str
    description: str = ""
    modality: str = "doc-reference"
    path: str = ""
    aliases: str = ""
    invocation: str = ""
    triggers: str = ""
    tags: str = ""
    category: str = "skills"
    health: str = "healthy"
    source_url: str = ""
    is_user_invocable: bool = False


@dataclass
class ScanDir:
    """A directory to scan, with its default modality and source URL."""

    path: Path
    modality: str = "doc-reference"
    source_url: str = ""


@dataclass
class ScanReport:
    """Result of comparing discovered skills against the existing index."""

    added: list[SkillMeta] = field(default_factory=list)
    updated: list[SkillMeta] = field(default_factory=list)
    healthy: int = 0
    path_fixed: int = 0
    skipped: int = 0


@dataclass
class SearchResult:
    """A single search hit with its relevance score."""

    name: str
    score: float
    modality: str
    path: str
    description: str
    tags: str = ""
    example: str = ""


# ──────────────────────────────────────────────
#  Modality helpers
# ──────────────────────────────────────────────

SUBDIR_MODALITY: dict[str, str] = {
    "skills": "skill-cc",
    "agents": "agent-sub",
    "commands": "cli-command",
}

MODALITY_CALL_TYPE: dict[str, str] = {
    "skill-cc": "slash-command",
    "agent-sub": "agent-call",
    "cli-command": "cli-command",
    "doc-reference": "read-only",
    "mcp-server": "mcp-tool",
}


def infer_modality(entry_path: Path, default: str) -> str:
    """Determine skill modality from its path and frontmatter.

    Priority:
      1. Subdirectory name override (skills/ → skill-cc, …).
      2. Returns the ``default`` otherwise.
    """
    for part in entry_path.parts:
        if part.lower() in SUBDIR_MODALITY:
            return SUBDIR_MODALITY[part.lower()]
    return default
