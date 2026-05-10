"""Tests for the Sprint class and Project sprint management."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from clasi.artifact import Artifact
from clasi.project import Project
from clasi.sprint import Sprint, MergeConflictError


def _make_sprint_dir(tmp_path, sprint_id="001", title="Test Sprint", slug="test-sprint"):
    """Create a minimal sprint directory for testing."""
    proj = Project(tmp_path)
    sprint_dir = proj.sprints_dir / f"{sprint_id}-{slug}"
    sprint_dir.mkdir(parents=True)
    (sprint_dir / "tickets").mkdir()
    (sprint_dir / "tickets" / "done").mkdir()

    sprint_md = sprint_dir / "sprint.md"
    sprint_md.write_text(
        f"---\nid: \"{sprint_id}\"\ntitle: \"{title}\"\n"
        f"status: planning\nbranch: sprint/{sprint_id}-{slug}\n---\n"
        f"# Sprint {sprint_id}: {title}\n",
        encoding="utf-8",
    )
    return proj, sprint_dir


def _add_ticket(sprint_dir, ticket_id="001", title="Fix Bug", status="open", done=False):
    """Create a ticket file in the sprint."""
    subdir = sprint_dir / "tickets" / ("done" if done else "")
    subdir.mkdir(parents=True, exist_ok=True)
    slug = title.lower().replace(" ", "-")
    path = subdir / f"{ticket_id}-{slug}.md"
    path.write_text(
        f"---\nid: \"{ticket_id}\"\ntitle: \"{title}\"\nstatus: {status}\n"
        f"use-cases: []\ndepends-on: []\ntodo: \"\"\n---\n# {title}\n",
        encoding="utf-8",
    )
    return path


class TestSprintProperties:
    """Test Sprint property accessors."""

    def test_id(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.id == "001"

    def test_title(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path, title="My Sprint")
        s = Sprint(sprint_dir, proj)
        assert s.title == "My Sprint"

    def test_slug(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path, slug="my-sprint")
        s = Sprint(sprint_dir, proj)
        assert s.slug == "my-sprint"

    def test_branch(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.branch == "sprint/001-test-sprint"

    def test_status(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.status == "planning"

    def test_path(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.path == sprint_dir

    def test_project(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.project is proj


class TestSprintArtifacts:
    """Test named artifact properties."""

    def test_sprint_doc(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert isinstance(s.sprint_doc, Artifact)
        assert s.sprint_doc.path == sprint_dir / "sprint.md"
        assert s.sprint_doc.exists

    def test_usecases(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.usecases.path == sprint_dir / "usecases.md"

    def test_technical_plan(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.technical_plan.path == sprint_dir / "technical-plan.md"
        assert not s.technical_plan.exists  # Not created by default

    def test_architecture(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.architecture.path == sprint_dir / "architecture-update.md"


class TestSprintPathAccessors:
    """Test well-known file path accessors."""

    def test_sprint_md(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.sprint_md == sprint_dir / "sprint.md"

    def test_usecases_md(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.usecases_md == sprint_dir / "usecases.md"

    def test_architecture_update_md(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.architecture_update_md == sprint_dir / "architecture-update.md"

    def test_tickets_dir(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.tickets_dir == sprint_dir / "tickets"

    def test_tickets_done_dir(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.tickets_done_dir == sprint_dir / "tickets" / "done"

    def test_sprint_md_returns_path(self, tmp_path):
        """Path accessors return Path objects."""
        from pathlib import Path
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert isinstance(s.sprint_md, Path)
        assert isinstance(s.usecases_md, Path)
        assert isinstance(s.architecture_update_md, Path)
        assert isinstance(s.tickets_dir, Path)
        assert isinstance(s.tickets_done_dir, Path)

    def test_sprint_md_file_exists(self, tmp_path):
        """sprint_md points to the actual file created by _make_sprint_dir."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.sprint_md.exists()

    def test_tickets_dir_exists(self, tmp_path):
        """tickets_dir points to the actual directory created by _make_sprint_dir."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.tickets_dir.is_dir()

    def test_tickets_done_dir_exists(self, tmp_path):
        """tickets_done_dir points to the actual done/ directory."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.tickets_done_dir.is_dir()

    def test_issues_dir_returns_path(self, tmp_path):
        """issues_dir returns <sprint_path>/issues."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.issues_dir == sprint_dir / "issues"

    def test_issues_dir_is_path_type(self, tmp_path):
        """issues_dir returns a Path object."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert isinstance(s.issues_dir, Path)


class TestSprintToDict:
    """Test Sprint.to_dict() serialization."""

    def test_to_dict_returns_dict(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        result = s.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_has_required_keys(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        result = s.to_dict()
        assert "id" in result
        assert "path" in result
        assert "branch" in result
        assert "files" in result
        assert "phase" in result

    def test_to_dict_values_are_strings(self, tmp_path):
        """All path values must be strings, not Path objects."""
        from pathlib import Path
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        result = s.to_dict()
        assert isinstance(result["path"], str)
        for v in result["files"].values():
            assert isinstance(v, str)
            assert not isinstance(v, Path)

    def test_to_dict_correct_values(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        result = s.to_dict()
        assert result["id"] == "001"
        assert result["branch"] == "sprint/001-test-sprint"
        assert result["path"] == str(sprint_dir)

    def test_to_dict_files_contains_sprint_artifacts(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        result = s.to_dict()
        assert "sprint.md" in result["files"]
        assert "usecases.md" in result["files"]
        assert "architecture-update.md" in result["files"]

    def test_to_dict_is_json_serializable(self, tmp_path):
        """to_dict() output must be json.dumps-safe."""
        import json
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        result = s.to_dict()
        # Should not raise
        serialized = json.dumps(result)
        assert '"id"' in serialized


class TestSprintTickets:
    """Test ticket management methods."""

    def test_list_tickets_empty(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.list_tickets() == []

    def test_list_tickets(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_ticket(sprint_dir, "001", "First")
        _add_ticket(sprint_dir, "002", "Second")
        s = Sprint(sprint_dir, proj)
        tickets = s.list_tickets()
        assert len(tickets) == 2

    def test_list_tickets_includes_done(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_ticket(sprint_dir, "001", "Active", status="in-progress")
        _add_ticket(sprint_dir, "002", "Done", status="done", done=True)
        s = Sprint(sprint_dir, proj)
        all_tickets = s.list_tickets()
        assert len(all_tickets) == 2

    def test_list_tickets_filter_status(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_ticket(sprint_dir, "001", "Active", status="in-progress")
        _add_ticket(sprint_dir, "002", "Done", status="done", done=True)
        s = Sprint(sprint_dir, proj)
        done_tickets = s.list_tickets(status="done")
        assert len(done_tickets) == 1
        assert done_tickets[0].status == "done"

    def test_get_ticket(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_ticket(sprint_dir, "001", "Fix Bug")
        s = Sprint(sprint_dir, proj)
        t = s.get_ticket("001")
        assert t.id == "001"
        assert t.title == "Fix Bug"

    def test_get_ticket_not_found(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        try:
            s.get_ticket("999")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_create_ticket(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        t = s.create_ticket("New Feature")
        assert t.id == "001"
        assert t.title == "New Feature"
        assert t.status == "open"
        assert t.path.exists()

    def test_create_ticket_increments_id(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_ticket(sprint_dir, "001", "First")
        s = Sprint(sprint_dir, proj)
        t = s.create_ticket("Second")
        assert t.id == "002"

    def test_create_ticket_with_todo(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        t = s.create_ticket("With Todo", todo="my-idea.md")
        assert t.issue_ref == "my-idea.md"

    def test_create_ticket_auto_links_sprint_todos(self, tmp_path):
        """When no todo param given, auto-link from sprint.md todos field."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        # Add todos field to sprint.md frontmatter
        sprint_md = sprint_dir / "sprint.md"
        sprint_md.write_text(
            '---\nid: "001"\ntitle: "Test Sprint"\n'
            "status: planning\nbranch: sprint/001-test-sprint\n"
            "todos:\n- idea-a.md\n---\n# Sprint 001\n",
            encoding="utf-8",
        )
        s = Sprint(sprint_dir, proj)
        t = s.create_ticket("Auto Linked")
        assert t.issue_ref == "idea-a.md"

    def test_create_ticket_explicit_todo_not_overridden(self, tmp_path):
        """Explicit todo param should NOT be overridden by sprint todos."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        sprint_md = sprint_dir / "sprint.md"
        sprint_md.write_text(
            '---\nid: "001"\ntitle: "Test Sprint"\n'
            "status: planning\nbranch: sprint/001-test-sprint\n"
            "todos:\n- idea-a.md\n- idea-b.md\n---\n# Sprint 001\n",
            encoding="utf-8",
        )
        s = Sprint(sprint_dir, proj)
        t = s.create_ticket("Explicit Todo", todo="explicit.md")
        assert t.issue_ref == "explicit.md"

    def test_create_ticket_no_todos_field_no_link(self, tmp_path):
        """When sprint.md has no todos field, no auto-linking happens."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        t = s.create_ticket("No Todos")
        assert t.issue_ref is None


def _add_issue(sprint_dir, filename="my-issue.md", status="pending"):
    """Create an issue file in <sprint_dir>/issues/."""
    issues_dir = sprint_dir / "issues"
    issues_dir.mkdir(parents=True, exist_ok=True)
    path = issues_dir / filename
    path.write_text(
        f"---\nstatus: {status}\n---\n# Issue {filename}\n",
        encoding="utf-8",
    )
    return path


class TestSprintIssues:
    """Tests for Sprint.issues_dir and Sprint.list_issues()."""

    def test_list_issues_empty_when_no_dir(self, tmp_path):
        """list_issues() returns [] when issues/ does not exist."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        assert s.list_issues() == []

    def test_list_issues_empty_dir(self, tmp_path):
        """list_issues() returns [] when issues/ exists but has no .md files."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        (sprint_dir / "issues").mkdir()
        s = Sprint(sprint_dir, proj)
        assert s.list_issues() == []

    def test_list_issues_returns_issue_objects(self, tmp_path):
        """list_issues() returns Issue instances."""
        from clasi.issue import Issue
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_issue(sprint_dir, "issue-a.md")
        s = Sprint(sprint_dir, proj)
        issues = s.list_issues()
        assert len(issues) == 1
        assert isinstance(issues[0], Issue)

    def test_list_issues_multiple_files(self, tmp_path):
        """list_issues() returns one Issue per .md file, sorted by name."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_issue(sprint_dir, "aaa.md")
        _add_issue(sprint_dir, "bbb.md")
        _add_issue(sprint_dir, "ccc.md")
        s = Sprint(sprint_dir, proj)
        issues = s.list_issues()
        assert len(issues) == 3
        assert [i.path.name for i in issues] == ["aaa.md", "bbb.md", "ccc.md"]

    def test_list_issues_issue_path_correct(self, tmp_path):
        """Returned Issue objects have correct path."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_issue(sprint_dir, "my-issue.md")
        s = Sprint(sprint_dir, proj)
        issue = s.list_issues()[0]
        assert issue.path == sprint_dir / "issues" / "my-issue.md"

    def test_list_issues_ignores_non_md_files(self, tmp_path):
        """list_issues() only picks up .md files."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        issues_dir = sprint_dir / "issues"
        issues_dir.mkdir()
        (issues_dir / "note.txt").write_text("plain text", encoding="utf-8")
        _add_issue(sprint_dir, "real.md")
        s = Sprint(sprint_dir, proj)
        issues = s.list_issues()
        assert len(issues) == 1
        assert issues[0].path.name == "real.md"


class TestSprintPhase:
    """Test phase from DB."""

    def test_phase_fallback_unknown(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        # No DB initialized, should fallback
        assert s.phase == "unknown"

    def test_phase_from_done_directory(self, tmp_path):
        proj = Project(tmp_path)
        done_dir = proj.sprints_dir / "done" / "001-test"
        done_dir.mkdir(parents=True)
        (done_dir / "sprint.md").write_text(
            "---\nid: \"001\"\ntitle: \"Test\"\nstatus: done\n"
            "branch: sprint/001-test\n---\n# Test\n",
            encoding="utf-8",
        )
        s = Sprint(done_dir, proj)
        assert s.phase == "done"

    def test_phase_from_db(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        proj.clasi_dir.mkdir(parents=True, exist_ok=True)
        proj.db.init()
        proj.db.register_sprint("001", "test-sprint", "sprint/001-test-sprint")
        s = Sprint(sprint_dir, proj)
        assert s.phase == "roadmap"


class TestProjectSprints:
    """Test Project.get_sprint, list_sprints, create_sprint."""

    def test_get_sprint(self, tmp_path):
        proj, _ = _make_sprint_dir(tmp_path)
        s = proj.get_sprint("001")
        assert s.id == "001"

    def test_get_sprint_not_found(self, tmp_path):
        proj = Project(tmp_path)
        proj.sprints_dir.mkdir(parents=True)
        try:
            proj.get_sprint("999")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_list_sprints(self, tmp_path):
        proj, _ = _make_sprint_dir(tmp_path, "001", "First", "first")
        # Add a second sprint
        sd2 = proj.sprints_dir / "002-second"
        sd2.mkdir()
        (sd2 / "sprint.md").write_text(
            "---\nid: \"002\"\ntitle: \"Second\"\nstatus: active\n"
            "branch: sprint/002-second\n---\n# Sprint 002\n",
            encoding="utf-8",
        )
        sprints = proj.list_sprints()
        assert len(sprints) == 2

    def test_list_sprints_filter_status(self, tmp_path):
        proj, _ = _make_sprint_dir(tmp_path, "001", "First", "first")
        sd2 = proj.sprints_dir / "002-second"
        sd2.mkdir()
        (sd2 / "sprint.md").write_text(
            "---\nid: \"002\"\ntitle: \"Second\"\nstatus: active\n"
            "branch: sprint/002-second\n---\n# Sprint 002\n",
            encoding="utf-8",
        )
        active = proj.list_sprints(status="active")
        assert len(active) == 1
        assert active[0].id == "002"

    def test_create_sprint(self, tmp_path):
        proj = Project(tmp_path)
        proj.sprints_dir.mkdir(parents=True)
        s = proj.create_sprint("My New Sprint")
        assert s.id == "001"
        assert s.title == "My New Sprint"
        assert s.sprint_doc.exists
        # Lightweight roadmap-phase sprint: only sprint.md is written
        assert not s.usecases.exists
        assert not s.architecture.exists
        assert not (s.path / "tickets").exists()

    def test_create_sprint_writes_only_sprint_md(self, tmp_path):
        """After create_sprint(), the sprint directory contains only sprint.md."""
        proj = Project(tmp_path)
        proj.sprints_dir.mkdir(parents=True)
        s = proj.create_sprint("Lightweight Sprint")
        files = list(s.path.iterdir())
        assert len(files) == 1, f"Expected only sprint.md, got: {[f.name for f in files]}"
        assert files[0].name == "sprint.md"

    def test_create_sprint_increments_id(self, tmp_path):
        proj, _ = _make_sprint_dir(tmp_path)
        s2 = proj.create_sprint("Second Sprint")
        assert s2.id == "002"

    def test_create_sprint_status_roadmap(self, tmp_path):
        """sprint.md written by create_sprint has status: roadmap in frontmatter."""
        from clasi.frontmatter import read_frontmatter

        proj = Project(tmp_path)
        proj.sprints_dir.mkdir(parents=True)
        s = proj.create_sprint("Roadmap Sprint")
        fm = read_frontmatter(s.sprint_md)
        assert fm.get("status") == "roadmap"


# ---------------------------------------------------------------------------
# Helpers to set up a sprint registered in the state DB (roadmap phase)
# ---------------------------------------------------------------------------


def _make_roadmap_sprint(tmp_path, sprint_id="001", title="Test Sprint", slug="test-sprint"):
    """Create a sprint directory and register it in the DB at roadmap phase."""
    proj = Project(tmp_path)
    proj.sprints_dir.mkdir(parents=True, exist_ok=True)
    proj.clasi_dir.mkdir(parents=True, exist_ok=True)
    proj.db.init()

    sprint_dir = proj.sprints_dir / f"{sprint_id}-{slug}"
    sprint_dir.mkdir(parents=True)

    sprint_md = sprint_dir / "sprint.md"
    sprint_md.write_text(
        f"---\nid: \"{sprint_id}\"\ntitle: \"{title}\"\n"
        f"status: roadmap\nbranch: sprint/{sprint_id}-{slug}\n---\n"
        f"# Sprint {sprint_id}: {title}\n",
        encoding="utf-8",
    )

    proj.db.register_sprint(sprint_id, slug, branch=f"sprint/{sprint_id}-{slug}")
    return proj, sprint_dir


class TestDetailPromote:
    """Tests for Sprint.detail_promote()."""

    def test_detail_promote_scaffolds_artifacts(self, tmp_path):
        """detail_promote() writes usecases.md, architecture-update.md, tickets/, tickets/done/.

        After promotion the sprint phase must be 'planning-docs'.
        """
        proj, sprint_dir = _make_roadmap_sprint(tmp_path)
        s = Sprint(sprint_dir, proj)

        result = s.detail_promote()

        # Return value
        assert result["sprint_id"] == "001"
        assert result["phase"] == "planning-docs"
        assert len(result["files_written"]) == 2

        # Artifact files exist
        assert (sprint_dir / "usecases.md").exists()
        assert (sprint_dir / "architecture-update.md").exists()

        # Directory structure created
        assert (sprint_dir / "tickets").is_dir()
        assert (sprint_dir / "tickets" / "done").is_dir()

        # Phase advanced in DB
        assert s.phase == "planning-docs"

    def test_detail_promote_rejects_non_roadmap(self, tmp_path):
        """detail_promote() raises ValueError when sprint is not in roadmap phase."""
        proj, sprint_dir = _make_roadmap_sprint(tmp_path)
        s = Sprint(sprint_dir, proj)

        # Advance past roadmap -> planning-docs
        proj.db.advance_phase("001")

        with pytest.raises(ValueError, match="not in roadmap phase"):
            s.detail_promote()

    def test_detail_promote_idempotent_guard(self, tmp_path):
        """detail_promote() raises ValueError when usecases.md already exists."""
        proj, sprint_dir = _make_roadmap_sprint(tmp_path)
        s = Sprint(sprint_dir, proj)

        # Manually pre-create usecases.md to simulate a partially-promoted sprint
        (sprint_dir / "usecases.md").write_text(
            "---\nstatus: draft\n---\n# Use Cases\n", encoding="utf-8"
        )

        with pytest.raises(ValueError, match="already detail-planned"):
            s.detail_promote()


# ---------------------------------------------------------------------------
# Helpers for git method tests
# ---------------------------------------------------------------------------


def _make_run_result(returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
    """Build a fake subprocess.CompletedProcess-like result."""
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class TestSprintCreateBranch:
    """Tests for Sprint.create_branch()."""

    def test_create_branch_success(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.return_value = _make_run_result(0)
            branch = s.create_branch()
        assert branch == "sprint/001-test-sprint"
        mock_run.assert_called_once_with(
            ["git", "checkout", "-b", "sprint/001-test-sprint"],
            capture_output=True,
            text=True,
        )

    def test_create_branch_already_exists_falls_back_to_checkout(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _make_run_result(1, stderr="already exists"),  # checkout -b fails
                _make_run_result(0),  # checkout succeeds
            ]
            branch = s.create_branch()
        assert branch == "sprint/001-test-sprint"
        assert mock_run.call_count == 2

    def test_create_branch_raises_on_failure(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _make_run_result(1, stderr="error A"),
                _make_run_result(1, stderr="error B"),
            ]
            try:
                s.create_branch()
                assert False, "Expected RuntimeError"
            except RuntimeError as e:
                assert "sprint/001-test-sprint" in str(e)
                assert "error B" in str(e)

    def test_create_branch_raises_when_no_branch_in_frontmatter(self, tmp_path):
        proj = Project(tmp_path)
        sprint_dir = proj.sprints_dir / "001-no-branch"
        sprint_dir.mkdir(parents=True)
        (sprint_dir / "sprint.md").write_text(
            "---\nid: \"001\"\ntitle: \"No Branch\"\nstatus: planning\n---\n",
            encoding="utf-8",
        )
        s = Sprint(sprint_dir, proj)
        try:
            s.create_branch()
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "no 'branch' field" in str(e)


class TestSprintMergeBranch:
    """Tests for Sprint.merge_branch()."""

    def test_merge_branch_success(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _make_run_result(0),  # git rev-parse --verify (branch exists)
                _make_run_result(1),  # git merge-base --is-ancestor (not yet merged)
                _make_run_result(0),  # git rebase master sprint/001-test-sprint
                _make_run_result(0),  # git checkout master
                _make_run_result(0),  # git merge --no-ff
            ]
            result = s.merge_branch("master")
        assert result["merged"] is True
        assert result["already_merged"] is False
        assert result["branch_exists"] is True

    def test_merge_branch_branch_already_gone(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.return_value = _make_run_result(1)  # rev-parse: branch gone
            result = s.merge_branch("master")
        assert result["merged"] is True
        assert result["already_merged"] is True
        assert result["branch_exists"] is False

    def test_merge_branch_already_ancestor(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _make_run_result(0),  # rev-parse: branch exists
                _make_run_result(0),  # merge-base: already ancestor
            ]
            result = s.merge_branch("master")
        assert result["merged"] is True
        assert result["already_merged"] is True
        assert result["branch_exists"] is True

    def test_merge_branch_rebase_failure_raises(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _make_run_result(0),  # rev-parse: branch exists
                _make_run_result(1),  # merge-base: not ancestor
                _make_run_result(1, stderr="rebase conflict"),  # rebase fails
                _make_run_result(0),  # git rebase --abort
            ]
            try:
                s.merge_branch("master")
                assert False, "Expected RuntimeError"
            except RuntimeError as e:
                assert "Rebase of" in str(e)
                assert "rebase conflict" in str(e)

    def test_merge_branch_conflict_raises_merge_conflict_error(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _make_run_result(0),  # rev-parse: branch exists
                _make_run_result(1),  # merge-base: not ancestor
                _make_run_result(0),  # git rebase master sprint/001-test-sprint
                _make_run_result(0),  # checkout master
                _make_run_result(1, stderr="Automatic merge failed"),  # git merge --no-ff
                _make_run_result(0, stdout="foo.py\nbar.py\n"),  # git diff
                _make_run_result(0),  # git merge --abort
            ]
            try:
                s.merge_branch("master")
                assert False, "Expected MergeConflictError"
            except MergeConflictError as e:
                assert "Merge conflict" in str(e)
                assert "foo.py" in e.conflicted_files
                assert "bar.py" in e.conflicted_files

    def test_merge_conflict_error_is_subclass_of_runtime_error(self, tmp_path):
        err = MergeConflictError("test", conflicted_files=["a.py"])
        assert isinstance(err, RuntimeError)
        assert err.conflicted_files == ["a.py"]

    def test_merge_branch_checkout_failure_raises(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _make_run_result(0),  # rev-parse: branch exists
                _make_run_result(1),  # merge-base: not ancestor
                _make_run_result(0),  # git rebase master sprint/001-test-sprint
                _make_run_result(1, stderr="not a git repo"),  # checkout fails
            ]
            try:
                s.merge_branch("master")
                assert False, "Expected RuntimeError"
            except RuntimeError as e:
                assert "Failed to checkout" in str(e)

    def test_merge_branch_raises_when_no_branch_in_frontmatter(self, tmp_path):
        proj = Project(tmp_path)
        sprint_dir = proj.sprints_dir / "001-no-branch"
        sprint_dir.mkdir(parents=True)
        (sprint_dir / "sprint.md").write_text(
            "---\nid: \"001\"\ntitle: \"No Branch\"\nstatus: planning\n---\n",
            encoding="utf-8",
        )
        s = Sprint(sprint_dir, proj)
        try:
            s.merge_branch()
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "no 'branch' field" in str(e)

    def test_merge_branch_rebase_produces_linear_history(self, tmp_path):
        """Integration test: rebase before --no-ff merge yields linear history.

        Uses a real git repo in tmp_path to verify that after merge_branch()
        the sprint commit appears on the first-parent chain of master.
        """
        import os
        import subprocess as sp

        git = lambda *args: sp.run(  # noqa: E731
            ["git", *args], capture_output=True, text=True, cwd=tmp_path, check=True
        )

        # Bootstrap a git repo with a single commit on master.
        git("init", "-b", "master")
        git("config", "user.email", "test@example.com")
        git("config", "user.name", "Test")
        (tmp_path / "base.txt").write_text("base", encoding="utf-8")
        git("add", "base.txt")
        git("commit", "-m", "initial commit")

        # Create sprint branch and add a commit on it.
        sprint_branch = "sprint/001-test-sprint"
        git("checkout", "-b", sprint_branch)
        (tmp_path / "sprint.txt").write_text("sprint work", encoding="utf-8")
        git("add", "sprint.txt")
        git("commit", "-m", "sprint commit")

        # Switch back to master and add a diverging commit.
        git("checkout", "master")
        (tmp_path / "master-extra.txt").write_text("master work", encoding="utf-8")
        git("add", "master-extra.txt")
        git("commit", "-m", "master diverge commit")

        # Build a Sprint object pointing at a sprint dir within tmp_path.
        proj = Project(tmp_path)
        sprint_dir = proj.sprints_dir / "001-test-sprint"
        sprint_dir.mkdir(parents=True)
        (sprint_dir / "tickets").mkdir()
        (sprint_dir / "tickets" / "done").mkdir()
        (sprint_dir / "sprint.md").write_text(
            f"---\nid: \"001\"\ntitle: \"Test Sprint\"\n"
            f"status: active\nbranch: {sprint_branch}\n---\n# Sprint 001\n",
            encoding="utf-8",
        )
        s = Sprint(sprint_dir, proj)

        # merge_branch() calls subprocess.run without cwd, so it operates on
        # the process's working directory.  Change into the test repo so that
        # all git commands target it.
        orig_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = s.merge_branch("master")
        finally:
            os.chdir(orig_dir)

        assert result["merged"] is True
        assert result["already_merged"] is False

        # Verify the merge commit appears on master's first-parent chain and
        # the sprint commit is reachable from master's full history.
        first_parent_log = sp.run(
            ["git", "log", "--oneline", "--first-parent", "master"],
            capture_output=True, text=True, cwd=tmp_path, check=True,
        )
        fp_subjects = [
            line.split(" ", 1)[1]
            for line in first_parent_log.stdout.strip().splitlines()
        ]
        assert any("sprint/001-test-sprint" in subj for subj in fp_subjects), (
            f"Merge commit not found in first-parent log: {fp_subjects}"
        )

        full_log = sp.run(
            ["git", "log", "--oneline", "master"],
            capture_output=True, text=True, cwd=tmp_path, check=True,
        )
        full_subjects = [
            line.split(" ", 1)[1]
            for line in full_log.stdout.strip().splitlines()
        ]
        assert any("sprint commit" in subj for subj in full_subjects), (
            f"Sprint commit not reachable from master: {full_subjects}"
        )


class TestSprintDeleteBranch:
    """Tests for Sprint.delete_branch()."""

    def test_delete_branch_success(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _make_run_result(0),  # rev-parse: branch exists
                _make_run_result(0),  # git branch -d succeeds
            ]
            deleted = s.delete_branch()
        assert deleted is True

    def test_delete_branch_not_present(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.return_value = _make_run_result(1)  # rev-parse: doesn't exist
            deleted = s.delete_branch()
        assert deleted is False

    def test_delete_branch_raises_on_git_failure(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _make_run_result(0),  # rev-parse: branch exists
                _make_run_result(1, stderr="not fully merged"),  # git branch -d fails
            ]
            try:
                s.delete_branch()
                assert False, "Expected RuntimeError"
            except RuntimeError as e:
                assert "Failed to delete branch" in str(e)
                assert "not fully merged" in str(e)

    def test_delete_branch_raises_when_no_branch_in_frontmatter(self, tmp_path):
        proj = Project(tmp_path)
        sprint_dir = proj.sprints_dir / "001-no-branch"
        sprint_dir.mkdir(parents=True)
        (sprint_dir / "sprint.md").write_text(
            "---\nid: \"001\"\ntitle: \"No Branch\"\nstatus: planning\n---\n",
            encoding="utf-8",
        )
        s = Sprint(sprint_dir, proj)
        try:
            s.delete_branch()
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "no 'branch' field" in str(e)


class TestSprintTicketCounts:
    """Tests for Sprint.ticket_counts()."""

    def test_ticket_counts_empty(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        counts = s.ticket_counts()
        assert counts == {"open": 0, "in_progress": 0, "done": 0}

    def test_ticket_counts_with_todo_tickets(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_ticket(sprint_dir, "001", "First", status="open")
        _add_ticket(sprint_dir, "002", "Second", status="open")
        s = Sprint(sprint_dir, proj)
        counts = s.ticket_counts()
        assert counts["open"] == 2
        assert counts["in_progress"] == 0
        assert counts["done"] == 0

    def test_ticket_counts_mixed_statuses(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_ticket(sprint_dir, "001", "Open", status="open")
        _add_ticket(sprint_dir, "002", "In Progress", status="in-progress")
        _add_ticket(sprint_dir, "003", "Done", status="done", done=True)
        s = Sprint(sprint_dir, proj)
        counts = s.ticket_counts()
        assert counts["open"] == 1
        assert counts["in_progress"] == 1
        assert counts["done"] == 1

    def test_ticket_counts_returns_in_progress_key(self, tmp_path):
        """Status 'in-progress' maps to 'in_progress' key."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_ticket(sprint_dir, "001", "In Progress", status="in-progress")
        s = Sprint(sprint_dir, proj)
        counts = s.ticket_counts()
        assert "in_progress" in counts
        assert counts["in_progress"] == 1

    def test_ticket_counts_includes_done_dir(self, tmp_path):
        """Counts include tickets in tickets/done/ directory."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_ticket(sprint_dir, "001", "Done", status="done", done=True)
        s = Sprint(sprint_dir, proj)
        counts = s.ticket_counts()
        assert counts["done"] == 1


class TestSprintArchive:
    """Tests for Sprint.archive()."""

    def test_archive_moves_to_done(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        result = s.archive()
        assert not sprint_dir.exists()
        done_dir = proj.sprints_dir / "done" / sprint_dir.name
        assert done_dir.exists()
        assert result["new_path"] == str(done_dir)
        assert result["old_path"] == str(sprint_dir)

    def test_archive_updates_status(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        s.archive()
        # After archiving, read frontmatter from new location
        new_sprint_md = proj.sprints_dir / "done" / sprint_dir.name / "sprint.md"
        from clasi.frontmatter import read_frontmatter
        fm = read_frontmatter(new_sprint_md)
        assert fm.get("status") == "done"

    def test_archive_updates_path(self, tmp_path):
        """Sprint._path is updated to the archived location."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        s.archive()
        assert s.path.parent.name == "done"

    def test_archive_copies_architecture_update(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        arch_update = sprint_dir / "architecture-update.md"
        arch_update.write_text("---\nstatus: final\n---\n# Update\n", encoding="utf-8")
        s = Sprint(sprint_dir, proj)
        s.archive()
        arch_dir = proj.clasi_dir / "architecture"
        dest = arch_dir / "architecture-update-001.md"
        assert dest.exists()

    def test_archive_raises_if_destination_exists(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        # Pre-create the destination
        done_dir = proj.sprints_dir / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        (done_dir / sprint_dir.name).mkdir()
        s = Sprint(sprint_dir, proj)
        try:
            s.archive()
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "already exists" in str(e)

    def test_archive_no_architecture_update_ok(self, tmp_path):
        """archive() succeeds even if architecture-update.md does not exist."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        # No architecture-update.md was created, should not raise
        result = s.archive()
        assert "new_path" in result

    def test_archive_carries_issues_dir(self, tmp_path):
        """archive() moves the entire sprint dir; issues/ travels with it."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        # Create issues/ subdir with a file
        issues_dir = sprint_dir / "issues"
        issues_dir.mkdir()
        issue_file = issues_dir / "my-issue.md"
        issue_file.write_text(
            "---\nstatus: in-progress\n---\n# My Issue\n", encoding="utf-8"
        )
        s = Sprint(sprint_dir, proj)
        s.archive()

        # The original location must be gone
        assert not sprint_dir.exists()

        # The issues dir must exist under done/<sprint>/issues/
        done_sprint_dir = proj.sprints_dir / "done" / sprint_dir.name
        done_issues_dir = done_sprint_dir / "issues"
        assert done_issues_dir.is_dir(), "issues/ was not carried to done/"
        assert (done_issues_dir / "my-issue.md").exists(), (
            "issue file was not carried to done/"
        )

    def test_archive_issues_accessible_via_sprint_after_archive(self, tmp_path):
        """After archive(), Sprint.list_issues() finds the moved issue files."""
        from clasi.issue import Issue
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        issues_dir = sprint_dir / "issues"
        issues_dir.mkdir()
        (issues_dir / "ticket-issue.md").write_text(
            "---\nstatus: in-progress\n---\n# Ticket Issue\n", encoding="utf-8"
        )
        s = Sprint(sprint_dir, proj)
        s.archive()

        # Sprint._path was updated; list_issues() should see the archived file
        issues = s.list_issues()
        assert len(issues) == 1
        assert isinstance(issues[0], Issue)
        assert "done" in str(issues[0].path)
