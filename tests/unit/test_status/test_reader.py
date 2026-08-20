"""Unit tests for ClasiStateReader.

Each method is tested with:
- The positive case (feature/state is present).
- The negative case (feature/state is absent or returns safe default).

A minimal CLASI project fixture is created in tmp_path so tests do real
filesystem and git I/O without touching the live project on disk.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from clasi.project import Project
from clasi.state_machine.context import StateReader
from clasi.status.reader import ClasiStateReader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _git_init(root: Path) -> None:
    """Initialise a throwaway git repo in *root*."""
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=root, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=root, check=True, capture_output=True,
    )


def _git_commit(root: Path, message: str = "init") -> None:
    """Stage everything and create a commit (needed so branches can be checked)."""
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", message],
        cwd=root, check=True, capture_output=True,
    )


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    """A minimal CLASI project in a git repo inside tmp_path."""
    _git_init(tmp_path)
    (tmp_path / ".clasi").mkdir()
    _git_commit(tmp_path, "initial")
    return Project(tmp_path)


@pytest.fixture()
def reader(project: Project) -> ClasiStateReader:
    return ClasiStateReader(project)


def _make_sprint(project: Project, sprint_id: str = "001", branch: str = "sprint/001") -> Path:
    """Scaffold a minimal sprint directory structure and return the sprint dir."""
    sprint_dir = project.sprints_dir / f"{sprint_id}-test-sprint"
    sprint_dir.mkdir(parents=True)
    (sprint_dir / "tickets").mkdir()
    (sprint_dir / "tickets" / "done").mkdir()
    fm = f"---\nid: '{sprint_id}'\ntitle: Test Sprint\nbranch: {branch}\nstatus: planning-docs\n---\n"
    (sprint_dir / "sprint.md").write_text(fm, encoding="utf-8")
    return sprint_dir


def _make_ticket(
    sprint_dir: Path,
    ticket_id: str,
    status: str = "open",
    depends_on: list[str] | None = None,
    exception: dict | None = None,
    reopen_requested: bool = False,
    body: str = "",
    in_done: bool = False,
) -> Path:
    """Write a ticket file; return the path."""
    import yaml

    fm_data: dict = {
        "id": ticket_id,
        "title": f"Ticket {ticket_id}",
        "status": status,
        "depends-on": depends_on if depends_on is not None else [],
    }
    if exception is not None:
        fm_data["exception"] = exception
    if reopen_requested:
        fm_data["reopen_requested"] = reopen_requested

    yaml_str = yaml.dump(fm_data, default_flow_style=False, sort_keys=False).strip()
    fm = f"---\n{yaml_str}\n---\n{body}"

    dest_dir = sprint_dir / "tickets" / ("done" if in_done else "")
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{ticket_id}-test-ticket.md"
    path.write_text(fm, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_isinstance_state_reader(self, reader: ClasiStateReader) -> None:
        assert isinstance(reader, StateReader)


# ---------------------------------------------------------------------------
# file_exists
# ---------------------------------------------------------------------------


class TestFileExists:
    def test_existing_file_returns_true(self, project: Project, reader: ClasiStateReader) -> None:
        f = project.root / "hello.txt"
        f.write_text("hi")
        assert reader.file_exists("hello.txt") is True

    def test_missing_file_returns_false(self, reader: ClasiStateReader) -> None:
        assert reader.file_exists("no-such-file.md") is False

    def test_nested_path(self, project: Project, reader: ClasiStateReader) -> None:
        (project.root / "docs" / "design").mkdir(parents=True)
        (project.root / "docs" / "design" / "overview.md").write_text("x")
        assert reader.file_exists("docs/design/overview.md") is True


# ---------------------------------------------------------------------------
# git_branch
# ---------------------------------------------------------------------------


class TestGitBranch:
    def test_returns_current_branch(self, project: Project, reader: ClasiStateReader) -> None:
        branch = reader.git_branch()
        # Should be the current branch (master or main after git init + commit)
        assert isinstance(branch, str)
        assert branch != ""

    def test_returns_string_on_non_git_dir(self, tmp_path: Path) -> None:
        non_git = tmp_path / "not-a-repo"
        non_git.mkdir()
        proj = Project(non_git)
        r = ClasiStateReader(proj)
        assert r.git_branch() == ""


# ---------------------------------------------------------------------------
# default_branch
# ---------------------------------------------------------------------------


class TestDefaultBranch:
    def test_returns_string(self, reader: ClasiStateReader) -> None:
        branch = reader.default_branch()
        assert isinstance(branch, str)

    def test_falls_back_to_master_when_no_remote(self, reader: ClasiStateReader) -> None:
        # Our test repo has no remote → falls back to "master"
        assert reader.default_branch() == "master"


# ---------------------------------------------------------------------------
# execution_lock
# ---------------------------------------------------------------------------


class TestExecutionLock:
    def test_returns_none_when_no_lock(self, reader: ClasiStateReader) -> None:
        # DB not initialised → no lock
        assert reader.execution_lock() is None

    def test_returns_dict_when_lock_held(self, project: Project, reader: ClasiStateReader) -> None:
        project.db.register_sprint("001", "test-sprint")
        project.db.acquire_lock("001")
        lock = reader.execution_lock()
        assert lock is not None
        assert lock["sprint_id"] == "001"


# ---------------------------------------------------------------------------
# sprint_phase
# ---------------------------------------------------------------------------


class TestSprintPhase:
    def test_returns_phase_from_db(self, project: Project, reader: ClasiStateReader) -> None:
        project.db.register_sprint("042", "test-sprint")
        assert reader.sprint_phase("042") == "roadmap"

    def test_returns_empty_for_unregistered(self, reader: ClasiStateReader) -> None:
        assert reader.sprint_phase("999") == ""


# ---------------------------------------------------------------------------
# sprint_gate
# ---------------------------------------------------------------------------


class TestSprintGate:
    def test_returns_gate_dict_when_recorded(self, project: Project, reader: ClasiStateReader) -> None:
        project.db.register_sprint("010", "s")
        # Advance to architecture-review phase (roadmap → planning-docs → architecture-review)
        project.db.advance_phase("010")  # → planning-docs
        project.db.advance_phase("010")  # → architecture-review
        project.db.record_gate("010", "architecture_review", "passed")
        gate = reader.sprint_gate("010", "architecture_review")
        assert gate is not None
        assert gate["result"] == "passed"

    def test_returns_none_when_not_recorded(self, project: Project, reader: ClasiStateReader) -> None:
        project.db.register_sprint("011", "s")
        assert reader.sprint_gate("011", "architecture_review") is None

    def test_returns_none_for_unregistered_sprint(self, reader: ClasiStateReader) -> None:
        assert reader.sprint_gate("999", "architecture_review") is None


# ---------------------------------------------------------------------------
# sprint_branch
# ---------------------------------------------------------------------------


class TestSprintBranch:
    def test_returns_branch_from_frontmatter(self, project: Project, reader: ClasiStateReader) -> None:
        _make_sprint(project, "003", branch="sprint/003-my-feature")
        assert reader.sprint_branch("003") == "sprint/003-my-feature"

    def test_returns_empty_for_unknown_sprint(self, reader: ClasiStateReader) -> None:
        assert reader.sprint_branch("999") == ""


# ---------------------------------------------------------------------------
# ticket_status
# ---------------------------------------------------------------------------


class TestTicketStatus:
    def test_returns_status(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", status="in-progress")
        assert reader.ticket_status("001", "001") == "in-progress"

    def test_returns_empty_for_missing_ticket(self, project: Project, reader: ClasiStateReader) -> None:
        _make_sprint(project)
        assert reader.ticket_status("001", "999") == ""

    def test_finds_ticket_in_done_dir(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "002", status="done", in_done=True)
        assert reader.ticket_status("001", "002") == "done"


# ---------------------------------------------------------------------------
# all_tickets_done
# ---------------------------------------------------------------------------


class TestAllTicketsDone:
    def test_true_when_all_done(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", status="done")
        _make_ticket(sprint_dir, "002", status="done")
        assert reader.all_tickets_done("001") is True

    def test_false_when_one_open(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", status="done")
        _make_ticket(sprint_dir, "002", status="open")
        assert reader.all_tickets_done("001") is False

    def test_true_when_no_tickets_dir(self, project: Project, reader: ClasiStateReader) -> None:
        # A sprint with no tickets/ directory
        sprint_dir = project.sprints_dir / "001-empty"
        sprint_dir.mkdir(parents=True)
        (sprint_dir / "sprint.md").write_text("---\nid: '001'\ntitle: t\nbranch: b\nstatus: planning-docs\n---\n")
        assert reader.all_tickets_done("001") is True

    def test_false_for_unknown_sprint(self, reader: ClasiStateReader) -> None:
        assert reader.all_tickets_done("999") is False


# ---------------------------------------------------------------------------
# ticket_in_done_dir
# ---------------------------------------------------------------------------


class TestTicketInDoneDir:
    def test_true_when_in_done(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", in_done=True)
        assert reader.ticket_in_done_dir("001", "001") is True

    def test_false_when_in_active_dir(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", in_done=False)
        assert reader.ticket_in_done_dir("001", "001") is False

    def test_false_for_missing_ticket(self, project: Project, reader: ClasiStateReader) -> None:
        _make_sprint(project)
        assert reader.ticket_in_done_dir("001", "999") is False


# ---------------------------------------------------------------------------
# exception_block
# ---------------------------------------------------------------------------


class TestExceptionBlock:
    def test_returns_block_when_present(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", exception={"thrown_by": "programmer", "surface": "internal"})
        block = reader.exception_block("001", "001")
        assert block is not None
        assert block["thrown_by"] == "programmer"

    def test_returns_none_when_absent(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001")
        assert reader.exception_block("001", "001") is None

    def test_returns_none_for_missing_ticket(self, project: Project, reader: ClasiStateReader) -> None:
        _make_sprint(project)
        assert reader.exception_block("001", "999") is None


# ---------------------------------------------------------------------------
# programmer_dispatched
# ---------------------------------------------------------------------------


class TestProgrammerDispatched:
    def test_true_when_in_progress(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", status="in-progress")
        assert reader.programmer_dispatched("001", "001") is True

    def test_false_when_open(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", status="open")
        assert reader.programmer_dispatched("001", "001") is False

    def test_false_when_done(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", status="done")
        assert reader.programmer_dispatched("001", "001") is False


# ---------------------------------------------------------------------------
# sprint_flag
# ---------------------------------------------------------------------------


class TestSprintFlag:
    def test_returns_flag_value(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = project.sprints_dir / "005-test"
        sprint_dir.mkdir(parents=True)
        fm = "---\nid: '005'\ntitle: t\nbranch: b\nstatus: planning-docs\npre_flight_review: passed\n---\n"
        (sprint_dir / "sprint.md").write_text(fm)
        assert reader.sprint_flag("005", "pre_flight_review") == "passed"

    def test_returns_empty_for_absent_flag(self, project: Project, reader: ClasiStateReader) -> None:
        _make_sprint(project)
        assert reader.sprint_flag("001", "nonexistent_flag") == ""

    def test_returns_empty_for_unknown_sprint(self, reader: ClasiStateReader) -> None:
        assert reader.sprint_flag("999", "anything") == ""


# ---------------------------------------------------------------------------
# branch_merged
# ---------------------------------------------------------------------------


class TestBranchMerged:
    def test_false_when_branch_not_merged(self, project: Project, reader: ClasiStateReader) -> None:
        _make_sprint(project, "001", branch="sprint/001-feature")
        # Create the branch but don't merge it
        subprocess.run(
            ["git", "checkout", "-b", "sprint/001-feature"],
            cwd=project.root, capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "-"],
            cwd=project.root, capture_output=True,
        )
        assert reader.branch_merged("001") is False

    def test_false_for_empty_branch(self, project: Project, reader: ClasiStateReader) -> None:
        # sprint with no branch field
        sprint_dir = project.sprints_dir / "002-nobranch"
        sprint_dir.mkdir(parents=True)
        (sprint_dir / "sprint.md").write_text("---\nid: '002'\ntitle: t\nbranch: ''\nstatus: planning-docs\n---\n")
        assert reader.branch_merged("002") is False

    def test_false_for_unknown_sprint(self, reader: ClasiStateReader) -> None:
        assert reader.branch_merged("999") is False


# ---------------------------------------------------------------------------
# Git-subprocess memoization (sprint 026 / ticket 003)
# ---------------------------------------------------------------------------


def _count_real_git_calls(monkeypatch):
    """Patch subprocess.run to count invocations while still running the
    real command (so callers observe real output), and return the list
    it appends argv tuples to."""
    real_run = subprocess.run
    calls: list[tuple[str, ...]] = []

    def counting_run(cmd, **kwargs):
        calls.append(tuple(cmd))
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", counting_run)
    return calls


class TestGitCallMemoization:
    """``ClasiStateReader``'s git-subprocess-backed methods memoize their
    result per instance — repeated calls to the same git query within one
    reader's lifetime shell out once, not once per call (sprint 026 /
    ticket 003)."""

    def test_repeated_git_branch_calls_shell_out_once(
        self, project: Project, reader: ClasiStateReader, monkeypatch
    ) -> None:
        calls = _count_real_git_calls(monkeypatch)
        for _ in range(5):
            reader.git_branch()
        assert len(calls) == 1

    def test_repeated_default_branch_calls_shell_out_once(
        self, project: Project, reader: ClasiStateReader, monkeypatch
    ) -> None:
        calls = _count_real_git_calls(monkeypatch)
        for _ in range(5):
            reader.default_branch()
        assert len(calls) == 1

    def test_git_branch_and_default_branch_cache_independently(
        self, project: Project, reader: ClasiStateReader, monkeypatch
    ) -> None:
        calls = _count_real_git_calls(monkeypatch)
        for _ in range(3):
            reader.git_branch()
        for _ in range(3):
            reader.default_branch()
        # Two distinct git queries -> two real subprocess calls total,
        # regardless of how many times each was individually requested.
        assert len(calls) == 2

    def test_branch_merged_across_multiple_sprints_shares_one_merged_list(
        self, project: Project, reader: ClasiStateReader, monkeypatch
    ) -> None:
        _make_sprint(project, "001", branch="sprint/001-a")
        _make_sprint(project, "002", branch="sprint/002-b")
        _make_sprint(project, "003", branch="sprint/003-c")

        calls = _count_real_git_calls(monkeypatch)
        reader.branch_merged("001")
        reader.branch_merged("002")
        reader.branch_merged("003")

        # `git branch --merged <default>` does not depend on sprint_id —
        # it's the SAME command for every sprint in this reader instance,
        # so it (plus the one `default_branch` resolution it depends on)
        # must shell out exactly twice total, not twice per sprint.
        assert len(calls) == 2

    def test_new_instance_starts_with_an_empty_cache(
        self, project: Project, monkeypatch
    ) -> None:
        """The cache is per-instance, not process-global — a fresh reader
        must not inherit another reader's cached git results."""
        reader_a = ClasiStateReader(project)
        reader_a.git_branch()

        calls = _count_real_git_calls(monkeypatch)
        reader_b = ClasiStateReader(project)
        reader_b.git_branch()

        assert len(calls) == 1

    def test_git_branch_result_unaffected_by_memoization(
        self, project: Project, reader: ClasiStateReader
    ) -> None:
        """Caching must not change the returned value — only how many
        times it shells out to compute it."""
        first = reader.git_branch()
        second = reader.git_branch()
        assert first == second != ""


# ---------------------------------------------------------------------------
# dependencies_done
# ---------------------------------------------------------------------------


class TestDependenciesDone:
    def test_true_when_no_dependencies(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", depends_on=[])
        assert reader.dependencies_done("001", "001") is True

    def test_true_when_all_deps_done(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", status="done")
        _make_ticket(sprint_dir, "002", depends_on=["001"])
        assert reader.dependencies_done("001", "002") is True

    def test_false_when_dep_not_done(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", status="open")
        _make_ticket(sprint_dir, "002", depends_on=["001"])
        assert reader.dependencies_done("001", "002") is False

    def test_false_for_missing_ticket(self, project: Project, reader: ClasiStateReader) -> None:
        _make_sprint(project)
        assert reader.dependencies_done("001", "999") is True  # no deps → True


# ---------------------------------------------------------------------------
# acceptance_criteria_met
# ---------------------------------------------------------------------------


class TestAcceptanceCriteriaMet:
    def test_true_when_all_checked(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        body = "## Criteria\n\n- [x] First thing done\n- [x] Second thing done\n"
        _make_ticket(sprint_dir, "001", body=body)
        assert reader.acceptance_criteria_met("001", "001") is True

    def test_false_when_unchecked_box(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        body = "## Criteria\n\n- [x] Done\n- [ ] Not done\n"
        _make_ticket(sprint_dir, "001", body=body)
        assert reader.acceptance_criteria_met("001", "001") is False

    def test_false_when_no_checkboxes(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        body = "## Description\n\nNo checkboxes here.\n"
        _make_ticket(sprint_dir, "001", body=body)
        assert reader.acceptance_criteria_met("001", "001") is False

    def test_false_for_missing_ticket(self, project: Project, reader: ClasiStateReader) -> None:
        _make_sprint(project)
        assert reader.acceptance_criteria_met("001", "999") is False


# ---------------------------------------------------------------------------
# tests_passing
# ---------------------------------------------------------------------------


class TestTestsPassing:
    def test_false_when_no_cache_file(self, reader: ClasiStateReader) -> None:
        # Default project fixture has no test-cache file
        assert reader.tests_passing() is False

    def test_true_when_cache_file_exists(self, project: Project, reader: ClasiStateReader) -> None:
        (project.clasi_dir / "test-cache").write_text("ok")
        assert reader.tests_passing() is True

    def test_false_after_cache_file_removed(self, project: Project, reader: ClasiStateReader) -> None:
        cache = project.clasi_dir / "test-cache"
        cache.write_text("ok")
        assert reader.tests_passing() is True
        cache.unlink()
        assert reader.tests_passing() is False


# ---------------------------------------------------------------------------
# blocker_identified
# ---------------------------------------------------------------------------


class TestBlockerIdentified:
    def test_true_when_exception_block_present(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", exception={"thrown_by": "programmer"})
        assert reader.blocker_identified("001", "001") is True

    def test_false_when_no_exception_block(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001")
        assert reader.blocker_identified("001", "001") is False


# ---------------------------------------------------------------------------
# blocker_resolved
# ---------------------------------------------------------------------------


class TestBlockerResolved:
    def test_true_when_resolved_true(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", exception={"thrown_by": "programmer", "resolved": True})
        assert reader.blocker_resolved("001", "001") is True

    def test_false_when_not_resolved(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", exception={"thrown_by": "programmer"})
        assert reader.blocker_resolved("001", "001") is False

    def test_false_when_no_exception_block(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001")
        assert reader.blocker_resolved("001", "001") is False


# ---------------------------------------------------------------------------
# reopen_requested
# ---------------------------------------------------------------------------


class TestReopenRequested:
    def test_true_when_flag_set(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", reopen_requested=True)
        assert reader.reopen_requested("001", "001") is True

    def test_false_when_not_set(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001", reopen_requested=False)
        assert reader.reopen_requested("001", "001") is False


# ---------------------------------------------------------------------------
# any_sprint_in_phase
# ---------------------------------------------------------------------------


class TestAnySprintInPhase:
    def test_true_when_sprint_in_phase(self, project: Project, reader: ClasiStateReader) -> None:
        _make_sprint(project, "001")
        project.db.register_sprint("001", "test-sprint")
        assert reader.any_sprint_in_phase("roadmap") is True

    def test_false_when_no_sprint_in_phase(self, project: Project, reader: ClasiStateReader) -> None:
        _make_sprint(project, "001")
        project.db.register_sprint("001", "test-sprint")
        assert reader.any_sprint_in_phase("executing") is False

    def test_false_when_no_sprints(self, reader: ClasiStateReader) -> None:
        assert reader.any_sprint_in_phase("roadmap") is False


# ---------------------------------------------------------------------------
# overview_exists
# ---------------------------------------------------------------------------


class TestOverviewExists:
    def test_true_when_overview_present(self, project: Project, reader: ClasiStateReader) -> None:
        design_dir = project.design_dir
        design_dir.mkdir(parents=True, exist_ok=True)
        (design_dir / "overview.md").write_text("# Overview\n")
        assert reader.overview_exists() is True

    def test_false_when_overview_absent(self, reader: ClasiStateReader) -> None:
        # design dir doesn't exist by default in fixture
        assert reader.overview_exists() is False

    def test_false_when_design_dir_missing(self, project: Project, reader: ClasiStateReader) -> None:
        # Ensure no design dir at all
        assert not project.design_dir.exists()
        assert reader.overview_exists() is False

    def test_true_with_custom_configured_design_dir(self, tmp_path: Path) -> None:
        """Ticket 026-005: overview_exists() must follow a NON-default
        paths.design config value, not just the docs/design/ default
        exercised above. This is the reader-side half of the
        "configured-path agreement" the ticket closes — a write into
        whatever design_dir a project actually configures must be seen
        by the SAME predicate that gates the `initialize` transition.
        """
        _git_init(tmp_path)
        (tmp_path / ".clasi").mkdir()
        (tmp_path / ".clasi" / "config.yaml").write_text(
            "process: se\npaths:\n  design: documentation/design-docs\n",
            encoding="utf-8",
        )
        _git_commit(tmp_path, "initial")

        project = Project(tmp_path)
        assert project.design_dir == tmp_path / "documentation" / "design-docs"

        project.design_dir.mkdir(parents=True, exist_ok=True)
        (project.design_dir / "overview.md").write_text("# Overview\n")

        reader = ClasiStateReader(project)
        assert reader.overview_exists() is True


# ---------------------------------------------------------------------------
# sprint_artifact_exists
# ---------------------------------------------------------------------------


class TestSprintArtifactExists:
    def test_true_when_artifact_present(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = project.sprints_dir / "001-my-sprint"
        sprint_dir.mkdir(parents=True)
        fm = "---\nid: '001'\ntitle: My Sprint\nstatus: open\nbranch: sprint/001-my-sprint\n---\n"
        (sprint_dir / "sprint.md").write_text(fm)
        assert reader.sprint_artifact_exists("001", "sprint.md") is True

    def test_false_when_artifact_missing(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = project.sprints_dir / "001-my-sprint"
        sprint_dir.mkdir(parents=True)
        fm = "---\nid: '001'\ntitle: My Sprint\nstatus: open\nbranch: sprint/001-my-sprint\n---\n"
        (sprint_dir / "sprint.md").write_text(fm)
        assert reader.sprint_artifact_exists("001", "architecture-update.md") is False

    def test_false_when_sprint_not_found(self, reader: ClasiStateReader) -> None:
        assert reader.sprint_artifact_exists("999", "sprint.md") is False


# ---------------------------------------------------------------------------
# ticket_file_present
# ---------------------------------------------------------------------------


class TestTicketFilePresent:
    def test_true_when_ticket_in_active_dir(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = project.sprints_dir / "001-my-sprint"
        tickets_dir = sprint_dir / "tickets"
        tickets_dir.mkdir(parents=True)
        fm_sprint = "---\nid: '001'\ntitle: My Sprint\nstatus: open\nbranch: sprint/001-my-sprint\n---\n"
        (sprint_dir / "sprint.md").write_text(fm_sprint)
        fm_ticket = "---\nid: '001-001'\ntitle: My Ticket\nstatus: open\n---\n"
        (tickets_dir / "001-001-my-ticket.md").write_text(fm_ticket)
        assert reader.ticket_file_present("001", "001-001") is True

    def test_false_when_ticket_missing(self, reader: ClasiStateReader) -> None:
        assert reader.ticket_file_present("001", "001-001") is False


# ---------------------------------------------------------------------------
# ticket_count
# ---------------------------------------------------------------------------


class TestTicketCount:
    def test_counts_active_tickets(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001")
        _make_ticket(sprint_dir, "002")
        assert reader.ticket_count("001") == 2

    def test_excludes_done_dir(self, project: Project, reader: ClasiStateReader) -> None:
        sprint_dir = _make_sprint(project)
        _make_ticket(sprint_dir, "001")
        _make_ticket(sprint_dir, "002", in_done=True)
        # tickets/done/ is a subdirectory; glob("*.md") on tickets/ won't descend
        assert reader.ticket_count("001") == 1

    def test_zero_when_no_tickets(self, project: Project, reader: ClasiStateReader) -> None:
        _make_sprint(project)
        assert reader.ticket_count("001") == 0

    def test_zero_for_unknown_sprint(self, reader: ClasiStateReader) -> None:
        assert reader.ticket_count("999") == 0
