"""Smoke tests for clasi/worktree.py stub module.

Verifies that:
- The module is importable.
- Every public function raises NotImplementedError when called.

These tests exist to confirm the stub API is present and consistent. They
will need to be replaced with real behavioural tests when the implementation
sprint fills in the function bodies.
"""

from __future__ import annotations

import pytest

import clasi.worktree as worktree
from pathlib import Path


class TestCreateWorktree:
    def test_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            worktree.create_worktree(
                repo_root=tmp_path,
                sprint_id="022",
                ticket_id="003",
            )


class TestCreateTicketBranch:
    def test_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            worktree.create_ticket_branch(
                worktree_path=tmp_path,
                sprint_id="022",
                ticket_id="003",
                slug="stub-worktree-module",
            )


class TestValidateWorktree:
    def test_raises_not_implemented(self, tmp_path: Path) -> None:
        ticket = tmp_path / "ticket.md"
        ticket.write_text("---\nstatus: done\n---\n")
        with pytest.raises(NotImplementedError):
            worktree.validate_worktree(
                worktree_path=tmp_path,
                ticket_path=ticket,
            )


class TestMergeTicketBranch:
    def test_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            worktree.merge_ticket_branch(
                repo_root=tmp_path,
                sprint_branch="sprint/022-worktree-process",
                ticket_branch="ticket/022-003-stub",
            )


class TestCleanupWorktree:
    def test_raises_not_implemented_keep_false(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            worktree.cleanup_worktree(
                repo_root=tmp_path,
                worktree_path=tmp_path / "wt",
                ticket_branch="ticket/022-003-stub",
                keep_branch=False,
            )

    def test_raises_not_implemented_keep_true(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            worktree.cleanup_worktree(
                repo_root=tmp_path,
                worktree_path=tmp_path / "wt",
                ticket_branch="ticket/022-003-stub",
                keep_branch=True,
            )


class TestWriteAuditRecord:
    def test_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            worktree.write_audit_record(
                sprint_dir=tmp_path,
                event={"ticket_id": "003", "state": "worktree_created"},
            )


class TestReadAuditRecord:
    def test_raises_not_implemented(self, tmp_path: Path) -> None:
        with pytest.raises(NotImplementedError):
            worktree.read_audit_record(sprint_dir=tmp_path)


class TestCheckIndependence:
    def test_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            worktree.check_independence(
                tickets=[
                    {
                        "id": "001",
                        "files_to_create": ["clasi/foo.py"],
                        "files_to_modify": [],
                    },
                    {
                        "id": "003",
                        "files_to_create": ["clasi/worktree.py"],
                        "files_to_modify": [],
                    },
                ]
            )
