"""Tests for the Issue class."""

from pathlib import Path

from clasi.project import Project
from clasi.issue import Issue


def _make_sprint(proj: Project, sprint_id: str = "001") -> Path:
    """Create a minimal sprint directory so get_sprint() can resolve it."""
    sprint_dir = proj.sprints_dir / f"{sprint_id}-test-sprint"
    sprint_dir.mkdir(parents=True, exist_ok=True)
    sprint_dir.joinpath("sprint.md").write_text(
        f'---\nid: "{sprint_id}"\ntitle: "Test Sprint"\nstatus: executing\n---\n',
        encoding="utf-8",
    )
    return sprint_dir


def _make_issue(tmp_path, filename="my-idea.md", title="My Idea",
                status="pending", sprint=None, tickets=None, source=None):
    """Create a project with an issue file."""
    proj = Project(tmp_path)

    if status == "in-progress":
        # Issues in-progress are now stored under the sprint dir; fall back to
        # issues_dir root for fixture purposes when no sprint path is available.
        todo_dir = proj.issues_dir / "in-progress"
    elif status == "done":
        todo_dir = proj.issues_dir / "done"
    else:
        todo_dir = proj.issues_dir
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

    issue = Issue(path, proj)
    return proj, issue


class TestIssueProperties:
    """Test Issue property accessors."""

    def test_title_from_heading(self, tmp_path):
        _, t = _make_issue(tmp_path, title="Great Idea")
        assert t.title == "Great Idea"

    def test_title_fallback_to_stem(self, tmp_path):
        proj = Project(tmp_path)
        proj.issues_dir.mkdir(parents=True)
        path = proj.issues_dir / "no-heading.md"
        path.write_text("---\nstatus: pending\n---\nNo heading here.\n", encoding="utf-8")
        t = Issue(path, proj)
        assert t.title == "no-heading"

    def test_status_pending(self, tmp_path):
        _, t = _make_issue(tmp_path, status="pending")
        assert t.status == "pending"

    def test_status_in_progress(self, tmp_path):
        _, t = _make_issue(tmp_path, status="in-progress")
        assert t.status == "in-progress"

    def test_sprint_none(self, tmp_path):
        _, t = _make_issue(tmp_path)
        assert t.sprint is None

    def test_sprint_set(self, tmp_path):
        _, t = _make_issue(tmp_path, status="in-progress", sprint="001")
        assert t.sprint == "001"

    def test_tickets_empty(self, tmp_path):
        _, t = _make_issue(tmp_path)
        assert t.tickets == []

    def test_tickets_list(self, tmp_path):
        _, t = _make_issue(tmp_path, status="in-progress",
                           sprint="001", tickets='["001-001", "001-002"]')
        assert t.tickets == ["001-001", "001-002"]

    def test_source(self, tmp_path):
        _, t = _make_issue(tmp_path, source="https://example.com")
        assert t.source == "https://example.com"

    def test_source_none(self, tmp_path):
        _, t = _make_issue(tmp_path)
        assert t.source is None

    def test_path(self, tmp_path):
        _, t = _make_issue(tmp_path, filename="test.md")
        assert t.path.name == "test.md"

    def test_frontmatter(self, tmp_path):
        _, t = _make_issue(tmp_path)
        assert "status" in t.frontmatter

    def test_content(self, tmp_path):
        _, t = _make_issue(tmp_path)
        assert "Some description." in t.content


class TestIssueMoveToInProgress:
    """Test move_to_in_progress."""

    def test_move_updates_frontmatter(self, tmp_path):
        proj, t = _make_issue(tmp_path, status="pending")
        _make_sprint(proj, "001")
        t.move_to_in_progress("001", "001-001")
        assert t.status == "in-progress"
        assert t.sprint == "001"
        assert "001-001" in t.tickets

    def test_move_changes_directory(self, tmp_path):
        proj, t = _make_issue(tmp_path, status="pending")
        sprint_dir = _make_sprint(proj, "001")
        t.move_to_in_progress("001", "001-001")
        assert t.path.parent == sprint_dir / "issues"
        assert t.path.exists()

    def test_move_already_in_progress(self, tmp_path):
        proj, t = _make_issue(tmp_path, status="in-progress", sprint="001")
        sprint_dir = _make_sprint(proj, "001")
        # Move into sprint issues dir first so it is already there
        sprint_issues = sprint_dir / "issues"
        sprint_issues.mkdir(parents=True, exist_ok=True)
        new_path = sprint_issues / t.path.name
        t.path.rename(new_path)
        from clasi.artifact import Artifact
        t._artifact = Artifact(new_path)
        # Should not raise, just update
        t.move_to_in_progress("001", "001-002")
        assert t.path.parent == sprint_issues
        assert "001-002" in t.tickets

    def test_move_creates_sprint_issues_dir(self, tmp_path):
        """Issues directory is created automatically on first move."""
        proj, t = _make_issue(tmp_path, status="pending")
        sprint_dir = _make_sprint(proj, "002")
        sprint_issues = sprint_dir / "issues"
        assert not sprint_issues.exists()
        t.move_to_in_progress("002", "002-001")
        assert sprint_issues.exists()
        assert t.path.parent == sprint_issues

    def test_move_not_placed_in_global_in_progress(self, tmp_path):
        """No file is created at the old global in-progress directory."""
        proj, t = _make_issue(tmp_path, status="pending")
        _make_sprint(proj, "003")
        t.move_to_in_progress("003", "003-001")
        global_in_progress = proj.issues_dir / "in-progress"
        assert not global_in_progress.exists()


class TestIssueMoveToDone:
    """Test move_to_done."""

    def test_move_to_done_sets_status(self, tmp_path):
        """move_to_done writes status=done to frontmatter."""
        _, t = _make_issue(tmp_path, status="pending")
        t.move_to_done()
        assert t.status == "done"

    def test_move_to_done_moves_to_done_dir(self, tmp_path):
        """move_to_done moves the file into a done/ subdirectory."""
        proj, t = _make_issue(tmp_path, status="pending")
        original_name = t.path.name
        t.move_to_done()
        assert t.path.parent.name == "done"
        assert t.path.name == original_name
        assert t.path.exists()

    def test_move_to_done_pool_issue(self, tmp_path):
        """Issue in .clasi/issues/ moves to .clasi/issues/done/."""
        proj, t = _make_issue(tmp_path, status="pending")
        original_name = t.path.name
        t.move_to_done()
        assert t.path.parent == proj.issues_dir / "done"
        assert t.path.name == original_name
        assert t.path.exists()

    def test_move_to_done_idempotent(self, tmp_path):
        """Calling move_to_done twice is a no-op on second call."""
        _, t = _make_issue(tmp_path, status="pending")
        t.move_to_done()
        first_path = t.path
        assert t.path.parent.name == "done"
        # Call again — should not raise, should stay in done/
        t.move_to_done()
        assert t.path == first_path
        assert t.status == "done"

    def test_move_to_done_sprint_in_issues_dir(self, tmp_path):
        """Issue in sprint issues/ dir moves to sprint issues/done/ on move_to_done."""
        proj, t = _make_issue(tmp_path, status="pending")
        sprint_dir = _make_sprint(proj, "001")
        t.move_to_in_progress("001", "001-001")
        sprint_issues = sprint_dir / "issues"
        assert t.path.parent == sprint_issues

        t.move_to_done(sprint_id="001", ticket_ids=["001-001"])
        assert t.status == "done"
        assert t.path.parent == sprint_issues / "done"
        assert t.path.exists()

    def test_move_to_done_sets_sprint_frontmatter(self, tmp_path):
        """sprint_id argument is written to frontmatter."""
        proj, t = _make_issue(tmp_path, status="pending")
        _make_sprint(proj, "001")
        t.move_to_in_progress("001", "001-001")
        t.move_to_done(sprint_id="001")
        assert t.sprint == "001"

    def test_move_to_done_sets_tickets_frontmatter(self, tmp_path):
        """ticket_ids argument is written to frontmatter."""
        proj, t = _make_issue(tmp_path, status="pending")
        _make_sprint(proj, "001")
        t.move_to_in_progress("001", "001-001")
        t.move_to_done(ticket_ids=["001-001", "001-002"])
        assert "001-001" in t.tickets
        assert "001-002" in t.tickets

    def test_move_to_done_from_pending_no_args(self, tmp_path):
        """move_to_done with no args works for a pending issue."""
        _, t = _make_issue(tmp_path, status="pending")
        t.move_to_done()
        assert t.status == "done"


class TestIssueAddTicketRef:
    """Test add_ticket_ref."""

    def test_add_first_ticket(self, tmp_path):
        _, t = _make_issue(tmp_path)
        t.add_ticket_ref("001-001")
        assert t.tickets == ["001-001"]

    def test_add_duplicate_ticket(self, tmp_path):
        _, t = _make_issue(tmp_path)
        t.add_ticket_ref("001-001")
        t.add_ticket_ref("001-001")
        assert t.tickets == ["001-001"]

    def test_add_multiple_tickets(self, tmp_path):
        _, t = _make_issue(tmp_path)
        t.add_ticket_ref("001-001")
        t.add_ticket_ref("001-002")
        assert t.tickets == ["001-001", "001-002"]


class TestProjectListIssues:
    """Test Project.list_issues and get_issue."""

    def test_list_issues_pending(self, tmp_path):
        proj, _ = _make_issue(tmp_path, filename="a.md", status="pending")
        # Add another
        path2 = proj.issues_dir / "b.md"
        path2.write_text("---\nstatus: pending\n---\n# B\n", encoding="utf-8")
        issues = proj.list_issues()
        assert len(issues) == 2

    def test_list_issues_pending_pool_only(self, tmp_path):
        """list_issues() returns only files in the pending pool top-level dir."""
        proj = Project(tmp_path)
        proj.issues_dir.mkdir(parents=True)
        (proj.issues_dir / "pending.md").write_text(
            "---\nstatus: pending\n---\n# Pending\n", encoding="utf-8"
        )
        # A file in a subdirectory should NOT be included
        ip_dir = proj.issues_dir / "in-progress"
        ip_dir.mkdir()
        (ip_dir / "active.md").write_text(
            "---\nstatus: in-progress\nsprint: \"001\"\n---\n# Active\n",
            encoding="utf-8",
        )
        issues = proj.list_issues()
        assert len(issues) == 1
        assert issues[0].path.name == "pending.md"

    def test_list_issues_excludes_done(self, tmp_path):
        proj = Project(tmp_path)
        proj.issues_dir.mkdir(parents=True)
        (proj.issues_dir / "pending.md").write_text(
            "---\nstatus: pending\n---\n# Pending\n", encoding="utf-8"
        )
        done_dir = proj.issues_dir / "done"
        done_dir.mkdir()
        (done_dir / "finished.md").write_text(
            "---\nstatus: done\n---\n# Finished\n", encoding="utf-8"
        )
        issues = proj.list_issues()
        assert len(issues) == 1

    def test_get_issue(self, tmp_path):
        proj, _ = _make_issue(tmp_path, filename="idea.md", title="My Idea")
        t = proj.get_issue("idea.md")
        assert t.title == "My Idea"

    def test_get_issue_finds_sprint_scoped_issue(self, tmp_path):
        """get_issue finds issues in <sprint>/issues/ directories."""
        proj = Project(tmp_path)
        sprint_dir = _make_sprint(proj, "001")
        issues_dir = sprint_dir / "issues"
        issues_dir.mkdir()
        (issues_dir / "wip.md").write_text(
            "---\nstatus: in-progress\nsprint: \"001\"\n---\n# WIP\n",
            encoding="utf-8",
        )
        t = proj.get_issue("wip.md")
        assert t.status == "in-progress"

    def test_get_issue_not_found(self, tmp_path):
        proj = Project(tmp_path)
        proj.issues_dir.mkdir(parents=True)
        try:
            proj.get_issue("nonexistent.md")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_get_issue_finds_sprint_done_dir(self, tmp_path):
        """get_issue finds issues in <sprint>/issues/done/ directories."""
        proj = Project(tmp_path)
        sprint_dir = _make_sprint(proj, "001")
        done_dir = sprint_dir / "issues" / "done"
        done_dir.mkdir(parents=True)
        (done_dir / "finished.md").write_text(
            "---\nstatus: done\nsprint: \"001\"\n---\n# Finished\n",
            encoding="utf-8",
        )
        t = proj.get_issue("finished.md")
        assert t.status == "done"
        assert t.path.parent.name == "done"


class TestSprintIssuesDoneDir:
    """Tests for Sprint.issues_done_dir and list_issues scanning both dirs."""

    def test_issues_done_dir_property(self, tmp_path):
        """Sprint.issues_done_dir returns <sprint_path>/issues/done."""
        proj = Project(tmp_path)
        sprint_dir = _make_sprint(proj, "001")
        sprint = proj.get_sprint("001")
        assert sprint.issues_done_dir == sprint_dir / "issues" / "done"

    def test_list_issues_includes_done_dir(self, tmp_path):
        """Sprint.list_issues() includes issues from issues/done/."""
        proj = Project(tmp_path)
        sprint_dir = _make_sprint(proj, "001")
        sprint = proj.get_sprint("001")

        issues_dir = sprint_dir / "issues"
        done_dir = issues_dir / "done"
        issues_dir.mkdir(parents=True, exist_ok=True)
        done_dir.mkdir(exist_ok=True)

        (issues_dir / "active.md").write_text(
            "---\nstatus: in-progress\n---\n# Active\n", encoding="utf-8"
        )
        (done_dir / "finished.md").write_text(
            "---\nstatus: done\n---\n# Finished\n", encoding="utf-8"
        )

        issues = sprint.list_issues()
        names = [i.path.name for i in issues]
        assert "active.md" in names
        assert "finished.md" in names
        assert len(issues) == 2

    def test_list_issues_sorted_across_dirs(self, tmp_path):
        """Sprint.list_issues() returns issues from both dirs in sorted order within each dir."""
        proj = Project(tmp_path)
        sprint_dir = _make_sprint(proj, "001")
        sprint = proj.get_sprint("001")

        issues_dir = sprint_dir / "issues"
        done_dir = issues_dir / "done"
        issues_dir.mkdir(parents=True, exist_ok=True)
        done_dir.mkdir(exist_ok=True)

        (issues_dir / "bbb.md").write_text("---\nstatus: in-progress\n---\n# B\n", encoding="utf-8")
        (done_dir / "aaa.md").write_text("---\nstatus: done\n---\n# A\n", encoding="utf-8")

        issues = sprint.list_issues()
        # issues_dir comes before issues_done_dir; within each dir files are sorted
        assert issues[0].path.name == "bbb.md"
        assert issues[1].path.name == "aaa.md"

    def test_list_issues_empty_when_neither_dir_exists(self, tmp_path):
        """Sprint.list_issues() returns [] when neither issues/ nor issues/done/ exists."""
        proj = Project(tmp_path)
        _make_sprint(proj, "001")
        sprint = proj.get_sprint("001")
        assert not sprint.issues_dir.exists()
        assert not sprint.issues_done_dir.exists()
        assert sprint.list_issues() == []
