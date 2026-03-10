"""Tests for sprint review MCP tools."""

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from claude_agent_skills.artifact_tools import (
    create_sprint,
    create_ticket,
    move_ticket_to_done,
    review_sprint_post_close,
    review_sprint_pre_close,
    review_sprint_pre_execution,
    update_ticket_status,
)
from claude_agent_skills.frontmatter import read_frontmatter, write_frontmatter
from claude_agent_skills.state_db import (
    acquire_lock,
    advance_phase,
    record_gate,
)


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    """Set up a temporary working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _advance_to_ticketing(work_dir, sprint_id: str) -> None:
    """Advance a sprint through review gates to ticketing phase."""
    db_path = work_dir / "docs" / "plans" / ".clasi.db"
    advance_phase(db_path, sprint_id)
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")
    advance_phase(db_path, sprint_id)


def _advance_to_executing(work_dir, sprint_id: str) -> None:
    """Advance a sprint through to execution phase."""
    _advance_to_ticketing(work_dir, sprint_id)
    db_path = work_dir / "docs" / "plans" / ".clasi.db"
    acquire_lock(db_path, sprint_id)
    advance_phase(db_path, sprint_id)


def _make_sprint_ready_for_execution(work_dir, sprint_id: str = "001"):
    """Create a sprint with real planning docs and tickets, ready for execution."""
    create_sprint("Test Sprint")
    sprint_dir = work_dir / "docs" / "plans" / "sprints" / "001-test-sprint"

    # Fill in sprint.md with real content
    fm = read_frontmatter(sprint_dir / "sprint.md")
    fm["status"] = "active"
    write_frontmatter(sprint_dir / "sprint.md", fm)
    (sprint_dir / "sprint.md").write_text(
        (sprint_dir / "sprint.md").read_text()
        .replace("(Describe what this sprint aims to accomplish.)",
                 "Build the widget system.")
        .replace("(What problem does this sprint address?)",
                 "We need widgets.")
        .replace("(High-level description of the approach.)",
                 "Add widget module.")
        .replace("(How will we know the sprint succeeded?)",
                 "Widgets work."),
    )

    # Fill in usecases.md with real content
    fm_uc = read_frontmatter(sprint_dir / "usecases.md")
    fm_uc["status"] = "approved"
    write_frontmatter(sprint_dir / "usecases.md", fm_uc)
    (sprint_dir / "usecases.md").write_text(
        "---\nstatus: approved\n---\n\n# Sprint 001 Use Cases\n\n"
        "## SUC-001-001: Create Widget\n\n"
        "- **Actor**: Developer\n"
        "- **Main Flow**: Create a widget\n",
    )

    # Fill in architecture.md with real content
    fm_arch = read_frontmatter(sprint_dir / "architecture.md")
    fm_arch["status"] = "approved"
    write_frontmatter(sprint_dir / "architecture.md", fm_arch)
    (sprint_dir / "architecture.md").write_text(
        "---\nstatus: approved\n---\n\n"
        "# Architecture\n\n"
        "## Architecture Overview\n\nThe widget module adds a new component.\n\n"
        "## Component Design\n\n### Component: Widget Engine\n\n"
        "Handles widget lifecycle.\n\n"
        "## Sprint Changes\n\nAdded widget engine component.\n",
    )

    # Create tickets
    _advance_to_ticketing(work_dir, sprint_id)
    create_ticket(sprint_id, "Implement widget")
    create_ticket(sprint_id, "Add widget tests")

    return sprint_dir


class TestReviewSprintPreExecution:
    """Tests for review_sprint_pre_execution."""

    def test_happy_path_passes(self, work_dir):
        """A properly set up sprint passes pre-execution review."""
        _make_sprint_ready_for_execution(work_dir)
        result = json.loads(review_sprint_pre_execution("001"))
        assert result["passed"] is True
        assert result["issues"] == []

    def test_sprint_not_found(self, work_dir):
        result = json.loads(review_sprint_pre_execution("999"))
        assert result["passed"] is False
        assert result["issues"][0]["check"] == "sprint_dir_exists"

    def test_draft_status_detected(self, work_dir):
        """Planning docs with draft status are flagged."""
        create_sprint("Test Sprint")
        sprint_dir = work_dir / "docs" / "plans" / "sprints" / "001-test-sprint"
        _advance_to_ticketing(work_dir, "001")
        create_ticket("001", "A ticket")

        result = json.loads(review_sprint_pre_execution("001"))
        assert result["passed"] is False
        # sprint.md has status "planning" (not draft), but usecases and
        # architecture have status "draft"
        status_issues = [i for i in result["issues"]
                         if i["check"].endswith("_status")]
        assert len(status_issues) >= 2

    def test_template_placeholder_detected(self, work_dir):
        """Files with template placeholder content are flagged."""
        create_sprint("Test Sprint")
        sprint_dir = work_dir / "docs" / "plans" / "sprints" / "001-test-sprint"

        # Update statuses but leave content as template
        for f in ["usecases.md", "architecture.md"]:
            fm = read_frontmatter(sprint_dir / f)
            fm["status"] = "approved"
            write_frontmatter(sprint_dir / f, fm)

        fm_s = read_frontmatter(sprint_dir / "sprint.md")
        fm_s["status"] = "active"
        write_frontmatter(sprint_dir / "sprint.md", fm_s)

        _advance_to_ticketing(work_dir, "001")
        create_ticket("001", "A ticket")

        result = json.loads(review_sprint_pre_execution("001"))
        assert result["passed"] is False
        content_issues = [i for i in result["issues"]
                          if i["check"].endswith("_content")]
        assert len(content_issues) >= 1

    def test_no_tickets_detected(self, work_dir):
        """Sprint with no tickets is flagged."""
        create_sprint("Test Sprint")
        result = json.loads(review_sprint_pre_execution("001"))
        assert result["passed"] is False
        ticket_issues = [i for i in result["issues"]
                         if "ticket" in i["check"]]
        assert len(ticket_issues) >= 1

    @patch("claude_agent_skills.artifact_tools._check_git_branch")
    def test_wrong_branch_detected(self, mock_branch, work_dir):
        """Being on the wrong branch is flagged."""
        mock_branch.return_value = "master"
        _make_sprint_ready_for_execution(work_dir)
        result = json.loads(review_sprint_pre_execution("001"))
        assert result["passed"] is False
        branch_issues = [i for i in result["issues"]
                         if i["check"] == "correct_branch"]
        assert len(branch_issues) == 1

    def test_issue_structure(self, work_dir):
        """Issues have the required fields."""
        result = json.loads(review_sprint_pre_execution("999"))
        issue = result["issues"][0]
        assert "severity" in issue
        assert "check" in issue
        assert "message" in issue
        assert "fix" in issue
        assert "path" in issue


class TestReviewSprintPreClose:
    """Tests for review_sprint_pre_close."""

    def test_happy_path_passes(self, work_dir):
        """A sprint with all tickets done passes pre-close review."""
        sprint_dir = _make_sprint_ready_for_execution(work_dir)

        # Complete all tickets
        tickets_dir = sprint_dir / "tickets"
        for f in sorted(tickets_dir.glob("*.md")):
            fm = read_frontmatter(f)
            if fm.get("id"):
                update_ticket_status(str(f), "done")
                move_ticket_to_done(str(f))

        result = json.loads(review_sprint_pre_close("001"))
        assert result["passed"] is True
        assert result["issues"] == []

    def test_ticket_not_done_detected(self, work_dir):
        """Tickets not in done status are flagged."""
        _make_sprint_ready_for_execution(work_dir)
        result = json.loads(review_sprint_pre_close("001"))
        assert result["passed"] is False
        done_issues = [i for i in result["issues"]
                       if i["check"] == "ticket_done"]
        assert len(done_issues) >= 1

    def test_ticket_not_in_done_dir_detected(self, work_dir):
        """Tickets not moved to done/ directory are flagged."""
        sprint_dir = _make_sprint_ready_for_execution(work_dir)

        # Set status to done but don't move files
        tickets_dir = sprint_dir / "tickets"
        for f in sorted(tickets_dir.glob("*.md")):
            fm = read_frontmatter(f)
            if fm.get("id"):
                update_ticket_status(str(f), "done")

        result = json.loads(review_sprint_pre_close("001"))
        assert result["passed"] is False
        dir_issues = [i for i in result["issues"]
                      if i["check"] == "ticket_in_done_dir"]
        assert len(dir_issues) >= 1

    def test_draft_planning_docs_detected(self, work_dir):
        """Planning docs still in draft are flagged."""
        create_sprint("Test Sprint")
        sprint_dir = work_dir / "docs" / "plans" / "sprints" / "001-test-sprint"
        _advance_to_ticketing(work_dir, "001")
        create_ticket("001", "A ticket")

        # Complete ticket
        ticket_path = sprint_dir / "tickets" / "001-a-ticket.md"
        update_ticket_status(str(ticket_path), "done")
        move_ticket_to_done(str(ticket_path))

        result = json.loads(review_sprint_pre_close("001"))
        assert result["passed"] is False
        status_issues = [i for i in result["issues"]
                         if i["check"].endswith("_status")]
        assert len(status_issues) >= 1


class TestReviewSprintPostClose:
    """Tests for review_sprint_post_close."""

    def test_sprint_not_archived_detected(self, work_dir):
        """Sprint still in active directory is flagged."""
        _make_sprint_ready_for_execution(work_dir)

        with patch("claude_agent_skills.artifact_tools._check_git_branch",
                    return_value="master"):
            result = json.loads(review_sprint_post_close("001"))

        assert result["passed"] is False
        archive_issues = [i for i in result["issues"]
                          if i["check"] == "sprint_archived"]
        assert len(archive_issues) == 1

    @patch("claude_agent_skills.artifact_tools._check_git_branch")
    def test_wrong_branch_detected(self, mock_branch, work_dir):
        """Not being on master/main is flagged."""
        mock_branch.return_value = "sprint/001-test"
        _make_sprint_ready_for_execution(work_dir)

        result = json.loads(review_sprint_post_close("001"))
        assert result["passed"] is False
        branch_issues = [i for i in result["issues"]
                         if i["check"] == "on_main_branch"]
        assert len(branch_issues) == 1

    @patch("claude_agent_skills.artifact_tools._check_git_branch")
    def test_happy_path_archived_sprint(self, mock_branch, work_dir):
        """A properly archived sprint passes post-close review."""
        mock_branch.return_value = "master"
        sprint_dir = _make_sprint_ready_for_execution(work_dir)

        # Complete all tickets
        tickets_dir = sprint_dir / "tickets"
        for f in sorted(tickets_dir.glob("*.md")):
            fm = read_frontmatter(f)
            if fm.get("id"):
                update_ticket_status(str(f), "done")
                move_ticket_to_done(str(f))

        # Archive the sprint
        done_dir = work_dir / "docs" / "plans" / "sprints" / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(sprint_dir), str(done_dir / sprint_dir.name))

        result = json.loads(review_sprint_post_close("001"))
        assert result["passed"] is True
        assert result["issues"] == []

    def test_sprint_not_found(self, work_dir):
        """Sprint not found anywhere is flagged."""
        (work_dir / "docs" / "plans" / "sprints").mkdir(parents=True)

        with patch("claude_agent_skills.artifact_tools._check_git_branch",
                    return_value="master"):
            result = json.loads(review_sprint_post_close("999"))

        assert result["passed"] is False
        assert result["issues"][0]["check"] == "sprint_dir_exists"


class TestTemplatePlaceholderDetection:
    """Tests for _is_template_placeholder helper."""

    def test_template_content_detected(self, work_dir):
        """File with template content is detected as placeholder."""
        from claude_agent_skills.artifact_tools import _is_template_placeholder
        from claude_agent_skills.templates import SPRINT_TEMPLATE

        create_sprint("Test Sprint")
        sprint_dir = work_dir / "docs" / "plans" / "sprints" / "001-test-sprint"
        assert _is_template_placeholder(
            sprint_dir / "sprint.md", SPRINT_TEMPLATE,
        ) is True

    def test_real_content_not_detected(self, work_dir):
        """File with real content is not detected as placeholder."""
        from claude_agent_skills.artifact_tools import _is_template_placeholder
        from claude_agent_skills.templates import SPRINT_TEMPLATE

        # Create a file with real content
        f = work_dir / "test.md"
        f.write_text(
            "---\nstatus: active\n---\n\n# Sprint 001: Real Sprint\n\n"
            "## Goals\n\nBuild the real thing.\n\n"
            "## Problem\n\nWe need it.\n",
        )
        assert _is_template_placeholder(f, SPRINT_TEMPLATE) is False
