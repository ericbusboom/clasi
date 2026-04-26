"""Tests for the Ticket class."""

from pathlib import Path

from clasi.project import Project
from clasi.sprint import Sprint
from clasi.ticket import Ticket


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


class TestTicketToDict:
    """Test Ticket.to_dict() serialization."""

    def test_to_dict_returns_dict(self, tmp_path):
        _, _, t = _setup(tmp_path)
        result = t.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_has_required_keys(self, tmp_path):
        _, _, t = _setup(tmp_path)
        result = t.to_dict()
        assert "id" in result
        assert "path" in result
        assert "title" in result
        assert "status" in result

    def test_to_dict_path_is_string(self, tmp_path):
        """path value must be a string, not a Path object."""
        _, _, t = _setup(tmp_path)
        result = t.to_dict()
        assert isinstance(result["path"], str)

    def test_to_dict_correct_values(self, tmp_path):
        _, _, t = _setup(tmp_path, title="Fix Bug", status="in-progress")
        result = t.to_dict()
        assert result["id"] == "001"
        assert result["title"] == "Fix Bug"
        assert result["status"] == "in-progress"
        assert "001-fix-bug.md" in result["path"]

    def test_to_dict_is_json_serializable(self, tmp_path):
        """to_dict() output must be json.dumps-safe."""
        import json
        _, _, t = _setup(tmp_path)
        result = t.to_dict()
        serialized = json.dumps(result)
        assert '"id"' in serialized


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


class TestTicketMoveToDoneWithPlan:
    """Test move_to_done_with_plan moves ticket and optional plan file."""

    def test_move_to_done_with_plan_no_plan(self, tmp_path):
        _, _, t = _setup(tmp_path)
        result = t.move_to_done_with_plan()
        assert "old_path" in result
        assert "new_path" in result
        assert "plan_old_path" not in result
        assert t.path.parent.name == "done"

    def test_move_to_done_with_plan_with_plan_file(self, tmp_path):
        proj, sprint, t = _setup(tmp_path)
        # Create a plan file alongside the ticket
        plan_path = t.path.parent / (t.path.stem + "-plan.md")
        plan_path.write_text("# Plan\n", encoding="utf-8")

        result = t.move_to_done_with_plan()

        assert "plan_old_path" in result
        assert "plan_new_path" in result
        assert not plan_path.exists()
        assert Path(result["plan_new_path"]).exists()
        assert Path(result["plan_new_path"]).parent.name == "done"

    def test_move_to_done_with_plan_returns_correct_paths(self, tmp_path):
        _, _, t = _setup(tmp_path)
        old_path = str(t.path)
        result = t.move_to_done_with_plan()
        assert result["old_path"] == old_path
        assert "done" in result["new_path"]


class TestTicketReopen:
    """Test Ticket.reopen() moves ticket back from done/ and resets status."""

    def test_reopen_from_done(self, tmp_path):
        _, _, t = _setup(tmp_path, status="done")
        t.move_to_done()
        assert t.path.parent.name == "done"

        result = t.reopen()

        assert result["old_status"] == "done"
        assert result["new_status"] == "todo"
        assert t.path.parent.name != "done"
        assert t.status == "todo"

    def test_reopen_not_in_done_resets_status(self, tmp_path):
        _, _, t = _setup(tmp_path, status="in-progress")
        result = t.reopen()

        assert result["old_status"] == "in-progress"
        assert result["new_status"] == "todo"
        assert t.status == "todo"
        # File should still be in same location
        assert t.path.parent.name != "done"

    def test_reopen_from_done_moves_plan_file(self, tmp_path):
        _, _, t = _setup(tmp_path, status="done")
        t.move_to_done()

        # Create a plan file in done/
        done_dir = t.path.parent
        plan_path = done_dir / (t.path.stem + "-plan.md")
        plan_path.write_text("# Plan\n", encoding="utf-8")

        result = t.reopen()

        assert "plan_old_path" in result
        assert "plan_new_path" in result
        assert not plan_path.exists()
        assert Path(result["plan_new_path"]).exists()
        assert Path(result["plan_new_path"]).parent.name != "done"

    def test_reopen_result_has_required_keys(self, tmp_path):
        _, _, t = _setup(tmp_path)
        t.move_to_done()
        result = t.reopen()
        assert "old_path" in result
        assert "new_path" in result
        assert "old_status" in result
        assert "new_status" in result


def _make_ticket_with_completes_todo(tmp_path, completes_todo_yaml: str) -> Ticket:
    """Create a ticket with an explicit completes_todo frontmatter line."""
    proj = Project(tmp_path)
    sprint_dir = proj.sprints_dir / "001-test-sprint"
    sprint_dir.mkdir(parents=True, exist_ok=True)
    tickets_dir = sprint_dir / "tickets"
    tickets_dir.mkdir(exist_ok=True)
    (tickets_dir / "done").mkdir(exist_ok=True)

    (sprint_dir / "sprint.md").write_text(
        '---\nid: "001"\ntitle: "Test Sprint"\nstatus: active\n'
        "branch: sprint/001-test-sprint\n---\n# Sprint 001\n",
        encoding="utf-8",
    )

    ticket_path = tickets_dir / "001-fix-bug.md"
    ticket_path.write_text(
        f'---\nid: "001"\ntitle: "Fix Bug"\nstatus: todo\n'
        f"use-cases: []\ndepends-on: []\ntodo: \"\"\n"
        f"{completes_todo_yaml}"
        f"---\n# Fix Bug\n\n## Description\n\nSome work.\n",
        encoding="utf-8",
    )

    sprint = Sprint(sprint_dir, proj)
    return Ticket(ticket_path, sprint)


class TestCompletesTodoFor:
    """Tests for Ticket.completes_todo_for()."""

    def test_absent_field_returns_true(self, tmp_path):
        """No completes_todo field → default True (backward-compatible)."""
        _, _, t = _setup(tmp_path)
        assert t.completes_todo_for("some-todo.md") is True

    def test_scalar_true_returns_true(self, tmp_path):
        """completes_todo: true → True."""
        t = _make_ticket_with_completes_todo(tmp_path, "completes_todo: true\n")
        assert t.completes_todo_for("some-todo.md") is True

    def test_scalar_false_returns_false(self, tmp_path):
        """completes_todo: false → False."""
        t = _make_ticket_with_completes_todo(tmp_path, "completes_todo: false\n")
        assert t.completes_todo_for("some-todo.md") is False

    def test_scalar_false_applies_to_any_filename(self, tmp_path):
        """completes_todo: false suppresses all filenames uniformly."""
        t = _make_ticket_with_completes_todo(tmp_path, "completes_todo: false\n")
        assert t.completes_todo_for("alpha.md") is False
        assert t.completes_todo_for("beta.md") is False

    def test_map_explicit_false(self, tmp_path):
        """Map with filename → false returns False for that filename."""
        t = _make_ticket_with_completes_todo(
            tmp_path, "completes_todo:\n  umbrella.md: false\n"
        )
        assert t.completes_todo_for("umbrella.md") is False

    def test_map_absent_key_defaults_to_true(self, tmp_path):
        """Map without the queried filename defaults to True."""
        t = _make_ticket_with_completes_todo(
            tmp_path, "completes_todo:\n  umbrella.md: false\n"
        )
        # A different filename not in the map → True
        assert t.completes_todo_for("single-sprint.md") is True

    def test_map_explicit_true(self, tmp_path):
        """Map with filename → true returns True."""
        t = _make_ticket_with_completes_todo(
            tmp_path, "completes_todo:\n  my-todo.md: true\n"
        )
        assert t.completes_todo_for("my-todo.md") is True
