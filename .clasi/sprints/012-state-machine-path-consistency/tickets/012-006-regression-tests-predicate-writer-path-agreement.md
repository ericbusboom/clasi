---
id: "012-006"
title: Add regression tests confirming predicate/writer path agreement
status: open
use-cases: [SUC-006]
depends-on: ["012-002", "012-003"]
issue:
- gh-16-state-machine-predicates-read-artifact-paths-that-don-t-match-where.md
- gh-18-predicates-read-legacy-docs-clasi-bare-id-paths-while-writers-use.md
---

# 012-006: Add regression tests confirming predicate/writer path agreement

## Description

After tickets 001-003 fix the predicate/reader layer, we need a regression test
that creates sprint and ticket artifacts using the same naming conventions the
write tools use, then asserts that all the fixed predicates return True. This
catches any future drift between writers and readers.

This ticket also consolidates the existing unit test updates that were partially
specified in tickets 001-003 into a single integration-style test file, and
ensures the full predicate test suite consistently uses the named mock methods
(`overview_exists`, `sprint_artifact_exists`, `ticket_file_present`) throughout.

## Acceptance Criteria

- [ ] New file `tests/unit/test_state_machine/test_predicate_path_agreement.py` exists.
- [ ] The new test creates a real `.clasi/sprints/001-my-sprint/` directory with `sprint.md`, `usecases.md`, `architecture-update.md`, `close-report.md` in `tmp_path`.
- [ ] The new test creates `tickets/001-001-my-ticket.md` with correct frontmatter under that sprint.
- [ ] The new test creates `.clasi/design/overview.md`.
- [ ] Asserts `is_overview_present` returns True (via `ClasiStateReader`).
- [ ] Asserts `is_sprint_doc_present` returns True.
- [ ] Asserts `is_usecases_present` returns True (file is `usecases.md`, not `use-cases.md`).
- [ ] Asserts `is_architecture_present` returns True.
- [ ] Asserts `is_close_report_present` returns True.
- [ ] Asserts `is_ticket_file_present` returns True (active dir).
- [ ] Asserts `is_ticket_file_present` returns True when ticket moved to `tickets/done/`.
- [ ] `_mock_reader` in `test_predicates.py` has `overview_exists`, `sprint_artifact_exists`, and `ticket_file_present` as named defaults (False).
- [ ] `pytest tests/unit/` passes fully.

## Implementation Plan

### Approach

Create `test_predicate_path_agreement.py` as a self-contained integration test.
It uses real filesystem I/O (no mocking) via `tmp_path`, instantiates
`ClasiStateReader`, loads the predicates directly, and asserts results.

### Files to Create

**`tests/unit/test_state_machine/test_predicate_path_agreement.py`**:

```python
"""Integration tests: artifacts created by writers satisfy their own predicates.

These tests use real filesystem I/O (via tmp_path) to confirm that the naming
conventions used by the write tools (slugged dirs, usecases.md, etc.) are
exactly what the predicates check. Any future drift between writers and readers
will be caught here.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from clasi.project import Project
from clasi.status.reader import ClasiStateReader
from clasi.state_machine.context import ProjectContext, SprintContext, TicketContext
import clasi.state_machine.predicates.project
import clasi.state_machine.predicates.sprint
import clasi.state_machine.predicates.ticket


SPRINT_ID = "001"
TICKET_ID = "001-001"


@pytest.fixture()
def project(tmp_path: Path) -> Project:
    """A minimal CLASI project with real sprint and ticket artifacts."""
    # Git init (required by branch-related methods)
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"],
                   cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"],
                   cwd=tmp_path, check=True, capture_output=True)
    
    clasi_dir = tmp_path / ".clasi"
    clasi_dir.mkdir()
    
    # Design dir + overview
    design_dir = clasi_dir / "design"
    design_dir.mkdir()
    (design_dir / "overview.md").write_text("# Overview\n")
    
    # Slugged sprint directory
    sprint_dir = clasi_dir / "sprints" / f"{SPRINT_ID}-my-sprint"
    sprint_dir.mkdir(parents=True)
    sprint_fm = (
        f"---\nid: '{SPRINT_ID}'\ntitle: My Sprint\nstatus: open\n"
        f"branch: sprint/{SPRINT_ID}-my-sprint\n---\n# Sprint\n"
    )
    (sprint_dir / "sprint.md").write_text(sprint_fm)
    (sprint_dir / "usecases.md").write_text("# Use Cases\n")
    (sprint_dir / "architecture-update.md").write_text("# Architecture\n")
    (sprint_dir / "close-report.md").write_text("# Close Report\n")
    
    # Slugged ticket file with correct frontmatter
    tickets_dir = sprint_dir / "tickets"
    tickets_dir.mkdir()
    ticket_fm = (
        f"---\nid: '{TICKET_ID}'\ntitle: My Ticket\nstatus: open\n---\n# Ticket\n"
    )
    (tickets_dir / f"{TICKET_ID}-my-ticket.md").write_text(ticket_fm)
    
    return Project(tmp_path)


@pytest.fixture()
def reader(project: Project) -> ClasiStateReader:
    return ClasiStateReader(project)


def _proj_ctx(reader):
    return ProjectContext(reader=reader)


def _sprint_ctx(reader):
    proj = _proj_ctx(reader)
    return SprintContext(sprint_id=SPRINT_ID, reader=reader, project=proj)


def _ticket_ctx(reader):
    sprint = _sprint_ctx(reader)
    return TicketContext(
        ticket_id=TICKET_ID, sprint_id=SPRINT_ID, reader=reader, sprint=sprint
    )


class TestOverviewPredicatesWithRealPaths:
    def test_overview_present_true(self, reader):
        from clasi.state_machine.predicates.project import is_overview_present
        assert is_overview_present(_proj_ctx(reader)) is True

    def test_overview_absent_false(self, reader):
        from clasi.state_machine.predicates.project import is_overview_absent
        assert is_overview_absent(_proj_ctx(reader)) is False


class TestSprintArtifactPredicatesWithRealPaths:
    def test_sprint_doc_present(self, reader):
        from clasi.state_machine.predicates.sprint import is_sprint_doc_present
        assert is_sprint_doc_present(_sprint_ctx(reader)) is True

    def test_usecases_present(self, reader):
        from clasi.state_machine.predicates.sprint import is_usecases_present
        assert is_usecases_present(_sprint_ctx(reader)) is True

    def test_architecture_present(self, reader):
        from clasi.state_machine.predicates.sprint import is_architecture_present
        assert is_architecture_present(_sprint_ctx(reader)) is True

    def test_close_report_present(self, reader):
        from clasi.state_machine.predicates.sprint import is_close_report_present
        assert is_close_report_present(_sprint_ctx(reader)) is True


class TestTicketPredicateWithRealPaths:
    def test_ticket_file_present_active(self, reader):
        from clasi.state_machine.predicates.ticket import is_ticket_file_present
        assert is_ticket_file_present(_ticket_ctx(reader)) is True

    def test_ticket_file_present_in_done_dir(self, reader, project):
        """Ticket moved to done/ is still found by is_ticket_file_present."""
        from clasi.state_machine.predicates.ticket import is_ticket_file_present
        sprint_dir = project.sprints_dir / f"{SPRINT_ID}-my-sprint"
        tickets_dir = sprint_dir / "tickets"
        done_dir = tickets_dir / "done"
        done_dir.mkdir(exist_ok=True)
        src = tickets_dir / f"{TICKET_ID}-my-ticket.md"
        dst = done_dir / f"{TICKET_ID}-my-ticket.md"
        src.rename(dst)
        assert is_ticket_file_present(_ticket_ctx(reader)) is True
```

### Files to Modify

**`tests/unit/test_state_machine/test_predicates.py`** — update `_mock_reader` defaults
(this consolidates changes from tickets 001, 002, 003):
```python
def _mock_reader(**kwargs) -> MagicMock:
    reader = MagicMock()
    # ... existing defaults ...
    reader.overview_exists.return_value = False          # NEW (ticket 001)
    reader.sprint_artifact_exists.return_value = False   # NEW (ticket 002)
    reader.ticket_file_present.return_value = False      # NEW (ticket 003)
    # Apply overrides
    for attr, val in kwargs.items():
        getattr(reader, attr).return_value = val
    return reader
```

### Testing Plan

The test file itself is the testing plan. Run:
```bash
pytest tests/unit/test_state_machine/test_predicate_path_agreement.py -v
pytest tests/unit/ -v
```
All should pass green.

### Documentation Updates

None beyond the new test file and the `_mock_reader` updates.
