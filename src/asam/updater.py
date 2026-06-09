"""
Update checker — query GitHub releases / tags to find the latest version
of skills that have a ``source_url`` pointing to a GitHub repository.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Optional


def parse_github_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """Extract ``(owner, repo)`` from a GitHub URL."""
    m = re.search(r"github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?$", url)
    if m:
        return m.group(1), m.group(2)
    return None, None


def gh_api(endpoint: str) -> Optional[Any]:
    """Call the GitHub API via the ``gh`` CLI (pre-authenticated).

    Returns the parsed JSON response, or ``None`` on failure.
    """
    try:
        result = subprocess.run(
            ["gh", "api", endpoint, "--jq", "."],
            capture_output=True,
            text=True,
            timeout=20,
            env={**os.environ, "GH_PAGER": ""},
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return None


def fetch_latest_version(owner: str, repo: str) -> tuple[Optional[str], str, str]:
    """Fetch the latest version for a GitHub repo.

    Tries, in order:
      1. Latest published release.
      2. Most recent tag.
      3. Default branch HEAD commit SHA (short).

    Returns ``(version_string, version_type, date_or_sha)``.
    """
    base = f"repos/{owner}/{repo}"
    pushed_at = ""

    repo_info = gh_api(base)
    if isinstance(repo_info, dict):
        pushed_at = repo_info.get("pushed_at", "")[:10]

    # 1. Latest release
    release = gh_api(f"{base}/releases/latest")
    if isinstance(release, dict) and "tag_name" in release:
        return release["tag_name"], "release", pushed_at

    # 2. Latest tag
    tags = gh_api(f"{base}/tags?per_page=3")
    if isinstance(tags, list) and tags:
        return tags[0].get("name", ""), "tag", pushed_at

    # 3. Default branch HEAD
    if isinstance(repo_info, dict):
        branch = repo_info.get("default_branch", "main")
        ref = gh_api(f"{base}/git/refs/heads/{branch}")
        if isinstance(ref, dict) and "object" in ref:
            sha = ref["object"].get("sha", "")[:8]
            return sha, "commit", pushed_at

    # 4. Fallback — last push date
    if pushed_at:
        return pushed_at, "date", pushed_at

    return None, "unknown", ""


def check_skill(name: str, url: str, current_version: str = "") -> dict:
    """Check a single skill's latest version against its current version.

    Returns a dict with keys: ``name``, ``url``, ``current_version``,
    ``latest_version``, ``needs_update``.
    """
    owner, repo = parse_github_url(url)
    if not owner or not repo:
        return {
            "name": name,
            "url": url,
            "status": "invalid_url",
        }

    latest, vtype, _ = fetch_latest_version(owner, repo)
    return {
        "name": name,
        "url": url,
        "current_version": current_version,
        "latest_version": latest or "N/A",
        "needs_update": bool(latest and current_version and latest != current_version),
    }
