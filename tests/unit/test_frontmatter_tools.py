"""Unit tests for frontmatter MCP tools."""

import json

import pytest

from claude_agent_skills.artifact_tools import (
    read_artifact_frontmatter,
    write_artifact_frontmatter,
)
from claude_agent_skills.mcp_server import set_project


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
        with pytest.raises(ValueError, match="File not found"):
            read_artifact_frontmatter(str(work_dir / "nonexistent.md"))


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
        with pytest.raises(ValueError, match="File not found"):
            write_artifact_frontmatter(
                str(work_dir / "nonexistent.md"), '{"key": "value"}'
            )

    def test_error_on_invalid_json(self, work_dir):
        f = work_dir / "doc.md"
        f.write_text("---\ntitle: Hello\n---\n")

        with pytest.raises(ValueError, match="Invalid JSON"):
            write_artifact_frontmatter(str(f), "not json")
