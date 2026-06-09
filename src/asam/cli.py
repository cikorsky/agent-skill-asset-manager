"""
CLI entry points for AIM.

Registered in ``pyproject.toml`` as console_scripts:
  ``aim-scan``, ``aim-sync``, ``aim-search``, ``aim-update``.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import config as cfg


def _load_synonyms() -> dict:
    """Load synonyms from the configured path (best-effort)."""
    try:
        from .discover import load_synonyms
        return load_synonyms()
    except Exception:
        return {}


def scan_main() -> None:
    """CLI for ``aim-scan`` — scan directories and show / apply changes."""
    from .scanner import scan_all, diff_against_index
    from . import sync as sync_mod

    parser = argparse.ArgumentParser(description="AIM scanner — discover AI skills")
    parser.add_argument("--apply", action="store_true", help="Apply changes to index")
    parser.add_argument("--health-check", action="store_true", help="Check path validity")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--config", type=str, help="Path to config file")
    args = parser.parse_args()

    if args.config:
        cfg.reset_cache()
        cfg.get_config(Path(args.config))

    if args.health_check:
        try:
            import pandas as pd  # type: ignore[import-untyped]
            excel = cfg.get_config()["workspace"] + "/" + cfg.get_config().get("excel", "assets_inventory.xlsx")
            df = pd.read_excel(excel)
            # Only check entries with file-like paths
            count = 0
            for idx, row in df.iterrows():
                p = str(row.get("路径", ""))
                if p and not p.startswith("npx ") and not p.startswith("http") and not p.startswith("mcp:"):
                    import os
                    if not os.path.exists(p):
                        df.at[idx, "health"] = "missing_path"
                        count += 1
            df.to_excel(excel, index=False, engine="openpyxl")
            print(f"Health check: {count} skills marked missing_path")
        except ImportError:
            print("Health check requires pandas + openpyxl")
        return

    discovered = scan_all()
    report = diff_against_index(discovered, [])

    if args.json:
        print(json.dumps({
            "total_discovered": len(discovered),
            "added": len(report.added),
            "updated": len(report.updated),
            "healthy": report.healthy,
            "path_fixed": report.path_fixed,
            "skipped": report.skipped,
        }, indent=2))
    else:
        print(f"Discovered: {len(discovered)} skills")
        print(f"  New:      {len(report.added)}")
        print(f"  Updated:  {len(report.updated)}")
        print(f"  Healthy:  {report.healthy}")
        print(f"  PathFixed:{report.path_fixed}")
        print(f"  Skipped:  {report.skipped}")

    if args.apply:
        from .sync import build_router, write_json
        data = build_router(discovered)
        conf = cfg.get_config()
        ws = conf["workspace"]
        write_json(data["router"], str(Path(ws) / conf["router"]))
        write_json(data["hotlist"], str(Path(ws) / conf["hotlist"]))
        write_json(data["usage"], str(Path(ws) / conf["usage"]))
        print(f"Applied: {len(discovered)} skills indexed")


def sync_main() -> None:
    """CLI for ``aim-sync`` — scan and build JSON index."""
    from . import sync as sync_mod

    parser = argparse.ArgumentParser(description="AIM sync — build JSON router index")
    parser.add_argument("--hotlist-size", type=int, default=20)
    parser.add_argument("--config", type=str)
    args = parser.parse_args()

    if args.config:
        cfg.reset_cache()
        cfg.get_config(Path(args.config))

    data = sync_mod.sync(hotlist_size=args.hotlist_size)
    print(f"Sync Successful: {len(data['router'])} skills indexed to JSON.")


def search_main() -> None:
    """CLI for ``aim-search`` — weighted skill search."""
    from .discover import search as search_func

    parser = argparse.ArgumentParser(description="AIM search — weighted skill discovery")
    parser.add_argument("query", nargs="*", help="Search query")
    parser.add_argument("--top", type=int, default=10, help="Max results")
    parser.add_argument("--modality", type=str, help="Filter by modality")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--config", type=str)
    args = parser.parse_args()

    if args.config:
        cfg.reset_cache()
        cfg.get_config(Path(args.config))

    query = " ".join(args.query) if args.query else ""
    if not query:
        parser.print_help()
        return

    results = search_func(query, top_n=args.top, modality_filter=args.modality)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        if not results:
            print("No results found.")
            return
        for i, r in enumerate(results, 1):
            name = r.get("name", "?")
            mod = r.get("modality", "")
            desc = r.get("description", "")[:80]
            print(f"{i:>3}. [{mod:12s}] {name:30s} {desc}")


def update_main() -> None:
    """CLI for ``aim-update`` — check GitHub versions."""
    from .updater import check_skill, parse_github_url

    parser = argparse.ArgumentParser(description="AIM updater — check skill versions")
    parser.add_argument("--config", type=str)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.config:
        cfg.reset_cache()
        cfg.get_config(Path(args.config))

    # Load router to find skills with source_url
    try:
        from .discover import load_router
        router = load_router()
    except Exception:
        router = []

    results = []
    for skill in router:
        url = skill.get("source_url", "")
        if url:
            r = check_skill(skill.get("name", "?"), url)
            results.append(r)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            icon = "⚠" if r.get("needs_update") else "✓"
            print(f"  {icon} {r.get('name', '?'):30s} {r.get('current_version', '')[:12]:12s} → {r.get('latest_version', '')[:12]:12s}")


if __name__ == "__main__":
    # Dispatch based on argv[0] name
    import sys
    cmd = Path(sys.argv[0]).stem
    dispatch = {
        "aim-scan": scan_main,
        "aim-sync": sync_main,
        "aim-search": search_main,
        "aim-update": update_main,
    }
    dispatch.get(cmd, scan_main)()
