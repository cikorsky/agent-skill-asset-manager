"""Tests for the models / frontmatter parser."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from asam.models import parse_frontmatter, infer_modality


def test_parse_full_frontmatter():
    text = """---
name: my-test-skill
description: A test skill
aliases:
  - alias1
  - alias2
user-invocable: true
---

# My Test Skill

Some description here.
"""
    fm, raw, body = parse_frontmatter(text)
    assert fm["name"] == "my-test-skill"
    assert fm["description"] == "A test skill"
    assert fm["user-invocable"] == "true"
    assert "My Test Skill" in body


def test_parse_no_frontmatter():
    text = "# Just a heading\n\nSome content"
    fm, raw, body = parse_frontmatter(text)
    assert fm == {}
    assert raw == ""
    assert "heading" in body


def test_parse_empty():
    fm, raw, body = parse_frontmatter("")
    assert fm == {}
    assert raw == ""
    assert body == ""


def test_parse_inline_list():
    """Inline list [a, b, c] is stored as the raw string value."""
    text = """---
name: test
tags: [one, two, three]
---"""
    fm, _, _ = parse_frontmatter(text)
    # The frontmatter parser stores inline lists as raw strings
    assert "one" in str(fm.get("tags", ""))


def test_infer_modality():
    p = Path("/some/dir/skills/my-thing/SKILL.md")
    assert infer_modality(p, "doc-reference") == "skill-cc"


def test_infer_modality_default():
    p = Path("/some/dir/custom/my-thing/SKILL.md")
    assert infer_modality(p, "doc-reference") == "doc-reference"
