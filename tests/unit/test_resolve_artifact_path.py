"""Unit tests for resolve_artifact_path."""

from pathlib import Path

import pytest

from clasi.tools.artifact_tools import resolve_artifact_path


class TestResolveArtifactPath:
    def test_finds_file_at_original_location(self, tmp_path):
        f = tmp_path / "tickets" / "001-foo.md"
        f.parent.mkdir(parents=True)
        f.write_text("hello")

        assert resolve_artifact_path(str(f)) == f

    def test_finds_file_in_done_subdirectory(self, tmp_path):
        done_file = tmp_path / "tickets" / "done" / "001-foo.md"
        done_file.parent.mkdir(parents=True)
        done_file.write_text("hello")

        # Ask for the original (non-done) path
        original = tmp_path / "tickets" / "001-foo.md"
        assert resolve_artifact_path(str(original)) == done_file

    def test_finds_file_when_path_contains_done_but_file_moved_back(self, tmp_path):
        # File was moved out of done/ back to parent
        f = tmp_path / "tickets" / "001-foo.md"
        f.parent.mkdir(parents=True)
        f.write_text("hello")

        # Ask for the done/ path
        done_path = tmp_path / "tickets" / "done" / "001-foo.md"
        assert resolve_artifact_path(str(done_path)) == f

    def test_handles_path_already_in_done(self, tmp_path):
        done_file = tmp_path / "tickets" / "done" / "001-foo.md"
        done_file.parent.mkdir(parents=True)
        done_file.write_text("hello")

        # Ask for the done/ path directly — should find it as-is
        assert resolve_artifact_path(str(done_file)) == done_file

    def test_raises_file_not_found_error(self, tmp_path):
        missing = tmp_path / "tickets" / "nonexistent.md"
        with pytest.raises(FileNotFoundError, match="Artifact not found"):
            resolve_artifact_path(str(missing))

    def test_error_message_includes_path(self, tmp_path):
        missing = tmp_path / "tickets" / "nonexistent.md"
        with pytest.raises(FileNotFoundError, match="nonexistent.md"):
            resolve_artifact_path(str(missing))


class TestResolveArtifactPathRootAnchoring:
    """Ticket 029/005: a relative path anchors to project.root, not the
    process's own cwd. Proven by setting the process cwd to a directory
    that is not the project root and confirming a root-relative path
    still resolves.
    """

    def test_relative_path_anchors_to_project_root_not_process_cwd(
        self, tmp_path, monkeypatch
    ):
        from clasi.mcp_server import set_project

        project_root = tmp_path / "project"
        elsewhere = tmp_path / "elsewhere"
        project_root.mkdir()
        elsewhere.mkdir()

        ticket = project_root / "clasi" / "sprints" / "001-foo" / "tickets" / "001-bar.md"
        ticket.parent.mkdir(parents=True)
        ticket.write_text("hello", encoding="utf-8")

        set_project(project_root)
        monkeypatch.chdir(elsewhere)

        relative = "clasi/sprints/001-foo/tickets/001-bar.md"
        resolved = resolve_artifact_path(relative)
        assert resolved == ticket

    def test_relative_path_done_variant_anchors_to_project_root(
        self, tmp_path, monkeypatch
    ):
        from clasi.mcp_server import set_project

        project_root = tmp_path / "project"
        elsewhere = tmp_path / "elsewhere"
        project_root.mkdir()
        elsewhere.mkdir()

        done_ticket = (
            project_root
            / "clasi"
            / "sprints"
            / "001-foo"
            / "tickets"
            / "done"
            / "001-bar.md"
        )
        done_ticket.parent.mkdir(parents=True)
        done_ticket.write_text("hello", encoding="utf-8")

        set_project(project_root)
        monkeypatch.chdir(elsewhere)

        # Ask for the non-done path -- should still find the done/ variant,
        # resolved against project_root rather than the process cwd.
        relative = "clasi/sprints/001-foo/tickets/001-bar.md"
        resolved = resolve_artifact_path(relative)
        assert resolved == done_ticket
