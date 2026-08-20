"""Tests for clasi.frontmatter module."""

import os
import stat
import tempfile

import pytest
import yaml
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


class TestLineAnchoredDelimiter:
    """A '---' inside a frontmatter value must not be mistaken for the
    closing fence (frontmatter.py finding 12 / F11 in the reliability
    review). The old ``content.find("---", 3)`` matched the substring
    anywhere in the file; the fix must only match a line that is
    *exactly* ``---``.
    """

    def test_indented_dashes_inside_value_not_mistaken_for_fence(self, tmp_md):
        """yaml.safe_dump folds a multi-line string value using a quoted
        scalar whose continuation lines are indented — including, here, a
        line that is just the indented text '---'. A non-line-anchored
        search matches that occurrence (it's a substring) and slices the
        body starting mid-frontmatter. This is the exact raw shape
        yaml.safe_dump produces for a value containing an embedded
        horizontal rule.
        """
        content = (
            "---\n"
            "notes: 'Above the line.\n"
            "\n"
            "  ---\n"
            "\n"
            "  Below the line.\n"
            "\n"
            "  '\n"
            "title: Real Title\n"
            "---\n"
            "Real body.\n"
        )
        p = tmp_md(content)
        fm, body = read_document(p)
        assert fm["title"] == "Real Title"
        assert fm["notes"] == "Above the line.\n---\nBelow the line.\n"
        assert body == "Real body.\n"

    def test_round_trip_survives_dash_dash_dash_in_value(self, tmp_md):
        """A document with a '---' inside a frontmatter value must survive
        a full read-modify-write cycle intact: the value, and the body
        that follows it, must both be unchanged afterward.
        """
        original_body = "# Real Body\n\nThis must not be swallowed.\n"
        original_notes = "Above the line.\n---\nBelow the line.\n"
        p = tmp_md(original_body)

        write_frontmatter(p, {"title": "Real Title", "notes": original_notes})

        fm, body = read_document(p)
        assert body == original_body
        assert fm["title"] == "Real Title"
        assert fm["notes"] == original_notes

        # Read-modify-write again — the historical bug compounds on every
        # round trip, so a second pass is the real regression guard.
        fm["status"] = "done"
        write_frontmatter(p, fm)

        fm2, body2 = read_document(p)
        assert fm2["notes"] == original_notes
        assert fm2["status"] == "done"
        assert body2 == original_body


class TestAtomicWrite:
    """`_write_document` must write via temp-file + os.replace in the same
    directory, never truncate the target in place, and preserve the
    target's permission bits (F11 in the reliability review).
    """

    def test_crash_before_replace_leaves_original_untouched(self, tmp_md, monkeypatch):
        p = tmp_md("---\nstatus: todo\n---\nOriginal body.\n")
        original_content = p.read_text(encoding="utf-8")

        def boom(*args, **kwargs):
            raise RuntimeError("simulated crash mid-write")

        monkeypatch.setattr("clasi.frontmatter.os.replace", boom)

        with pytest.raises(RuntimeError, match="simulated crash"):
            write_frontmatter(p, {"status": "done"})

        # The original file must be byte-for-byte untouched...
        assert p.read_text(encoding="utf-8") == original_content
        # ...and the temp file must not be left behind either.
        leftovers = [f for f in p.parent.iterdir() if f != p]
        assert leftovers == []

    def test_temp_file_written_in_same_directory(self, tmp_md, monkeypatch):
        """os.replace is only atomic within a filesystem, so the temp file
        must be created in the same directory as the target."""
        p = tmp_md("---\nstatus: todo\n---\nBody.\n")
        seen_dirs = []
        real_mkstemp = tempfile.mkstemp

        def spy_mkstemp(*args, **kwargs):
            seen_dirs.append(kwargs.get("dir"))
            return real_mkstemp(*args, **kwargs)

        monkeypatch.setattr("clasi.frontmatter.tempfile.mkstemp", spy_mkstemp)

        write_frontmatter(p, {"status": "done"})

        assert seen_dirs
        assert Path(seen_dirs[0]) == p.parent

    def test_preserves_existing_file_permissions(self, tmp_md):
        p = tmp_md("---\nstatus: todo\n---\nBody.\n")
        os.chmod(p, 0o640)

        write_frontmatter(p, {"status": "done"})

        assert stat.S_IMODE(p.stat().st_mode) == 0o640

    def test_no_leftover_temp_file_on_success(self, tmp_md):
        p = tmp_md("---\nstatus: todo\n---\nBody.\n")
        write_frontmatter(p, {"status": "done"})
        leftovers = [f for f in p.parent.iterdir() if f != p]
        assert leftovers == []


class TestSafeDump:
    """`_write_document` must use yaml.safe_dump, not yaml.dump — dumping a
    type safe_dump doesn't know how to represent must raise loudly instead
    of silently round-tripping it through an unsafe !!python/object tag.
    """

    def test_unsafe_python_object_raises(self, tmp_md):
        class NotYamlSafe:
            """A type with no YAML representer registered under SafeDumper."""

        p = tmp_md("---\nstatus: todo\n---\nBody.\n")
        original_content = p.read_text(encoding="utf-8")

        with pytest.raises(yaml.representer.RepresenterError):
            write_frontmatter(p, {"bad": NotYamlSafe()})

        # The rejection must happen before any file I/O — the original
        # file is untouched.
        assert p.read_text(encoding="utf-8") == original_content

    def test_safe_types_still_dump_fine(self, tmp_md):
        """Sanity check: ordinary JSON-safe values are unaffected by the
        switch from yaml.dump to yaml.safe_dump."""
        p = tmp_md("---\nstatus: todo\n---\nBody.\n")
        write_frontmatter(
            p, {"status": "done", "count": 3, "tags": ["a", "b"], "ok": True}
        )
        fm, _ = read_document(p)
        assert fm == {"status": "done", "count": 3, "tags": ["a", "b"], "ok": True}
