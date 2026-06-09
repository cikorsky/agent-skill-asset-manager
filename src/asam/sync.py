"""
Sync — export scanned skill inventory to JSON router index (and optionally Excel).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Optional

from . import config as cfg
from .scanner import scan_all


def _clean_nan(obj: Any) -> Any:
    """Recursively replace NaN/NaT with None for clean JSON."""
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nan(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


def _make_row(skill) -> dict:
    """Convert a SkillMeta (or dict) to a plain dictionary for the router."""
    if hasattr(skill, "name"):
        return {
            "name": skill.name,
            "category": getattr(skill, "category", "skills"),
            "modality": skill.modality,
            "path": skill.path,
            "description": skill.description,
            "tags": getattr(skill, "tags", ""),
            "example": getattr(skill, "invocation", ""),
            "health": "healthy",
        }
    return dict(skill)


def build_router(
    skills: Optional[list] = None,
    hotlist_size: int = 20,
) -> dict:
    """Build the router, hotlist, and usage data structures.

    Args:
        skills:  List of SkillMeta or dict. When ``None``, runs a full scan.
        hotlist_size: How many top entries the hotlist holds.

    Returns:
        Dictionary with keys ``router``, ``hotlist``, ``usage``.
    """
    if skills is None:
        skills = scan_all()

    router_data = [_make_row(s) for s in skills]
    router_data = _clean_nan(router_data)

    # Build hotlist from healthy skills with names
    healthy = [s for s in router_data if s.get("health") == "healthy" and s.get("name")]
    hotlist = healthy[:hotlist_size]

    return {
        "router": router_data,
        "hotlist": hotlist,
        "usage": {},
    }


def write_json(data: dict, path: str) -> None:
    """Write a JSON file, creating parent directories if needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(_clean_nan(data), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def sync(
    hotlist_size: Optional[int] = None,
    excel_path: Optional[str] = None,
    router_path: Optional[str] = None,
    hotlist_path: Optional[str] = None,
    usage_path: Optional[str] = None,
) -> dict:
    """Full sync pipeline: scan → build router → write JSON files.

    Returns the router data dictionary.
    """
    conf = cfg.get_config()
    ws = conf["workspace"]

    hotlist_size = hotlist_size or conf.get("hotlist_size", 20)
    router_path = router_path or str(Path(ws) / conf.get("router", "skills_router.json"))
    hotlist_path = hotlist_path or str(Path(ws) / conf.get("hotlist", "skills_hotlist.json"))
    usage_path = usage_path or str(Path(ws) / conf.get("usage", "skills_usage.json"))

    skills = scan_all()
    data = build_router(skills, hotlist_size=hotlist_size)

    write_json(data["router"], router_path)
    write_json(data["hotlist"], hotlist_path)
    write_json(data["usage"], usage_path)

    return data
