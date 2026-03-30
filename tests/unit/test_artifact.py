"""Tests for the Artifact class."""

import pytest

from claude_agent_skills.artifact import Artifact


class TestArtifact:
    """Test Artifact read/write operations."""

    def test_exists_false_for_missing_file(self, tmp_path):
        art = Artifact(tmp_path / "missing.md")
        assert art.exists is False

    def test_exists_true_for_real_file(self, tmp_path):
        p = tmp_path / "real.md"
        p.write_text("---\ntitle: hello\n---\nbody\n")
        art = Artifact(p)
        assert art.exists is True

    def test_path_property(self, tmp_path):
        p = tmp_path / "file.md"
        art = Artifact(p)
        assert art.path == p

    def test_frontmatter_property(self, tmp_path):
        p = tmp_path / "doc.md"
        p.write_text("---\nstatus: open\npriority: 1\n---\nSome body.\n")
        art = Artifact(p)
        assert art.frontmatter == {"status": "open", "priority": 1}

    def test_content_property(self, tmp_path):
        p = tmp_path / "doc.md"
        p.write_text("---\nstatus: open\n---\nBody text here.\n")
        art = Artifact(p)
        assert art.content == "Body text here.\n"

    def test_read_document(self, tmp_path):
        p = tmp_path / "doc.md"
        p.write_text("---\nkey: val\n---\nThe body.\n")
        art = Artifact(p)
        fm, body = art.read_document()
        assert fm == {"key": "val"}
        assert body == "The body.\n"

    def test_write_and_read_roundtrip(self, tmp_path):
        p = tmp_path / "roundtrip.md"
        art = Artifact(p)
        art.write({"title": "Test", "status": "draft"}, "Hello world.\n")
        assert art.exists
        fm, body = art.read_document()
        assert fm["title"] == "Test"
        assert fm["status"] == "draft"
        assert body == "Hello world.\n"

    def test_write_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "a" / "b" / "deep.md"
        art = Artifact(p)
        art.write({"x": 1}, "content\n")
        assert p.exists()

    def test_update_frontmatter_preserves_other_fields(self, tmp_path):
        p = tmp_path / "doc.md"
        p.write_text("---\ntitle: Original\nstatus: open\npriority: 1\n---\nBody.\n")
        art = Artifact(p)
        art.update_frontmatter(status="closed")
        fm = art.frontmatter
        assert fm["title"] == "Original"
        assert fm["status"] == "closed"
        assert fm["priority"] == 1

    def test_update_frontmatter_adds_new_fields(self, tmp_path):
        p = tmp_path / "doc.md"
        p.write_text("---\ntitle: X\n---\nBody.\n")
        art = Artifact(p)
        art.update_frontmatter(new_field="value")
        fm = art.frontmatter
        assert fm["title"] == "X"
        assert fm["new_field"] == "value"

    def test_content_preserved_after_update_frontmatter(self, tmp_path):
        p = tmp_path / "doc.md"
        p.write_text("---\ntitle: X\n---\nImportant body.\n")
        art = Artifact(p)
        art.update_frontmatter(title="Y")
        assert art.content == "Important body.\n"

    def test_no_frontmatter_file(self, tmp_path):
        p = tmp_path / "plain.md"
        p.write_text("Just plain text, no frontmatter.\n")
        art = Artifact(p)
        assert art.frontmatter == {}
        assert art.content == "Just plain text, no frontmatter.\n"
