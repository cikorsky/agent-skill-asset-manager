"""Tests for the weighted search / discovery module."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from asam.discover import tokenize, expand_query, score_skill, field_score, search


def test_tokenize():
    assert tokenize("hello world") == ["hello", "world"]
    assert tokenize("") == []
    assert tokenize("hello-world_test") == ["hello", "world", "test"]
    # CJK: tokenize returns the full CJK block as one token
    result = tokenize("搜索测试")
    assert len(result) >= 1


def test_expand_query():
    tokens = ["test"]
    groups = {"testing": ["test", "testing", "qa"]}
    expanded = expand_query(tokens, groups)
    names = [t for t, _ in expanded]
    assert "test" in names
    assert "testing" in names
    assert "qa" in names


def test_field_score():
    tokens = [("test", 1.0)]
    assert field_score("this is a test", tokens) > 0
    assert field_score("no match here", tokens) == 0


def test_score_skill():
    skill = {
        "name": "my-test-skill",
        "description": "A great testing tool",
        "tags": "testing, qa",
        "modality": "skill-cc",
        "category": "skills",
        "example": "/my-test-skill",
        "aliases": "",
        "triggers": "",
    }
    tokens = [("test", 1.0)]
    assert score_skill(skill, tokens) > 0


def test_search_no_synonyms():
    router = [
        {"name": "markdown-ppt", "description": "Convert markdown to presentations", "modality": "skill-cc"},
        {"name": "image-gen", "description": "Generate images from text", "modality": "skill-cc"},
    ]
    results = search("presentation", top_n=5, router_data=router, synonyms={})
    assert len(results) >= 1


def test_search_empty_query():
    assert search("", top_n=5) == []
