"""Unit tests for clasi.tools.artifact_tools — focused on update_ticket_status and throw_ticket_exception."""

import json

import pytest

from clasi.tools.artifact_tools import update_ticket_status, throw_ticket_exception
from clasi.artifact import Artifact


def _make_ticket(tmp_path, status="open"):
    """Write a minimal ticket file and return its path as a string."""
    ticket = tmp_path / "001-task.md"
    ticket.write_text(
        f"---\nid: \"001\"\ntitle: \"Task\"\nstatus: {status}\n"
        "use-cases: []\ndepends-on: []\nissue: \"\"\n---\n# Task\n",
        encoding="utf-8",
    )
    return str(ticket)


class TestUpdateTicketStatusException:
    """Tests for 'exception' status support in update_ticket_status."""

    def test_update_ticket_status_accepts_exception(self, tmp_path):
        """update_ticket_status(path, 'exception') succeeds without raising."""
        path = _make_ticket(tmp_path)
        result = json.loads(update_ticket_status(path, "exception"))
        assert result["new_status"] == "exception"
        assert result["old_status"] == "open"

    def test_update_ticket_status_rejects_unknown(self, tmp_path):
        """update_ticket_status raises ValueError for an invalid status value."""
        path = _make_ticket(tmp_path)
        with pytest.raises(ValueError, match="Invalid status"):
            update_ticket_status(path, "invalid-value")

    def test_update_ticket_status_accepts_all_valid_statuses(self, tmp_path):
        """All four valid statuses are accepted without raising."""
        for status in ("open", "in-progress", "done", "exception"):
            path = _make_ticket(tmp_path)
            result = json.loads(update_ticket_status(path, status))
            assert result["new_status"] == status


class TestThrowTicketException:
    """Tests for throw_ticket_exception tool."""

    _VALID_ARGS = dict(
        thrown_by="programmer",
        attempted="implemented feature X",
        conflict="architecture decision ADR-003 prohibits approach",
        surface="internal",
    )

    def test_throw_ticket_exception_writes_frontmatter(self, tmp_path):
        """Calling throw_ticket_exception writes the exception block to frontmatter."""
        path = _make_ticket(tmp_path)
        result = json.loads(throw_ticket_exception(path, **self._VALID_ARGS))

        artifact = Artifact(path)
        fm = artifact.frontmatter
        exc = fm.get("exception")
        assert exc is not None, "exception block missing from frontmatter"
        assert exc["thrown_by"] == "programmer"
        assert exc["attempted"] == self._VALID_ARGS["attempted"]
        assert exc["conflict"] == self._VALID_ARGS["conflict"]
        assert exc["surface"] == "internal"
        assert "thrown_at" in exc

    def test_throw_ticket_exception_sets_status_to_exception(self, tmp_path):
        """Calling throw_ticket_exception sets ticket status to 'exception'."""
        path = _make_ticket(tmp_path, status="in-progress")
        result = json.loads(throw_ticket_exception(path, **self._VALID_ARGS))

        assert result["old_status"] == "in-progress"
        assert result["new_status"] == "exception"

        artifact = Artifact(path)
        assert artifact.frontmatter["status"] == "exception"

    def test_throw_ticket_exception_returns_expected_json(self, tmp_path):
        """Return payload contains path, old_status, new_status, thrown_at."""
        path = _make_ticket(tmp_path)
        result = json.loads(throw_ticket_exception(path, **self._VALID_ARGS))

        assert result["new_status"] == "exception"
        assert result["old_status"] == "open"
        assert "thrown_at" in result
        assert "path" in result

    def test_throw_ticket_exception_thrown_at_is_utc_iso8601(self, tmp_path):
        """thrown_at is an ISO-8601 UTC timestamp."""
        from datetime import datetime, timezone

        path = _make_ticket(tmp_path)
        result = json.loads(throw_ticket_exception(path, **self._VALID_ARGS))

        thrown_at = result["thrown_at"]
        # Should parse without error and be timezone-aware
        dt = datetime.fromisoformat(thrown_at)
        assert dt.tzinfo is not None

    def test_throw_ticket_exception_invalid_thrown_by(self, tmp_path):
        """Invalid thrown_by raises ValueError."""
        path = _make_ticket(tmp_path)
        with pytest.raises(ValueError, match="thrown_by"):
            throw_ticket_exception(
                path,
                thrown_by="team-lead",
                attempted="x",
                conflict="y",
                surface="internal",
            )

    def test_throw_ticket_exception_invalid_surface(self, tmp_path):
        """Invalid surface raises ValueError."""
        path = _make_ticket(tmp_path)
        with pytest.raises(ValueError, match="surface"):
            throw_ticket_exception(
                path,
                thrown_by="programmer",
                attempted="x",
                conflict="y",
                surface="public",
            )

    def test_throw_ticket_exception_unknown_path(self, tmp_path):
        """Unknown ticket path raises ValueError with clear message."""
        with pytest.raises(ValueError, match="Ticket not found"):
            throw_ticket_exception(
                str(tmp_path / "nonexistent.md"),
                **self._VALID_ARGS,
            )

    def test_throw_ticket_exception_both_writes_occur(self, tmp_path):
        """Both exception payload and status are written (not partial)."""
        path = _make_ticket(tmp_path, status="open")
        throw_ticket_exception(path, **self._VALID_ARGS)

        artifact = Artifact(path)
        fm = artifact.frontmatter
        # Both must be set
        assert fm["status"] == "exception"
        assert fm.get("exception") is not None

    def test_throw_ticket_exception_sprint_planner_thrown_by(self, tmp_path):
        """'sprint-planner' is a valid thrown_by value."""
        path = _make_ticket(tmp_path)
        result = json.loads(
            throw_ticket_exception(
                path,
                thrown_by="sprint-planner",
                attempted="planned sprint",
                conflict="dependency not resolved",
                surface="user-visible",
            )
        )
        assert result["new_status"] == "exception"
        artifact = Artifact(path)
        assert artifact.frontmatter["exception"]["thrown_by"] == "sprint-planner"
        assert artifact.frontmatter["exception"]["surface"] == "user-visible"
