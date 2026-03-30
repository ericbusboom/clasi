"""Tests for the Todo class."""

from pathlib import Path

from claude_agent_skills.project import Project
from claude_agent_skills.todo import Todo


def _make_todo(tmp_path, filename="my-idea.md", title="My Idea",
               status="pending", sprint=None, tickets=None, source=None):
    """Create a project with a TODO file."""
    proj = Project(tmp_path)

    if status == "in-progress":
        todo_dir = proj.todo_dir / "in-progress"
    elif status == "done":
        todo_dir = proj.todo_dir / "done"
    else:
        todo_dir = proj.todo_dir
    todo_dir.mkdir(parents=True, exist_ok=True)

    fm_lines = [f"status: {status}"]
    if sprint:
        fm_lines.append(f"sprint: \"{sprint}\"")
    if tickets:
        fm_lines.append(f"tickets: {tickets}")
    if source:
        fm_lines.append(f"source: \"{source}\"")
    fm_str = "\n".join(fm_lines)

    path = todo_dir / filename
    path.write_text(
        f"---\n{fm_str}\n---\n# {title}\n\nSome description.\n",
        encoding="utf-8",
    )

    todo = Todo(path, proj)
    return proj, todo


class TestTodoProperties:
    """Test Todo property accessors."""

    def test_title_from_heading(self, tmp_path):
        _, t = _make_todo(tmp_path, title="Great Idea")
        assert t.title == "Great Idea"

    def test_title_fallback_to_stem(self, tmp_path):
        proj = Project(tmp_path)
        proj.todo_dir.mkdir(parents=True)
        path = proj.todo_dir / "no-heading.md"
        path.write_text("---\nstatus: pending\n---\nNo heading here.\n", encoding="utf-8")
        t = Todo(path, proj)
        assert t.title == "no-heading"

    def test_status_pending(self, tmp_path):
        _, t = _make_todo(tmp_path, status="pending")
        assert t.status == "pending"

    def test_status_in_progress(self, tmp_path):
        _, t = _make_todo(tmp_path, status="in-progress")
        assert t.status == "in-progress"

    def test_sprint_none(self, tmp_path):
        _, t = _make_todo(tmp_path)
        assert t.sprint is None

    def test_sprint_set(self, tmp_path):
        _, t = _make_todo(tmp_path, status="in-progress", sprint="001")
        assert t.sprint == "001"

    def test_tickets_empty(self, tmp_path):
        _, t = _make_todo(tmp_path)
        assert t.tickets == []

    def test_tickets_list(self, tmp_path):
        _, t = _make_todo(tmp_path, status="in-progress",
                          sprint="001", tickets='["001-001", "001-002"]')
        assert t.tickets == ["001-001", "001-002"]

    def test_source(self, tmp_path):
        _, t = _make_todo(tmp_path, source="https://example.com")
        assert t.source == "https://example.com"

    def test_source_none(self, tmp_path):
        _, t = _make_todo(tmp_path)
        assert t.source is None

    def test_path(self, tmp_path):
        _, t = _make_todo(tmp_path, filename="test.md")
        assert t.path.name == "test.md"

    def test_frontmatter(self, tmp_path):
        _, t = _make_todo(tmp_path)
        assert "status" in t.frontmatter

    def test_content(self, tmp_path):
        _, t = _make_todo(tmp_path)
        assert "Some description." in t.content


class TestTodoMoveToInProgress:
    """Test move_to_in_progress."""

    def test_move_updates_frontmatter(self, tmp_path):
        _, t = _make_todo(tmp_path, status="pending")
        t.move_to_in_progress("001", "001-001")
        assert t.status == "in-progress"
        assert t.sprint == "001"
        assert "001-001" in t.tickets

    def test_move_changes_directory(self, tmp_path):
        proj, t = _make_todo(tmp_path, status="pending")
        old_dir = t.path.parent
        t.move_to_in_progress("001", "001-001")
        assert t.path.parent == proj.todo_dir / "in-progress"
        assert t.path.exists()

    def test_move_already_in_progress(self, tmp_path):
        proj, t = _make_todo(tmp_path, status="in-progress", sprint="001")
        # Should not raise, just update
        t.move_to_in_progress("001", "001-002")
        assert t.path.parent == proj.todo_dir / "in-progress"
        assert "001-002" in t.tickets


class TestTodoMoveToDone:
    """Test move_to_done."""

    def test_move_to_done_from_pending(self, tmp_path):
        proj, t = _make_todo(tmp_path, status="pending")
        t.move_to_done()
        assert t.status == "done"
        assert t.path.parent == proj.todo_dir / "done"
        assert t.path.exists()

    def test_move_to_done_from_in_progress(self, tmp_path):
        proj, t = _make_todo(tmp_path, status="in-progress", sprint="001")
        t.move_to_done()
        assert t.status == "done"
        assert t.path.parent == proj.todo_dir / "done"


class TestTodoAddTicketRef:
    """Test add_ticket_ref."""

    def test_add_first_ticket(self, tmp_path):
        _, t = _make_todo(tmp_path)
        t.add_ticket_ref("001-001")
        assert t.tickets == ["001-001"]

    def test_add_duplicate_ticket(self, tmp_path):
        _, t = _make_todo(tmp_path)
        t.add_ticket_ref("001-001")
        t.add_ticket_ref("001-001")
        assert t.tickets == ["001-001"]

    def test_add_multiple_tickets(self, tmp_path):
        _, t = _make_todo(tmp_path)
        t.add_ticket_ref("001-001")
        t.add_ticket_ref("001-002")
        assert t.tickets == ["001-001", "001-002"]


class TestProjectListTodos:
    """Test Project.list_todos and get_todo."""

    def test_list_todos_pending(self, tmp_path):
        proj, _ = _make_todo(tmp_path, filename="a.md", status="pending")
        # Add another
        path2 = proj.todo_dir / "b.md"
        path2.write_text("---\nstatus: pending\n---\n# B\n", encoding="utf-8")
        todos = proj.list_todos()
        assert len(todos) == 2

    def test_list_todos_includes_in_progress(self, tmp_path):
        proj = Project(tmp_path)
        proj.todo_dir.mkdir(parents=True)
        (proj.todo_dir / "pending.md").write_text(
            "---\nstatus: pending\n---\n# Pending\n", encoding="utf-8"
        )
        ip_dir = proj.todo_dir / "in-progress"
        ip_dir.mkdir()
        (ip_dir / "active.md").write_text(
            "---\nstatus: in-progress\nsprint: \"001\"\n---\n# Active\n",
            encoding="utf-8",
        )
        todos = proj.list_todos()
        assert len(todos) == 2

    def test_list_todos_excludes_done(self, tmp_path):
        proj = Project(tmp_path)
        proj.todo_dir.mkdir(parents=True)
        (proj.todo_dir / "pending.md").write_text(
            "---\nstatus: pending\n---\n# Pending\n", encoding="utf-8"
        )
        done_dir = proj.todo_dir / "done"
        done_dir.mkdir()
        (done_dir / "finished.md").write_text(
            "---\nstatus: done\n---\n# Finished\n", encoding="utf-8"
        )
        todos = proj.list_todos()
        assert len(todos) == 1

    def test_get_todo(self, tmp_path):
        proj, _ = _make_todo(tmp_path, filename="idea.md", title="My Idea")
        t = proj.get_todo("idea.md")
        assert t.title == "My Idea"

    def test_get_todo_in_progress(self, tmp_path):
        proj, _ = _make_todo(tmp_path, filename="wip.md",
                             status="in-progress", sprint="001")
        t = proj.get_todo("wip.md")
        assert t.status == "in-progress"

    def test_get_todo_not_found(self, tmp_path):
        proj = Project(tmp_path)
        proj.todo_dir.mkdir(parents=True)
        try:
            proj.get_todo("nonexistent.md")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass
