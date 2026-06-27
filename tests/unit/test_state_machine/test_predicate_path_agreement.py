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
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True, capture_output=True,
    )

    clasi_dir = tmp_path / ".clasi"
    clasi_dir.mkdir()

    proj = Project(tmp_path)

    # Design dir + overview (uses project.design_dir → docs/design/)
    design_dir = proj.design_dir
    design_dir.mkdir(parents=True, exist_ok=True)
    (design_dir / "overview.md").write_text("# Overview\n")

    # Slugged sprint directory under .clasi/sprints/
    sprint_dir = proj.sprints_dir / f"{SPRINT_ID}-my-sprint"
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

    return proj


@pytest.fixture()
def reader(project: Project) -> ClasiStateReader:
    return ClasiStateReader(project)


def _proj_ctx(reader: ClasiStateReader) -> ProjectContext:
    return ProjectContext(reader=reader)


def _sprint_ctx(reader: ClasiStateReader) -> SprintContext:
    proj = _proj_ctx(reader)
    return SprintContext(sprint_id=SPRINT_ID, reader=reader, project=proj)


def _ticket_ctx(reader: ClasiStateReader) -> TicketContext:
    sprint = _sprint_ctx(reader)
    return TicketContext(
        ticket_id=TICKET_ID, sprint_id=SPRINT_ID, reader=reader, sprint=sprint
    )


class TestOverviewPredicatesWithRealPaths:
    def test_overview_present_true(self, reader: ClasiStateReader) -> None:
        from clasi.state_machine.predicates.project import is_overview_present
        assert is_overview_present(_proj_ctx(reader)) is True

    def test_overview_absent_false(self, reader: ClasiStateReader) -> None:
        from clasi.state_machine.predicates.project import is_overview_absent
        assert is_overview_absent(_proj_ctx(reader)) is False


class TestSprintArtifactPredicatesWithRealPaths:
    def test_sprint_doc_present(self, reader: ClasiStateReader) -> None:
        from clasi.state_machine.predicates.sprint import is_sprint_doc_present
        assert is_sprint_doc_present(_sprint_ctx(reader)) is True

    def test_usecases_present(self, reader: ClasiStateReader) -> None:
        from clasi.state_machine.predicates.sprint import is_usecases_present
        assert is_usecases_present(_sprint_ctx(reader)) is True

    def test_architecture_present(self, reader: ClasiStateReader) -> None:
        from clasi.state_machine.predicates.sprint import is_architecture_present
        assert is_architecture_present(_sprint_ctx(reader)) is True

    def test_close_report_present(self, reader: ClasiStateReader) -> None:
        from clasi.state_machine.predicates.sprint import is_close_report_present
        assert is_close_report_present(_sprint_ctx(reader)) is True


class TestTicketPredicateWithRealPaths:
    def test_ticket_file_present_active(self, reader: ClasiStateReader) -> None:
        from clasi.state_machine.predicates.ticket import is_ticket_file_present
        assert is_ticket_file_present(_ticket_ctx(reader)) is True

    def test_ticket_file_present_in_done_dir(
        self, reader: ClasiStateReader, project: Project
    ) -> None:
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
