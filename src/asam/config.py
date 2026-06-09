"""
Configuration management for AIM.

Loads settings from a YAML file, environment variables, or CLI defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def find_config(path: Optional[Path] = None) -> Path:
    """Locate the configuration file.

    Resolution order:
      1. Explicit ``path`` argument.
      2. ``AIM_CONFIG`` environment variable.
      3. ``./aim-config.yaml`` (current directory).
      4. ``~/.aim/config.yaml`` (user home).
    """
    if path is not None:
        return path

    env = os.environ.get("AIM_CONFIG")
    if env:
        return Path(env)

    cwd = Path.cwd() / "aim-config.yaml"
    if cwd.exists():
        return cwd

    home = Path.home() / ".aim" / "config.yaml"
    if home.exists():
        return home

    return cwd  # fallback — will trigger YAML load error with a clear message


def load_config(path: Optional[Path] = None) -> dict:
    """Load the AIM configuration as a dictionary.

    If PyYAML is installed it is preferred; a minimal TOML-style fallback
    parser is used when PyYAML is unavailable so that the ``scan`` and
    ``search`` commands (which need path information) can still function.
    """
    cfg_path = find_config(path)
    raw = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else ""

    try:
        import yaml  # type: ignore[import-untyped]
        config: dict = yaml.safe_load(raw) or {}
    except ImportError:
        config = _parse_fallback(raw)

    return _merge_defaults(config)


def _parse_fallback(raw: str) -> dict:
    """Minimal YAML subset parser — supports the config keys AIM needs."""
    result: dict = {}
    current_key: Optional[str] = None

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if current_key:
                if not isinstance(result.get(current_key), list):
                    result[current_key] = []
                result[current_key].append(stripped[2:].strip())
            continue
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            current_key = key.strip()
            val = val.strip()
            if val:
                # Basic type coercion
                if val.lower() == "true":
                    val = True
                elif val.lower() == "false":
                    val = False
                elif val.isdigit():
                    val = int(val)
                result[current_key] = val
    return result


def _merge_defaults(config: dict) -> dict:
    """Fill in sensible defaults for any missing keys."""
    defaults = {
        "workspace": str(Path.cwd() / "results"),
        "excel": "assets_inventory.xlsx",
        "router": "skills_router.json",
        "hotlist": "skills_hotlist.json",
        "usage": "skills_usage.json",
        "hotlist_size": 20,
        "synonyms": "",
        "scan_dirs": [],
    }
    for key, val in defaults.items():
        config.setdefault(key, val)

    # Resolve relative workspace to absolute
    ws = Path(config["workspace"])
    if not ws.is_absolute():
        ws = Path.cwd() / ws
    config["workspace"] = str(ws.resolve())

    return config


# ---- Convenience accessors (cached) ----
_CONFIG_CACHE: Optional[dict] = None


def get_config(path: Optional[Path] = None) -> dict:
    """Return the cached configuration, loading it on first call."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = load_config(path)
    return _CONFIG_CACHE


def reset_cache() -> None:
    """Clear the cached configuration (useful in tests)."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None
