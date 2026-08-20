"""Unit tests for frontmatter MCP tools."""

import json

import pytest

from clasi.tools.artifact_tools import (
    read_artifact_frontmatter,
    write_artifact_frontmatter,
)
from clasi.mcp_server import set_project


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    set_project(tmp_path)
    return tmp_path


class TestReadArtifactFrontmatter:
    def test_reads_frontmatter(self, work_dir):
        f = work_dir / "doc.md"
        f.write_text("---\ntitle: Hello\nstatus: active\n---\n\nBody.\n")

        result = json.loads(read_artifact_frontmatter(str(f)))
        assert result == {"title": "Hello", "status": "active"}

    def test_resolves_done_path(self, work_dir):
        done = work_dir / "tickets" / "done"
        done.mkdir(parents=True)
        f = done / "001.md"
        f.write_text("---\nid: '001'\n---\n\nBody.\n")

        # Ask for the non-done path
        original = work_dir / "tickets" / "001.md"
        result = json.loads(read_artifact_frontmatter(str(original)))
        assert result["id"] == "001"

    def test_no_frontmatter(self, work_dir):
        f = work_dir / "plain.md"
        f.write_text("Just text.\n")

        result = json.loads(read_artifact_frontmatter(str(f)))
        assert result == {}

    def test_error_on_missing_file(self, work_dir):
        """@clasi_tool (030/005) converts the domain ValueError into an
        {"ok": false, "error": ...} envelope instead of a raw MCP error."""
        result = json.loads(read_artifact_frontmatter(str(work_dir / "nonexistent.md")))
        assert result["ok"] is False
        assert "File not found" in result["error"]["message"]


class TestWriteArtifactFrontmatter:
    def test_merges_updates(self, work_dir):
        f = work_dir / "doc.md"
        f.write_text("---\ntitle: Hello\nstatus: active\n---\n\nBody.\n")

        result = json.loads(
            write_artifact_frontmatter(str(f), '{"status": "done"}')
        )
        assert result["updated_fields"] == ["status"]

        # Verify the file was updated
        content = f.read_text()
        assert "status: done" in content
        assert "title: Hello" in content
        assert "Body." in content

    def test_creates_frontmatter_on_plain_file(self, work_dir):
        f = work_dir / "plain.md"
        f.write_text("Just text.\n")

        write_artifact_frontmatter(str(f), '{"status": "new"}')

        content = f.read_text()
        assert content.startswith("---")
        assert "status: new" in content
        assert "Just text." in content

    def test_resolves_done_path(self, work_dir):
        done = work_dir / "tickets" / "done"
        done.mkdir(parents=True)
        f = done / "001.md"
        f.write_text("---\nid: '001'\n---\n\nBody.\n")

        original = work_dir / "tickets" / "001.md"
        write_artifact_frontmatter(str(original), '{"status": "done"}')

        content = f.read_text()
        assert "status: done" in content

    def test_error_on_missing_file(self, work_dir):
        """@clasi_tool (030/005) converts the domain ValueError into an
        {"ok": false, "error": ...} envelope instead of a raw MCP error."""
        result = json.loads(
            write_artifact_frontmatter(
                str(work_dir / "nonexistent.md"), '{"key": "value"}'
            )
        )
        assert result["ok"] is False
        assert "File not found" in result["error"]["message"]

    def test_error_on_invalid_json(self, work_dir):
        f = work_dir / "doc.md"
        f.write_text("---\ntitle: Hello\n---\n")

        result = json.loads(write_artifact_frontmatter(str(f), "not json"))
        assert result["ok"] is False
        assert "Invalid JSON" in result["error"]["message"]
