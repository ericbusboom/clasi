"""Unit tests for clasi.state_machine.loader.

Covers round-trip loading of all three machines, error cases (missing
name, invalid YAML, missing required keys), and structural invariants
(state counts, transition counts, specific state and predicate presence).
"""

from __future__ import annotations

import textwrap
from unittest.mock import MagicMock, patch

import pytest
import yaml

import clasi.state_machine.loader as loader_module
from clasi.state_machine.loader import load_machine
from clasi.state_machine.models import Machine, MachineSyntaxError


# ---------------------------------------------------------------------------
# Cache isolation (sprint 026 / ticket 003: load_machine is now
# functools.lru_cache'd, process-lifetime). Tests in this module patch
# importlib.resources.as_file to inject alternate YAML text for the SAME
# machine names ("project") that other tests in this module load for
# real — without clearing the cache first, a monkeypatched test would
# silently get back the real, already-cached Machine instead of parsing
# its patched (often intentionally invalid) text. Per this sprint's
# state_machine-DESIGN.md overlay note, tests that need a fresh parse
# must clear the cache explicitly rather than relying on caching being
# disabled — this autouse fixture does that before AND after every test
# in this module so no state leaks in either direction.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_load_machine_cache():
    load_machine.cache_clear()
    yield
    load_machine.cache_clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_yaml_text(monkeypatch, text: str):
    """Patch load_machine to read *text* instead of the real YAML file.

    Returns the original load_machine but intercepts the file-read step
    by patching importlib.resources so that the path.read_text() call
    returns *text*.
    """
    # We patch at the yaml.safe_load level for simplicity: replace the
    # entire file-read + parse path by patching importlib.resources.as_file.
    import contextlib
    import importlib.resources as _res
    from pathlib import Path
    import tempfile, os

    # Write text to a temp file and make as_file return its path.
    @contextlib.contextmanager
    def fake_as_file(resource):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(text)
            tmp_path = f.name
        try:
            yield Path(tmp_path)
        finally:
            os.unlink(tmp_path)

    monkeypatch.setattr(_res, "as_file", fake_as_file)


# ---------------------------------------------------------------------------
# Round-trip: project machine
# ---------------------------------------------------------------------------


class TestLoadProjectMachine:
    def test_returns_machine(self):
        m = load_machine("project")
        assert isinstance(m, Machine)

    def test_name(self):
        m = load_machine("project")
        assert m.name == "project"

    def test_context_type(self):
        m = load_machine("project")
        assert m.context_type == "ProjectContext"

    def test_initial_state(self):
        m = load_machine("project")
        assert m.initial == "uninitialized"

    def test_state_count(self):
        # project.yaml defines 3 states: uninitialized, planning, in-sprint
        m = load_machine("project")
        assert len(m.states) == 3

    def test_state_names(self):
        m = load_machine("project")
        assert set(m.states.keys()) == {"uninitialized", "planning", "in-sprint"}

    def test_uninitialized_invariants(self):
        m = load_machine("project")
        assert m.states["uninitialized"].invariants == ("is_overview_absent",)

    def test_planning_invariants(self):
        m = load_machine("project")
        assert "is_overview_present" in m.states["planning"].invariants
        assert "is_on_default_branch" in m.states["planning"].invariants
        assert "is_execution_lock_released" in m.states["planning"].invariants

    def test_in_sprint_invariants(self):
        m = load_machine("project")
        assert "is_on_sprint_branch" in m.states["in-sprint"].invariants
        assert "is_execution_lock_held" in m.states["in-sprint"].invariants
        assert "is_any_sprint_executing" in m.states["in-sprint"].invariants

    def test_initialize_transition(self):
        m = load_machine("project")
        t = m.states["uninitialized"].transitions["initialize"]
        assert t.to == "planning"
        assert t.conditions == ()
        assert t.action == "write_overview"

    def test_enter_sprint_transition(self):
        m = load_machine("project")
        t = m.states["planning"].transitions["enter-sprint"]
        assert t.to == "in-sprint"
        assert "is_any_sprint_ticketed" in t.conditions
        assert t.action == "enter_sprint_branch"

    def test_exit_sprint_transition(self):
        m = load_machine("project")
        t = m.states["in-sprint"].transitions["exit-sprint"]
        assert t.to == "planning"
        assert t.conditions == ()
        assert t.action == "return_to_default_branch"


# ---------------------------------------------------------------------------
# Round-trip: sprint machine
# ---------------------------------------------------------------------------


class TestLoadSprintMachine:
    def test_returns_machine(self):
        m = load_machine("sprint")
        assert isinstance(m, Machine)

    def test_name(self):
        m = load_machine("sprint")
        assert m.name == "sprint"

    def test_context_type(self):
        m = load_machine("sprint")
        assert m.context_type == "SprintContext"

    def test_initial_state(self):
        m = load_machine("sprint")
        assert m.initial == "open"

    def test_state_count(self):
        # sprint.yaml defines 7 states
        m = load_machine("sprint")
        assert len(m.states) == 7

    def test_state_names(self):
        m = load_machine("sprint")
        expected = {"open", "planned", "pre-flight", "ticketed", "executing", "review", "closed"}
        assert set(m.states.keys()) == expected

    def test_closed_has_no_transitions(self):
        m = load_machine("sprint")
        assert m.states["closed"].transitions == {}

    def test_ticketed_execute_transition(self):
        m = load_machine("sprint")
        t = m.states["ticketed"].transitions["execute"]
        assert t.to == "executing"
        assert "is_no_other_sprint_executing" in t.conditions
        assert t.action == "acquire_execution_lock"

    def test_executing_complete_transition(self):
        m = load_machine("sprint")
        t = m.states["executing"].transitions["complete"]
        assert t.to == "review"
        assert t.conditions == ()
        assert t.action == "enter_review"

    def test_review_close_transition(self):
        m = load_machine("sprint")
        t = m.states["review"].transitions["close"]
        assert t.to == "closed"
        assert t.action == "close_sprint"

    def test_executing_invariants(self):
        m = load_machine("sprint")
        invs = m.states["executing"].invariants
        assert "is_on_sprint_branch" in invs
        assert "is_execution_lock_held_by_this_sprint" in invs
        assert "is_at_least_one_ticket" in invs

    def test_ticketed_invariant_count(self):
        # ticketed has 4 invariants under the single-doc model
        # (is_architecture_present/is_usecases_present removed).
        m = load_machine("sprint")
        assert len(m.states["ticketed"].invariants) == 4


# ---------------------------------------------------------------------------
# Round-trip: ticket machine
# ---------------------------------------------------------------------------


class TestLoadTicketMachine:
    def test_returns_machine(self):
        m = load_machine("ticket")
        assert isinstance(m, Machine)

    def test_name(self):
        m = load_machine("ticket")
        assert m.name == "ticket"

    def test_context_type(self):
        m = load_machine("ticket")
        assert m.context_type == "TicketContext"

    def test_initial_state(self):
        m = load_machine("ticket")
        assert m.initial == "open"

    def test_state_count(self):
        # ticket.yaml defines 4 states: open, in-progress, exception, done
        m = load_machine("ticket")
        assert len(m.states) == 4

    def test_state_names(self):
        m = load_machine("ticket")
        assert set(m.states.keys()) == {"open", "in-progress", "exception", "done"}

    def test_open_start_transition(self):
        m = load_machine("ticket")
        t = m.states["open"].transitions["start"]
        assert t.to == "in-progress"
        assert "is_dependencies_done" in t.conditions
        assert t.action == "dispatch_programmer"

    def test_in_progress_finish_transition(self):
        m = load_machine("ticket")
        t = m.states["in-progress"].transitions["finish"]
        assert t.to == "done"
        assert "is_acceptance_criteria_met" in t.conditions
        # is_tests_passing was removed (030/002): its backing marker file
        # (.clasi/test-cache) has no writer, so the condition could never
        # be satisfied by anything real.
        assert "is_tests_passing" not in t.conditions
        assert t.action == "move_ticket_to_done"

    def test_in_progress_throw_transition(self):
        m = load_machine("ticket")
        t = m.states["in-progress"].transitions["throw"]
        assert t.to == "exception"
        assert "is_blocker_identified" in t.conditions
        assert t.action == "write_exception_block"

    def test_exception_recover_transition(self):
        m = load_machine("ticket")
        t = m.states["exception"].transitions["recover"]
        assert t.to == "in-progress"
        assert "is_blocker_resolved" in t.conditions
        assert t.action == "clear_exception_block"

    def test_done_reopen_transition(self):
        m = load_machine("ticket")
        t = m.states["done"].transitions["reopen"]
        assert t.to == "open"
        # is_reopen_requested was removed (030/002): no writer ever sets
        # it, so the transition's conditions are now empty.
        assert "is_reopen_requested" not in t.conditions
        assert t.conditions == ()
        assert t.action == "move_ticket_out_of_done"

    def test_open_invariants(self):
        m = load_machine("ticket")
        invs = m.states["open"].invariants
        assert "is_ticket_file_present" in invs
        assert "is_ticket_not_in_done_dir" in invs
        assert "is_no_exception_block" in invs

    def test_done_invariants(self):
        m = load_machine("ticket")
        invs = m.states["done"].invariants
        assert "is_ticket_file_present" in invs
        assert "is_ticket_in_done_dir" in invs
        assert "is_no_exception_block" in invs


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestMissingName:
    def test_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError) as exc_info:
            load_machine("nonexistent_machine_xyz")
        assert "nonexistent_machine_xyz" in str(exc_info.value)

    def test_error_message_is_clear(self):
        with pytest.raises(FileNotFoundError) as exc_info:
            load_machine("bogus")
        msg = str(exc_info.value)
        assert "bogus" in msg
        assert "state-machines" in msg or "state machine" in msg.lower()


class TestInvalidYAML:
    def test_raises_machine_syntax_error(self, monkeypatch):
        bad_yaml = "machine: test\n  bad indentation:\nfoo: [unclosed"
        _patch_yaml_text(monkeypatch, bad_yaml)
        with pytest.raises(MachineSyntaxError) as exc_info:
            load_machine("project")
        assert "syntax" in str(exc_info.value).lower() or "YAML" in str(exc_info.value)

    def test_wraps_yaml_error(self, monkeypatch):
        bad_yaml = ": invalid: yaml: : :"
        _patch_yaml_text(monkeypatch, bad_yaml)
        with pytest.raises(MachineSyntaxError) as exc_info:
            load_machine("project")
        # Must wrap the original error (chained).
        assert exc_info.value.__cause__ is not None or "YAML" in str(exc_info.value)


class TestMissingRequiredKeys:
    def test_missing_machine_key(self, monkeypatch):
        yaml_without_machine = textwrap.dedent("""\
            context: ProjectContext
            initial: open
            states:
              open:
                description: test
                invariants: []
                transitions: {}
        """)
        _patch_yaml_text(monkeypatch, yaml_without_machine)
        with pytest.raises(MachineSyntaxError) as exc_info:
            load_machine("project")
        assert "'machine'" in str(exc_info.value) or "machine" in str(exc_info.value)

    def test_missing_states_key(self, monkeypatch):
        yaml_without_states = textwrap.dedent("""\
            machine: project
            context: ProjectContext
            initial: open
        """)
        _patch_yaml_text(monkeypatch, yaml_without_states)
        with pytest.raises(MachineSyntaxError) as exc_info:
            load_machine("project")
        assert "'states'" in str(exc_info.value) or "states" in str(exc_info.value)

    def test_missing_context_key(self, monkeypatch):
        yaml_without_context = textwrap.dedent("""\
            machine: project
            initial: open
            states:
              open:
                description: test
                invariants: []
                transitions: {}
        """)
        _patch_yaml_text(monkeypatch, yaml_without_context)
        with pytest.raises(MachineSyntaxError) as exc_info:
            load_machine("project")
        assert "'context'" in str(exc_info.value) or "context" in str(exc_info.value)

    def test_missing_initial_key(self, monkeypatch):
        yaml_without_initial = textwrap.dedent("""\
            machine: project
            context: ProjectContext
            states:
              open:
                description: test
                invariants: []
                transitions: {}
        """)
        _patch_yaml_text(monkeypatch, yaml_without_initial)
        with pytest.raises(MachineSyntaxError) as exc_info:
            load_machine("project")
        assert "'initial'" in str(exc_info.value) or "initial" in str(exc_info.value)

    def test_transition_missing_to_key(self, monkeypatch):
        yaml_bad_transition = textwrap.dedent("""\
            machine: project
            context: ProjectContext
            initial: open
            states:
              open:
                description: test
                invariants: []
                transitions:
                  go:
                    conditions: []
                    action: do_something
        """)
        _patch_yaml_text(monkeypatch, yaml_bad_transition)
        with pytest.raises(MachineSyntaxError) as exc_info:
            load_machine("project")
        assert "'to'" in str(exc_info.value) or "to" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Consistency checks across all three machines
# ---------------------------------------------------------------------------


class TestAllMachinesConsistency:
    @pytest.mark.parametrize("name", ["project", "sprint", "ticket"])
    def test_all_machines_load(self, name):
        m = load_machine(name)
        assert isinstance(m, Machine)
        assert m.name == name

    @pytest.mark.parametrize("name", ["project", "sprint", "ticket"])
    def test_initial_state_exists_in_states(self, name):
        m = load_machine(name)
        assert m.initial in m.states, (
            f"Machine {name!r}: initial state {m.initial!r} not in states"
        )

    @pytest.mark.parametrize("name", ["project", "sprint", "ticket"])
    def test_all_transition_targets_exist(self, name):
        m = load_machine(name)
        for state_name, state in m.states.items():
            for t_name, transition in state.transitions.items():
                assert transition.to in m.states, (
                    f"Machine {name!r}: transition {t_name!r} in state {state_name!r} "
                    f"targets unknown state {transition.to!r}"
                )

    @pytest.mark.parametrize("name", ["project", "sprint", "ticket"])
    def test_all_states_have_descriptions(self, name):
        m = load_machine(name)
        for state_name, state in m.states.items():
            assert state.description, (
                f"Machine {name!r}: state {state_name!r} has empty description"
            )


# ---------------------------------------------------------------------------
# Process-lifetime caching (sprint 026 / ticket 003)
# ---------------------------------------------------------------------------


class TestLoadMachineCaching:
    """``load_machine`` is wrapped with ``functools.lru_cache(maxsize=None)``
    — repeated calls for the same name return the identical cached
    ``Machine`` object and parse the underlying YAML exactly once per
    distinct name, not once per call."""

    def test_repeated_calls_same_name_return_identical_object(self):
        m1 = load_machine("project")
        m2 = load_machine("project")
        assert m1 is m2

    def test_yaml_parsed_once_per_name_across_repeated_calls(self, monkeypatch):
        real_safe_load = yaml.safe_load
        calls: list[str] = []

        def counting_safe_load(text):
            calls.append(text)
            return real_safe_load(text)

        monkeypatch.setattr(loader_module.yaml, "safe_load", counting_safe_load)

        for _ in range(5):
            load_machine("project")
        for _ in range(5):
            load_machine("sprint")
        for _ in range(5):
            load_machine("ticket")

        # 3 distinct machine names x 5 calls each = 15 total load_machine()
        # calls; without caching that's 15 YAML parses. With lru_cache it
        # collapses to exactly one parse per distinct name.
        assert len(calls) == 3

    def test_cache_clear_forces_a_fresh_parse(self, monkeypatch):
        real_safe_load = yaml.safe_load
        calls: list[str] = []

        def counting_safe_load(text):
            calls.append(text)
            return real_safe_load(text)

        monkeypatch.setattr(loader_module.yaml, "safe_load", counting_safe_load)

        load_machine("project")
        load_machine("project")
        assert len(calls) == 1

        load_machine.cache_clear()
        load_machine("project")
        assert len(calls) == 2

    def test_failed_parse_is_not_cached(self, monkeypatch):
        """A name that raises must not poison the cache — the next call
        (e.g. after the underlying condition is fixed) tries again rather
        than replaying the failure or a stale success."""
        bad_yaml = "machine: test\n  bad indentation:\nfoo: [unclosed"
        _patch_yaml_text(monkeypatch, bad_yaml)

        with pytest.raises(MachineSyntaxError):
            load_machine("project")
        with pytest.raises(MachineSyntaxError):
            load_machine("project")
