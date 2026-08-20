"""Unit tests for clasi.tools.artifact_tools — focused on update_ticket_status and throw_ticket_exception."""

import json
from unittest.mock import MagicMock, patch

import pytest

from clasi.tools.artifact_tools import (
    _derive_overlay_slug,
    _resolve_overlay_doc_path,
    close_sprint,
    create_sprint,
    update_ticket_status,
    throw_ticket_exception,
)
from clasi.artifact import Artifact
from clasi.mcp_server import set_project
from clasi.project import Project
from clasi.state_db import acquire_lock, advance_phase, record_gate


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
        # Isolate the project: as of sprint 030 ticket 003,
        # update_ticket_status(path, "done") also runs the sprint-issue
        # sweep, which reads get_project().issues_dir. Without an explicit
        # set_project() here, that call falls back to Path.cwd() -- this
        # repo's own real clasi/issues/ -- and can crash trying to compare
        # against this test's made-up (nonexistent) sprint.md.
        set_project(tmp_path)
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


# ---------------------------------------------------------------------------
# Helpers shared by TestCloseSprintExitCode5
# ---------------------------------------------------------------------------


def _advance_to_executing(work_dir, sprint_id: str = "001") -> None:
    """Advance a sprint through all review gates to executing phase."""
    db_path = work_dir / ".clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # roadmap -> planning-docs
    advance_phase(db_path, sprint_id)  # planning-docs -> architecture-review
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)  # architecture-review -> stakeholder-review
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")
    advance_phase(db_path, sprint_id)  # stakeholder-review -> ticketing
    acquire_lock(db_path, sprint_id)   # lock must be held before ticketing -> executing
    advance_phase(db_path, sprint_id)  # ticketing -> executing


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    """Minimal CLASI project in a temp directory."""
    monkeypatch.chdir(tmp_path)
    set_project(tmp_path)
    return tmp_path


def _make_subprocess_result(returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
    """Return a fake subprocess.CompletedProcess-like MagicMock."""
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class TestCloseSprintExitCode5:
    """Pytest exit code 5 (no tests collected) must not be treated as a failure."""

    def test_exit_code_5_does_not_produce_test_failure_error(self, work_dir):
        """When subprocess returns exit code 5, close_sprint continues past the test step."""
        create_sprint("Sprint")
        _advance_to_executing(work_dir, "001")

        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_result(5)
            result = json.loads(close_sprint("001"))

        # The response must NOT be a test-failure error.
        assert result.get("status") != "error" or result.get("error", {}).get("step") != "tests", (
            "Exit code 5 (no tests collected) must not be reported as a test failure. "
            f"Got: {result}"
        )


def _make_project_with_sources(tmp_path, sources):
    """Write .clasi/config.yaml with the given sources: list and return a Project."""
    config_dir = tmp_path / ".clasi"
    config_dir.mkdir(parents=True, exist_ok=True)
    sources_yaml = "\n".join(f"  - {s}" for s in sources)
    (config_dir / "config.yaml").write_text(
        f"sources:\n{sources_yaml}\n", encoding="utf-8"
    )
    return Project(tmp_path)


class TestDeriveOverlaySlug:
    """Ticket 001: unique, stable, reversible overlay slug per canonical doc."""

    def test_colocated_subsystem_doc_under_source_root(self, tmp_path):
        project = _make_project_with_sources(tmp_path, ["src"])
        canonical = tmp_path / "src" / "firm" / "app" / "DESIGN.md"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text("# App\n", encoding="utf-8")

        slug = _derive_overlay_slug(project, canonical)

        assert slug == "firm-app-DESIGN.md"

    def test_system_level_doc_has_no_source_root_prefix(self, tmp_path):
        project = _make_project_with_sources(tmp_path, ["src"])
        canonical = tmp_path / "docs" / "design" / "design.md"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text("# System\n", encoding="utf-8")

        slug = _derive_overlay_slug(project, canonical)

        assert slug == "design.md"

    def test_reseed_reproduces_the_same_slug(self, tmp_path):
        project = _make_project_with_sources(tmp_path, ["src"])
        canonical = tmp_path / "src" / "firm" / "app" / "DESIGN.md"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text("# App\n", encoding="utf-8")

        first = _derive_overlay_slug(project, canonical)
        second = _derive_overlay_slug(project, canonical)

        assert first == second == "firm-app-DESIGN.md"

    def test_doc_directly_at_source_root_keeps_bare_basename(self, tmp_path):
        project = _make_project_with_sources(tmp_path, ["src"])
        canonical = tmp_path / "src" / "DESIGN.md"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text("# Src overview\n", encoding="utf-8")

        slug = _derive_overlay_slug(project, canonical)

        assert slug == "DESIGN.md"

    def test_two_colocated_docs_produce_distinct_slugs(self, tmp_path):
        project = _make_project_with_sources(tmp_path, ["src"])
        alpha = tmp_path / "src" / "firm" / "app" / "DESIGN.md"
        beta = tmp_path / "host" / "robot_radio" / "DESIGN.md"
        alpha.parent.mkdir(parents=True, exist_ok=True)
        alpha.write_text("# Alpha\n", encoding="utf-8")

        project_multi = _make_project_with_sources(tmp_path, ["src", "host"])
        beta.parent.mkdir(parents=True, exist_ok=True)
        beta.write_text("# Beta\n", encoding="utf-8")

        slug_alpha = _derive_overlay_slug(project_multi, alpha)
        slug_beta = _derive_overlay_slug(project_multi, beta)

        assert slug_alpha == "firm-app-DESIGN.md"
        assert slug_beta == "robot_radio-DESIGN.md"
        assert slug_alpha != slug_beta


class TestResolveOverlayDocPath:
    """doc_names accepts both docs/design/-relative names and co-located paths."""

    def test_bare_filename_resolves_relative_to_design_dir(self, tmp_path):
        project = _make_project_with_sources(tmp_path, [])
        resolved = _resolve_overlay_doc_path(project, "design.md")

        assert resolved == (tmp_path / "docs" / "design" / "design.md").resolve()

    def test_colocated_path_resolves_relative_to_project_root_no_escape(self, tmp_path):
        project = _make_project_with_sources(tmp_path, ["src"])
        resolved = _resolve_overlay_doc_path(project, "src/firm/app/DESIGN.md")

        assert resolved == (tmp_path / "src" / "firm" / "app" / "DESIGN.md").resolve()
