"""Unit tests for hook-injection handlers: handle_status_inject and the
status block prepended by handle_subagent_start.

All tests use tmp_path to simulate different project states (no .clasi/,
.clasi/ without oop, .clasi/oop present) and capture stdout to verify the
emitted block.
"""

from __future__ import annotations

import importlib
import logging
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

import clasi.state_machine.predicates  # noqa: F401 — side-effect: registers all predicates
import clasi.state_machine.predicates.project
import clasi.state_machine.predicates.sprint
import clasi.state_machine.predicates.ticket
from clasi.state_machine.loader import load_machine
import clasi.state_machine.loader as loader_module
from clasi.state_machine.registry import clear_registry
from clasi.hook_handlers import (
    handle_status_inject,
    handle_subagent_start,
    _trim_empty_preflight_sprints,
)
from clasi.state_db import init_db, register_sprint, acquire_lock


# ---------------------------------------------------------------------------
# Registry guard: several tests below exercise the REAL, unmocked state
# machine (via handle_status_inject -> build_status). If a prior test
# module's autouse fixture cleared the predicate registry (e.g.
# test_evaluator._clean_registry) and ran after this module's normal
# import-time registration, evaluate_state() would raise
# UnknownPredicateError. Re-registering before every test — matching the
# guard already used in test_reporter.py — makes this file's real-state-
# machine tests independent of module run order.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_predicates_registered():
    clear_registry()
    importlib.reload(clasi.state_machine.predicates.project)
    importlib.reload(clasi.state_machine.predicates.sprint)
    importlib.reload(clasi.state_machine.predicates.ticket)
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chdir(tmp_path: Path):
    """Context manager: change cwd to tmp_path and restore on exit."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            yield
        finally:
            os.chdir(old)

    return _ctx()


def _capture_stdout(fn, *args, **kwargs) -> tuple[str, int]:
    """Call fn(*args, **kwargs), capture stdout, return (output, exit_code).

    Catches SystemExit so the hook's sys.exit() doesn't kill the test.
    """
    buf = StringIO()
    exit_code = 0
    with patch("sys.stdout", buf):
        try:
            fn(*args, **kwargs)
        except SystemExit as exc:
            exit_code = int(exc.code) if exc.code is not None else 0
    return buf.getvalue(), exit_code


def _make_clasi_dir(tmp_path: Path) -> Path:
    """Create a minimal .clasi/ directory so project is CLASI-initialized."""
    clasi_dir = tmp_path / ".clasi"
    clasi_dir.mkdir()
    return clasi_dir


# ---------------------------------------------------------------------------
# Realistic multi-sprint on-disk fixture (019-006) — REAL, unmocked
# handle_status_inject output is what the size/narrowing/imperative tests
# below assert against.  Every existing test above this point mocks
# _build_status_block away, which is exactly how the original 34KB block
# shipped unnoticed (see ticket 006).
# ---------------------------------------------------------------------------


def _write_fresh_config(root: Path) -> None:
    """Write config.yaml with no paths: block -> uses new default layout
    (clasi/sprints/, clasi/issues/, etc. — visible, not dot-hidden)."""
    clasi_dir = root / ".clasi"
    clasi_dir.mkdir(parents=True, exist_ok=True)
    (clasi_dir / "config.yaml").write_text("process: se\n", encoding="utf-8")


def _write_sprint_md(
    sprint_dir: Path,
    sprint_id: str,
    title: str,
    status: str = "executing",
) -> None:
    sprint_dir.mkdir(parents=True, exist_ok=True)
    slug = title.lower().replace(" ", "-")
    (sprint_dir / "sprint.md").write_text(
        f"---\nid: \"{sprint_id}\"\ntitle: \"{title}\"\n"
        f"status: {status}\nbranch: sprint/{sprint_id}-{slug}\n---\n"
        f"# Sprint {sprint_id}: {title}\n",
        encoding="utf-8",
    )


def _write_ticket(
    sprint_dir: Path,
    ticket_id: str,
    title: str,
    status: str = "open",
    done_dir: bool = False,
) -> None:
    tickets_dir = sprint_dir / "tickets" / ("done" if done_dir else "")
    tickets_dir.mkdir(parents=True, exist_ok=True)
    slug = title.lower().replace(" ", "-")
    (tickets_dir / f"{ticket_id}-{slug}.md").write_text(
        f"---\nid: '{ticket_id}'\ntitle: {title}\nstatus: {status}\n"
        "use-cases: []\ndepends-on: []\n---\n"
        f"# {title}\n\n"
        "## Description\n\n"
        "Some reasonably realistic prose describing this ticket's scope, "
        "acceptance criteria, and testing notes, so the fixture is not "
        "unrealistically tiny compared to real sprint content.\n",
        encoding="utf-8",
    )


def _build_realistic_multi_sprint_fixture(tmp_path: Path) -> str:
    """Build an on-disk multi-sprint project: several done/ archived
    sprints (each with several done tickets) plus one executing sprint
    with a mix of done and in-progress tickets.

    Returns the sprint_id of the executing sprint (the one with an
    execution lock held in the state DB).
    """
    _write_fresh_config(tmp_path)
    sprints_root = tmp_path / "clasi" / "sprints"

    # Several archived (done/) sprints, each with several done tickets —
    # mirrors the real project's ~18-sprint history.
    for n in range(1, 6):
        sid = f"{n:03d}"
        sprint_dir = sprints_root / "done" / f"{sid}-archived-sprint-{n}"
        _write_sprint_md(sprint_dir, sid, f"Archived Sprint {n}", status="done")
        for t in range(1, 5):
            tid = f"{t:03d}"
            _write_ticket(
                sprint_dir, tid, f"Archived ticket {n}-{t}",
                status="done", done_dir=True,
            )

    # One currently-executing sprint with a mix of done and in-progress
    # tickets — this is the sprint under the execution lock.
    active_sid = "019"
    active_dir = sprints_root / f"{active_sid}-current-sprint"
    _write_sprint_md(active_dir, active_sid, "Current Sprint", status="executing")
    for t in range(1, 4):
        tid = f"{t:03d}"
        _write_ticket(
            active_dir, tid, f"Finished ticket {t}", status="done", done_dir=True,
        )
    _write_ticket(active_dir, "006", "Shrink status block", status="in-progress")

    db_path = str(tmp_path / ".clasi" / ".clasi.db")
    init_db(db_path)
    register_sprint(db_path, active_sid, "current-sprint")
    acquire_lock(db_path, active_sid)

    return active_sid


def _build_fixture_no_active_ticket(tmp_path: Path) -> str:
    """Like _build_realistic_multi_sprint_fixture, but the executing
    sprint has zero in-progress tickets (all done) — the scenario that
    should trigger the ticket-gate imperative."""
    _write_fresh_config(tmp_path)
    sprints_root = tmp_path / "clasi" / "sprints"

    for n in range(1, 4):
        sid = f"{n:03d}"
        sprint_dir = sprints_root / "done" / f"{sid}-archived-sprint-{n}"
        _write_sprint_md(sprint_dir, sid, f"Archived Sprint {n}", status="done")
        for t in range(1, 4):
            tid = f"{t:03d}"
            _write_ticket(
                sprint_dir, tid, f"Archived ticket {n}-{t}",
                status="done", done_dir=True,
            )

    active_sid = "020"
    active_dir = sprints_root / f"{active_sid}-current-sprint"
    _write_sprint_md(active_dir, active_sid, "Current Sprint", status="executing")
    for t in range(1, 4):
        tid = f"{t:03d}"
        _write_ticket(
            active_dir, tid, f"Finished ticket {t}", status="done", done_dir=True,
        )

    db_path = str(tmp_path / ".clasi" / ".clasi.db")
    init_db(db_path)
    register_sprint(db_path, active_sid, "current-sprint")
    acquire_lock(db_path, active_sid)

    return active_sid


def _run_status_inject(tmp_path: Path, agent: str = "team-lead") -> str:
    """Run the REAL, unmocked handle_status_inject against tmp_path (cwd
    switched there) and return the captured stdout output."""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    old_agent = os.environ.get("CLASI_AGENT_NAME")
    try:
        os.environ["CLASI_AGENT_NAME"] = agent
        buf = StringIO()
        with patch("sys.stdout", buf):
            try:
                handle_status_inject({})
            except SystemExit:
                pass
        return buf.getvalue()
    finally:
        os.chdir(old_cwd)
        if old_agent is None:
            os.environ.pop("CLASI_AGENT_NAME", None)
        else:
            os.environ["CLASI_AGENT_NAME"] = old_agent


def _extract_yaml(block: str) -> dict:
    """Parse the fenced ```yaml ... ``` body out of a ## CLASI status block."""
    start = block.index("```yaml\n") + len("```yaml\n")
    end = block.index("```", start)
    return yaml.safe_load(block[start:end])


# ---------------------------------------------------------------------------
# Size assertion — the REAL, unmocked handle_status_inject output (019-006)
# ---------------------------------------------------------------------------


class TestRealStatusBlockSize:
    """Byte-size assertion against the actual, unmocked status block —
    not _build_status_block mocked away. This is the test the ticket
    calls out as the one that matters: every prior test in this file
    mocked the block builder, which is exactly how a 34KB block shipped
    unnoticed."""

    def test_real_multi_sprint_output_well_under_5kb(self, tmp_path):
        _build_realistic_multi_sprint_fixture(tmp_path)

        output = _run_status_inject(tmp_path, agent="team-lead")

        assert output != ""
        assert len(output.encode("utf-8")) < 5000

    def test_real_multi_sprint_programmer_output_well_under_5kb(self, tmp_path):
        _build_realistic_multi_sprint_fixture(tmp_path)

        output = _run_status_inject(tmp_path, agent="programmer")

        assert output != ""
        assert len(output.encode("utf-8")) < 5000


# ---------------------------------------------------------------------------
# Git-call and load_machine parse-count collapse across a REAL, realistic
# multi-sprint build_status invocation (sprint 026 / ticket 003).
#
# These are structural call-count assertions, not wall-clock timing —
# the ticket explicitly calls out that a mock/debug-counter assertion is
# required, not variance-prone timing alone (timing is covered separately
# by the `time clasi hook status-inject` measurement recorded in the
# ticket file).
# ---------------------------------------------------------------------------


class TestGitCallAndLoadMachineCountCollapse:
    def test_git_subprocess_call_count_stays_small_across_multi_sprint_status(
        self, tmp_path
    ):
        """Baseline measured about 28 git subprocess calls for one
        build_status invocation (is_on_sprint_branch alone shelled out
        14x). Per-instance memoization in ClasiStateReader must collapse
        this to about 3 distinct git queries (show-current, symbolic-ref,
        branch --merged <default>) regardless of how many sprints/tickets
        the evaluated machines touch."""
        _build_realistic_multi_sprint_fixture(tmp_path)

        real_run = subprocess.run
        calls: list[tuple] = []

        def counting_run(cmd, **kwargs):
            calls.append(tuple(cmd))
            return real_run(cmd, **kwargs)

        with patch("clasi.status.reader.subprocess.run", side_effect=counting_run):
            output = _run_status_inject(tmp_path, agent="team-lead")

        assert output != ""
        assert len(calls) <= 3, f"expected <=3 git subprocess calls, got {calls}"

    def test_load_machine_parse_count_is_three_across_multi_sprint_status(
        self, tmp_path
    ):
        """Baseline measured about 20 load_machine re-parses for one
        build_status invocation (project/sprint/ticket machines
        re-parsed once per evaluation). functools.lru_cache must collapse
        this to exactly 3 real parse-and-construct passes — one per
        distinct machine name — no matter how many sprints/tickets are
        evaluated.

        Counts calls to the module-private ``_build_machine`` (reached
        only on an actual cache miss inside ``load_machine``) rather than
        ``yaml.safe_load`` directly — the latter is also used elsewhere
        in the codebase (e.g. config.yaml parsing) and would over-count.
        """
        _build_realistic_multi_sprint_fixture(tmp_path)
        load_machine.cache_clear()

        real_build_machine = loader_module._build_machine
        calls: list[str] = []

        def counting_build_machine(data, source_name):
            calls.append(source_name)
            return real_build_machine(data, source_name)

        with patch.object(
            loader_module, "_build_machine", side_effect=counting_build_machine
        ):
            output = _run_status_inject(tmp_path, agent="team-lead")

        assert output != ""
        assert len(calls) == 3, f"expected exactly 3 parses, got {calls}"
        assert set(calls) == {"project", "sprint", "ticket"}


# ---------------------------------------------------------------------------
# done/ exclusion at the hook level (fix 1)
# ---------------------------------------------------------------------------


class TestHookExcludesDone:
    def test_done_sprints_absent_from_injected_block(self, tmp_path):
        _build_realistic_multi_sprint_fixture(tmp_path)

        output = _run_status_inject(tmp_path, agent="team-lead")
        parsed = _extract_yaml(output)

        sprint_ids = {s["id"] for s in parsed["sprints"]}
        # Archived sprints 001-005 must not appear; only the executing
        # sprint 019 should be present.
        assert sprint_ids == {"019"}

    def test_done_tickets_absent_from_remaining_sprint(self, tmp_path):
        _build_realistic_multi_sprint_fixture(tmp_path)

        output = _run_status_inject(tmp_path, agent="team-lead")
        parsed = _extract_yaml(output)

        sprint_019 = next(s for s in parsed["sprints"] if s["id"] == "019")
        detail_ids = {d["id"] for d in sprint_019["tickets"].get("details", [])}
        # Only the in-progress ticket should remain; the three done
        # tickets (001, 002, 003) must be excluded.
        assert "019-006" in detail_ids or "006" in detail_ids
        assert not ({"019-001", "001"} & detail_ids)


# ---------------------------------------------------------------------------
# available_transitions/blocked_by trim for empty pre-flight sprints
# (sprint 026 / ticket 003)
# ---------------------------------------------------------------------------


class TestTrimEmptyPreflightSprintsHelper:
    """Direct unit tests for _trim_empty_preflight_sprints, isolated from
    the rest of the hook pipeline: a sprint entry with zero tickets has
    available_transitions dropped; a sprint entry with at least one
    ticket is left completely untouched."""

    def test_drops_available_transitions_for_zero_ticket_sprint(self):
        narrowed = {
            "sprints": [
                {
                    "id": "025",
                    "state": "planned",
                    "available_transitions": [
                        {"name": "architecture-review", "to": "pre-flight",
                         "fireable": True, "blocked_by": []},
                    ],
                    "tickets": {"total": 0},
                },
            ],
        }
        _trim_empty_preflight_sprints(narrowed)
        assert "available_transitions" not in narrowed["sprints"][0]

    def test_keeps_available_transitions_for_sprint_with_tickets(self):
        entry = {
            "id": "019",
            "state": "executing",
            "available_transitions": [
                {"name": "complete", "to": "review",
                 "fireable": False, "blocked_by": ["is_all_tickets_done"]},
            ],
            "tickets": {"total": 3, "by_state": {"open": 3}},
        }
        narrowed = {"sprints": [dict(entry)]}
        _trim_empty_preflight_sprints(narrowed)
        assert narrowed["sprints"][0] == entry

    def test_other_sprint_keys_unaffected_by_trim(self):
        narrowed = {
            "sprints": [
                {"id": "025", "state": "open",
                 "available_transitions": [{"name": "plan"}],
                 "tickets": {"total": 0}},
            ],
        }
        _trim_empty_preflight_sprints(narrowed)
        sprint_entry = narrowed["sprints"][0]
        assert sprint_entry["id"] == "025"
        assert sprint_entry["state"] == "open"
        assert sprint_entry["tickets"] == {"total": 0}

    def test_missing_sprints_key_is_a_noop(self):
        narrowed = {"agent": "team-lead"}
        _trim_empty_preflight_sprints(narrowed)  # must not raise
        assert narrowed == {"agent": "team-lead"}

    def test_missing_tickets_block_treated_as_zero(self):
        """A sprint entry with no `tickets` key at all (defensive) is
        treated the same as total == 0 -> trimmed, never raises."""
        narrowed = {"sprints": [{"id": "099", "available_transitions": [{"name": "x"}]}]}
        _trim_empty_preflight_sprints(narrowed)
        assert "available_transitions" not in narrowed["sprints"][0]

    def test_no_available_transitions_key_is_a_noop(self):
        """A sprint entry that already lacks available_transitions (e.g.
        narrowed away by a different agent view) must not raise."""
        narrowed = {"sprints": [{"id": "099", "tickets": {"total": 0}}]}
        _trim_empty_preflight_sprints(narrowed)
        assert "available_transitions" not in narrowed["sprints"][0]


def _build_fixture_with_empty_and_active_sprints(tmp_path: Path) -> str:
    """One executing sprint with an in-progress ticket, plus one bare
    (sprint.md only, zero tickets) pre-flight sprint — the exact contrast
    the trim targets: the empty sprint's available_transitions must be
    dropped from the injected block; the active sprint's must not."""
    _write_fresh_config(tmp_path)
    sprints_root = tmp_path / "clasi" / "sprints"

    active_sid = "019"
    active_dir = sprints_root / f"{active_sid}-current-sprint"
    _write_sprint_md(active_dir, active_sid, "Current Sprint", status="executing")
    _write_ticket(active_dir, "001", "In progress ticket", status="in-progress")

    empty_sid = "025"
    empty_dir = sprints_root / f"{empty_sid}-future-sprint"
    _write_sprint_md(empty_dir, empty_sid, "Future Sprint", status="open")
    (empty_dir / "tickets").mkdir(parents=True, exist_ok=True)

    db_path = str(tmp_path / ".clasi" / ".clasi.db")
    init_db(db_path)
    register_sprint(db_path, active_sid, "current-sprint")
    acquire_lock(db_path, active_sid)

    return active_sid


class TestTrimEmptyPreflightSprintsEndToEnd:
    """Real, unmocked handle_status_inject output — proves the trim is
    actually wired into the hook path (not just correct in isolation),
    and that a sprint with tickets keeps its full detail."""

    def test_empty_sprint_available_transitions_absent_from_output(self, tmp_path):
        _build_fixture_with_empty_and_active_sprints(tmp_path)

        output = _run_status_inject(tmp_path, agent="team-lead")
        parsed = _extract_yaml(output)

        empty_sprint = next(s for s in parsed["sprints"] if s["id"] == "025")
        assert empty_sprint["tickets"]["total"] == 0
        assert "available_transitions" not in empty_sprint

    def test_active_ticketed_sprint_available_transitions_present(self, tmp_path):
        _build_fixture_with_empty_and_active_sprints(tmp_path)

        output = _run_status_inject(tmp_path, agent="team-lead")
        parsed = _extract_yaml(output)

        active_sprint = next(s for s in parsed["sprints"] if s["id"] == "019")
        assert active_sprint["tickets"]["total"] >= 1
        assert "available_transitions" in active_sprint


# ---------------------------------------------------------------------------
# detect_inconsistencies removed from the status-inject hook path
# (sprint 026 / ticket 003)
# ---------------------------------------------------------------------------


class TestStatusInjectSkipsInconsistencies:
    """End-to-end confirmation, against the REAL (unmocked) hook handler,
    that detect_inconsistencies never runs on the status-inject path.
    The clasi status CLI / get_status MCP tool path is verified
    unaffected in tests/integration/test_status_e2e.py."""

    def test_detect_inconsistencies_not_called_on_real_status_inject(self, tmp_path):
        _build_realistic_multi_sprint_fixture(tmp_path)

        with patch(
            "clasi.status.inconsistency.detect_inconsistencies"
        ) as mock_detect:
            output = _run_status_inject(tmp_path, agent="team-lead")

        mock_detect.assert_not_called()
        parsed = _extract_yaml(output)
        assert parsed["inconsistencies"] == []


# ---------------------------------------------------------------------------
# Real sprint_id/ticket_id narrowing (fix 2)
# ---------------------------------------------------------------------------


class TestRealNarrowing:
    """narrow_status must actually receive real sprint_id/ticket_id —
    verified here by asserting the RETURNED DICT is smaller/scoped for a
    sprint-planner/programmer role than the team-lead's full view, not
    merely that narrow_status was called."""

    def test_programmer_view_scoped_to_single_sprint(self, tmp_path):
        _build_realistic_multi_sprint_fixture(tmp_path)

        team_lead_output = _run_status_inject(tmp_path, agent="team-lead")
        programmer_output = _run_status_inject(tmp_path, agent="programmer")

        team_lead_parsed = _extract_yaml(team_lead_output)
        programmer_parsed = _extract_yaml(programmer_output)

        assert programmer_parsed["agent"] == "programmer"
        # Programmer view must be scoped to (at most) one sprint.
        assert len(programmer_parsed["sprints"]) <= 1
        assert len(programmer_parsed["sprints"]) <= len(team_lead_parsed["sprints"])

    def test_programmer_view_ticket_details_scoped_to_single_ticket(self, tmp_path):
        _build_realistic_multi_sprint_fixture(tmp_path)

        output = _run_status_inject(tmp_path, agent="programmer")
        parsed = _extract_yaml(output)

        assert len(parsed["sprints"]) == 1
        details = parsed["sprints"][0].get("tickets", {}).get("details", [])
        # programmer narrowing keeps exactly the single matching ticket.
        assert len(details) == 1

    def test_programmer_view_smaller_than_team_lead_view(self, tmp_path):
        _build_realistic_multi_sprint_fixture(tmp_path)

        team_lead_output = _run_status_inject(tmp_path, agent="team-lead")
        programmer_output = _run_status_inject(tmp_path, agent="programmer")

        team_lead_parsed = _extract_yaml(team_lead_output)
        programmer_parsed = _extract_yaml(programmer_output)

        # The actual returned dict must be demonstrably smaller/scoped —
        # not just "narrow_status was called".
        assert len(str(programmer_parsed)) < len(str(team_lead_parsed))

    def test_sprint_planner_view_scoped_to_single_sprint(self, tmp_path):
        _build_realistic_multi_sprint_fixture(tmp_path)

        team_lead_output = _run_status_inject(tmp_path, agent="team-lead")
        planner_output = _run_status_inject(tmp_path, agent="sprint-planner")

        team_lead_parsed = _extract_yaml(team_lead_output)
        planner_parsed = _extract_yaml(planner_output)

        assert planner_parsed["agent"] == "sprint-planner"
        assert len(planner_parsed["sprints"]) == 1
        assert planner_parsed["sprints"][0]["id"] == "019"
        # Sprint-planner narrowing drops per-ticket details (summary only).
        assert "details" not in planner_parsed["sprints"][0].get("tickets", {})
        assert len(str(planner_parsed)) < len(str(team_lead_parsed))


# ---------------------------------------------------------------------------
# Missing imperative when sprint executing + zero in-progress tickets (fix 3)
# ---------------------------------------------------------------------------


class TestGateImperative:
    def test_imperative_present_when_zero_in_progress_tickets(self, tmp_path):
        _build_fixture_no_active_ticket(tmp_path)

        output = _run_status_inject(tmp_path, agent="team-lead")
        parsed = _extract_yaml(output)

        focus = parsed["notes"]["current_focus"]
        assert "gated" in focus.lower() or "in-progress" in focus.lower()
        assert "execute-ticket" in focus
        assert ".clasi/oop" in focus

    def test_imperative_absent_when_ticket_in_progress(self, tmp_path):
        _build_realistic_multi_sprint_fixture(tmp_path)

        output = _run_status_inject(tmp_path, agent="team-lead")
        parsed = _extract_yaml(output)

        focus = parsed["notes"]["current_focus"]
        assert "gated closed" not in focus

    def test_imperative_absent_when_no_sprint_executing(self, tmp_path):
        _write_fresh_config(tmp_path)
        # No sprint directories, no execution lock at all.

        output = _run_status_inject(tmp_path, agent="team-lead")
        assert output == "" or "gated closed" not in output

    def test_imperative_absent_when_oop_active(self, tmp_path):
        active_sid = _build_fixture_no_active_ticket(tmp_path)
        (tmp_path / ".clasi" / "oop").touch()

        output = _run_status_inject(tmp_path, agent="team-lead")
        # OOP bypass short-circuits handle_status_inject before the full
        # status block is built (the gate imperative never appears), but
        # it must NOT go silent: a minimal OOP status block is still
        # emitted (ticket 024-005 — an active bypass must stay visible).
        assert "gated closed" not in output
        assert output != ""
        assert "OOP active" in output


# ---------------------------------------------------------------------------
# Logged warning replacing the silent except Exception: return "" (fix 4)
# ---------------------------------------------------------------------------


class TestLoggedWarningOnFailure:
    def test_warning_logged_when_build_status_raises(self, tmp_path, caplog):
        _make_clasi_dir(tmp_path)

        with caplog.at_level(logging.WARNING, logger="clasi.hook_handlers"):
            with patch(
                "clasi.status.build_status", side_effect=RuntimeError("boom"),
            ):
                output = _run_status_inject(tmp_path, agent="team-lead")

        assert output == ""
        assert any(
            record.levelno >= logging.WARNING for record in caplog.records
        )

    def test_hook_still_exits_cleanly_when_build_status_raises(self, tmp_path):
        _make_clasi_dir(tmp_path)

        with patch(
            "clasi.status.build_status", side_effect=RuntimeError("boom"),
        ):
            old_cwd = os.getcwd()
            os.chdir(tmp_path)
            try:
                with pytest.raises(SystemExit) as exc:
                    handle_status_inject({})
                assert exc.value.code == 0
            finally:
                os.chdir(old_cwd)

    def test_no_warning_logged_on_healthy_build(self, tmp_path, caplog):
        _build_realistic_multi_sprint_fixture(tmp_path)

        with caplog.at_level(logging.WARNING, logger="clasi.hook_handlers"):
            _run_status_inject(tmp_path, agent="team-lead")

        assert not any(
            record.levelno >= logging.WARNING for record in caplog.records
        )


# ---------------------------------------------------------------------------
# Minimal status stub so tests don't need a real project on disk
# ---------------------------------------------------------------------------


def _minimal_status_dict() -> dict:
    return {
        "agent": "team-lead",
        "computed_at": "2026-01-01T00:00:00+00:00",
        "project": {"state": "active"},
        "sprints": [],
        "issues": [],
        "inconsistencies": [],
        "notes": {"current_focus": ""},
    }


# ---------------------------------------------------------------------------
# handle_status_inject — OOP bypass
# ---------------------------------------------------------------------------


class TestStatusInjectOopBypass:
    """handle_status_inject exits 0 with a minimal, non-empty OOP status
    block when .clasi/oop exists — never silent (ticket 024-005)."""

    def test_oop_bypass_minimal_block(self, tmp_path):
        clasi_dir = _make_clasi_dir(tmp_path)
        (clasi_dir / "oop").touch()

        with _chdir(tmp_path):
            output, code = _capture_stdout(handle_status_inject, {})

        assert code == 0
        assert output != ""
        assert "## CLASI status" in output
        assert "OOP active (override file .clasi/oop)" in output

    def test_oop_bypass_does_not_call_build_status(self, tmp_path):
        clasi_dir = _make_clasi_dir(tmp_path)
        (clasi_dir / "oop").touch()

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block") as mock_build:
                try:
                    handle_status_inject({})
                except SystemExit:
                    pass

        mock_build.assert_not_called()


# ---------------------------------------------------------------------------
# handle_status_inject — non-CLASI project (no .clasi/ dir)
# ---------------------------------------------------------------------------


class TestStatusInjectNonClasi:
    """handle_status_inject exits 0 with no output when .clasi/ does not exist."""

    def test_no_clasi_dir_no_output(self, tmp_path):
        # tmp_path has no .clasi/ subdirectory
        with _chdir(tmp_path):
            output, code = _capture_stdout(handle_status_inject, {})

        assert code == 0
        assert output == ""

    def test_no_clasi_dir_does_not_call_build_status(self, tmp_path):
        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block") as mock_build:
                try:
                    handle_status_inject({})
                except SystemExit:
                    pass

        mock_build.assert_not_called()


# ---------------------------------------------------------------------------
# handle_status_inject — valid CLASI project
# ---------------------------------------------------------------------------


class TestStatusInjectValid:
    """handle_status_inject emits a ## CLASI status YAML block on a valid project."""

    def test_output_contains_heading(self, tmp_path):
        _make_clasi_dir(tmp_path)
        with _chdir(tmp_path):
            with patch(
                "clasi.hook_handlers._build_status_block",
                return_value="## CLASI status\n\n```yaml\nagent: team-lead\n```\n",
            ):
                output, code = _capture_stdout(handle_status_inject, {})

        assert code == 0
        assert "## CLASI status" in output

    def test_output_contains_yaml_fence(self, tmp_path):
        _make_clasi_dir(tmp_path)
        with _chdir(tmp_path):
            with patch(
                "clasi.hook_handlers._build_status_block",
                return_value="## CLASI status\n\n```yaml\nagent: team-lead\n```\n",
            ):
                output, code = _capture_stdout(handle_status_inject, {})

        assert "```yaml" in output
        assert "agent: team-lead" in output

    def test_uses_clasi_agent_name_env(self, tmp_path):
        _make_clasi_dir(tmp_path)
        captured_agent = {}

        def fake_build(agent: str, skip_inconsistencies: bool = False) -> str:
            captured_agent["agent"] = agent
            captured_agent["skip_inconsistencies"] = skip_inconsistencies
            return f"## CLASI status\n\n```yaml\nagent: {agent}\n```\n"

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", side_effect=fake_build):
                with patch.dict(os.environ, {"CLASI_AGENT_NAME": "programmer"}):
                    _capture_stdout(handle_status_inject, {})

        assert captured_agent["agent"] == "programmer"

    def test_defaults_to_team_lead_when_no_env(self, tmp_path):
        _make_clasi_dir(tmp_path)
        captured_agent = {}

        def fake_build(agent: str, skip_inconsistencies: bool = False) -> str:
            captured_agent["agent"] = agent
            captured_agent["skip_inconsistencies"] = skip_inconsistencies
            return f"## CLASI status\n\n```yaml\nagent: {agent}\n```\n"

        env_without_agent = {k: v for k, v in os.environ.items() if k != "CLASI_AGENT_NAME"}
        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", side_effect=fake_build):
                with patch.dict(os.environ, env_without_agent, clear=True):
                    _capture_stdout(handle_status_inject, {})

        assert captured_agent["agent"] == "team-lead"

    def test_passes_skip_inconsistencies_true(self, tmp_path):
        """status-inject is the hot per-prompt path — it must opt out of
        the ~400ms detect_inconsistencies pass (sprint 026 / ticket 003)."""
        _make_clasi_dir(tmp_path)
        captured = {}

        def fake_build(agent: str, skip_inconsistencies: bool = False) -> str:
            captured["skip_inconsistencies"] = skip_inconsistencies
            return "## CLASI status\n\n```yaml\nagent: team-lead\n```\n"

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", side_effect=fake_build):
                _capture_stdout(handle_status_inject, {})

        assert captured["skip_inconsistencies"] is True

    def test_empty_block_no_output(self, tmp_path):
        """If _build_status_block returns empty string, no output is produced."""
        _make_clasi_dir(tmp_path)
        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", return_value=""):
                output, code = _capture_stdout(handle_status_inject, {})

        assert code == 0
        assert output == ""


# ---------------------------------------------------------------------------
# handle_subagent_start — status block prepended
# ---------------------------------------------------------------------------


class TestSubagentStartStatusBlock:
    """handle_subagent_start prepends a ## CLASI status block to stdout."""

    def _minimal_payload(self, agent_type: str = "programmer") -> dict:
        return {
            "agent_type": agent_type,
            "agent_id": "agent-test-001",
            "session_id": "sess-001",
        }

    def test_status_block_prepended_for_programmer(self, tmp_path):
        _make_clasi_dir(tmp_path)
        with _chdir(tmp_path):
            with patch(
                "clasi.hook_handlers._build_status_block",
                return_value="## CLASI status\n\n```yaml\nagent: programmer\n```\n",
            ):
                output, _code = _capture_stdout(
                    handle_subagent_start, self._minimal_payload("programmer")
                )

        assert "## CLASI status" in output

    def test_agent_type_maps_to_programmer_role(self, tmp_path):
        _make_clasi_dir(tmp_path)
        captured_agent = {}

        def fake_build(agent: str) -> str:
            captured_agent["agent"] = agent
            return f"## CLASI status\n\n```yaml\nagent: {agent}\n```\n"

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", side_effect=fake_build):
                _capture_stdout(
                    handle_subagent_start, self._minimal_payload("programmer")
                )

        assert captured_agent["agent"] == "programmer"

    def test_agent_type_maps_to_sprint_planner_role(self, tmp_path):
        _make_clasi_dir(tmp_path)
        captured_agent = {}

        def fake_build(agent: str) -> str:
            captured_agent["agent"] = agent
            return f"## CLASI status\n\n```yaml\nagent: {agent}\n```\n"

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", side_effect=fake_build):
                _capture_stdout(
                    handle_subagent_start, self._minimal_payload("sprint-planner")
                )

        assert captured_agent["agent"] == "sprint-planner"

    def test_unknown_agent_type_defaults_to_team_lead(self, tmp_path):
        _make_clasi_dir(tmp_path)
        captured_agent = {}

        def fake_build(agent: str) -> str:
            captured_agent["agent"] = agent
            return f"## CLASI status\n\n```yaml\nagent: {agent}\n```\n"

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", side_effect=fake_build):
                _capture_stdout(
                    handle_subagent_start, self._minimal_payload("unknown-agent")
                )

        assert captured_agent["agent"] == "team-lead"

    def test_does_not_pass_skip_inconsistencies_true(self, tmp_path):
        """Ticket 003 scopes the detect_inconsistencies removal to the
        status-inject (UserPromptSubmit) hook path only — subagent-start's
        status block must keep running it, unchanged."""
        _make_clasi_dir(tmp_path)
        captured = {}

        def fake_build(agent: str, skip_inconsistencies: bool = False) -> str:
            captured["skip_inconsistencies"] = skip_inconsistencies
            return f"## CLASI status\n\n```yaml\nagent: {agent}\n```\n"

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers._build_status_block", side_effect=fake_build):
                _capture_stdout(
                    handle_subagent_start, self._minimal_payload("programmer")
                )

        assert captured["skip_inconsistencies"] is False

    def test_oop_suppresses_status_block(self, tmp_path):
        clasi_dir = _make_clasi_dir(tmp_path)
        (clasi_dir / "oop").touch()

        with _chdir(tmp_path):
            with patch(
                "clasi.hook_handlers._build_status_block",
            ) as mock_build:
                _capture_stdout(
                    handle_subagent_start, self._minimal_payload("programmer")
                )

        mock_build.assert_not_called()


# ---------------------------------------------------------------------------
# Staleness warning prepended to the status block (ticket 020-002)
# ---------------------------------------------------------------------------


def _write_clasi_repo_skeleton(root: Path, declared_version: str) -> None:
    """Make *root* look like a CLASI source checkout with a declared
    pyproject.toml version that differs from the real running package's
    metadata_version — deterministically triggers the "dogfooding drift"
    staleness signal (clasi.staleness._is_clasi_source_repo + version
    mismatch), independent of the source_path check.
    """
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "clasi"\nversion = "{declared_version}"\n',
        encoding="utf-8",
    )
    src_clasi = root / "src" / "clasi"
    src_clasi.mkdir(parents=True, exist_ok=True)
    (src_clasi / "__init__.py").write_text('"""CLASI."""\n', encoding="utf-8")


class TestStatusInjectStalenessWarning:
    """The real, unmocked _build_status_block prepends a staleness warning
    when this repo IS the CLASI source repo and its declared pyproject.toml
    version doesn't match the running package's real metadata_version —
    this is the actual production surface (bare/uv-run `clasi hook
    status-inject`) where sprint 019's stale-build incident would have
    been visible on every turn, had this existed then.
    """

    def test_stale_dogfooding_repo_shows_warning_naming_both_versions(self, tmp_path):
        import importlib.metadata

        _make_clasi_dir(tmp_path)
        real_version = importlib.metadata.version("clasi")
        newer_fake_version = "0.99990101.1"
        assert newer_fake_version != real_version
        _write_clasi_repo_skeleton(tmp_path, newer_fake_version)

        output = _run_status_inject(tmp_path, agent="team-lead")

        assert "STALE CLASI INSTALL DETECTED" in output
        assert newer_fake_version in output
        assert real_version in output

    def test_matching_dogfooding_repo_shows_no_warning(self, tmp_path):
        """Revert-check counterpart: repo version AND editable source path
        both genuinely match the real running package -> no staleness
        warning is prepended. src/clasi/__init__.py is a real symlink to
        the actual running module's backing file — the only way to
        construct a true match for the source_path signal without faking
        clasi.staleness's internals."""
        import importlib.metadata
        import importlib.util

        _make_clasi_dir(tmp_path)
        real_version = importlib.metadata.version("clasi")

        (tmp_path / "pyproject.toml").write_text(
            f'[project]\nname = "clasi"\nversion = "{real_version}"\n',
            encoding="utf-8",
        )
        src_clasi = tmp_path / "src" / "clasi"
        src_clasi.mkdir(parents=True, exist_ok=True)
        spec = importlib.util.find_spec("clasi")
        real_init = Path(spec.origin).resolve()
        (src_clasi / "__init__.py").symlink_to(real_init)

        output = _run_status_inject(tmp_path, agent="team-lead")

        assert "STALE CLASI INSTALL DETECTED" not in output

    def test_non_dogfooding_project_shows_no_warning(self, tmp_path):
        """An ordinary CLASI-managed project (no pyproject.toml naming
        clasi) never shows this warning, regardless of the running
        package's real version — consumer projects are out of scope for
        the dogfooding signal."""
        _build_realistic_multi_sprint_fixture(tmp_path)

        output = _run_status_inject(tmp_path, agent="team-lead")

        assert "STALE CLASI INSTALL DETECTED" not in output

    def test_warning_present_even_when_rest_of_status_build_fails(self, tmp_path):
        """The staleness check runs and is reported independently of
        build_status — a broken status build must not swallow the
        staleness warning, since that would defeat the whole point of
        surfacing it on every turn."""
        import importlib.metadata

        _make_clasi_dir(tmp_path)
        real_version = importlib.metadata.version("clasi")
        newer_fake_version = "0.99990101.1"
        _write_clasi_repo_skeleton(tmp_path, newer_fake_version)

        with patch("clasi.status.build_status", side_effect=RuntimeError("boom")):
            output = _run_status_inject(tmp_path, agent="team-lead")

        assert "STALE CLASI INSTALL DETECTED" in output
        assert newer_fake_version in output


# ---------------------------------------------------------------------------
# handle_hook dispatcher recognizes status-inject
# ---------------------------------------------------------------------------


class TestHookDispatch:
    """Verify handle_hook routes 'status-inject' correctly."""

    def test_status_inject_routed(self, tmp_path):
        from clasi.hook_handlers import handle_hook

        with _chdir(tmp_path):
            with patch("clasi.hook_handlers.handle_status_inject") as mock_handler:
                with patch("clasi.hook_handlers.read_payload", return_value={}):
                    mock_handler.side_effect = SystemExit(0)
                    try:
                        handle_hook("status-inject")
                    except SystemExit:
                        pass

        mock_handler.assert_called_once_with({})
