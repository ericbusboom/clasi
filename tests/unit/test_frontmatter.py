"""Tests for clasi.frontmatter module."""

import pytest
from pathlib import Path

from clasi.frontmatter import (
    MalformedFrontmatterError,
    read_document,
    read_frontmatter,
    write_frontmatter,
)


@pytest.fixture
def tmp_md(tmp_path):
    """Return a helper that writes content to a temp .md file and returns its path."""
    def _write(content: str) -> Path:
        p = tmp_path / "test.md"
        p.write_text(content, encoding="utf-8")
        return p
    return _write


class TestReadDocument:
    def test_basic(self, tmp_md):
        p = tmp_md("---\ntitle: Hello\nstatus: draft\n---\nBody text.\n")
        fm, body = read_document(p)
        assert fm == {"title": "Hello", "status": "draft"}
        assert body == "Body text.\n"

    def test_no_frontmatter(self, tmp_md):
        p = tmp_md("Just a plain file.\n")
        fm, body = read_document(p)
        assert fm == {}
        assert body == "Just a plain file.\n"

    def test_empty_frontmatter(self, tmp_md):
        p = tmp_md("---\n---\nBody only.\n")
        fm, body = read_document(p)
        assert fm == {}
        assert body == "Body only.\n"

    def test_no_closing_delimiter(self, tmp_md):
        p = tmp_md("---\ntitle: oops\nno closing\n")
        fm, body = read_document(p)
        assert fm == {}
        assert body == "---\ntitle: oops\nno closing\n"

    def test_list_in_frontmatter(self, tmp_md):
        p = tmp_md("---\nid: \"001\"\nuse-cases: [UC-001, UC-002]\n---\n# Title\n")
        fm, body = read_document(p)
        assert fm["id"] == "001"
        assert fm["use-cases"] == ["UC-001", "UC-002"]
        assert body == "# Title\n"

    def test_multiline_body(self, tmp_md):
        content = "---\nk: v\n---\nLine 1\nLine 2\nLine 3\n"
        p = tmp_md(content)
        fm, body = read_document(p)
        assert fm == {"k": "v"}
        assert body == "Line 1\nLine 2\nLine 3\n"


class TestReadFrontmatter:
    def test_returns_dict(self, tmp_md):
        p = tmp_md("---\nstatus: todo\n---\n# Heading\n")
        assert read_frontmatter(p) == {"status": "todo"}

    def test_no_frontmatter(self, tmp_md):
        p = tmp_md("No front matter here.\n")
        assert read_frontmatter(p) == {}


class TestMalformedFrontmatter:
    """Tests for MalformedFrontmatterError raised on corrupted fence."""

    def test_malformed_fence_raises(self, tmp_md):
        """A file whose first line starts with '-' but is not '---' should raise."""
        p = tmp_md("---bad\nsome content\n")
        with pytest.raises(MalformedFrontmatterError) as exc_info:
            read_frontmatter(p)
        assert str(p) in str(exc_info.value)

    def test_malformed_fence_message_contains_first_line(self, tmp_md):
        """Error message includes the actual first-line text found."""
        p = tmp_md("---x\nsome content\n")
        with pytest.raises(MalformedFrontmatterError) as exc_info:
            read_frontmatter(p)
        assert "---x" in str(exc_info.value)

    def test_malformed_fence_single_dash(self, tmp_md):
        """A single '-' at start also raises."""
        p = tmp_md("-not-frontmatter\ncontent\n")
        with pytest.raises(MalformedFrontmatterError):
            read_frontmatter(p)

    def test_no_frontmatter_returns_empty(self, tmp_md):
        """File whose first character is not '-' returns {} without raising."""
        p = tmp_md("# Just a body\nNo frontmatter here.\n")
        assert read_frontmatter(p) == {}

    def test_no_frontmatter_space_first(self, tmp_md):
        """File starting with space also returns {}."""
        p = tmp_md(" ---\nstatus: draft\n---\n")
        assert read_frontmatter(p) == {}

    def test_valid_frontmatter_parses(self, tmp_md):
        """Well-formed frontmatter is parsed correctly."""
        p = tmp_md('---\nid: "001"\n---\n')
        assert read_frontmatter(p) == {"id": "001"}

    def test_malformed_error_is_value_error_subclass(self, tmp_md):
        """MalformedFrontmatterError is a subclass of ValueError for backwards compat."""
        p = tmp_md("---bad\ncontent\n")
        with pytest.raises(ValueError):
            read_frontmatter(p)

    def test_read_document_malformed_raises(self, tmp_md):
        """read_document also raises MalformedFrontmatterError for corrupted fence."""
        p = tmp_md("---xyz\ncontent\n")
        with pytest.raises(MalformedFrontmatterError):
            read_document(p)


class TestWriteFrontmatter:
    def test_update_existing(self, tmp_md):
        p = tmp_md("---\nstatus: todo\n---\n# My Doc\n\nBody.\n")
        write_frontmatter(p, {"status": "done", "title": "My Doc"})
        fm, body = read_document(p)
        assert fm["status"] == "done"
        assert fm["title"] == "My Doc"
        assert "# My Doc" in body
        assert "Body." in body

    def test_create_new_file(self, tmp_path):
        p = tmp_path / "new.md"
        write_frontmatter(p, {"id": "001", "title": "New"})
        fm, body = read_document(p)
        assert fm == {"id": "001", "title": "New"}
        assert body == ""

    def test_round_trip(self, tmp_md):
        original_body = "# Sprint 001\n\nSome content here.\n"
        p = tmp_md(f"---\nid: \"001\"\ntitle: Test Sprint\nstatus: planning\n---\n{original_body}")
        fm, body = read_document(p)
        assert body == original_body
        fm["status"] = "active"
        write_frontmatter(p, fm)
        fm2, body2 = read_document(p)
        assert fm2["status"] == "active"
        assert fm2["id"] == "001"
        assert body2 == original_body

    def test_prepend_to_plain_file(self, tmp_md):
        p = tmp_md("Plain content.\n")
        write_frontmatter(p, {"status": "new"})
        fm, body = read_document(p)
        assert fm == {"status": "new"}
        assert body == "Plain content.\n"
