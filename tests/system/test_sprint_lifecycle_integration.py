"""Sprint-lifecycle three-way integration test (030/006) -- the sprint's own
acceptance test.

Drives one sprint through every real writer -- create, detail, gates,
tickets, in-progress, done, close -- against a real temporary project (real
files under ``tmp_path``, a real SQLite ``.clasi.db``, a real git repo).
**No** ``StateReader`` stubbing anywhere in this module: every predicate
check goes through :class:`~clasi.status.reader.ClasiStateReader`, reading
the same filesystem/DB/git state the writers just produced.

Why this exists (see ``sprint.md`` Architecture M6 and finding 20 of
``docs/reviews/2026-08-reliability/01-state-layer.md``): the pre-existing
state-machine tests stub the reader to echo back whatever phase string a
predicate asks for -- which is exactly how the ``"ticketed"``-vs-
``"ticketing"`` vocabulary drift, the unrecordable ``sprint_review`` gate,
and the frontmatter/DB divergences this sprint fixes (tickets 001-004) all
shipped undetected: a stub that always agrees with the predicate can never
catch a *writer* disagreeing with itself. This test asserts, at every
lifecycle step, using the real writers and real readers:

1. DB phase, frontmatter ``status:``, and the computed sprint-machine state
   agree in the sense ticket 001's redesigned ``detect_inconsistencies``
   defines agreement: DB phase == frontmatter status (both written together
   by ``Sprint.set_sprint_stage()``). The computed sprint-machine state
   (the ``open``/``planned``/.../``ticketed``/``executing``/``closed``
   vocabulary) is a *distinct* signal answering a different question ("what
   can happen next", not "what stage is recorded") -- see the explicit
   "ticketed vs ticketing" assertion in step 6 below (right after
   ``create_ticket``), which checks that vocabulary's own value without ever
   comparing it to DB phase.
2. Gate predicates and ``StateDB.advance_phase`` agree on gate semantics: a
   ``"failed"`` gate result satisfies neither; a ``"passed"``/``"skipped"``
   result satisfies both.
3. ``detect_inconsistencies`` reports zero drift entries at every step
   along the healthy path.

Regression-teeth verification (ticket 030/006 acceptance criterion 4)
----------------------------------------------------------------------
This test was manually confirmed to fail (go red) against three
deliberately reintroduced regressions, each reverting one landed fix from
this sprint, then confirmed green again after reverting the regression.
This is a documented **manual** verification step (the alternative the
ticket allows to an in-file regression sub-test) -- it was not left as
permanent code here because each regression requires editing production
source directly (there is nothing in this test's own fixture to flip).

  A. **Ticket 001** (single writer): commented out the
     ``self.sprint_doc.update_frontmatter(status=phase)`` line in
     ``Sprint.set_sprint_stage()`` (``src/clasi/sprint.py``). Result: RED
     at the very first ``_assert_sprint_agreement`` call after
     ``detail_sprint`` -- DB phase advanced to ``"planning-docs"``, frontmatter
     stayed ``"roadmap"``. Reverted; confirmed GREEN again.
  B. **Ticket 002** (gate semantics): changed
     ``is_pre_flight_satisfied`` in
     ``src/clasi/state_machine/predicates/sprint.py`` from
     ``gate.get("result") in {"passed", "skipped"}`` back to
     ``gate.get("result") == "passed"``. Result: RED at the "Gate
     semantics probe #2" assertion (step 5 below, right after recording a
     ``"skipped"`` ``stakeholder_approval`` gate) -- the predicate returned
     ``False`` while ``StateDB.advance_phase`` (unchanged, still
     permissive) would have let the sprint advance past
     ``stakeholder-review`` anyway, exactly the disagreement criterion 2
     exists to catch. Reverted; confirmed GREEN again.
  C. **Ticket 003** (ticket done single writer): in
     ``Ticket.mark_done()`` (``src/clasi/ticket.py``), skipped the
     ``self.move_to_done_with_plan()`` call (left the file in ``tickets/``
     while still writing ``status: done``). Result: RED immediately at the
     step-8 file-move assertion (``done_ticket_path.exists()``) -- the
     ticket was never moved to ``tickets/done/``. (Had that assertion not
     existed, the very next zero-drift check would have caught it too:
     declared ``"done"`` vs. computed ``"open"``, since
     ``is_ticket_in_done_dir`` never becomes true.) Reverted; confirmed
     GREEN again.

Each regression was reverted immediately after observing the failure;
``git diff`` against ``src/clasi/`` was confirmed clean before this file
was committed.
"""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest

import clasi.state_machine.predicates  # noqa: F401 — side-effect: registers all predicates
import clasi.state_machine.predicates.project
import clasi.state_machine.predicates.sprint
import clasi.state_machine.predicates.ticket
from clasi.mcp_server import get_project, set_project
from clasi.state_machine import ProjectContext, SprintContext, evaluate_state, load_machine
from clasi.state_machine.registry import clear_registry, get_predicate
from clasi.status.inconsistency import detect_inconsistencies
from clasi.status.reader import ClasiStateReader
from clasi.status.reporter import StatusReporter
from clasi.tools.artifact_tools import (
    acquire_execution_lock,
    advance_sprint_phase,
    close_sprint,
    create_sprint,
    create_ticket,
    detail_sprint,
    record_gate_result,
    update_ticket_status,
)


# ---------------------------------------------------------------------------
# Registry guard: this module evaluates the real, unmocked sprint machine
# (step 10 below, added by 031/001). If a prior test module's autouse
# fixture cleared the predicate registry and this module happened to run
# afterward in the same session (e.g. `pytest test_predicates.py
# test_sprint_lifecycle_integration.py`), evaluate_state() would raise
# UnknownPredicateError for a reason that has nothing to do with what this
# module actually tests. Re-registering before every test — matching the
# guard already used in test_hook_injection.py / test_reporter.py — makes
# this file's real-state-machine assertion independent of module run order.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_predicates_registered():
    clear_registry()
    importlib.reload(clasi.state_machine.predicates.project)
    importlib.reload(clasi.state_machine.predicates.sprint)
    importlib.reload(clasi.state_machine.predicates.ticket)
    yield


# ---------------------------------------------------------------------------
# Git helpers (mirrors tests/system/test_close_sprint_resumability.py)
# ---------------------------------------------------------------------------


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "master", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True, capture_output=True)


def _git_commit(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", message], cwd=root, check=True, capture_output=True)


@pytest.fixture
def work_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real, scratch git repository seeded as a CLASI project.

    Never this repo's own sprint 030 -- a throwaway repo so close_sprint's
    real version-bump/tag/merge machinery has real git state to work
    against, and so nothing here can touch this repository's own history.
    """
    root = tmp_path / "repo"
    root.mkdir()
    _git_init(root)

    (root / "pyproject.toml").write_text(
        '[project]\nname = "lifecycle-dry-run"\nversion = "0.20260101.1"\n',
        encoding="utf-8",
    )
    clasi_dir = root / ".clasi"
    clasi_dir.mkdir(parents=True, exist_ok=True)
    (clasi_dir / "config.yaml").write_text("process: se\n", encoding="utf-8")
    _git_commit(root, "initial")

    monkeypatch.chdir(root)
    set_project(root)
    return root


# ---------------------------------------------------------------------------
# Assertion helpers -- these are the acceptance-criteria checks, factored
# out so every lifecycle step below reads as "do the real thing, then
# assert the three-way agreement" instead of repeating the plumbing.
# ---------------------------------------------------------------------------


def _assert_sprint_agreement(sprint_id: str, expected_phase: str) -> None:
    """DB phase and frontmatter status: must both equal *expected_phase*
    and therefore each other -- the agreement ticket 001's
    Sprint.set_sprint_stage() (the sole writer) guarantees by construction.
    """
    project = get_project()
    db_phase = project.db.get_sprint_state(sprint_id)["phase"]
    sprint = project.get_sprint(sprint_id)
    fm_status = sprint.sprint_doc.frontmatter.get("status")

    assert db_phase == expected_phase, (
        f"DB phase was {db_phase!r}, expected {expected_phase!r}"
    )
    assert fm_status == expected_phase, (
        f"frontmatter status: was {fm_status!r}, expected {expected_phase!r}"
    )
    assert db_phase == fm_status, (
        "DB phase and frontmatter status disagree "
        f"({db_phase!r} != {fm_status!r}) -- set_sprint_stage() is supposed "
        "to make this impossible for a sprint written after ticket 030/001"
    )


def _build_status() -> dict:
    """Build the full status dict via the real StatusReporter (a fresh
    ClasiStateReader every call -- no reader is held across git-mutating
    steps, so nothing here can serve a stale git-subprocess cache)."""
    return StatusReporter(get_project()).build(skip_inconsistencies=True)


def _assert_zero_drift() -> dict:
    """Call the real detect_inconsistencies() against a freshly built
    status dict and assert it reports no drift. Returns the status dict
    so callers that also want the computed sprint/ticket state can reuse
    it without a second build.
    """
    project = get_project()
    status = _build_status()
    drift = detect_inconsistencies(project, status)
    assert drift == [], f"detect_inconsistencies reported drift: {drift}"
    status["inconsistencies"] = drift
    return status


def _sprint_entry(status: dict, sprint_id: str) -> dict:
    for entry in status["sprints"]:
        if entry["id"] == sprint_id:
            return entry
    raise AssertionError(f"sprint {sprint_id!r} not present in status dict")


def _ticket_entry(status: dict, sprint_id: str, ticket_id: str) -> dict:
    sprint_entry = _sprint_entry(status, sprint_id)
    for entry in sprint_entry["tickets"].get("details", []):
        if entry["id"] == ticket_id:
            return entry
    raise AssertionError(f"ticket {ticket_id!r} not present in sprint {sprint_id!r}")


def _sprint_ctx(sprint_id: str) -> SprintContext:
    """A fresh SprintContext backed by a fresh, real ClasiStateReader --
    no stub anywhere in this module."""
    project = get_project()
    reader = ClasiStateReader(project)
    return SprintContext(sprint_id=sprint_id, reader=reader, project=ProjectContext(reader=reader))


# ---------------------------------------------------------------------------
# The main lifecycle test
# ---------------------------------------------------------------------------


class TestSprintLifecycleThreeWayIntegration:
    """Drives one sprint through every real writer end to end, asserting
    three-way agreement (DB phase / frontmatter / drift-checker) at each
    step -- this class's docstring at module level documents the manual
    regression-teeth verification (acceptance criterion 4)."""

    def test_full_lifecycle_create_through_close(
        self, work_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project = get_project()

        # ------------------------------------------------------------
        # 1. create (Project.create_sprint, via the create_sprint tool,
        #    which also registers the sprint in the state DB)
        # ------------------------------------------------------------
        create_result = json.loads(create_sprint("Lifecycle Dry Run"))
        sprint_id = create_result["id"]
        sprint_dir = Path(create_result["path"])
        branch_name = create_result["branch"]
        assert sprint_dir.exists(), f"expected sprint directory at {sprint_dir}"

        _assert_sprint_agreement(sprint_id, "roadmap")
        _assert_zero_drift()

        # ------------------------------------------------------------
        # 2. detail (Sprint.detail_promote -> Sprint.set_sprint_stage)
        # ------------------------------------------------------------
        detail_result = json.loads(detail_sprint(sprint_id))
        assert detail_result["phase"] == "planning-docs", detail_result

        _assert_sprint_agreement(sprint_id, "planning-docs")
        _assert_zero_drift()

        # ------------------------------------------------------------
        # 3. advance to architecture-review (Sprint.advance_phase, via
        #    the advance_sprint_phase tool)
        # ------------------------------------------------------------
        advance_result = json.loads(advance_sprint_phase(sprint_id))
        assert advance_result["new_phase"] == "architecture-review", advance_result

        _assert_sprint_agreement(sprint_id, "architecture-review")
        _assert_zero_drift()

        # ------------------------------------------------------------
        # 4. Gate semantics probe #1 (acceptance criterion 2): a
        #    "failed" architecture_review gate satisfies neither
        #    StateDB.advance_phase nor is_architecture_review_recorded.
        #    Uses the low-level StateDB.advance_phase directly (not the
        #    Sprint/set_sprint_stage path) precisely because we expect
        #    it to raise and change nothing -- no drift risk from a
        #    call that never succeeds.
        # ------------------------------------------------------------
        record_gate_result(sprint_id, "architecture_review", "failed", "NONE")

        with pytest.raises(ValueError):
            project.db.advance_phase(sprint_id)

        is_arch_recorded = get_predicate("is_architecture_review_recorded")
        assert is_arch_recorded(_sprint_ctx(sprint_id)) is False, (
            "a 'failed' architecture_review gate must not satisfy "
            "is_architecture_review_recorded -- if it does, the predicate "
            "and StateDB.advance_phase's gate check have diverged"
        )

        # Also confirm the removed "sprint_review" gate name (finding
        # named in this ticket's description -- the unrecordable gate)
        # is rejected outright, not silently accepted into a gate no
        # predicate could ever be satisfied by.
        with pytest.raises(ValueError):
            project.db.record_gate(sprint_id, "sprint_review", "passed")

        # Now satisfy the gate for real.
        record_gate_result(sprint_id, "architecture_review", "passed", "NONE")
        assert is_arch_recorded(_sprint_ctx(sprint_id)) is True

        # 031/002: recording the gate does NOT itself move the phase --
        # the phase machine's stakeholder-review phase is deleted, and
        # 'ticketing' now arrives only as a side effect of create_ticket's
        # first call (below), never a separate advance_sprint_phase call.
        # This is the exact gate-order fix this ticket exists to ship:
        # under the pre-031/002 code, the *documented* flow (record the
        # gate, then create tickets) was rejected here because
        # create_ticket hard-required 'ticketing' phase, which only a
        # since-deleted stakeholder-review step could reach.
        _assert_sprint_agreement(sprint_id, "architecture-review")
        _assert_zero_drift()

        # ------------------------------------------------------------
        # 5. tickets (create_ticket) -- SUC-002's Main Flow: this call
        #    both checks the recorded architecture_review gate directly
        #    (not a phase index) and auto-advances the phase to
        #    'ticketing' as a side effect, with zero rejected calls.
        # ------------------------------------------------------------
        ticket_result = json.loads(create_ticket(sprint_id, "Do the thing"))
        ticket_id = ticket_result["id"]
        ticket_path = Path(ticket_result["path"])
        assert ticket_path.exists(), f"expected ticket file at {ticket_path}"
        assert ticket_result["status"] == "open", ticket_result

        _assert_sprint_agreement(sprint_id, "ticketing")
        status = _assert_zero_drift()
        ticket_entry = _ticket_entry(status, sprint_id, ticket_id)
        assert ticket_entry["state"] == "open", ticket_entry

        # is_any_sprint_ticketed queries the real DB-phase vocabulary
        # ("ticketing"), not the computed sprint-machine vocabulary's
        # "ticketed" state below -- true as soon as the DB phase says so,
        # independent of whether stakeholder_approval has been recorded
        # yet (that only affects the *computed* "ticketed" state, step 6
        # below, under the new architecture_review -> create_ticket ->
        # stakeholder_approval order this ticket ships). This is the
        # exact "ticketed" vs. "ticketing" vocabulary collision named in
        # this ticket's description and fixed by 030/002.
        is_any_sprint_ticketed = get_predicate("is_any_sprint_ticketed")
        assert is_any_sprint_ticketed(ProjectContext(reader=ClasiStateReader(project))) is True

        # ------------------------------------------------------------
        # 6. Gate semantics probe #2: "skipped" satisfies both sides
        #    just as "passed" does (the other half of criterion 2).
        #    031/002: stakeholder_approval no longer gates a DB-phase
        #    transition (recording it here does not itself move the DB
        #    phase) -- it gates acquire_execution_lock instead, step 7
        #    below. It DOES complete the *computed* sprint-machine's
        #    'ticketed' state invariants (schemas/state-machines/
        #    sprint.yaml's 'ticketed' state requires
        #    is_pre_flight_satisfied among four invariants, unchanged by
        #    this ticket) -- under the new create-then-approve order, the
        #    computed state only becomes 'ticketed' here, not at
        #    ticket-creation time (step 5) as it did under the old
        #    approve-then-create order this ticket replaces.
        # ------------------------------------------------------------
        record_gate_result(sprint_id, "stakeholder_approval", "skipped", "NONE")

        is_pre_flight_satisfied = get_predicate("is_pre_flight_satisfied")
        assert is_pre_flight_satisfied(_sprint_ctx(sprint_id)) is True, (
            "a 'skipped' stakeholder_approval gate must satisfy "
            "is_pre_flight_satisfied, same as 'passed'"
        )

        _assert_sprint_agreement(sprint_id, "ticketing")
        status = _assert_zero_drift()

        # Acceptance criterion 1's "distinct, non-compared signal":
        # DB phase == "ticketing" (recorded-stage vocabulary) while the
        # computed sprint-machine state == "ticketed" (transition
        # vocabulary, now satisfied: doc present, architecture_review
        # recorded, pre-flight satisfied, at least one ticket) -- two
        # different strings, both correct, precisely because they answer
        # different questions. Assert the computed value directly rather
        # than comparing it to DB phase.
        sprint_entry = _sprint_entry(status, sprint_id)
        assert sprint_entry["state"] == "ticketed", sprint_entry
        db_phase_now = project.db.get_sprint_state(sprint_id)["phase"]
        assert db_phase_now == "ticketing"
        assert sprint_entry["state"] != db_phase_now, (
            "the computed sprint-machine state and the DB phase are "
            "different vocabularies by design -- seeing them collide "
            "here would mean a writer accidentally aligned them"
        )

        # ------------------------------------------------------------
        # 7. in-progress: acquire the execution lock (creates + checks
        #    out the sprint branch for real). 031/002: this call itself
        #    checks the recorded stakeholder_approval gate (rejecting,
        #    granting no lock, if it hadn't passed) and auto-advances the
        #    phase to 'executing' as a side effect -- no separate
        #    advance_sprint_phase call. Then move the ticket to
        #    in-progress.
        # ------------------------------------------------------------
        lock_result = json.loads(acquire_execution_lock(sprint_id))
        assert lock_result["branch"] == branch_name, lock_result
        assert project.db.get_lock_holder()["sprint_id"] == sprint_id

        _assert_sprint_agreement(sprint_id, "executing")
        _assert_zero_drift()

        update_ticket_status(str(ticket_path), "in-progress")

        status = _assert_zero_drift()
        ticket_entry = _ticket_entry(status, sprint_id, ticket_id)
        assert ticket_entry["state"] == "in-progress", ticket_entry

        # Real "work": a file change, committed for real, so the
        # eventual merge has real content to carry across.
        (work_dir / "feature.py").write_text("# ticket work\n", encoding="utf-8")
        _git_commit(work_dir, f"feat: work on ticket ({sprint_id}-{ticket_id})")

        # ------------------------------------------------------------
        # 8. done (update_ticket_status -> Ticket.mark_done — status
        #    write and the tickets/done/ move in one call, per 030/003)
        # ------------------------------------------------------------
        update_ticket_status(str(ticket_path), "done")
        done_ticket_path = ticket_path.parent / "done" / ticket_path.name
        assert done_ticket_path.exists(), f"expected ticket moved to {done_ticket_path}"

        status = _assert_zero_drift()
        ticket_entry = _ticket_entry(status, sprint_id, ticket_id)
        assert ticket_entry["state"] == "done", ticket_entry

        _git_commit(work_dir, f"chore: complete ticket ({sprint_id}-{ticket_id})")

        # ------------------------------------------------------------
        # 9. close (close.SprintCloser / StateDB.force_close, via the
        #    close_sprint tool)
        #
        # delete_branch=True (the tool's own default) deliberately, not
        # False: this is the exact real-world sequence that exposed
        # 031/001 (branch merged, archived, then deleted) -- a run with
        # delete_branch=False would never touch that code path and could
        # not have caught the regression the closed-state assertion
        # below now guards against.
        # ------------------------------------------------------------
        close_result = json.loads(
            close_sprint(
                sprint_id=sprint_id,
                branch_name=branch_name,
                main_branch="master",
                push_tags=False,
                delete_branch=True,
                test_command="SKIP",
            )
        )
        assert close_result["status"] == "success", close_result

        # Final three-way agreement check. detect_inconsistencies
        # exempts an archived (sprints/done/) sprint from its own
        # phase-vs-frontmatter check by design (a terminal sprint has
        # no outbound transitions to reconcile toward -- see
        # status/inconsistency.py's _sprint_is_terminal), so the
        # agreement here is asserted directly against both signals
        # rather than through detect_inconsistencies.
        final_phase = project.db.get_sprint_state(sprint_id)["phase"]
        archived_sprint = project.get_sprint(sprint_id)
        final_status = archived_sprint.sprint_doc.frontmatter.get("status")

        assert final_phase == "done", final_phase
        assert final_status == "done", final_status
        assert archived_sprint.path.parent.name == "done", archived_sprint.path

        assert project.db.get_lock_holder() is None

        # done_ticket_path was resolved against the pre-archive sprint
        # directory; archive() has since moved the whole sprint tree
        # under sprints/done/, so re-resolve the ticket via the
        # archived Sprint object rather than the stale path.
        archived_ticket = archived_sprint.get_ticket(ticket_id)
        assert archived_ticket.status == "done"
        assert archived_ticket.path.parent.name == "done"

        # ------------------------------------------------------------
        # 10. computed sprint-machine state after a real close (031/001
        #    regression teeth). This is distinct from final_phase/
        #    final_status above -- those are the recorded DB phase and
        #    frontmatter status: ("done"); this is the *computed*
        #    sprint-machine state ("closed"), evaluated against a fresh
        #    ClasiStateReader the same way `clasi status` would. Before
        #    031/001, `closed`'s invariants were
        #    [is_sprint_archived, is_branch_merged], and is_branch_merged
        #    read `git branch --merged <default>` -- a query that can
        #    never see a branch close_sprint has just deleted
        #    (delete_branch=True above). That made `closed` permanently
        #    unreachable and evaluate_state fell back to the
        #    most-advanced state that still matched ("pre-flight"). This
        #    assertion is the one this sprint's own bug report shows was
        #    missing.
        # ------------------------------------------------------------
        sprint_machine = load_machine("sprint")
        final_state = evaluate_state(sprint_machine, _sprint_ctx(sprint_id))
        assert final_state.name == "closed", (
            f"expected computed sprint-machine state 'closed', got "
            f"{final_state.name!r}"
        )
