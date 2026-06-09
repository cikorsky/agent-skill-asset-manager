"""
Weighted skill discovery — search, semantic expansion, usage tracking,
and hotlist generation.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from . import config as cfg

# Field weights for relevance scoring
WEIGHTS = {
    "name": 10,
    "aliases": 8,
    "triggers": 7,
    "tags": 5,
    "modality": 3,
    "category": 3,
    "example": 2,
    "description": 2,
}

SYNONYM_WEIGHT = 0.5


def load_router(path: Optional[str] = None) -> list[dict]:
    """Load the skills router JSON file."""
    if path is None:
        conf = cfg.get_config()
        path = str(Path(conf["workspace"]) / conf.get("router", "skills_router.json"))

    p = Path(path)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def load_synonyms(path: Optional[str] = None) -> dict[str, list[str]]:
    """Load domain synonym groups from a JSON file."""
    if path is None:
        conf = cfg.get_config()
        path = conf.get("synonyms", "")

    if not path:
        return {}

    p = Path(path).expanduser()
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("groups", {})


def tokenize(text: str) -> list[str]:
    """Normalize and split text into search tokens."""
    text = text.lower()
    # Split on non-alphanumeric (keep CJK characters)
    tokens = re.findall(r"[a-z0-9]+|[一-鿿]+", text)
    return [t for t in tokens if len(t) >= 1]


def expand_query(
    query_tokens: list[str],
    synonym_groups: dict[str, list[str]],
) -> list[tuple[str, float]]:
    """Expand query tokens with synonyms.

    Returns ``[(token, weight), ...]``. Original tokens get weight 1.0,
    synonyms get ``SYNONYM_WEIGHT``.
    """
    expanded: list[tuple[str, float]] = [(t, 1.0) for t in query_tokens]
    seen = set(query_tokens)

    for token in query_tokens:
        for group_name, members in synonym_groups.items():
            if token in members or token in group_name:
                for member in members:
                    if member not in seen:
                        expanded.append((member, SYNONYM_WEIGHT))
                        seen.add(member)
    return expanded


def field_score(field_value: str, weighted_tokens: list[tuple[str, float]]) -> float:
    """Score a single field against the weighted query tokens."""
    if not field_value:
        return 0.0
    field_lower = field_value.lower()
    score = 0.0
    for token, weight in weighted_tokens:
        if token in field_lower:
            count = field_lower.count(token)
            score += weight * count
    return score


def score_skill(skill: dict, weighted_tokens: list[tuple[str, float]]) -> float:
    """Compute total relevance score for one skill against the query."""
    total = 0.0
    for field, weight in WEIGHTS.items():
        val = skill.get(field, "")
        if isinstance(val, list):
            val = " ".join(val)
        total += field_score(str(val), weighted_tokens) * weight
    return total


def search(
    query: str,
    top_n: int = 10,
    modality_filter: Optional[str] = None,
    router_data: Optional[list[dict]] = None,
    synonyms: Optional[dict[str, list[str]]] = None,
) -> list[dict]:
    """Search the skill index with weighted scoring.

    Args:
        query: Free-text search query.
        top_n: Maximum results to return.
        modality_filter: Optional modality to restrict (e.g. ``"skill-cc"``).
        router_data: Pre-loaded router list; loaded from config if ``None``.
        synonyms: Pre-loaded synonym groups; loaded from config if ``None``.

    Returns:
        Top-``top_n`` skills sorted by descending relevance score.
    """
    if router_data is None:
        router_data = load_router()
    if synonyms is None:
        synonyms = load_synonyms()

    tokens = tokenize(query)
    if not tokens:
        return []

    weighted_tokens = expand_query(tokens, synonyms)

    scored: list[tuple[float, dict]] = []
    for skill in router_data:
        if modality_filter and skill.get("modality") != modality_filter:
            continue
        s = score_skill(skill, weighted_tokens)
        if s > 0:
            scored.append((s, skill))

    scored.sort(key=lambda x: -x[0])
    return scored[:top_n]


def format_results(results: list[dict]) -> str:
    """Format search results as a human-readable string."""
    lines = []
    for i, r in enumerate(results, 1):
        name = r.get("name", "?")
        score = r.get("score", 0)
        mod = r.get("modality", "")
        desc = r.get("description", "")[:80]
        lines.append(f"{i:>3}. [{mod:12s}] {name:30s} (score={score:.1f}) {desc}")
    return "\n".join(lines)
