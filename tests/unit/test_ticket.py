"""Tests for the Ticket class."""

from pathlib import Path

from claude_agent_skills.project import Project
from claude_agent_skills.sprint import Sprint
from claude_agent_skills.ticket import Ticket


def _setup(tmp_path, ticket_id="001", title="Fix Bug", status="todo",
           depends_on=None, todo="", use_cases=None):
    """Create a project + sprint + ticket for testing."""
    proj = Project(tmp_path)
    sprint_dir = proj.sprints_dir / "001-test-sprint"
    sprint_dir.mkdir(parents=True)
    tickets_dir = sprint_dir / "tickets"
    tickets_dir.mkdir()
    (tickets_dir / "done").mkdir()

    (sprint_dir / "sprint.md").write_text(
        "---\nid: \"001\"\ntitle: \"Test Sprint\"\nstatus: active\n"
        "branch: sprint/001-test-sprint\n---\n# Sprint 001\n",
        encoding="utf-8",
    )

    deps = depends_on or []
    ucs = use_cases or []
    slug = title.lower().replace(" ", "-")
    ticket_path = tickets_dir / f"{ticket_id}-{slug}.md"
    deps_str = str(deps)
    ucs_str = str(ucs)
    todo_val = f'"{todo}"' if todo else '""'
    ticket_path.write_text(
        f"---\nid: \"{ticket_id}\"\ntitle: \"{title}\"\nstatus: {status}\n"
        f"use-cases: {ucs_str}\ndepends-on: {deps_str}\ntodo: {todo_val}\n---\n"
        f"# {title}\n\n## Description\n\nSome work.\n",
        encoding="utf-8",
    )

    sprint = Sprint(sprint_dir, proj)
    ticket = Ticket(ticket_path, sprint)
    return proj, sprint, ticket


class TestTicketProperties:
    """Test Ticket property accessors."""

    def test_id(self, tmp_path):
        _, _, t = _setup(tmp_path)
        assert t.id == "001"

    def test_title(self, tmp_path):
        _, _, t = _setup(tmp_path, title="Add Feature")
        assert t.title == "Add Feature"

    def test_status(self, tmp_path):
        _, _, t = _setup(tmp_path, status="in-progress")
        assert t.status == "in-progress"

    def test_default_status(self, tmp_path):
        _, _, t = _setup(tmp_path)
        assert t.status == "todo"

    def test_depends_on_empty(self, tmp_path):
        _, _, t = _setup(tmp_path)
        assert t.depends_on == []

    def test_depends_on_list(self, tmp_path):
        _, _, t = _setup(tmp_path, depends_on=["001", "002"])
        assert t.depends_on == ["001", "002"]

    def test_todo_ref_empty(self, tmp_path):
        _, _, t = _setup(tmp_path)
        assert t.todo_ref is None

    def test_todo_ref_set(self, tmp_path):
        _, _, t = _setup(tmp_path, todo="my-idea.md")
        assert t.todo_ref == "my-idea.md"

    def test_use_cases(self, tmp_path):
        _, _, t = _setup(tmp_path, use_cases=["UC-1", "UC-2"])
        assert t.use_cases == ["UC-1", "UC-2"]

    def test_sprint_reference(self, tmp_path):
        _, sprint, t = _setup(tmp_path)
        assert t.sprint is sprint

    def test_path(self, tmp_path):
        _, _, t = _setup(tmp_path)
        assert t.path.exists()
        assert t.path.name == "001-fix-bug.md"

    def test_frontmatter(self, tmp_path):
        _, _, t = _setup(tmp_path)
        fm = t.frontmatter
        assert "id" in fm
        assert "title" in fm

    def test_content(self, tmp_path):
        _, _, t = _setup(tmp_path)
        assert "## Description" in t.content


class TestTicketSetStatus:
    """Test set_status updates frontmatter."""

    def test_set_status(self, tmp_path):
        _, _, t = _setup(tmp_path, status="todo")
        assert t.status == "todo"
        t.set_status("in-progress")
        assert t.status == "in-progress"

    def test_set_status_preserves_content(self, tmp_path):
        _, _, t = _setup(tmp_path)
        original_content = t.content
        t.set_status("done")
        assert t.content == original_content


class TestTicketMoveToDone:
    """Test move_to_done moves file."""

    def test_move_to_done(self, tmp_path):
        _, _, t = _setup(tmp_path)
        old_path = t.path
        new_path = t.move_to_done()
        assert not old_path.exists()
        assert new_path.exists()
        assert new_path.parent.name == "done"
        assert t.path == new_path

    def test_move_to_done_already_in_done(self, tmp_path):
        _, _, t = _setup(tmp_path)
        first = t.move_to_done()
        # Moving again should be a no-op
        second = t.move_to_done()
        assert first == second
