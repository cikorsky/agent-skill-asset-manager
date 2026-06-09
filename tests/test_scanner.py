"""Tests for the directory scanner."""

from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from asam.models import ScanDir
from asam.scanner import scan_directory


def test_scan_directory_empty():
    """Scan a non-existent directory → empty list."""
    sd = ScanDir(path=Path("/nonexistent/path"))
    result = scan_directory(sd)
    assert result == []


def test_scan_directory_skip_non_skill():
    """Files without frontmatter are skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "skills" / "test-skill"
        d.mkdir(parents=True)
        (d / "README.md").write_text("# Just a readme")
        (d / "notes.txt").write_text("some notes")

        sd = ScanDir(path=Path(tmp), modality="skill-cc")
        result = scan_directory(sd)
        assert len(result) == 0


def test_scan_directory_finds_skill():
    """A proper SKILL.md with frontmatter is discovered."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "skills" / "my-skill"
        d.mkdir(parents=True)
        skill_md = d / "SKILL.md"
        skill_md.write_text("""---
name: my-skill
description: A test skill
user-invocable: true
---

# My Skill

This is a test skill.
""")

        sd = ScanDir(path=Path(tmp), modality="doc-reference")
        result = scan_directory(sd)
        assert len(result) == 1
        assert result[0].name == "my-skill"
        assert result[0].modality == "skill-cc"  # user-invocable overrides
        assert "test skill" in result[0].description
        assert ".claude" not in result[0].path  # no hardcoded paths


def test_scan_directory_multiple_skills():
    """Multiple skills in the same root are all discovered."""
    with tempfile.TemporaryDirectory() as tmp:
        for name in ["skill-a", "skill-b", "skill-c"]:
            d = Path(tmp) / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"""---
name: {name}
description: The {name} skill
---

# {name}
""")
        sd = ScanDir(path=Path(tmp), modality="doc-reference")
        result = scan_directory(sd)
        assert len(result) == 3
        names = {s.name for s in result}
        assert names == {"skill-a", "skill-b", "skill-c"}
