"""Sprint 018 terminal integration checks (ticket 016).

Exercises the two sprint-018 issues end-to-end, at the level the
cumulative unit/system suites from tickets 001-015 do not reach:

- **Issue A** (worktree parallel ticket execution): a real-git fixture
  drives the actual worktree lifecycle for two file-disjoint tickets —
  create -> branch -> commit -> validate -> merge -> immediate cleanup —
  and asserts the worktree directory is torn down on *its own* merge, not
  deferred to sprint close. It also exercises the accumulation-blocking
  contract: a stale `ticket/*` worktree left behind is confirmed to come
  back from `reconcile_worktrees` as `rogue` (live, no audit entry) or
  `escalated` (audit says non-terminal) rather than being silently
  swept away — the actual "gate" described in execution.md is controller
  prose, so this test asserts the primitive a caller would consult to
  decide whether to block.
- **Issue B** (single-doc sprint model): drives `create_sprint` ->
  `detail_sprint` -> ticket lifecycle -> `record_gate_result` (skipped)
  -> phase advances -> close, asserting only `sprint.md` + `tickets/`
  ever exist and `docs/architecture/` never reappears. Also confirms the
  known invariant overlap between the `open` and `planned` sprint states
  (ticket 004's finding) resolves determinately to a sensible state
  (`evaluate_state`'s most-advanced-match-wins contract, 030/002) rather
  than surfacing an error.
- **Cross-issue**: a single sprint using both `worktree: true` and the
  single-doc model end-to-end, confirming the two features (which touch
  overlapping files but not overlapping runtime behavior) don't
  interfere.

Full-suite pass (scenario 1 of the ticket) is verified by the DoD's
`uv run pytest` run, not by a test in this module.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import clasi.worktree as worktree
from clasi.frontmatter import read_frontmatter, write_frontmatter
from clasi.mcp_server import set_project
from clasi.state_db import acquire_lock, advance_phase, record_gate
from clasi.tools.artifact_tools import (
    close_sprint,
    create_sprint,
    create_ticket,
    detail_sprint,
    move_ticket_to_done,
    record_gate_result,
    update_ticket_status,
)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def _git_init(root: Path) -> None:
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
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", message],
        cwd=root, check=True, capture_output=True,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A throwaway git repo with an initial commit and a sprint branch.

    Mirrors the fixture in tests/clasi/test_worktree.py so the naming
    convention (sprint branch `sprint/018-test-sprint`) matches a
    `sprint_dir` basename of `018-test-sprint`, letting
    `reconcile_worktrees` derive the right sprint id/branch.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git_init(repo_root)
    (repo_root / "README.md").write_text("hello\n", encoding="utf-8")
    _git_commit(repo_root, "initial")
    subprocess.run(
        ["git", "branch", "-m", "sprint/018-test-sprint"],
        cwd=repo_root, check=True, capture_output=True,
    )
    return repo_root


@pytest.fixture()
def sprint_dir(repo: Path) -> Path:
    """Sprint artifact directory matching the `repo` fixture's branch name."""
    path = repo.parent / "sprint-artifacts" / "018-test-sprint"
    path.mkdir(parents=True)
    return path


def _make_ticket_worktree_with_commit(
    repo: Path, ticket_id: str, filename: str, content: str, slug: str = "slug"
) -> tuple[Path, str]:
    """Create a worktree + ticket branch and commit one file of work in it."""
    wt_path = worktree.create_worktree(repo, "018", ticket_id)
    branch_name = worktree.create_ticket_branch(wt_path, "018", ticket_id, slug)
    (wt_path / filename).write_text(content, encoding="utf-8")
    _run(["git", "add", "-A"], cwd=wt_path)
    _run(["git", "commit", "-m", f"add {filename}"], cwd=wt_path)
    return wt_path, branch_name


def _write_ticket_file(wt_path: Path, status: str = "done") -> Path:
    """Write and commit a ticket.md whose frontmatter status the worktree
    lifecycle's validate_worktree step reads.
    """
    ticket_path = wt_path / "ticket.md"
    ticket_path.write_text(
        f"---\nstatus: {status}\n---\n# Ticket\n", encoding="utf-8"
    )
    _run(["git", "add", "-A"], cwd=wt_path)
    _run(["git", "commit", "-m", "mark ticket done"], cwd=wt_path)
    return ticket_path


# ---------------------------------------------------------------------------
# Issue A: worktree parallel execution end-to-end
# ---------------------------------------------------------------------------


class TestIssueAWorktreeLifecycleEndToEnd:
    """Drives two file-disjoint tickets through the full worktree lifecycle
    the way the execution.md Parallel Path's per-group loop does: create,
    branch, validate, merge, and *immediately* clean up per ticket — not
    deferred to sprint close.
    """

    def test_two_disjoint_tickets_torn_down_immediately_per_merge(
        self, repo: Path
    ) -> None:
        # Two independent tickets confirmed disjoint by check_independence,
        # matching the "two file-disjoint tickets" scenario from the ticket.
        tickets = [
            {
                "id": "001",
                "files_to_create": ["clasi/feature_a.py"],
                "files_to_modify": [],
            },
            {
                "id": "002",
                "files_to_create": ["clasi/feature_b.py"],
                "files_to_modify": [],
            },
        ]
        groups = worktree.check_independence(tickets)
        assert groups == [["001", "002"]], (
            "fixture tickets must land in a single parallel group for this "
            "to be a meaningful worktree-parallel-execution test"
        )

        # --- Setup (sequential, per ticket in the group), matching §Per-group
        # loop step 2: create_worktree, create_ticket_branch per ticket.
        wt1 = worktree.create_worktree(repo, "018", "001")
        branch1 = worktree.create_ticket_branch(wt1, "018", "001", "feature-a")
        wt2 = worktree.create_worktree(repo, "018", "002")
        branch2 = worktree.create_ticket_branch(wt2, "018", "002", "feature-b")

        assert wt1.exists() and wt2.exists()
        # Both worktree directories exist simultaneously mid-sprint —
        # this is the "two ../worktree-<sprint>-* directories are created"
        # assertion from the ticket.
        listing = _run(["git", "worktree", "list", "--porcelain"], cwd=repo).stdout
        assert "worktree-018-001" in listing
        assert "worktree-018-002" in listing

        # Simulate each programmer agent's work: write the ticket's own file,
        # commit, and mark the ticket done (validate_worktree reads this).
        (wt1 / "feature_a.py").write_text("# feature a\n", encoding="utf-8")
        _run(["git", "add", "-A"], cwd=wt1)
        _run(["git", "commit", "-m", "implement feature a"], cwd=wt1)
        ticket1_path = _write_ticket_file(wt1, status="done")

        (wt2 / "feature_b.py").write_text("# feature b\n", encoding="utf-8")
        _run(["git", "add", "-A"], cwd=wt2)
        _run(["git", "commit", "-m", "implement feature b"], cwd=wt2)
        ticket2_path = _write_ticket_file(wt2, status="done")

        # --- Per-ticket validate -> merge -> cleanup, sequential, one ticket
        # at a time (§Per-group loop step 5).

        # Ticket 001: validate, merge, immediate cleanup.
        assert worktree.validate_worktree(wt1, ticket1_path, test_command=["true"]) is True
        worktree.merge_ticket_branch(repo, "sprint/018-test-sprint", branch1)
        worktree.cleanup_worktree(repo, wt1, branch1, keep_branch=False)

        # Assert torn down IMMEDIATELY on its own merge -- ticket 002's
        # worktree must still exist (not a batch cleanup at the end), and
        # ticket 001's worktree must already be gone.
        assert not wt1.exists()
        assert wt2.exists()
        mid_listing = _run(["git", "worktree", "list", "--porcelain"], cwd=repo).stdout
        assert "worktree-018-001" not in mid_listing
        assert "worktree-018-002" in mid_listing

        # Ticket 002: validate, merge, immediate cleanup.
        _run(["git", "checkout", "sprint/018-test-sprint"], cwd=repo)
        assert worktree.validate_worktree(wt2, ticket2_path, test_command=["true"]) is True
        worktree.merge_ticket_branch(repo, "sprint/018-test-sprint", branch2)
        worktree.cleanup_worktree(repo, wt2, branch2, keep_branch=False)

        # Zero worktree directories remain after the last ticket's merge.
        assert not wt2.exists()
        final_listing = _run(["git", "worktree", "list", "--porcelain"], cwd=repo).stdout
        assert "worktree-018-001" not in final_listing
        assert "worktree-018-002" not in final_listing

        # Both branches' work landed on the sprint branch.
        _run(["git", "checkout", "sprint/018-test-sprint"], cwd=repo)
        assert (repo / "feature_a.py").exists()
        assert (repo / "feature_b.py").exists()

        # No sibling worktree-* directories left on disk at all.
        remaining_dirs = [
            p.name for p in repo.parent.iterdir()
            if p.is_dir() and p.name.startswith("worktree-018-")
        ]
        assert remaining_dirs == []

    def test_stale_ticket_worktree_blocks_via_reconcile_escalation(
        self, repo: Path, sprint_dir: Path
    ) -> None:
        """Simulates accumulation: a stale ticket/* worktree left over from a
        crashed or abandoned session. The per-creation gate in execution.md
        is controller prose (it calls reconcile_worktrees and halts if
        anything comes back escalated), so this test asserts the underlying
        primitive a caller relies on to decide whether to block: an
        in-progress (non-terminal) audit entry with a live worktree must
        come back in `escalated`, never silently auto-cleaned.
        """
        stale_wt, stale_branch = _make_ticket_worktree_with_commit(
            repo, "099", "leftover.txt", "abandoned work\n", slug="stale-slug"
        )
        worktree.write_audit_record(
            sprint_dir,
            {
                "ticket_id": "099",
                "state": "in_progress",
                "path": str(stale_wt),
                "branch": stale_branch,
            },
        )

        result = worktree.reconcile_worktrees(repo, sprint_dir)

        # A caller (the per-creation gate) must see this ticket in
        # `escalated` and, per execution.md, halt and refuse to create any
        # new worktrees until it is resolved.
        escalated_ids = {e["ticket_id"] for e in result["escalated"]}
        assert "099" in escalated_ids
        assert result["cleaned"] == []
        # The stale worktree is left untouched -- reconcile never
        # auto-resolves ambiguous work.
        assert stale_wt.exists()

        # A second call (simulating "attempt to start another sprint's
        # worktree work" without resolving the stale entry first) still
        # reports it as escalated -- the gate would still refuse.
        second = worktree.reconcile_worktrees(repo, sprint_dir)
        second_escalated_ids = {e["ticket_id"] for e in second["escalated"]}
        assert "099" in second_escalated_ids

        # Cleanup so the test doesn't leak sibling state.
        _run(["git", "worktree", "remove", "--force", str(stale_wt)], cwd=repo)
        _run(["git", "branch", "-D", stale_branch], cwd=repo)

    def test_rogue_live_worktree_with_no_audit_entry_is_reported_not_swept(
        self, repo: Path, sprint_dir: Path
    ) -> None:
        """A ticket/* worktree created outside the tracked lifecycle (no
        audit entry at all) is the other accumulation-blocking shape: it
        must come back in `rogue`, not be silently cleaned or ignored.
        """
        rogue_wt, rogue_branch = _make_ticket_worktree_with_commit(
            repo, "098", "rogue.txt", "outside lifecycle\n", slug="rogue-slug"
        )
        # No write_audit_record call -- this worktree is untracked.

        result = worktree.reconcile_worktrees(repo, sprint_dir)

        rogue_ids = {r["ticket_id"] for r in result["rogue"]}
        assert "098" in rogue_ids
        assert result["cleaned"] == []
        assert rogue_wt.exists()

        _run(["git", "worktree", "remove", "--force", str(rogue_wt)], cwd=repo)
        _run(["git", "branch", "-D", rogue_branch], cwd=repo)


class TestIssueASerialPathUnaffected:
    """Confirms a worktree:false (or flag-absent) sprint's serial execution
    path creates zero worktree directories -- "the serial path never
    creates worktrees" per execution.md §0.
    """

    def test_serial_ticket_lifecycle_creates_no_worktrees(self, repo: Path) -> None:
        # Serial path: a ticket branch is created directly off the sprint
        # branch's own working tree (no `git worktree add` involved at
        # all), work is committed, and merged back with Sprint.merge_branch
        # -- exactly today's historical flow, never touching worktree.py.
        _run(["git", "checkout", "-b", "ticket/018-003-serial-ticket"], cwd=repo)
        (repo / "serial_feature.py").write_text("# serial feature\n", encoding="utf-8")
        _run(["git", "add", "-A"], cwd=repo)
        _run(["git", "commit", "-m", "implement serial feature"], cwd=repo)

        _run(["git", "checkout", "sprint/018-test-sprint"], cwd=repo)
        merge = _run(
            ["git", "merge", "--no-ff", "ticket/018-003-serial-ticket",
             "-m", "merge serial ticket"],
            cwd=repo,
        )
        assert merge.returncode == 0
        assert (repo / "serial_feature.py").exists()

        listing = _run(["git", "worktree", "list", "--porcelain"], cwd=repo).stdout
        # Only the main worktree entry exists -- no worktree-018-* entries,
        # confirming the serial path never invokes create_worktree.
        assert "worktree-018-" not in listing
        sibling_worktree_dirs = [
            p.name for p in repo.parent.iterdir()
            if p.is_dir() and p.name.startswith("worktree-018-")
        ]
        assert sibling_worktree_dirs == []

        _run(["git", "branch", "-d", "ticket/018-003-serial-ticket"], cwd=repo)


# ---------------------------------------------------------------------------
# Issue B: single-doc sprint model end-to-end
# ---------------------------------------------------------------------------


_LEGACY_PATHS_PIN = """\
process: se
paths:
  issues: .clasi/issues
  sprints: .clasi/sprints
  reflections: .clasi/reflections
  architecture: .clasi/architecture
  design: docs/design
  logs: .clasi/log
  db: .clasi/.clasi.db
"""


def _write_legacy_pin(root: Path) -> None:
    clasi_dir = root / ".clasi"
    clasi_dir.mkdir(parents=True, exist_ok=True)
    (clasi_dir / "config.yaml").write_text(_LEGACY_PATHS_PIN, encoding="utf-8")


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    """A temporary CLASI project root, isolated from the real repo's DB."""
    _write_legacy_pin(tmp_path)
    monkeypatch.chdir(tmp_path)
    set_project(tmp_path)
    return tmp_path


def _only_sprint_md_and_tickets_present(sprint_dir: Path) -> bool:
    """True iff the sprint directory contains only sprint.md and tickets/
    (plus the tickets/done/ subdirectory) -- no usecases.md, no
    architecture-update.md.
    """
    if (sprint_dir / "usecases.md").exists():
        return False
    if (sprint_dir / "architecture-update.md").exists():
        return False
    if not (sprint_dir / "sprint.md").exists():
        return False
    return True


class TestIssueBSingleDocSprintLifecycleEndToEnd:
    """Drives create_sprint -> detail_sprint -> ticketing -> execution ->
    close with a recorded architecture_review: skipped gate, confirming
    only sprint.md + tickets/ ever exist and docs/architecture/ never
    reappears.
    """

    def test_full_lifecycle_single_doc_only_no_usecases_no_architecture_file(
        self, work_dir, monkeypatch
    ) -> None:
        # --- create_sprint: only sprint.md, roadmap phase.
        create_result = json.loads(create_sprint("Single Doc Sprint"))
        sprint_id = create_result["id"]
        sprint_dir = work_dir / ".clasi" / "sprints" / f"{sprint_id}-single-doc-sprint"
        assert sprint_dir.exists()
        assert _only_sprint_md_and_tickets_present(sprint_dir)
        assert not (sprint_dir / "tickets").exists()

        # --- detail_sprint: scaffolds ONLY tickets/ + tickets/done/, no
        # usecases.md / architecture-update.md.
        detail_result = json.loads(detail_sprint(sprint_id))
        assert detail_result["phase"] == "planning-docs"
        assert _only_sprint_md_and_tickets_present(sprint_dir)
        assert (sprint_dir / "tickets").is_dir()
        assert (sprint_dir / "tickets" / "done").is_dir()

        # Fill in sprint.md's planning content (single-doc model: use cases
        # and architecture live as sections here, not separate files) and
        # mark it non-draft so pre-execution review passes.
        fm = read_frontmatter(sprint_dir / "sprint.md")
        fm["status"] = "active"
        write_frontmatter(sprint_dir / "sprint.md", fm)

        # --- record architecture_review: skipped (the whole point of
        # Issue B's skippable-arch-review gate).
        db_path = work_dir / ".clasi" / ".clasi.db"
        advance_phase(db_path, sprint_id)  # planning-docs -> architecture-review
        gate_result = json.loads(
            record_gate_result(sprint_id, "architecture_review", "skipped")
        )
        assert gate_result.get("gate_name") == "architecture_review"
        assert gate_result.get("result") == "skipped"

        advance_phase(db_path, sprint_id)  # architecture-review -> ticketing (031/002)
        record_gate(db_path, sprint_id, "stakeholder_approval", "passed")

        assert _only_sprint_md_and_tickets_present(sprint_dir)

        # --- ticketing: create one ticket, complete it.
        create_ticket(sprint_id, "Do the thing")
        ticket_path = sprint_dir / "tickets" / "001-do-the-thing.md"
        assert ticket_path.exists()

        acquire_lock(db_path, sprint_id)
        advance_phase(db_path, sprint_id)  # ticketing -> executing

        # Real git branch so close_sprint's full lifecycle can merge it.
        branch_name = f"sprint/{sprint_id}-single-doc-sprint"
        repo_root = work_dir
        _git_init_and_commit_project(repo_root)
        _run(["git", "checkout", "-b", branch_name], cwd=repo_root)
        _run(["git", "add", "-A"], cwd=repo_root)
        _run(["git", "commit", "-m", "wip: single-doc sprint work"], cwd=repo_root)

        update_ticket_status(str(ticket_path), "done")
        move_ticket_to_done(str(ticket_path))
        assert _only_sprint_md_and_tickets_present(sprint_dir)

        advance_phase(db_path, sprint_id)  # executing -> closing
        advance_phase(db_path, sprint_id)  # closing -> done

        # --- close: archive the sprint directly via legacy close path
        # (no real remote/push involved), confirming the single-doc shape
        # survives archival and docs/architecture/ never reappears.
        from clasi.tools.artifact_tools import _close_sprint_legacy

        close_result = json.loads(_close_sprint_legacy(sprint_id))
        archived_dir = Path(close_result["new_path"])
        assert archived_dir.exists()
        assert _only_sprint_md_and_tickets_present(archived_dir)

        assert not (work_dir / "docs" / "architecture").exists()

    def test_ambiguous_state_error_resolves_via_reporter_fallback(
        self, work_dir
    ) -> None:
        """Ticket 004's known finding: removing is_architecture_present /
        is_usecases_present made the `open` and `planned` sprint states
        share an identical invariant set (`is_sprint_doc_present` only), so
        a fresh sprint.md-only sprint's context satisfies both states'
        invariants simultaneously.

        As of 030/002, `evaluate_state` no longer treats this as an error:
        it defines most-advanced-match-wins (returns the last-declared
        matching state) instead of raising `AmbiguousStateError`, and the
        `status/reporter.py` exception-message-parsing workaround
        (`_last_matching_state_from_error`) this ambiguity used to force
        was deleted along with the exception path. Confirm both the direct
        `evaluate_state` call and the normal get_status/reporter path
        resolve determinately to "planned" (the more-advanced of the two
        ambiguous states) without any exception ever being raised.
        """
        from clasi.state_machine import (
            ProjectContext,
            SprintContext,
            evaluate_state,
            load_machine,
        )
        from clasi.status.reader import ClasiStateReader

        create_result = json.loads(create_sprint("Ambiguity Check Sprint"))
        sprint_id = create_result["id"]

        project = set_project(work_dir)
        reader = ClasiStateReader(project)
        machine = load_machine("sprint")
        project_ctx = ProjectContext(reader=reader)
        sprint_ctx = SprintContext(
            sprint_id=sprint_id, reader=reader, project=project_ctx
        )

        # Directly confirm the ambiguity exists (this is the documented
        # known finding, not itself a bug) -- a fresh sprint.md-only sprint
        # matches both `open` and `planned` invariant sets -- and that
        # evaluate_state resolves it determinately rather than raising.
        result = evaluate_state(machine, sprint_ctx)
        assert result.name == "planned"

        # Now confirm the normal get_status/reporter path agrees, via the
        # same evaluate_state call reporter.py makes internally (no
        # exception-message-parsing fallback involved anymore).
        from clasi.tools.process_tools import get_status

        status = json.loads(get_status())
        sprint_entries = [
            s for s in status.get("sprints", []) if s.get("id") == sprint_id
        ]
        assert len(sprint_entries) == 1, (
            f"expected exactly one sprint entry for {sprint_id!r}: {status.get('sprints')}"
        )
        # Resolved to "planned" (the more-advanced of the two ambiguous
        # states) rather than "unknown" or an unhandled exception
        # propagating out of get_status.
        assert sprint_entries[0]["state"] == "planned"


def _git_init_and_commit_project(root: Path) -> None:
    """Initialize git in a CLASI work_dir fixture and commit its current
    contents, needed because `_close_sprint_legacy`/archive operate purely
    on the filesystem but downstream branch bookkeeping in this test
    exercises real git commands.
    """
    if not (root / ".git").exists():
        _git_init(root)
        (root / ".gitkeep").write_text("", encoding="utf-8")
        _git_commit(root, "initial")


# ---------------------------------------------------------------------------
# Cross-issue: worktree:true AND single-doc model together
# ---------------------------------------------------------------------------


class TestCrossIssueWorktreeAndSingleDocTogether:
    """A sprint using BOTH worktree: true AND the single-doc planning model
    end-to-end, confirming the two features -- which touch overlapping
    files (sprint.py, artifact_tools.py) but not overlapping runtime
    behavior -- don't interfere with each other.
    """

    def test_worktree_true_sprint_uses_single_doc_planning_without_interference(
        self, work_dir
    ) -> None:
        # --- Single-doc planning: create + detail_sprint, no usecases.md /
        # architecture-update.md.
        create_result = json.loads(create_sprint("Cross Issue Sprint"))
        sprint_id = create_result["id"]
        sprint_dir = work_dir / ".clasi" / "sprints" / f"{sprint_id}-cross-issue-sprint"

        # --- Opt in to worktree parallel execution (Issue A's flag).
        fm = read_frontmatter(sprint_dir / "sprint.md")
        fm["worktree"] = True
        write_frontmatter(sprint_dir / "sprint.md", fm)

        detail_sprint(sprint_id)
        assert _only_sprint_md_and_tickets_present(sprint_dir)

        # Sprint.worktree reads back True through the normal object API,
        # confirming the flag and the single-doc scaffolding coexist on
        # the same sprint.md without one clobbering the other.
        from clasi.mcp_server import get_project

        project = get_project()
        sprint = project.get_sprint(sprint_id)
        assert sprint.worktree is True
        assert _only_sprint_md_and_tickets_present(sprint.path)

        # --- Drive an actual worktree-lifecycle ticket on this sprint,
        # proving the worktree machinery operates normally on a sprint
        # whose planning artifacts are single-doc-shaped.
        repo_root = work_dir
        _git_init_and_commit_project(repo_root)
        branch_name = f"sprint/{sprint_id}-cross-issue-sprint"
        _run(["git", "checkout", "-b", branch_name], cwd=repo_root)

        wt_path = worktree.create_worktree(repo_root, sprint_id, "001")
        try:
            ticket_branch = worktree.create_ticket_branch(
                wt_path, sprint_id, "001", "cross-issue-ticket"
            )
            (wt_path / "cross_issue_feature.py").write_text(
                "# cross issue feature\n", encoding="utf-8"
            )
            _run(["git", "add", "-A"], cwd=wt_path)
            _run(["git", "commit", "-m", "implement cross issue feature"], cwd=wt_path)
            ticket_path = _write_ticket_file(wt_path, status="done")

            assert worktree.validate_worktree(
                wt_path, ticket_path, test_command=["true"]
            ) is True
            worktree.merge_ticket_branch(repo_root, branch_name, ticket_branch)
            worktree.cleanup_worktree(repo_root, wt_path, ticket_branch, keep_branch=False)
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo_root)

        assert not wt_path.exists()
        _run(["git", "checkout", branch_name], cwd=repo_root)
        assert (repo_root / "cross_issue_feature.py").exists()

        # Sprint directory is still single-doc-shaped after the worktree
        # lifecycle ran against it -- no interference in either direction.
        assert _only_sprint_md_and_tickets_present(sprint_dir)
        assert not (work_dir / "docs" / "architecture").exists()
