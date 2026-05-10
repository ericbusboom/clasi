"""Unit tests for clasi.tools.artifact_tools — focused on update_ticket_status."""

import json

import pytest

from clasi.tools.artifact_tools import update_ticket_status


def _make_ticket(tmp_path, status="open"):
    """Write a minimal ticket file and return its path as a string."""
    ticket = tmp_path / "001-task.md"
    ticket.write_text(
        f"---\nid: \"001\"\ntitle: \"Task\"\nstatus: {status}\n"
        "use-cases: []\ndepends-on: []\ntodo: \"\"\n---\n# Task\n",
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
