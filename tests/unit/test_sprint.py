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

    def test_merge_branch_conflict_raises_merge_conflict_error(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        s = Sprint(sprint_dir, proj)
        with patch("clasi.sprint.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _make_run_result(0),  # rev-parse: branch exists
                _make_run_result(1),  # merge-base: not ancestor
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
        assert counts == {"todo": 0, "in_progress": 0, "done": 0}

    def test_ticket_counts_with_todo_tickets(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_ticket(sprint_dir, "001", "First", status="todo")
        _add_ticket(sprint_dir, "002", "Second", status="todo")
        s = Sprint(sprint_dir, proj)
        counts = s.ticket_counts()
        assert counts["todo"] == 2
        assert counts["in_progress"] == 0
        assert counts["done"] == 0

    def test_ticket_counts_mixed_statuses(self, tmp_path):
        proj, sprint_dir = _make_sprint_dir(tmp_path)
        _add_ticket(sprint_dir, "001", "Todo", status="todo")
        _add_ticket(sprint_dir, "002", "In Progress", status="in-progress")
        _add_ticket(sprint_dir, "003", "Done", status="done", done=True)
        s = Sprint(sprint_dir, proj)
        counts = s.ticket_counts()
        assert counts["todo"] == 1
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
