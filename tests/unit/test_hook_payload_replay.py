"""Replay tests for tests/fixtures/hook_payloads/*.json (ticket 029-008).

Every existing test in test_hook_handlers.py builds its payloads by hand
— structurally unable to catch a harness-side payload-shape change, which
is exactly the direction the real 876-event fail-open incident came from
(the nested-then-flat file_path rule drifted between two hand-rolled
implementations, and nothing caught it because nothing replayed a real
payload). This module replays VERBATIM captured payloads through
``read_payload`` -> the relevant handler and asserts the same allow/deny
decision, so a future harness-side shape change fails a test instead of
drifting silently a second time.

Fixture provenance (see each fixture's corresponding entry in
``_FIXTURES`` below, and the ticket's own final report for the full
methodology):

- ``role-guard-deny-stale-guard.json``: a genuine, organically-captured
  denial from THIS repository's own ``.clasi/log/denied/`` corpus
  (sprint 028's deny-payload capture) — a real Claude-Code-dispatched
  Edit call blocked by role-guard's staleness fail-closed gate during
  this ticket's own sprint session. Copied verbatim (only a trailing
  newline differs).
- ``role-guard-deny-blk-write.json`` / ``mcp-guard-deny-tier0.json``:
  captured via a temporary, sandboxed live invocation of the real
  ``clasi hook <event>`` CLI (tier 0, a source-shaped path / an
  MCP artifact-creation tool call) against a throwaway scratch project
  — not this repository — with the exact stdin bytes fed to that
  process also written to the fixture file via a shell-level ``tee``.
  This is the "temporary tee, per the issue's own suggested approach"
  the ticket names as the fallback when the organic corpus (one file at
  the time this ticket started) is too thin to reach two deny fixtures
  on its own.
- ``role-guard-allow-tier2.json``, ``mcp-guard-allow-tier1.json``,
  ``subagent-start-allow.json``, ``subagent-stop-allow.json``,
  ``plan-to-issue-no-file.json``: allow-path fixtures, captured the same
  way (live CLI invocation against the scratch project, shell-tee'd to
  the fixture file) — sprint 028's automatic deny-payload dump only
  fires for ``exit_code == 2``, so there is no equivalent built-in
  capture mechanism for the allow path.
- ``role-guard-allow-tier0-sprints.json`` (ticket 031-003): captured the
  same live-CLI-against-a-scratch-project way, tier 0 (env var unset), a
  ``Write`` to a ``clasi/sprints/**`` path. Proves the stakeholder-decided
  policy change (2026-08-19) that removed the tier-0 blk-sprint block —
  team-lead may now write sprint artifacts directly; only ``create_ticket``
  stays MCP-gated (see ``TestMcpGuardMatcherScope`` in
  ``test_hook_handlers.py`` for that half of the same policy).
- ``role-guard-deny-no-ticket.json`` / ``role-guard-allow-ticket-done-edit.json``
  (ticket 029-010): captured the same tee-against-a-scratch-project way,
  tier 2, against a scratch project with a real execution lock held for
  sprint "029" (``clasi.state_db.init_db`` / ``register_sprint`` /
  ``acquire_lock``) and zero tickets ``status: in-progress`` anywhere in
  that sprint. The deny fixture's ``file_path`` targets an ordinary
  source path (``src/app/other.py``) — the ticket-state gate's
  ``no-ticket`` case, proving the gate still fails closed for the write
  it exists to police. The allow fixture's ``file_path`` targets a
  ticket file already relocated to that sprint's own
  ``tickets/done/001-done-ticket.md`` — the reported bug this ticket
  fixes: a completed ticket's own file must be editable (e.g. to record
  after-the-fact evidence) even though no ticket anywhere in the sprint
  is in-progress. Both captures were verified against the real,
  unmodified ``clasi hook role-guard`` entrypoint before being copied
  into the corpus (exit 2 / ``gate=ticket-state:no-ticket`` and exit 0 /
  ``gate=ticket-state:tickets-exempt`` respectively, per the scratch
  project's own ``.clasi/log/hooks.log``). Unlike every other fixture
  above, replaying these two also requires reconstructing the captured
  project's DB-backed lock/tickets state (not just its ``file_path``) —
  see ``_setup_ticket_gate_lock_state`` and the ``pre_setup`` field on
  ``_Fixture`` below.

No temporary code was added to ``hook_handlers.py`` itself to capture
these — the tee happened entirely at the shell level, piping into the
real, unmodified ``clasi hook`` entrypoint, so there is nothing to
revert in the source module for this capture step.

Portability note: role-guard's decision depends on the captured
file_path *relative to the project root it was captured under* — a
raw byte-for-byte absolute path from a scratch capture directory (or
from this repo's own checkout, for the one organic fixture) would not
be "under" a fresh pytest ``tmp_path`` on replay, and would misresolve
as an ("outside-root", always-allow) path instead of reproducing the
original decision. Fixtures whose file_path needs this are rewritten,
at replay time only, to the same relative suffix rooted under the
test's own ``tmp_path`` — the fixture FILE ON DISK stays exactly as
captured; only the in-memory payload used for a given replay run is
re-rooted. Fixtures with no absolute file_path (mcp-guard, subagent
events, plan-to-issue) need no rewriting at all.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import pytest

from clasi.hook_handlers import handle_hook
from clasi.state_db import acquire_lock, init_db, register_sprint

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "hook_payloads"

_FRESH_LAYOUT_CONFIG = "process: se\n"


def _write_fresh_config(root: Path) -> None:
    clasi_dir = root / ".clasi"
    clasi_dir.mkdir(parents=True, exist_ok=True)
    (clasi_dir / "config.yaml").write_text(_FRESH_LAYOUT_CONFIG, encoding="utf-8")


def _setup_ticket_gate_lock_state(tmp_path: Path) -> None:
    """Reconstruct the DB-backed execution lock + tickets/done/ state the
    two ticket-state-gate fixtures (ticket 029-010) were captured
    against: sprint "029"'s lock held, zero tickets status: in-progress
    anywhere in the sprint, and one ticket already relocated to
    ``clasi/sprints/029-fixture-sprint/tickets/done/001-done-ticket.md``.

    Every other fixture's replay only needs ``_write_fresh_config`` plus
    (for some) a rewritten ``file_path`` — see the module docstring.
    These two are the first fixtures whose captured decision also
    depended on project DB/filesystem state beyond the payload itself,
    so replay must reconstruct that state explicitly rather than relying
    on ``_write_fresh_config`` alone.
    """
    db_path = str(tmp_path / ".clasi" / ".clasi.db")
    init_db(db_path)
    register_sprint(db_path, "029", "sprint-029-fixture")
    acquire_lock(db_path, "029")

    done_dir = tmp_path / "clasi" / "sprints" / "029-fixture-sprint" / "tickets" / "done"
    done_dir.mkdir(parents=True, exist_ok=True)
    (done_dir / "001-done-ticket.md").write_text(
        "---\nid: '001'\ntitle: Done ticket\nstatus: done\n---\n# Done ticket\n",
        encoding="utf-8",
    )


def _last_hooks_log_line(tmp_path: Path, event_type: str) -> str:
    hooks_log = tmp_path / ".clasi" / "log" / "hooks.log"
    lines = hooks_log.read_text(encoding="utf-8").splitlines()
    matching = [ln for ln in lines if event_type in ln]
    assert matching, f"no {event_type} log line found: {lines}"
    return matching[-1]


@dataclass
class _Fixture:
    filename: str
    event: str
    tier_env: Optional[str]  # None = leave CLASI_AGENT_TIER unset
    expected_exit: int
    expected_reason: Optional[str] = None  # None = don't assert the reason
    path_rewrite_suffix: Optional[str] = None  # re-root file_path under tmp_path
    # hooks.log's event_type column uses a short reason-code-style name
    # for the two subagent events ("sub-start"/"sub-stop") distinct from
    # the CLI dispatch name ("subagent-start"/"subagent-stop") used
    # everywhere else in this table — see handle_subagent_start/stop's
    # own _exit_hook calls. None (the default) means the log event_type
    # is identical to `event`.
    log_event: Optional[str] = None
    # Called with tmp_path, after _write_fresh_config and before the
    # replay itself, for a fixture whose captured decision depended on
    # DB/filesystem project state beyond file_path (ticket 029-010's two
    # ticket-state-gate fixtures — see _setup_ticket_gate_lock_state).
    # None (the default, every pre-existing fixture) means no extra
    # setup is needed.
    pre_setup: Optional[Callable[[Path], None]] = None


# One row per captured fixture. expected_reason is asserted only where the
# decision is fully reproducible from a fresh, isolated tmp_path project —
# see role-guard-deny-stale-guard.json's row for the one case where it
# deliberately is not (that fixture's original "stale-guard" reason is
# specific to THIS repo's own identity, which a synthetic tmp_path project
# is never recognized as; role-guard still fails CLOSED there, just via
# the ordinary default-block path instead — exit code 2 either way, which
# is the portable, meaningful invariant this replay corpus exists to
# pin down).
_FIXTURES = [
    _Fixture(
        "role-guard-deny-stale-guard.json", "role-guard", "",
        expected_exit=2, path_rewrite_suffix="src/clasi/staleness.py",
    ),
    _Fixture(
        "role-guard-deny-blk-write.json", "role-guard", "0",
        expected_exit=2, expected_reason="blk-write",
        path_rewrite_suffix="src/app/main.py",
    ),
    _Fixture(
        "role-guard-allow-tier2.json", "role-guard", "2",
        expected_exit=0, expected_reason="tier-2",
        path_rewrite_suffix="src/app/new_module.py",
    ),
    _Fixture(
        # Ticket 031-003 (stakeholder decision, 2026-08-19): tier 0
        # (team-lead) may now write directly under sprints_dir — the
        # tier-0 blk-sprint block was removed (create_ticket stays
        # gated separately, via mcp-guard). Captured live against a
        # throwaway scratch project the same tee-against-the-real-CLI
        # way as the sibling role-guard fixtures above, tier unset
        # (functionally tier 0).
        "role-guard-allow-tier0-sprints.json", "role-guard", "0",
        expected_exit=0, expected_reason="tier-1",
        path_rewrite_suffix="clasi/sprints/013-x/sprint.md",
    ),
    _Fixture(
        # Ticket 029-010, AC2/AC3: tier 2, execution lock held, zero
        # tickets in-progress, file_path an ordinary source path -> the
        # ticket-state gate must still fail closed for the write it
        # exists to police, even after adding the tickets/ exemption
        # below. See _setup_ticket_gate_lock_state.
        "role-guard-deny-no-ticket.json", "role-guard", "2",
        expected_exit=2, expected_reason="no-ticket",
        path_rewrite_suffix="src/app/other.py",
        pre_setup=_setup_ticket_gate_lock_state,
    ),
    _Fixture(
        # Ticket 029-010, AC1/AC3: same lock-held/zero-in-progress state
        # as the deny fixture above, but file_path targets a ticket
        # already relocated to tickets/done/ — the reported bug. Must
        # re-root under the SAME "029-fixture-sprint" tickets/done/ tree
        # _setup_ticket_gate_lock_state creates, or the gate's tickets/
        # prefix match would never fire.
        "role-guard-allow-ticket-done-edit.json", "role-guard", "2",
        expected_exit=0, expected_reason="tier-2",
        path_rewrite_suffix="clasi/sprints/029-fixture-sprint/tickets/done/001-done-ticket.md",
        pre_setup=_setup_ticket_gate_lock_state,
    ),
    _Fixture(
        "mcp-guard-deny-tier0.json", "mcp-guard", "0",
        expected_exit=2, expected_reason="blk-mcp",
    ),
    _Fixture(
        "mcp-guard-allow-tier1.json", "mcp-guard", "1",
        expected_exit=0, expected_reason="tier-allowed",
    ),
    _Fixture(
        "subagent-start-allow.json", "subagent-start", None,
        expected_exit=0, expected_reason="logged", log_event="sub-start",
    ),
    _Fixture(
        # Replayed standalone (no matching subagent-start run first in
        # this same tmp_path/DB), so the DB lookup that would let this
        # resolve to "logged" finds no record — "no-log-file" is the
        # correct, still-non-blocking outcome for that case. subagent-stop
        # is pure logging, never a guard; exit 0 either way is the
        # portable invariant, matching every other fixture's own
        # replay-time environment divergence from its original capture.
        "subagent-stop-allow.json", "subagent-stop", None,
        expected_exit=0, expected_reason="no-log-file", log_event="sub-stop",
    ),
    _Fixture(
        "plan-to-issue-no-file.json", "plan-to-issue", None,
        expected_exit=0, expected_reason="no-file",
    ),
]

# AC: "at least two deny-path fixtures" / "covers every hook event type
# with at least one captured fixture" — asserted directly against the
# table above so a future edit that thins the corpus back out fails a
# test immediately, not silently.
_DENY_FIXTURES = [f for f in _FIXTURES if f.expected_exit == 2]
_EVENT_TYPES = {f.event for f in _FIXTURES}


class TestReplayCorpusComposition:
    def test_at_least_two_deny_fixtures(self):
        assert len(_DENY_FIXTURES) >= 2, _DENY_FIXTURES

    def test_covers_every_migrated_handler_event_type(self):
        assert _EVENT_TYPES == {
            "role-guard", "mcp-guard", "subagent-start",
            "subagent-stop", "plan-to-issue",
        }

    def test_every_fixture_file_referenced_by_the_table_exists(self):
        for fx in _FIXTURES:
            assert (_FIXTURES_DIR / fx.filename).exists(), fx.filename

    def test_no_orphan_fixture_files_missing_from_the_table(self):
        """Every *.json under the corpus directory is exercised by some
        row above — a fixture added without a corresponding table entry
        would otherwise sit there untested indefinitely."""
        on_disk = {p.name for p in _FIXTURES_DIR.glob("*.json")}
        in_table = {fx.filename for fx in _FIXTURES}
        assert on_disk == in_table


@pytest.mark.parametrize("fx", _FIXTURES, ids=lambda fx: fx.filename)
def test_replay_fixture_reproduces_decision(fx: _Fixture, tmp_path: Path, monkeypatch):
    """Load one verbatim captured fixture, replay it through
    read_payload() -> handle_hook(event) exactly as production does, and
    assert it reproduces the originally observed allow/deny decision."""
    _write_fresh_config(tmp_path)

    if fx.pre_setup is not None:
        fx.pre_setup(tmp_path)

    raw = (_FIXTURES_DIR / fx.filename).read_text(encoding="utf-8")
    payload = json.loads(raw)

    if fx.path_rewrite_suffix:
        tool_input = payload.get("tool_input")
        assert isinstance(tool_input, dict), fx.filename
        new_value = str(tmp_path / fx.path_rewrite_suffix)
        for key in ("file_path", "path", "new_path"):
            if key in tool_input:
                tool_input[key] = new_value

    if fx.tier_env is None:
        monkeypatch.delenv("CLASI_AGENT_TIER", raising=False)
    else:
        monkeypatch.setenv("CLASI_AGENT_TIER", fx.tier_env)

    monkeypatch.setattr("clasi.hook_handlers.read_payload", lambda: payload)

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with pytest.raises(SystemExit) as exc:
            handle_hook(fx.event)
    finally:
        os.chdir(old_cwd)

    assert exc.value.code == fx.expected_exit, (
        f"{fx.filename}: expected exit {fx.expected_exit}, got {exc.value.code}"
    )

    if fx.expected_reason is not None:
        line = _last_hooks_log_line(tmp_path, fx.log_event or fx.event)
        # hooks.log's reason column is fixed-width (12 chars, left
        # justified) — a substring check is enough to pin the reason
        # without coupling this test to the exact padding.
        assert f" {fx.expected_reason}" in line, (
            f"{fx.filename}: expected reason {fx.expected_reason!r} in line: {line}"
        )
