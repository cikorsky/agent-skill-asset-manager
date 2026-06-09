"""ASAM — Agent Skill Asset Manager.

Scan, index, search, and maintain AI skill libraries across
your filesystem.

Modules:
    config:  Configuration loading and access
    models:  Data models and SKILL.md frontmatter parsing
    scanner: Directory scanner that extracts skill metadata
    sync:    Export scanned data to JSON router index
    discover:Weighted search and discovery over indexed skills
    updater: Check GitHub repos for skill version updates
"""

__version__ = "1.0.0"
