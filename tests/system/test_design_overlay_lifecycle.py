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
from clasi.tools.design_tools import validate_design


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
    """Write a minimal canonical docs/design/ doc set and commit it.

    Includes the required root-level ``src/DESIGN.md`` overview so the
    doc set validates cleanly at sprint close.
    """
    project = set_project(root)
    source_root = (root / "src").resolve()
    subsystem = (root / "src" / "clasi").resolve()
    subsystem.mkdir(parents=True, exist_ok=True)
    write_system_doc(project, "# System design\n\nOriginal system doc.\n")
    write_design_doc(project, source_root, "# src root overview\n\nOriginal.\n")
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


def _configure_multi_root_sources_and_opt_in(root: Path) -> None:
    """Two declared source roots (``src/firm``, ``src/host``), opted in.

    Each root gets its own required root-level ``DESIGN.md`` overview,
    plus one subsystem one level below it (``app`` under ``src/firm``,
    ``robot_radio`` under ``src/host``) -- the issue's own example
    pairing (sprint 025 issue: "firm/app and host/robot_radio"). Two
    separate source roots (rather than one root with two subsystems)
    keeps each subsystem exactly one level below its declared root,
    matching ``clasi.design.store._subsystem_dirs``'s "top-level
    subdirectory only" enumeration rule.
    """
    config_dir = root / ".clasi"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        "sources:\n  - src/firm\n  - src/host\ndesign_docs: enabled\n",
        encoding="utf-8",
    )


def _seed_multi_doc_canonical_docs(root: Path) -> None:
    """Write a full canonical doc set spanning two subsystems and commit it.

    System doc + each source root's own overview + each root's one
    subsystem doc (``src/firm/app/DESIGN.md``,
    ``src/host/robot_radio/DESIGN.md``) -- everything
    ``clasi.design.validator`` requires for a clean ``validate_design()``
    pass.
    """
    project = set_project(root)
    firm_root = (root / "src" / "firm").resolve()
    host_root = (root / "src" / "host").resolve()
    firm_app = (root / "src" / "firm" / "app").resolve()
    host_robot_radio = (root / "src" / "host" / "robot_radio").resolve()
    firm_app.mkdir(parents=True, exist_ok=True)
    host_robot_radio.mkdir(parents=True, exist_ok=True)

    write_system_doc(project, "# System design\n\nOriginal system doc.\n")
    write_design_doc(project, firm_root, "# firm root overview\n\nOriginal.\n")
    write_design_doc(project, host_root, "# host root overview\n\nOriginal.\n")
    write_design_doc(project, firm_app, "# firm/app subsystem\n\nOriginal firm/app.\n")
    write_design_doc(
        project,
        host_robot_radio,
        "# host/robot_radio subsystem\n\nOriginal host/robot_radio.\n",
    )
    _commit_all(root, "docs: seed multi-subsystem canonical design doc set")


class TestMultiDocOverlayLifecycle:
    """Sprint 025 ticket 003: full lifecycle over a MULTI-DOC overlay.

    Exercises tickets 001 (slug-based seeding, manifest keyed by slug)
    and 002 (validator resolves overlay targets via manifest) together,
    end to end: seed two co-located ``DESIGN.md`` fixtures from
    different subsystems in one call, edit both distinguishably,
    generate per-file diffs, validate, and apply -- asserting each
    canonical file receives only its own edit.

    Per the ticket's acceptance criteria, this test asserts (by
    behavior, not inspection) that ``generate_diffs`` and ``apply``
    (``clasi.design.overlay``) required no source changes to pass under
    the slug-keyed manifest -- this test file is the only diff for this
    ticket.
    """

    def test_seed_two_colocated_design_docs_in_one_call_yields_two_distinct_overlays(
        self, repo
    ):
        _configure_multi_root_sources_and_opt_in(repo)
        _seed_multi_doc_canonical_docs(repo)

        create_sprint("Multi Doc Overlay Sprint")
        detail_sprint("001")

        seed_result = json.loads(
            seed_sprint_design_overlay(
                "001",
                doc_names=["src/firm/app/DESIGN.md", "src/host/robot_radio/DESIGN.md"],
            )
        )
        assert seed_result["opted_in"] is True
        assert len(seed_result["seeded"]) == 2

        sprint_design_dir = (
            repo / "clasi" / "sprints" / "001-multi-doc-overlay-sprint" / "design"
        )
        # Slugs are derived relative to each doc's own declared source
        # root (src/firm, src/host) -- see _derive_overlay_slug.
        overlay_firm = sprint_design_dir / "app-DESIGN.md"
        overlay_host = sprint_design_dir / "robot_radio-DESIGN.md"

        # Two distinct overlay files exist -- neither overwrote the other.
        assert overlay_firm.exists()
        assert overlay_host.exists()
        assert overlay_firm.read_text(encoding="utf-8") == (
            "# firm/app subsystem\n\nOriginal firm/app.\n"
        )
        assert overlay_host.read_text(encoding="utf-8") == (
            "# host/robot_radio subsystem\n\nOriginal host/robot_radio.\n"
        )

        # Two distinct _sources.json manifest entries.
        manifest = json.loads(
            (sprint_design_dir / "_sources.json").read_text(encoding="utf-8")
        )
        assert manifest["app-DESIGN.md"] == str(
            (repo / "src" / "firm" / "app" / "DESIGN.md").resolve()
        )
        assert manifest["robot_radio-DESIGN.md"] == str(
            (repo / "src" / "host" / "robot_radio" / "DESIGN.md").resolve()
        )

    def test_full_lifecycle_edit_diff_validate_apply_keeps_each_doc_independent(
        self, repo
    ):
        _configure_multi_root_sources_and_opt_in(repo)
        _seed_multi_doc_canonical_docs(repo)

        create_sprint("Multi Doc Overlay Sprint")
        detail_sprint("001")
        seed_sprint_design_overlay(
            "001",
            doc_names=["src/firm/app/DESIGN.md", "src/host/robot_radio/DESIGN.md"],
        )

        sprint_design_dir = (
            repo / "clasi" / "sprints" / "001-multi-doc-overlay-sprint" / "design"
        )
        overlay_firm = sprint_design_dir / "app-DESIGN.md"
        overlay_host = sprint_design_dir / "robot_radio-DESIGN.md"

        # Edit both seeded copies with distinguishable, non-overlapping content.
        firm_edit = "# firm/app subsystem\n\nOriginal firm/app.\n\nFIRM APP EDIT ONLY.\n"
        host_edit = (
            "# host/robot_radio subsystem\n\nOriginal host/robot_radio.\n\n"
            "HOST ROBOT_RADIO EDIT ONLY.\n"
        )
        overlay_firm.write_text(firm_edit, encoding="utf-8")
        overlay_host.write_text(host_edit, encoding="utf-8")

        # generate_diffs: this is the CRITICAL acceptance point -- no
        # change to clasi.design.overlay's generate_diffs() body was made
        # for this ticket; it already resolves each overlay file
        # independently and writes a per-file .diff.md sibling.
        from clasi.design.overlay import generate_diffs

        written = generate_diffs(sprint_design_dir, repo_root=repo)
        assert len(written) == 2

        diff_firm = sprint_design_dir / "app-DESIGN.diff.md"
        diff_host = sprint_design_dir / "robot_radio-DESIGN.diff.md"
        assert set(written) == {diff_firm, diff_host}

        diff_firm_text = diff_firm.read_text(encoding="utf-8")
        diff_host_text = diff_host.read_text(encoding="utf-8")

        # Each .diff.md carries content specific to its own file's edit,
        # never the other file's edit.
        assert "FIRM APP EDIT ONLY." in diff_firm_text
        assert "HOST ROBOT_RADIO EDIT ONLY." not in diff_firm_text
        assert "HOST ROBOT_RADIO EDIT ONLY." in diff_host_text
        assert "FIRM APP EDIT ONLY." not in diff_host_text

        # commit_edits so the overlay dir is clean before validate/apply,
        # matching the real pre-execution lifecycle step.
        from clasi.design.overlay import commit_edits

        commit_edits(sprint_design_dir, repo_root=repo)

        # validate_design (clasi design validate --overlay equivalent)
        # passes: every overlay file resolves to its own distinct
        # canonical target via the manifest, and every diff is fresh.
        validation = json.loads(validate_design(overlay_dir=str(sprint_design_dir)))
        assert validation == {"ok": True, "messages": [], "info": []}, validation

        # apply: also CRITICAL -- clasi.design.overlay.apply() required
        # no code change either; it already resolves targets solely via
        # the _sources.json manifest, never by overlay filename.
        from clasi.design.overlay import apply

        canonical_firm = (repo / "src" / "firm" / "app" / "DESIGN.md").resolve()
        canonical_host = (repo / "src" / "host" / "robot_radio" / "DESIGN.md").resolve()

        applied = apply(sprint_design_dir)
        assert set(applied) == {canonical_firm, canonical_host}

        # Each canonical file received ITS OWN edit -- firm/app never
        # receives host/robot_radio's content, and vice versa.
        assert canonical_firm.read_text(encoding="utf-8") == firm_edit
        assert canonical_host.read_text(encoding="utf-8") == host_edit
        assert "HOST ROBOT_RADIO EDIT ONLY." not in canonical_firm.read_text(
            encoding="utf-8"
        )
        assert "FIRM APP EDIT ONLY." not in canonical_host.read_text(encoding="utf-8")
