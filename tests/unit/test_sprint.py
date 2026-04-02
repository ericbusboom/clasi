"""Tests for the Sprint class and Project sprint management."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

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


def _add_ticket(sprint_dir, ticket_id="001", title="Fix Bug", status="todo", done=False):
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
        assert t.status == "todo"
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
        assert t.todo_ref == "my-idea.md"

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
        assert t.todo_ref == "idea-a.md"

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
        assert t.todo_ref == "explicit.md"

    def test_create_ticket_no_todos_field_no_link(self, tmp_path):
        """When sprint.md has no todos field, no auto-linking happens."""
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        t = s.create_ticket("No Todos")
        assert t.todo_ref is None


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
        assert s.phase == "planning-docs"


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
        assert s.usecases.exists
        assert s.architecture.exists
        assert (s.path / "tickets").is_dir()
        assert (s.path / "tickets" / "done").is_dir()

    def test_create_sprint_increments_id(self, tmp_path):
        proj, _ = _make_sprint_dir(tmp_path)
        s2 = proj.create_sprint("Second Sprint")
        assert s2.id == "002"
