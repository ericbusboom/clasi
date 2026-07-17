"""System tests for sprint 021 ticket 006: sprint lifecycle integration of the
design overlay hooks (seed, commit-edits, apply) across
create_sprint/detail_sprint -> seed_sprint_design_overlay ->
review_sprint_pre_execution -> acquire_execution_lock -> close_sprint.

Two full-lifecycle paths are covered:
- opt-in ON: pristine seed commit, edit, diff+commit at pre-execution,
  branch cut from a tree that already has the edits, apply at close.
- opt-in OFF (default/unset): no design/ directory anywhere, no extra
  commits, existing lifecycle tools behave exactly as before this sprint.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from clasi.design.store import write_design_doc, write_system_doc
from clasi.frontmatter import read_frontmatter, write_frontmatter
from clasi.mcp_server import set_project
from clasi.state_db import advance_phase, record_gate
from clasi.tools.artifact_tools import (
    acquire_execution_lock,
    close_sprint,
    create_sprint,
    detail_sprint,
    review_sprint_pre_execution,
    seed_sprint_design_overlay,
)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True
    )
    assert result.returncode == 0, f"{args} failed: {result.stderr}"
    return result


def _init_repo(root: Path) -> None:
    _run(["init", "-b", "master"], root)
    _run(["config", "user.email", "test@example.com"], root)
    _run(["config", "user.name", "Test"], root)


def _commit_all(root: Path, message: str) -> None:
    _run(["add", "-A"], root)
    # Nothing to commit is fine for an empty initial state guard.
    status = _run(["status", "--porcelain"], root)
    if status.stdout.strip():
        _run(["commit", "-m", message], root)


def _configure_sources_and_opt_in(root: Path, enabled: bool) -> None:
    config_dir = root / ".clasi"
    config_dir.mkdir(parents=True, exist_ok=True)
    opt = "enabled" if enabled else "disabled"
    (config_dir / "config.yaml").write_text(
        f"sources:\n  - src\ndesign_docs: {opt}\n", encoding="utf-8"
    )


def _commit_count(root: Path) -> int:
    return int(_run(["rev-list", "--count", "HEAD"], root).stdout.strip())


def _log_subjects(root: Path) -> list[str]:
    result = _run(["log", "--format=%s"], root)
    return result.stdout.strip().split("\n")


def _git_status_porcelain(root: Path, path: str) -> str:
    return _run(["status", "--porcelain", "--", path], root).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A real git repo rooted at tmp_path, set as the active CLASI project."""
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("placeholder\n", encoding="utf-8")
    _commit_all(tmp_path, "initial commit")
    monkeypatch.chdir(tmp_path)
    set_project(tmp_path)
    return tmp_path


def _seed_canonical_docs(root: Path) -> None:
    """Write a minimal canonical docs/design/ doc set and commit it."""
    project = set_project(root)
    subsystem = (root / "src" / "clasi").resolve()
    subsystem.mkdir(parents=True, exist_ok=True)
    write_system_doc(project, "# System design\n\nOriginal system doc.\n")
    write_design_doc(project, subsystem, "# clasi subsystem\n\nOriginal.\n")
    _commit_all(root, "docs: seed canonical design doc set")


def _advance_to_ticketing(work_dir: Path, sprint_id: str) -> None:
    """Advance a sprint from planning-docs (post detail_sprint) to ticketing."""
    db_path = work_dir / ".clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # planning-docs -> architecture-review
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)  # architecture-review -> stakeholder-review
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")
    advance_phase(db_path, sprint_id)  # stakeholder-review -> ticketing


def _fill_sprint_placeholders(work_dir: Path, sprint_dir_name: str) -> None:
    """Replace sprint.md's template placeholders with real content and set
    status to 'active', so review_sprint_pre_execution's content/status
    checks pass -- unrelated to the design overlay hooks under test, but
    required for those hooks' step to actually run (it only runs after
    the pre-existing checks pass)."""
    sprint_md = work_dir / "clasi" / "sprints" / sprint_dir_name / "sprint.md"
    fm = read_frontmatter(sprint_md)
    fm["status"] = "active"
    write_frontmatter(sprint_md, fm)
    content = sprint_md.read_text(encoding="utf-8")
    for placeholder, real in [
        ("(Describe what this sprint aims to accomplish.)", "Ship the overlay lifecycle."),
        ("(What problem does this sprint address?)", "Architecture docs never merge back."),
        ("(High-level description of the approach.)", "Overlay copies applied at close."),
        ("(How will we know the sprint succeeded?)", "Overlay round-trips cleanly."),
    ]:
        content = content.replace(placeholder, real)
    sprint_md.write_text(content, encoding="utf-8")


class TestOptInFullLifecycle:
    def test_seed_commit_before_edits_git_log_ordering(self, repo):
        _configure_sources_and_opt_in(repo, enabled=True)
        _seed_canonical_docs(repo)

        create_sprint("Design Overlay Sprint")
        detail_sprint("001")

        commits_before_seed = _commit_count(repo)
        result = json.loads(
            seed_sprint_design_overlay("001", doc_names=["design.md"])
        )
        assert result["opted_in"] is True
        assert len(result["seeded"]) == 1

        # Pristine copy is committed immediately, before any edit.
        assert _commit_count(repo) == commits_before_seed + 1
        assert "seed sprint 001 design overlay" in _log_subjects(repo)[0]

        sprint_design_dir = repo / "clasi" / "sprints" / "001-design-overlay-sprint" / "design"
        overlay_file = sprint_design_dir / "design.md"
        assert overlay_file.exists()
        pristine_content = overlay_file.read_text(encoding="utf-8")

        # Now the sprint-planner edits the pristine copy.
        overlay_file.write_text(pristine_content + "\nSprint 001 addition.\n", encoding="utf-8")

        # Working tree is dirty exactly in design/.
        assert _git_status_porcelain(repo, str(sprint_design_dir)).strip() != ""

    def test_pre_execution_commits_edits_and_acquire_lock_branches_from_clean_tree(self, repo):
        _configure_sources_and_opt_in(repo, enabled=True)
        _seed_canonical_docs(repo)

        create_sprint("Design Overlay Sprint")
        detail_sprint("001")
        seed_sprint_design_overlay("001", doc_names=["design.md"])
        _advance_to_ticketing(repo, "001")
        _fill_sprint_placeholders(repo, "001-design-overlay-sprint")

        from clasi.tools.artifact_tools import create_ticket
        create_ticket("001", "Do the thing")

        sprint_design_dir = repo / "clasi" / "sprints" / "001-design-overlay-sprint" / "design"
        overlay_file = sprint_design_dir / "design.md"
        overlay_file.write_text(
            overlay_file.read_text(encoding="utf-8") + "\nEdited by sprint-planner.\n",
            encoding="utf-8",
        )

        commits_before_review = _commit_count(repo)
        # review_sprint_pre_execution runs on main, before
        # acquire_execution_lock cuts the sprint branch (see sprint.md Open
        # Question 3) -- match that by neutralizing the branch check here,
        # exactly as the existing pre-021 test suite does for cases not
        # specifically exercising branch mismatch (real git repos otherwise
        # report "master", tripping the unrelated correct_branch check).
        with patch("clasi.tools.artifact_tools._check_git_branch", return_value=""):
            review = json.loads(review_sprint_pre_execution("001"))
        assert review["passed"] is True
        assert review["design_overlay"]["opted_in"] is True
        assert review["design_overlay"]["committed"] is True
        assert len(review["design_overlay"]["diffs_written"]) == 1

        # Exactly one new commit (edits + diff file), tree now clean.
        assert _commit_count(repo) == commits_before_review + 1
        assert _git_status_porcelain(repo, str(sprint_design_dir)).strip() == ""
        assert (sprint_design_dir / "design.diff.md").exists()

        # acquire_execution_lock cuts the branch from a tree that already
        # includes the edited-copy commit (both commits happened on main).
        lock_result = json.loads(acquire_execution_lock("001"))
        assert lock_result["branch"] == "sprint/001-design-overlay-sprint"
        current_branch = _run(
            ["rev-parse", "--abbrev-ref", "HEAD"], repo
        ).stdout.strip()
        assert current_branch == "sprint/001-design-overlay-sprint"
        # The branch tip must contain the edit commit.
        assert _git_status_porcelain(repo, str(sprint_design_dir)).strip() == ""
        log_on_branch = _run(["log", "--format=%s", "-n", "3"], repo).stdout
        assert "commit sprint 001 design overlay edits" in log_on_branch

    def test_review_pre_execution_failure_does_not_commit_design(self, repo):
        """A sprint that fails existing pre-execution checks (no tickets)
        must not get a design commit either."""
        _configure_sources_and_opt_in(repo, enabled=True)
        _seed_canonical_docs(repo)

        create_sprint("Design Overlay Sprint")
        detail_sprint("001")
        seed_sprint_design_overlay("001", doc_names=["design.md"])
        # Deliberately do NOT advance to ticketing / create tickets, and do
        # NOT check out the sprint branch -- review_sprint_pre_execution
        # should report failing checks (wrong branch and/or no tickets).

        sprint_design_dir = repo / "clasi" / "sprints" / "001-design-overlay-sprint" / "design"
        overlay_file = sprint_design_dir / "design.md"
        overlay_file.write_text(
            overlay_file.read_text(encoding="utf-8") + "\nEdited.\n", encoding="utf-8"
        )

        commits_before = _commit_count(repo)
        review = json.loads(review_sprint_pre_execution("001"))
        assert review["passed"] is False
        assert "committed" not in review["design_overlay"]
        assert _commit_count(repo) == commits_before
        # Tree is still dirty -- nothing was committed.
        assert _git_status_porcelain(repo, str(sprint_design_dir)).strip() != ""

    def test_close_applies_overlay_to_canonical_docs_and_validates(self, repo):
        _configure_sources_and_opt_in(repo, enabled=True)
        _seed_canonical_docs(repo)

        create_sprint("Design Overlay Sprint")
        detail_sprint("001")
        seed_sprint_design_overlay("001", doc_names=["design.md"])
        _advance_to_ticketing(repo, "001")
        _fill_sprint_placeholders(repo, "001-design-overlay-sprint")

        from clasi.tools.artifact_tools import create_ticket, update_ticket_status, move_ticket_to_done
        ticket = json.loads(create_ticket("001", "Do the thing"))

        sprint_design_dir = repo / "clasi" / "sprints" / "001-design-overlay-sprint" / "design"
        overlay_file = sprint_design_dir / "design.md"
        final_content = overlay_file.read_text(encoding="utf-8") + "\nFinal sprint content.\n"
        overlay_file.write_text(final_content, encoding="utf-8")

        with patch("clasi.tools.artifact_tools._check_git_branch", return_value=""):
            review_sprint_pre_execution("001")
        acquire_execution_lock("001")

        # Finish the ticket so close_sprint's precondition passes.
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])
        _commit_all(repo, "chore: finish ticket 001")

        close_result = json.loads(
            close_sprint(
                "001",
                branch_name="sprint/001-design-overlay-sprint",
                main_branch="master",
                push_tags=False,
                delete_branch=False,
                test_command="",
            )
        )
        assert close_result.get("status") != "error", close_result

        canonical = repo / "docs" / "design" / "design.md"
        assert canonical.read_text(encoding="utf-8") == final_content

    def test_close_blocks_tag_on_apply_failure(self, repo, monkeypatch):
        _configure_sources_and_opt_in(repo, enabled=True)
        _seed_canonical_docs(repo)

        create_sprint("Design Overlay Sprint")
        detail_sprint("001")
        seed_sprint_design_overlay("001", doc_names=["design.md"])
        _advance_to_ticketing(repo, "001")
        _fill_sprint_placeholders(repo, "001-design-overlay-sprint")

        from clasi.tools.artifact_tools import create_ticket, update_ticket_status, move_ticket_to_done
        ticket = json.loads(create_ticket("001", "Do the thing"))

        sprint_design_dir = repo / "clasi" / "sprints" / "001-design-overlay-sprint" / "design"
        overlay_file = sprint_design_dir / "design.md"
        overlay_file.write_text(
            overlay_file.read_text(encoding="utf-8") + "\nEdit.\n", encoding="utf-8"
        )

        with patch("clasi.tools.artifact_tools._check_git_branch", return_value=""):
            review_sprint_pre_execution("001")
        acquire_execution_lock("001")

        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])
        _commit_all(repo, "chore: finish ticket 001")

        # Sabotage: delete the canonical docs/design/ dir on the branch so
        # apply cannot map the overlay file to a canonical target.
        import shutil
        shutil.rmtree(repo / "docs" / "design")
        _commit_all(repo, "chore: remove docs/design for failure test")

        result = json.loads(
            close_sprint(
                "001",
                branch_name="sprint/001-design-overlay-sprint",
                main_branch="master",
                push_tags=False,
                delete_branch=False,
                test_command="",
            )
        )
        assert result["status"] == "error"
        assert result["error"]["step"] == "design_overlay_apply"
        assert "design_overlay_apply" not in result["completed_steps"]
        assert "version_bump" not in result["completed_steps"]
        # No tag should have been created.
        tags = _run(["tag"], repo).stdout.strip()
        assert tags == ""


class TestOptOutRegression:
    """With opt-in off (default/unset), lifecycle tools behave exactly as
    they did before sprint 021 -- no design/ dir, no extra commits."""

    def test_no_design_dir_and_no_extra_commits_full_lifecycle(self, repo):
        # No config.yaml at all -- design_docs_opt_in is None (unset).
        create_sprint("Plain Sprint")
        detail_sprint("001")

        seed_result = json.loads(
            seed_sprint_design_overlay("001", doc_names=["design.md"])
        )
        assert seed_result["opted_in"] is False
        assert seed_result["seeded"] == []

        sprint_dir = repo / "clasi" / "sprints" / "001-plain-sprint"
        assert not (sprint_dir / "design").exists()

        _advance_to_ticketing(repo, "001")
        _fill_sprint_placeholders(repo, "001-plain-sprint")
        from clasi.tools.artifact_tools import create_ticket, update_ticket_status, move_ticket_to_done
        ticket = json.loads(create_ticket("001", "Do the thing"))

        with patch("clasi.tools.artifact_tools._check_git_branch", return_value=""):
            review = json.loads(review_sprint_pre_execution("001"))
        assert review["passed"] is True
        assert review["design_overlay"] == {"opted_in": False}

        acquire_execution_lock("001")
        update_ticket_status(ticket["path"], "done")
        move_ticket_to_done(ticket["path"])
        _commit_all(repo, "chore: finish ticket 001")

        close_result = json.loads(
            close_sprint(
                "001",
                branch_name="sprint/001-plain-sprint",
                main_branch="master",
                push_tags=False,
                delete_branch=False,
                test_command="",
            )
        )
        assert close_result.get("status") != "error", close_result
        assert not (repo / "docs" / "design").exists()

    def test_explicit_opt_out_behaves_same_as_unset(self, repo):
        _configure_sources_and_opt_in(repo, enabled=False)
        create_sprint("Plain Sprint")
        detail_sprint("001")

        seed_result = json.loads(
            seed_sprint_design_overlay("001", doc_names=["design.md"])
        )
        assert seed_result["opted_in"] is False
        assert seed_result["seeded"] == []
        sprint_dir = repo / "clasi" / "sprints" / "001-plain-sprint"
        assert not (sprint_dir / "design").exists()
