"""Unit tests for issue management MCP tools."""

import json
from unittest.mock import MagicMock, patch

import pytest

from clasi.tools.artifact_tools import (
    close_sprint,
    create_sprint,
    create_ticket,
    link_sprint_issues,
    list_issues,
    move_issue_to_done,
    split_issue,
)
from clasi.frontmatter import read_frontmatter, write_frontmatter
from clasi.mcp_server import set_project
from clasi.state_db import (
    acquire_lock,
    advance_phase,
    record_gate,
)


@pytest.fixture
def todo_dir(tmp_path, monkeypatch):
    """Set up a temporary working directory with .clasi/issues/ (pending pool)."""
    monkeypatch.chdir(tmp_path)
    set_project(tmp_path)
    todo = tmp_path / ".clasi" / "issues"
    todo.mkdir(parents=True)
    return todo


def _advance_to_ticketing(work_dir, sprint_id: str) -> None:
    """Advance a sprint through review gates to ticketing phase for testing."""
    db_path = work_dir / ".clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # roadmap -> planning-docs
    advance_phase(db_path, sprint_id)  # planning-docs -> architecture-review
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)  # architecture-review -> stakeholder-review
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")
    advance_phase(db_path, sprint_id)  # stakeholder-review -> ticketing


def _advance_to_executing(work_dir, sprint_id: str) -> None:
    """Advance a sprint all the way to executing phase."""
    db_path = work_dir / ".clasi" / ".clasi.db"
    _advance_to_ticketing(work_dir, sprint_id)
    acquire_lock(str(db_path), sprint_id)
    advance_phase(str(db_path), sprint_id)  # ticketing → executing


class TestListIssues:
    def test_lists_todos(self, todo_dir):
        (todo_dir / "idea-one.md").write_text(
            "---\nstatus: pending\n---\n\n# Idea One\n\nSome details.\n"
        )
        (todo_dir / "idea-two.md").write_text(
            "---\nstatus: pending\n---\n\n# Idea Two\n\nMore details.\n"
        )

        result = json.loads(list_issues())
        assert len(result) == 2
        assert result[0]["filename"] == "idea-one.md"
        assert result[0]["title"] == "Idea One"
        assert result[0]["status"] == "pending"
        assert result[1]["filename"] == "idea-two.md"
        assert result[1]["title"] == "Idea Two"
        assert result[1]["status"] == "pending"

    def test_excludes_done_directory(self, todo_dir):
        (todo_dir / "active.md").write_text("# Active\n")
        done = todo_dir / "done"
        done.mkdir()
        (done / "finished.md").write_text("# Finished\n")

        result = json.loads(list_issues())
        assert len(result) == 1
        assert result[0]["filename"] == "active.md"

    def test_empty_directory(self, todo_dir):
        result = json.loads(list_issues())
        assert result == []

    def test_no_todo_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        result = json.loads(list_issues())
        assert result == []

    def test_file_without_heading(self, todo_dir):
        (todo_dir / "no-heading.md").write_text("Just some text.\n")

        result = json.loads(list_issues())
        assert len(result) == 1
        assert result[0]["title"] == "no-heading"

    def test_shows_sprint_ticket_linkage_for_in_progress(self, todo_dir):
        """In-progress TODOs show sprint and ticket linkage."""
        (todo_dir / "linked.md").write_text(
            "---\nstatus: in-progress\nsprint: '024'\n"
            "tickets:\n  - '024-001'\n  - '024-002'\n---\n\n# Linked\n"
        )
        (todo_dir / "pending.md").write_text(
            "---\nstatus: pending\n---\n\n# Pending\n"
        )

        result = json.loads(list_issues())
        linked = next(r for r in result if r["filename"] == "linked.md")
        pending = next(r for r in result if r["filename"] == "pending.md")

        assert linked["status"] == "in-progress"
        assert linked["sprint"] == "024"
        assert linked["tickets"] == ["024-001", "024-002"]

        assert pending["status"] == "pending"
        assert "sprint" not in pending
        assert "tickets" not in pending


class TestMoveIssueToDone:
    """move_issue_to_done moves the file to done/ and updates frontmatter."""

    def test_sets_status_done(self, todo_dir):
        (todo_dir / "idea.md").write_text("---\nstatus: pending\n---\n\n# Idea\n")

        result = json.loads(move_issue_to_done("idea.md"))
        assert result["status"] == "done"

    def test_file_moved_to_done_dir(self, todo_dir):
        """The file is moved to done/ subdirectory."""
        (todo_dir / "idea.md").write_text("---\nstatus: pending\n---\n\n# Idea\n")

        move_issue_to_done("idea.md")

        assert not (todo_dir / "idea.md").exists()
        assert (todo_dir / "done" / "idea.md").exists()

    def test_done_directory_created(self, todo_dir):
        """done/ subdirectory is created when it doesn't exist."""
        (todo_dir / "idea.md").write_text("---\nstatus: pending\n---\n\n# Idea\n")
        assert not (todo_dir / "done").exists()

        move_issue_to_done("idea.md")

        assert (todo_dir / "done").exists()
        assert (todo_dir / "done" / "idea.md").exists()

    def test_error_on_nonexistent(self, todo_dir):
        with pytest.raises(ValueError, match="TODO not found"):
            move_issue_to_done("nonexistent.md")

    def test_writes_traceability_frontmatter(self, todo_dir):
        """ticket_ids are written to frontmatter (no sprint_id to avoid validation)."""
        (todo_dir / "idea.md").write_text("---\nstatus: pending\n---\n\n# Idea\n\nDetails.\n")

        move_issue_to_done("idea.md", ticket_ids=["001", "002"])

        content = (todo_dir / "done" / "idea.md").read_text()
        assert "status: done" in content
        assert "001" in content
        assert "002" in content

    def test_writes_status_done_without_sprint(self, todo_dir):
        (todo_dir / "idea.md").write_text("---\nstatus: pending\n---\n# Idea\n")

        move_issue_to_done("idea.md")

        content = (todo_dir / "done" / "idea.md").read_text()
        assert "status: done" in content

    def test_preserves_existing_frontmatter(self, todo_dir):
        (todo_dir / "idea.md").write_text(
            "---\nstatus: pending\nsource: https://example.com\n---\n\n# Idea\n"
        )

        move_issue_to_done("idea.md")

        content = (todo_dir / "done" / "idea.md").read_text()
        assert "status: done" in content
        assert "source" in content  # original frontmatter field preserved

    def test_sprint_id_validation_wrong_location(self, todo_dir, tmp_path):
        """Raises if sprint_id given but issue is NOT in that sprint's issues dir."""
        from clasi.tools.artifact_tools import create_sprint
        from clasi.mcp_server import set_project
        set_project(tmp_path)

        (todo_dir / "idea.md").write_text("---\nstatus: pending\n---\n\n# Idea\n")
        create_sprint("Test Sprint")

        with pytest.raises(ValueError, match="not in the expected sprint issues"):
            move_issue_to_done("idea.md", sprint_id="001")

    def test_sprint_id_validation_already_done_dir(self, todo_dir, tmp_path):
        """Succeeds if sprint_id given and issue is already in sprint issues/done/."""
        from clasi.tools.artifact_tools import create_sprint, create_ticket
        from clasi.mcp_server import set_project
        from clasi.state_db import advance_phase, record_gate

        set_project(tmp_path)
        create_sprint("Test Sprint")

        # Advance to ticketing so we can create a ticket
        db_path = tmp_path / ".clasi" / ".clasi.db"
        advance_phase(db_path, "001")  # roadmap -> planning-docs
        advance_phase(db_path, "001")  # planning-docs -> architecture-review
        record_gate(db_path, "001", "architecture_review", "passed")
        advance_phase(db_path, "001")  # architecture-review -> stakeholder-review
        record_gate(db_path, "001", "stakeholder_approval", "passed")
        advance_phase(db_path, "001")  # stakeholder-review -> ticketing

        # Create the issue and claim it
        (todo_dir / "idea.md").write_text("---\nstatus: pending\n---\n\n# Idea\n")
        create_ticket("001", "Task", todo="idea.md")

        # Manually move it to done/ as if it was already completed
        from pathlib import Path
        sprints_dir = tmp_path / ".clasi" / "sprints"
        sprint_dir = next(d for d in sprints_dir.iterdir() if d.is_dir() and d.name.startswith("001-"))
        issues_dir = sprint_dir / "issues"
        done_dir = issues_dir / "done"
        done_dir.mkdir(exist_ok=True)
        (issues_dir / "idea.md").rename(done_dir / "idea.md")

        # Calling move_issue_to_done with sprint_id on an already-done-dir issue
        # should succeed (idempotent)
        set_project(tmp_path)
        result = json.loads(move_issue_to_done("idea.md", sprint_id="001"))
        assert result["status"] == "done"


class TestCreateTicketWithTodo:
    """Tests for the create_ticket todo parameter (cross-referencing)."""

    @pytest.fixture
    def work_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        return tmp_path

    def _setup_sprint(self, work_dir):
        """Create a sprint and advance to ticketing phase."""
        create_sprint("Test Sprint")
        _advance_to_ticketing(work_dir, "001")
        # Create the pending pool directory
        todo = work_dir / ".clasi" / "issues"
        todo.mkdir(parents=True, exist_ok=True)
        return todo

    def _sprint_issues_dir(self, work_dir, sprint_id: str = "001"):
        """Return the sprint-scoped issues directory."""
        from pathlib import Path
        sprints_dir = work_dir / ".clasi" / "sprints"
        for d in sorted(sprints_dir.iterdir()):
            if d.is_dir() and d.name.startswith(sprint_id + "-"):
                return d / "issues"
        raise ValueError(f"Sprint dir for {sprint_id!r} not found")

    def test_creates_ticket_with_todo_field(self, work_dir):
        todo = self._setup_sprint(work_dir)
        (todo / "my-idea.md").write_text("---\nstatus: pending\n---\n\n# My Idea\n")

        result = json.loads(create_ticket("001", "Implement Idea", todo="my-idea.md"))
        from pathlib import Path
        ticket_fm = read_frontmatter(result["path"])
        assert ticket_fm["issue"] == "my-idea.md"

    def test_updates_todo_frontmatter_on_create(self, work_dir):
        todo = self._setup_sprint(work_dir)
        (todo / "my-idea.md").write_text("---\nstatus: pending\n---\n\n# My Idea\n")

        create_ticket("001", "Implement Idea", todo="my-idea.md")

        # TODO is now in sprint issues dir
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        todo_fm = read_frontmatter(sprint_issues / "my-idea.md")
        assert todo_fm["status"] == "in-progress"
        assert todo_fm["sprint"] == "001"
        assert "001-001" in todo_fm["tickets"]

    def test_multiple_todos(self, work_dir):
        todo = self._setup_sprint(work_dir)
        (todo / "idea-a.md").write_text("---\nstatus: pending\n---\n\n# Idea A\n")
        (todo / "idea-b.md").write_text("---\nstatus: pending\n---\n\n# Idea B\n")

        result = json.loads(
            create_ticket("001", "Both Ideas", todo=["idea-a.md", "idea-b.md"])
        )
        from pathlib import Path
        ticket_fm = read_frontmatter(result["path"])
        assert ticket_fm["issue"] == ["idea-a.md", "idea-b.md"]

        # Both TODOs should be in sprint issues dir
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        fm_a = read_frontmatter(sprint_issues / "idea-a.md")
        fm_b = read_frontmatter(sprint_issues / "idea-b.md")
        assert fm_a["status"] == "in-progress"
        assert fm_b["status"] == "in-progress"
        assert fm_a["sprint"] == "001"
        assert fm_b["sprint"] == "001"

    def test_multiple_tickets_same_todo(self, work_dir):
        todo = self._setup_sprint(work_dir)
        (todo / "big-idea.md").write_text("---\nstatus: pending\n---\n\n# Big Idea\n")

        create_ticket("001", "Part 1", todo="big-idea.md")
        create_ticket("001", "Part 2", todo="big-idea.md")

        # TODO is in sprint issues dir
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        todo_fm = read_frontmatter(sprint_issues / "big-idea.md")
        assert todo_fm["tickets"] == ["001-001", "001-002"]

    def test_missing_todo_file_handled_gracefully(self, work_dir):
        self._setup_sprint(work_dir)
        # Don't create the TODO file -- should not raise
        result = json.loads(
            create_ticket("001", "Orphan", todo="nonexistent.md")
        )
        assert result["id"] == "001"

    def test_todo_moves_to_in_progress_not_done(self, work_dir):
        """TODO moves to sprint issues dir (not done/) when ticket is created."""
        todo = self._setup_sprint(work_dir)
        (todo / "my-idea.md").write_text("---\nstatus: pending\n---\n\n# My Idea\n")

        create_ticket("001", "Implement Idea", todo="my-idea.md")

        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        # Should be in sprint issues dir, not in pending or done
        assert not (todo / "my-idea.md").exists()
        assert (sprint_issues / "my-idea.md").exists()
        assert not (todo / "done" / "my-idea.md").exists()


class TestCloseSprintTodoHandling:
    """Tests for close_sprint TODO verification (no bulk-move)."""

    @pytest.fixture
    def work_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        return tmp_path

    def _sprint_issues_dir(self, work_dir, sprint_id: str = "001"):
        """Return the sprint-scoped issues directory (checks active and done)."""
        sprints_dir = work_dir / ".clasi" / "sprints"
        for location in [sprints_dir, sprints_dir / "done"]:
            if not location.exists():
                continue
            for d in sorted(location.iterdir()):
                if d.is_dir() and d.name.startswith(sprint_id + "-"):
                    return d / "issues"
        raise ValueError(f"Sprint dir for {sprint_id!r} not found")

    def test_close_succeeds_when_todos_already_done(self, work_dir):
        """TODOs marked done by ticket completion don't block close."""
        from clasi.tools.artifact_tools import move_ticket_to_done

        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / ".clasi" / "issues"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "my-idea.md").write_text("---\nstatus: pending\n---\n\n# My Idea\n")

        result = json.loads(create_ticket("001", "Task", todo="my-idea.md"))
        ticket_path = result["path"]

        # Complete ticket which triggers TODO completion (file moves to done/)
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)
        move_ticket_to_done(ticket_path)

        # TODO should now have status=done in sprint issues/done/ dir (file moved)
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        assert not (sprint_issues / "my-idea.md").exists()
        assert (sprint_issues / "done" / "my-idea.md").exists()
        from clasi.frontmatter import read_frontmatter as rfm
        fm_todo = rfm(sprint_issues / "done" / "my-idea.md")
        assert fm_todo["status"] == "done"

        result = json.loads(close_sprint("001"))
        # No bulk-move needed
        assert "moved_todos" not in result

    def test_close_reports_unresolved_in_progress_todos(self, work_dir):
        """In-progress TODOs are reported as unresolved, not bulk-moved."""
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / ".clasi" / "issues"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "idea.md").write_text("---\nstatus: pending\n---\n\n# Idea\n")

        create_ticket("001", "Task", todo="idea.md")
        # Don't complete the ticket — TODO stays in-progress
        result = json.loads(close_sprint("001"))
        assert "unresolved_todos" in result
        assert "idea.md" in result["unresolved_todos"]

    def test_close_without_linked_todos(self, work_dir):
        create_sprint("Sprint")
        result = json.loads(close_sprint("001"))
        assert "moved_todos" not in result
        assert "unresolved_todos" not in result

    def test_unlinked_todos_not_affected(self, work_dir):
        """TODOs not linked to the sprint are not touched."""
        from clasi.tools.artifact_tools import move_ticket_to_done

        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / ".clasi" / "issues"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "linked.md").write_text("---\nstatus: pending\n---\n\n# Linked\n")
        (todo / "unlinked.md").write_text(
            "---\nstatus: pending\n---\n\n# Unlinked\n"
        )

        result = json.loads(create_ticket("001", "Task", todo="linked.md"))
        ticket_path = result["path"]

        # Complete ticket to mark linked TODO as done (file moves to done/)
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)
        move_ticket_to_done(ticket_path)

        close_sprint("001")

        # Linked should have moved to sprint issues/done/ (file moved by completion)
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "done" / "linked.md").exists()
        # Unlinked should still be in active todo dir, untouched
        assert (todo / "unlinked.md").exists()
        assert not (todo / "done" / "unlinked.md").exists()

    def test_close_sprint_allows_deferred_todo(self, work_dir):
        """Legacy path: in-progress TODO with completes_issue: false does not block close.

        A ticket in the sprint has completes_issue: false for the TODO, so the
        TODO is intentionally deferred (it spans future sprints). The sprint
        should close without reporting the TODO as unresolved.
        """
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / ".clasi" / "issues"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "umbrella.md").write_text("---\nstatus: pending\n---\n\n# Umbrella\n")

        result = json.loads(create_ticket("001", "Partial Work", todo="umbrella.md"))
        ticket_path = result["path"]

        # Mark ticket as done but set completes_issue: false — deferred pattern
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        fm["completes_issue"] = False
        write_frontmatter(ticket_path, fm)

        # Close sprint — TODO is still in-progress but deferred, so no error
        result = json.loads(close_sprint("001"))
        assert "unresolved_todos" not in result
        # TODO must still be in sprint issues dir (not archived)
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "umbrella.md").exists()

    def test_close_sprint_blocks_unresolved_todo(self, work_dir):
        """Legacy path: in-progress TODO with no completes_issue: false is an error.

        All tickets referencing the TODO have completes_issue: true (default).
        The TODO should have been archived but was not — the sprint close must
        report it as unresolved.
        """
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / ".clasi" / "issues"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "unresolved.md").write_text("---\nstatus: pending\n---\n\n# Unresolved\n")

        result = json.loads(create_ticket("001", "Task", todo="unresolved.md"))
        ticket_path = result["path"]

        # Mark ticket done but do NOT set completes_issue: false — default (true)
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)
        # Do NOT call move_ticket_to_done so the TODO stays in in-progress/

        result = json.loads(close_sprint("001"))
        assert "unresolved_todos" in result
        assert "unresolved.md" in result["unresolved_todos"]

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260425.1")
    @patch("subprocess.run")
    def test_close_sprint_full_allows_deferred_todo(
        self, mock_run, mock_ver, mock_tag, work_dir
    ):
        """Full lifecycle path (_close_sprint_full): deferred TODO does not block precondition.

        A ticket has completes_issue: false. The precondition check (step 1b)
        should skip the TODO and let close_sprint proceed past the precondition
        step. With mocked subprocess, the sprint closes successfully.
        """
        from clasi.tools.artifact_tools import move_ticket_to_done, update_ticket_status

        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )

        todo = work_dir / ".clasi" / "issues"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "umbrella.md").write_text("---\nstatus: pending\n---\n\n# Umbrella\n")

        result = json.loads(create_ticket("001", "Partial Work", todo="umbrella.md"))
        ticket_path = result["path"]

        # Set completes_issue: false before moving ticket to done
        fm = read_frontmatter(ticket_path)
        fm["completes_issue"] = False
        write_frontmatter(ticket_path, fm)

        update_ticket_status(ticket_path, "done")
        move_ticket_to_done(ticket_path)

        # TODO must still be in sprint issues dir (suppressed by completes_issue: false)
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "umbrella.md").exists()

        # Mock subprocess calls for the full lifecycle
        def _ok(returncode=0, stdout="", stderr=""):
            r = MagicMock()
            r.returncode = returncode
            r.stdout = stdout
            r.stderr = stderr
            return r

        mock_run.side_effect = [
            _ok(0, "all tests passed"),  # pytest
            _ok(0),  # git add -A (version bump)
            _ok(0),  # git commit (version bump)
            _ok(0, ""),  # git status --porcelain .clasi.db (clean)
            _ok(0),  # git rev-parse --verify branch (merge check)
            _ok(0),  # git merge-base --is-ancestor (already merged)
            _ok(0),  # git push --tags
            _ok(0),  # git rev-parse --verify branch (delete check)
            _ok(0),  # git branch -d
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        # Must succeed — precondition step must not have blocked on the deferred TODO
        assert result.get("status") == "success", (
            f"Expected success but got: {result}"
        )
        # A precondition error would have "step": "precondition" in the error block;
        # success confirms the deferred TODO did not trigger a precondition failure
        assert "error" not in result

    # ── New tests for T002: done-dir awareness and legacy migration ──

    def test_legacy_done_dir_issues_pass_cleanly(self, work_dir):
        """Legacy path: issues already in <sprint>/issues/done/ pass cleanly.

        An issue that was previously moved to done/ should not generate a
        repair entry and close should succeed without error.
        """
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")

        # Find the sprint directory and manually place an issue in issues/done/
        sprints_dir = work_dir / ".clasi" / "sprints"
        sprint_dir = next(d for d in sprints_dir.iterdir() if d.name.startswith("001-"))
        done_dir = sprint_dir / "issues" / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        (done_dir / "already-done.md").write_text(
            "---\nstatus: done\nsprint: '001'\n---\n\n# Already Done\n"
        )

        result = json.loads(close_sprint("001"))

        # Close should succeed, no unresolved_todos reported
        assert "unresolved_todos" not in result
        # The already-done issue should still be in done/ (now under archived sprint)
        sprints_done_dir = work_dir / ".clasi" / "sprints" / "done"
        archived = next(d for d in sprints_done_dir.iterdir() if d.name.startswith("001-"))
        assert (archived / "issues" / "done" / "already-done.md").exists()

    def test_legacy_top_level_done_issue_migrated(self, work_dir):
        """Legacy path: top-level done issue is self-repaired to <sprint>/issues/done/.

        An issue sitting at <sprint>/issues/ with status: done (a legacy state)
        should be moved to done/ by the self-repair logic.
        """
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")

        sprints_dir = work_dir / ".clasi" / "sprints"
        sprint_dir = next(d for d in sprints_dir.iterdir() if d.name.startswith("001-"))
        issues_dir = sprint_dir / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        (issues_dir / "stale-done.md").write_text(
            "---\nstatus: done\nsprint: '001'\n---\n\n# Stale Done\n"
        )

        result = json.loads(close_sprint("001"))

        # No unresolved issues
        assert "unresolved_todos" not in result
        # File should be under archived sprint issues/done/
        sprints_done_dir = work_dir / ".clasi" / "sprints" / "done"
        archived = next(d for d in sprints_done_dir.iterdir() if d.name.startswith("001-"))
        assert (archived / "issues" / "done" / "stale-done.md").exists()
        assert not (archived / "issues" / "stale-done.md").exists()

    def test_legacy_pending_pool_done_issue_relocated_to_sprint_done(self, work_dir):
        """Legacy path: pending-pool done issue is relocated to <sprint>/issues/done/.

        An issue in .clasi/issues/ with sprint: '001' and status: done should
        be relocated directly to <sprint>/issues/done/, not to .clasi/issues/done/.
        """
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")

        # Place a done-tagged issue in the pending pool
        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "pool-done.md").write_text(
            "---\nstatus: done\nsprint: '001'\n---\n\n# Pool Done\n"
        )

        result = json.loads(close_sprint("001"))

        # Should have moved the pending pool issue
        assert "moved_todos" in result
        assert "pool-done.md" in result["moved_todos"]
        # Issue should be under archived sprint issues/done/
        sprints_done_dir = work_dir / ".clasi" / "sprints" / "done"
        archived = next(d for d in sprints_done_dir.iterdir() if d.name.startswith("001-"))
        assert (archived / "issues" / "done" / "pool-done.md").exists()
        # NOT in the pending pool's done/ dir
        assert not (pending_pool / "done" / "pool-done.md").exists()

    def test_legacy_inprogress_issue_hard_fails(self, work_dir):
        """Legacy path: in-progress issue at top level that is not deferred hard-fails.

        Existing behavior: sprint close returns unresolved_todos (not an error
        dict for legacy path, but unresolved_todos key present).
        """
        create_sprint("Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / ".clasi" / "issues"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "blocker.md").write_text("---\nstatus: pending\n---\n\n# Blocker\n")

        create_ticket("001", "Task", todo="blocker.md")
        # Do NOT complete the ticket — issue stays in-progress

        result = json.loads(close_sprint("001"))
        assert "unresolved_todos" in result
        assert "blocker.md" in result["unresolved_todos"]

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260425.2")
    @patch("subprocess.run")
    def test_full_done_dir_issues_pass_cleanly(
        self, mock_run, mock_ver, mock_tag, work_dir
    ):
        """Full lifecycle path: issues in <sprint>/issues/done/ pass cleanly.

        An issue already in done/ should not appear in repairs and should not
        block the precondition check.
        """
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )

        sprints_dir = work_dir / ".clasi" / "sprints"
        sprint_dir = next(d for d in sprints_dir.iterdir() if d.name.startswith("001-"))
        done_dir = sprint_dir / "issues" / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        (done_dir / "already-done.md").write_text(
            "---\nstatus: done\nsprint: '001'\n---\n\n# Already Done\n"
        )

        def _ok(returncode=0, stdout="", stderr=""):
            r = MagicMock()
            r.returncode = returncode
            r.stdout = stdout
            r.stderr = stderr
            return r

        mock_run.side_effect = [
            _ok(0, "all tests passed"),  # pytest
            _ok(0),  # git add -A
            _ok(0),  # git commit
            _ok(0, ""),  # git status --porcelain
            _ok(0),  # git rev-parse (merge check)
            _ok(0),  # git merge-base (already merged)
            _ok(0),  # git push --tags
            _ok(0),  # git rev-parse (delete check)
            _ok(0),  # git branch -d
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result.get("status") == "success", f"Expected success but got: {result}"
        # Repairs should NOT mention the already-done issue
        repairs = result.get("repairs", [])
        assert not any("already-done.md" in r for r in repairs), (
            f"already-done.md should not appear in repairs: {repairs}"
        )

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260425.3")
    @patch("subprocess.run")
    def test_full_top_level_done_issue_migrated(
        self, mock_run, mock_ver, mock_tag, work_dir
    ):
        """Full lifecycle path: top-level done issue is self-repaired to done/.

        A stale issue at <sprint>/issues/ with status: done triggers the repair
        message and close succeeds.
        """
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )

        sprints_dir = work_dir / ".clasi" / "sprints"
        sprint_dir = next(d for d in sprints_dir.iterdir() if d.name.startswith("001-"))
        issues_dir = sprint_dir / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        (issues_dir / "stale-done.md").write_text(
            "---\nstatus: done\nsprint: '001'\n---\n\n# Stale Done\n"
        )

        def _ok(returncode=0, stdout="", stderr=""):
            r = MagicMock()
            r.returncode = returncode
            r.stdout = stdout
            r.stderr = stderr
            return r

        mock_run.side_effect = [
            _ok(0, "all tests passed"),  # pytest
            _ok(0),  # git add -A
            _ok(0),  # git commit
            _ok(0, ""),  # git status --porcelain
            _ok(0),  # git rev-parse (merge check)
            _ok(0),  # git merge-base (already merged)
            _ok(0),  # git push --tags
            _ok(0),  # git rev-parse (delete check)
            _ok(0),  # git branch -d
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result.get("status") == "success", f"Expected success but got: {result}"
        # The repair should be logged
        repairs = result.get("repairs", [])
        assert any("stale-done.md" in r for r in repairs), (
            f"Expected repair for stale-done.md in: {repairs}"
        )

    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260425.4")
    @patch("subprocess.run")
    def test_full_pending_pool_done_issue_relocated_to_sprint_done(
        self, mock_run, mock_ver, mock_tag, work_dir
    ):
        """Full lifecycle path: pending-pool done issue relocated to <sprint>/issues/done/.

        An issue in .clasi/issues/ with sprint: '001' and status: done is
        moved to <sprint>/issues/done/ (not .clasi/issues/done/).
        """
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")
        (work_dir / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n'
        )

        pending_pool = work_dir / ".clasi" / "issues"
        pending_pool.mkdir(parents=True, exist_ok=True)
        (pending_pool / "pool-done.md").write_text(
            "---\nstatus: done\nsprint: '001'\n---\n\n# Pool Done\n"
        )

        def _ok(returncode=0, stdout="", stderr=""):
            r = MagicMock()
            r.returncode = returncode
            r.stdout = stdout
            r.stderr = stderr
            return r

        mock_run.side_effect = [
            _ok(0, "all tests passed"),  # pytest
            _ok(0),  # git add -A
            _ok(0),  # git commit
            _ok(0, ""),  # git status --porcelain
            _ok(0),  # git rev-parse (merge check)
            _ok(0),  # git merge-base (already merged)
            _ok(0),  # git push --tags
            _ok(0),  # git rev-parse (delete check)
            _ok(0),  # git branch -d
        ]

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result.get("status") == "success", f"Expected success but got: {result}"
        # NOT in the pending pool's done/ dir
        assert not (pending_pool / "done" / "pool-done.md").exists()
        # The repair should be logged
        repairs = result.get("repairs", [])
        assert any("pool-done.md" in r for r in repairs), (
            f"Expected repair for pool-done.md in: {repairs}"
        )

    def test_full_inprogress_issue_hard_fails(self, work_dir):
        """Full lifecycle path: in-progress issue at top level that is not deferred hard-fails.

        Place an in-progress issue directly in <sprint>/issues/ without any
        ticket to reference it (so it is NOT deferred). Precondition check
        should return a structured error with step: 'precondition'.

        We use branch_name to trigger the full path, but close returns before
        any subprocess calls (precondition fails before tests step).
        """
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")

        sprints_dir = work_dir / ".clasi" / "sprints"
        sprint_dir = next(d for d in sprints_dir.iterdir() if d.name.startswith("001-"))
        issues_dir = sprint_dir / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        # Place in-progress issue directly — no ticket references it, so not deferred
        (issues_dir / "blocker.md").write_text(
            "---\nstatus: in-progress\nsprint: '001'\n---\n\n# Blocker\n"
        )

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))
        assert result.get("status") == "error"
        assert result["error"]["step"] == "precondition"
        assert "blocker.md" in result["error"]["message"]


class TestMoveTicketToDoneCompletesTodoGuard:
    """Tests for move_ticket_to_done respecting completes_issue_for."""

    @pytest.fixture
    def work_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        return tmp_path

    def _sprint_issues_dir(self, work_dir, sprint_id: str = "001"):
        """Return the sprint-scoped issues directory."""
        sprints_dir = work_dir / ".clasi" / "sprints"
        for d in sorted(sprints_dir.iterdir()):
            if d.is_dir() and d.name.startswith(sprint_id + "-"):
                return d / "issues"
        raise ValueError(f"Sprint dir for {sprint_id!r} not found")

    def _setup_sprint_with_todo(self, work_dir, todo_filename: str = "my-idea.md"):
        """Create sprint 001, create a ticket linked to todo_filename.

        Returns (pending_pool_dir, ticket_path).
        """
        from clasi.tools.artifact_tools import move_ticket_to_done  # noqa: F401

        create_sprint("Test Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / ".clasi" / "issues"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / todo_filename).write_text(
            "---\nstatus: pending\n---\n\n# My Idea\n"
        )

        result = json.loads(create_ticket("001", "Task", todo=todo_filename))
        ticket_path = result["path"]

        # Mark ticket as done in frontmatter
        fm = read_frontmatter(ticket_path)
        fm["status"] = "done"
        write_frontmatter(ticket_path, fm)

        return todo, ticket_path

    def test_archives_single_sprint_todo_by_default(self, work_dir):
        """No completes_issue field → TODO is moved to done/ and marked done."""
        from clasi.tools.artifact_tools import move_ticket_to_done

        _, ticket_path = self._setup_sprint_with_todo(work_dir, "my-idea.md")

        result = json.loads(move_ticket_to_done(ticket_path))

        assert "completed_todos" in result
        assert "my-idea.md" in result["completed_todos"]
        # File is moved to sprint issues/done/ dir
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        assert not (sprint_issues / "my-idea.md").exists()
        assert (sprint_issues / "done" / "my-idea.md").exists()
        from clasi.frontmatter import read_frontmatter as rfm
        assert rfm(sprint_issues / "done" / "my-idea.md")["status"] == "done"

    def test_does_not_archive_when_completes_todo_scalar_false(self, work_dir):
        """completes_issue: false on the ticket → TODO is NOT marked done."""
        from clasi.tools.artifact_tools import move_ticket_to_done

        todo, ticket_path = self._setup_sprint_with_todo(work_dir, "umbrella.md")

        # Add completes_issue: false to the ticket frontmatter
        fm = read_frontmatter(ticket_path)
        fm["completes_issue"] = False
        write_frontmatter(ticket_path, fm)

        result = json.loads(move_ticket_to_done(ticket_path))

        assert "completed_todos" not in result
        # TODO should still be in sprint issues dir with in-progress status
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "umbrella.md").exists()
        from clasi.frontmatter import read_frontmatter as rfm
        assert rfm(sprint_issues / "umbrella.md")["status"] == "in-progress"

    def test_does_not_archive_when_any_ref_ticket_has_false(self, work_dir):
        """If any referencing ticket has completes_issue: false, TODO is NOT archived.

        Scenario: two tickets reference the same TODO; ticket 001 has
        completes_issue: false, ticket 002 has none (defaults to True).
        After both are done, moving ticket 002 to done must not archive the TODO.
        """
        from clasi.tools.artifact_tools import move_ticket_to_done

        create_sprint("Test Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / ".clasi" / "issues"
        todo.mkdir(parents=True, exist_ok=True)
        (todo / "umbrella.md").write_text("---\nstatus: pending\n---\n\n# Umbrella\n")

        # Create ticket 001 linked to umbrella.md
        r1 = json.loads(create_ticket("001", "Part One", todo="umbrella.md"))
        ticket1_path = r1["path"]

        # Create ticket 002 linked to umbrella.md
        r2 = json.loads(create_ticket("001", "Part Two", todo="umbrella.md"))
        ticket2_path = r2["path"]

        # Mark ticket 001 as done and give it completes_issue: false
        fm1 = read_frontmatter(ticket1_path)
        fm1["status"] = "done"
        fm1["completes_issue"] = False
        write_frontmatter(ticket1_path, fm1)
        move_ticket_to_done(ticket1_path)

        # Now mark ticket 002 as done (no completes_issue flag)
        fm2 = read_frontmatter(ticket2_path)
        fm2["status"] = "done"
        write_frontmatter(ticket2_path, fm2)
        result = json.loads(move_ticket_to_done(ticket2_path))

        # TODO must NOT be marked done because ticket 001 suppressed it
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        assert "completed_todos" not in result
        assert (sprint_issues / "umbrella.md").exists()
        from clasi.frontmatter import read_frontmatter as rfm
        assert rfm(sprint_issues / "umbrella.md")["status"] == "in-progress"

    def test_completed_todos_not_populated_for_suppressed(self, work_dir):
        """result['completed_todos'] must not include suppressed TODOs."""
        from clasi.tools.artifact_tools import move_ticket_to_done

        todo, ticket_path = self._setup_sprint_with_todo(work_dir, "umbrella.md")

        fm = read_frontmatter(ticket_path)
        fm["completes_issue"] = False
        write_frontmatter(ticket_path, fm)

        result = json.loads(move_ticket_to_done(ticket_path))

        # Key must be absent entirely (not an empty list)
        assert "completed_todos" not in result
        # TODO must still be in-progress (not marked done)
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        from clasi.frontmatter import read_frontmatter as rfm
        assert rfm(sprint_issues / "umbrella.md")["status"] == "in-progress"


class TestSplitIssue:
    """Tests for the split_issue MCP tool."""

    @pytest.fixture
    def todo_dir(self, tmp_path, monkeypatch):
        """Set up a temporary working directory with .clasi/issues/ (pending pool)."""
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        todo = tmp_path / ".clasi" / "issues"
        todo.mkdir(parents=True)
        return todo

    @pytest.fixture
    def work_dir(self, tmp_path, monkeypatch):
        """Set up a working directory suitable for sprint operations."""
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        todo = tmp_path / ".clasi" / "issues"
        todo.mkdir(parents=True)
        return tmp_path

    def _sprint_issues_dir(self, work_dir, sprint_id: str = "001"):
        """Return the sprint-scoped issues directory."""
        sprints_dir = work_dir / ".clasi" / "sprints"
        for d in sorted(sprints_dir.iterdir()):
            if d.is_dir() and d.name.startswith(sprint_id + "-"):
                return d / "issues"
        raise ValueError(f"Sprint dir for {sprint_id!r} not found")

    def test_split_pending_pool_issue(self, todo_dir):
        """Splitting a pending-pool issue creates a sibling in .clasi/issues/."""
        (todo_dir / "original.md").write_text(
            "---\nstatus: pending\n---\n\n# Original\n\nSome work here.\n"
        )

        result = json.loads(
            split_issue("original.md", "new-part.md", "New Part", "New part body.")
        )

        # New file exists as sibling
        assert (todo_dir / "new-part.md").exists()
        # Return value contains correct paths
        assert result["new_path"].endswith("new-part.md")
        assert result["original_path"].endswith("original.md")

        # New file has correct frontmatter
        new_fm = read_frontmatter(todo_dir / "new-part.md")
        assert new_fm["status"] == "pending"
        assert new_fm["split_from"] == "original.md"
        assert "sprint" not in new_fm

        # Original has split_into set
        orig_fm = read_frontmatter(todo_dir / "original.md")
        assert "new-part.md" in orig_fm["split_into"]

    def test_split_sprint_scoped_in_progress_issue(self, work_dir):
        """Splitting a sprint-scoped in-progress issue creates a sibling in <sprint>/issues/ with inherited sprint context."""
        create_sprint("Test Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / ".clasi" / "issues"
        (todo / "big-issue.md").write_text(
            "---\nstatus: pending\n---\n\n# Big Issue\n\nBody.\n"
        )

        # Move to in-progress via create_ticket
        create_ticket("001", "Task", todo="big-issue.md")

        # Now the issue is in sprint-scoped dir with status in-progress
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        assert (sprint_issues / "big-issue.md").exists()

        result = json.loads(
            split_issue("big-issue.md", "big-issue-part2.md", "Big Issue Part 2", "Remaining scope.")
        )

        # New file is a sibling in the sprint issues dir
        assert (sprint_issues / "big-issue-part2.md").exists()
        assert result["new_path"].endswith("big-issue-part2.md")

        # New file inherits sprint context
        new_fm = read_frontmatter(sprint_issues / "big-issue-part2.md")
        assert new_fm["status"] == "in-progress"
        assert new_fm["sprint"] == "001"
        assert new_fm["split_from"] == "big-issue.md"

        # Original has split_into
        orig_fm = read_frontmatter(sprint_issues / "big-issue.md")
        assert "big-issue-part2.md" in orig_fm["split_into"]

    def test_split_from_sprint_scoped_done(self, work_dir):
        """Splitting from sprint-scoped done/ creates a sibling in done/ with pending status.

        A done issue is no longer in-progress, so the new file starts as pending
        (no sprint inherited) — this mirrors the architecture decision.
        """
        create_sprint("Test Sprint")
        _advance_to_ticketing(work_dir, "001")

        todo = work_dir / ".clasi" / "issues"
        (todo / "done-issue.md").write_text(
            "---\nstatus: pending\n---\n\n# Done Issue\n\nBody.\n"
        )

        # Move to in-progress then to done
        create_ticket("001", "Task", todo="done-issue.md")
        sprint_issues = self._sprint_issues_dir(work_dir, "001")
        done_dir = sprint_issues / "done"
        done_dir.mkdir(exist_ok=True)
        (sprint_issues / "done-issue.md").rename(done_dir / "done-issue.md")
        # Update frontmatter to done
        fm = read_frontmatter(done_dir / "done-issue.md")
        fm["status"] = "done"
        write_frontmatter(done_dir / "done-issue.md", fm)

        result = json.loads(
            split_issue("done-issue.md", "done-split.md", "Split From Done", "Leftover scope.")
        )

        # New file is a sibling in done/
        assert (done_dir / "done-split.md").exists()
        # New file is pending (done issue is not in-progress)
        new_fm = read_frontmatter(done_dir / "done-split.md")
        assert new_fm["status"] == "pending"
        assert "sprint" not in new_fm
        assert new_fm["split_from"] == "done-issue.md"

        # Original has split_into
        orig_fm = read_frontmatter(done_dir / "done-issue.md")
        assert "done-split.md" in orig_fm["split_into"]

    def test_split_copies_source(self, todo_dir):
        """Source URL from original is copied to the new file."""
        (todo_dir / "sourced.md").write_text(
            "---\nstatus: pending\nsource: https://example.com\n---\n\n# Sourced Issue\n"
        )

        split_issue("sourced.md", "sourced-split.md", "Sourced Split", "Body.")

        new_fm = read_frontmatter(todo_dir / "sourced-split.md")
        assert new_fm["source"] == "https://example.com"

    def test_split_no_source(self, todo_dir):
        """When original has no source, new file has no source key."""
        (todo_dir / "no-source.md").write_text(
            "---\nstatus: pending\n---\n\n# No Source\n"
        )

        split_issue("no-source.md", "no-source-split.md", "No Source Split", "Body.")

        new_fm = read_frontmatter(todo_dir / "no-source-split.md")
        assert "source" not in new_fm

    def test_split_updated_body(self, todo_dir):
        """updated_body replaces the original's body content."""
        (todo_dir / "original.md").write_text(
            "---\nstatus: pending\n---\n\n# Original\n\nOld body content.\n"
        )

        split_issue(
            "original.md",
            "split.md",
            "Split",
            "New file body.",
            updated_body="\n# Original\n\nRevised body content.\n",
        )

        _, orig_body = __import__("clasi.frontmatter", fromlist=["read_document"]).read_document(
            todo_dir / "original.md"
        )
        assert "Revised body content." in orig_body
        assert "Old body content." not in orig_body

    def test_split_twice_appends(self, todo_dir):
        """Splitting the same issue twice appends to split_into, does not overwrite."""
        (todo_dir / "original.md").write_text(
            "---\nstatus: pending\n---\n\n# Original\n\nBody.\n"
        )

        split_issue("original.md", "split-1.md", "Split 1", "First split.")
        split_issue("original.md", "split-2.md", "Split 2", "Second split.")

        orig_fm = read_frontmatter(todo_dir / "original.md")
        assert "split-1.md" in orig_fm["split_into"]
        assert "split-2.md" in orig_fm["split_into"]
        assert len(orig_fm["split_into"]) == 2

    def test_split_target_exists_raises(self, todo_dir):
        """Raises ValueError when new_filename already exists."""
        (todo_dir / "original.md").write_text(
            "---\nstatus: pending\n---\n\n# Original\n"
        )
        (todo_dir / "existing.md").write_text(
            "---\nstatus: pending\n---\n\n# Already Exists\n"
        )

        with pytest.raises(ValueError, match="Target file already exists"):
            split_issue("original.md", "existing.md", "Conflict", "Body.")

    def test_split_missing_original_raises(self, todo_dir):
        """Raises ValueError when the original issue is not found."""
        with pytest.raises(ValueError, match="Issue not found"):
            split_issue("nonexistent.md", "new.md", "New", "Body.")

    def test_split_returns_paths(self, todo_dir):
        """Return value contains original_path and new_path as strings."""
        (todo_dir / "issue.md").write_text(
            "---\nstatus: pending\n---\n\n# Issue\n"
        )

        result = json.loads(split_issue("issue.md", "issue-part2.md", "Part 2", "Body."))

        assert "original_path" in result
        assert "new_path" in result
        assert isinstance(result["original_path"], str)
        assert isinstance(result["new_path"], str)
        assert result["original_path"].endswith("issue.md")
        assert result["new_path"].endswith("issue-part2.md")

    def test_split_new_file_body_content(self, todo_dir):
        """New file contains the title heading and body content."""
        (todo_dir / "issue.md").write_text(
            "---\nstatus: pending\n---\n\n# Issue\n"
        )

        split_issue("issue.md", "new-issue.md", "New Title", "New body content here.")

        from clasi.frontmatter import read_document
        _, body = read_document(todo_dir / "new-issue.md")
        assert "# New Title" in body
        assert "New body content here." in body


class TestLinkSprintIssues:
    """Tests for the link_sprint_issues MCP tool."""

    @pytest.fixture
    def work_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        issues = tmp_path / ".clasi" / "issues"
        issues.mkdir(parents=True)
        return tmp_path

    def _sprint_dir(self, work_dir, sprint_id: str = "001"):
        """Return the sprint directory path."""
        sprints_dir = work_dir / ".clasi" / "sprints"
        for d in sorted(sprints_dir.iterdir()):
            if d.is_dir() and d.name.startswith(sprint_id + "-"):
                return d
        raise ValueError(f"Sprint dir for {sprint_id!r} not found")

    def _issues_dir(self, work_dir):
        return work_dir / ".clasi" / "issues"

    def _make_issue(self, work_dir, filename: str, status: str = "pending", sprint: str | None = None):
        """Create an issue file in the pending pool."""
        lines = [f"---\nstatus: {status}\n"]
        if sprint is not None:
            lines.append(f"sprint: '{sprint}'\n")
        lines.append(f"---\n\n# {filename.removesuffix('.md')}\n")
        (self._issues_dir(work_dir) / filename).write_text("".join(lines))

    def test_links_two_valid_issues(self, work_dir):
        """Two valid issues get sprint: <id> set; sprint.md issues: contains both."""
        create_sprint("My Sprint")
        self._make_issue(work_dir, "issue-a.md")
        self._make_issue(work_dir, "issue-b.md")

        result = json.loads(link_sprint_issues("001", ["issue-a.md", "issue-b.md"]))

        assert result["sprint_id"] == "001"
        assert sorted(result["linked"]) == ["issue-a.md", "issue-b.md"]
        assert result["already_linked"] == []
        assert result["not_found"] == []

        # Issues have sprint: '001' written to frontmatter
        fm_a = read_frontmatter(self._issues_dir(work_dir) / "issue-a.md")
        fm_b = read_frontmatter(self._issues_dir(work_dir) / "issue-b.md")
        assert fm_a["sprint"] == "001"
        assert fm_b["sprint"] == "001"

        # Sprint.md issues: list contains both filenames
        sprint_fm = read_frontmatter(self._sprint_dir(work_dir) / "sprint.md")
        assert "issue-a.md" in sprint_fm["issues"]
        assert "issue-b.md" in sprint_fm["issues"]

    def test_idempotent_second_call(self, work_dir):
        """Calling twice with same args → all in already_linked, no duplicates."""
        create_sprint("My Sprint")
        self._make_issue(work_dir, "issue-a.md")

        link_sprint_issues("001", ["issue-a.md"])
        result = json.loads(link_sprint_issues("001", ["issue-a.md"]))

        assert result["linked"] == []
        assert result["already_linked"] == ["issue-a.md"]
        assert result["not_found"] == []

        # Sprint.md issues: has exactly one entry (no duplicate)
        sprint_fm = read_frontmatter(self._sprint_dir(work_dir) / "sprint.md")
        assert sprint_fm["issues"].count("issue-a.md") == 1

    def test_not_found_continues(self, work_dir):
        """Unknown filename → in not_found, does not error."""
        create_sprint("My Sprint")

        result = json.loads(link_sprint_issues("001", ["ghost.md"]))

        assert result["not_found"] == ["ghost.md"]
        assert result["linked"] == []
        assert result["already_linked"] == []

    def test_mixed_valid_already_linked_not_found(self, work_dir):
        """One valid, one already linked, one not found → correct categorization."""
        create_sprint("My Sprint")
        self._make_issue(work_dir, "new-issue.md")
        self._make_issue(work_dir, "old-issue.md", sprint="001")

        result = json.loads(
            link_sprint_issues("001", ["new-issue.md", "old-issue.md", "missing.md"])
        )

        assert result["linked"] == ["new-issue.md"]
        assert result["already_linked"] == ["old-issue.md"]
        assert result["not_found"] == ["missing.md"]

    def test_create_sprint_produces_issues_field(self, work_dir):
        """create_sprint produces a sprint.md with issues: [] in frontmatter."""
        result_str = create_sprint("Template Test Sprint")
        result = json.loads(result_str)
        sprint_id = result["id"]

        sprint_dir = self._sprint_dir(work_dir, sprint_id)
        sprint_fm = read_frontmatter(sprint_dir / "sprint.md")

        assert "issues" in sprint_fm
        assert sprint_fm["issues"] == []

    def test_unknown_sprint_returns_error(self, work_dir):
        """Calling with a non-existent sprint_id returns error key."""
        result = json.loads(link_sprint_issues("999", ["issue-a.md"]))
        assert "error" in result

    def test_sprint_issues_list_no_duplicates_on_repeated_link(self, work_dir):
        """Calling link_sprint_issues with overlapping lists never duplicates entries."""
        create_sprint("Dup Test")
        self._make_issue(work_dir, "item-a.md")
        self._make_issue(work_dir, "item-b.md")

        link_sprint_issues("001", ["item-a.md"])
        link_sprint_issues("001", ["item-a.md", "item-b.md"])

        sprint_fm = read_frontmatter(self._sprint_dir(work_dir) / "sprint.md")
        assert sprint_fm["issues"].count("item-a.md") == 1
        assert sprint_fm["issues"].count("item-b.md") == 1
