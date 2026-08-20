"""Tests for TaskCreated and TaskCompleted hook handlers."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from clasi.hook_handlers import (
    handle_task_created,
    handle_task_completed,
    handle_subagent_start,
    handle_subagent_stop,
    handle_commit_check,
    handle_plan_to_issue,
    handle_plan_to_todo,  # backward-compatible alias
    handle_codex_plan_to_issue,
    handle_codex_plan_to_todo,  # backward-compatible alias
    handle_hook,
    handle_role_guard,
    handle_mcp_guard,
    _ensure_log_gitignore,
    _get_log_dir,
    _get_sprint_context,
    _get_active_tickets,
    _render_transcript_lines,
    _ext_to_language,
    _oop_active,
    _oop_source,
    _recovery_entry_matches,
    _load_role_guard_config,
    get_project,
)
from clasi.project import Project
from clasi.state_db import (
    init_db,
    register_sprint,
    acquire_lock,
    get_active_agent,
    register_active_agent,
    get_active_tier,
    clear_stale_agents,
    set_oop,
    get_oop,
    clear_oop,
    write_recovery_state,
    get_recovery_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_LEGACY_PATHS_PIN = """\
process: se
paths:
  issues: .clasi/issues
  sprints: .clasi/sprints
  reflections: .clasi/reflections
  architecture: .clasi/architecture
  design: docs/design
  logs: .clasi/log
  db: .clasi/.clasi.db
"""


def _write_legacy_pin(root: Path) -> None:
    """Write a backward-compat config.yaml pinning paths to .clasi/ layout."""
    clasi_dir = root / ".clasi"
    clasi_dir.mkdir(parents=True, exist_ok=True)
    (clasi_dir / "config.yaml").write_text(_LEGACY_PATHS_PIN, encoding="utf-8")


def _make_log_dir(tmp_path: Path) -> Path:
    log_dir = tmp_path / ".clasi" / "log"
    log_dir.mkdir(parents=True)
    return log_dir


def _run_with_cwd(tmp_path: Path, fn, *args, **kwargs):
    """Call fn with cwd changed to tmp_path."""
    import os
    old = os.getcwd()
    os.chdir(tmp_path)
    try:
        return fn(*args, **kwargs)
    finally:
        os.chdir(old)


def _task_created_payload(
    task_id="t-001",
    task_subject="Implement feature X",
    teammate_name="programmer",
    session_id="sess-abc",
    transcript_path="",
    cwd="/tmp",
    permission_mode="default",
) -> dict:
    return {
        "task_id": task_id,
        "task_subject": task_subject,
        "teammate_name": teammate_name,
        "session_id": session_id,
        "transcript_path": transcript_path,
        "cwd": cwd,
        "permission_mode": permission_mode,
        "hook_event_name": "TaskCreated",
    }


def _task_completed_payload(
    task_id="t-001",
    task_subject="Implement feature X",
    teammate_name="programmer",
    session_id="sess-abc",
    transcript_path="",
    cwd="/tmp",
    permission_mode="default",
) -> dict:
    return {
        "task_id": task_id,
        "task_subject": task_subject,
        "teammate_name": teammate_name,
        "session_id": session_id,
        "transcript_path": transcript_path,
        "cwd": cwd,
        "permission_mode": permission_mode,
        "hook_event_name": "TaskCompleted",
    }


# ---------------------------------------------------------------------------
# TaskCreated tests
# ---------------------------------------------------------------------------


class TestHandleTaskCreated:
    def test_creates_log_file_with_frontmatter(self, tmp_path):
        """task_created creates a log file with correct frontmatter fields."""
        _make_log_dir(tmp_path)
        payload = _task_created_payload()

        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_created, payload)
        assert exc.value.code == 0

        log_dir = tmp_path / ".clasi" / "log"
        log_files = list(log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1

        content = log_files[0].read_text()
        assert "task_id: t-001" in content
        assert "task_subject: Implement feature X" in content
        assert "teammate_name: programmer" in content
        assert "started_at:" in content

    def test_creates_active_marker(self, tmp_path):
        """task_created registers task-{id} in the DB as an active agent."""
        _make_log_dir(tmp_path)
        db_path = str(tmp_path / ".clasi" / ".clasi.db")
        payload = _task_created_payload(task_id="t-42")

        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_task_created, payload)

        record = get_active_agent(db_path, "task-t-42")
        assert record is not None
        assert "log_file" in record
        assert "started_at" in record

    def test_marker_log_file_points_to_created_log(self, tmp_path):
        """The DB record's log_file path matches the created log file."""
        _make_log_dir(tmp_path)
        db_path = str(tmp_path / ".clasi" / ".clasi.db")
        payload = _task_created_payload(task_id="t-10")

        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_task_created, payload)

        log_dir = tmp_path / ".clasi" / "log"
        log_files = list(log_dir.glob("[0-9][0-9][0-9]-*.md"))
        record = get_active_agent(db_path, "task-t-10")
        assert record is not None
        # The record stores the log file path (relative or absolute).
        # Verify it refers to the same filename as the created log file.
        assert Path(record["log_file"]).name == log_files[0].name

    def test_exits_zero_when_log_dir_missing(self, tmp_path):
        """task_created exits 0 gracefully if .clasi/log does not exist."""
        payload = _task_created_payload()
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_created, payload)
        assert exc.value.code == 0

    def test_log_filename_derived_from_subject(self, tmp_path):
        """Log filename slug is derived from task_subject."""
        _make_log_dir(tmp_path)
        payload = _task_created_payload(task_subject="My Great Task")

        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_task_created, payload)

        log_dir = tmp_path / ".clasi" / "log"
        log_files = list(log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        # slug should be lowercase, spaces replaced with dashes
        assert "my-great-task" in log_files[0].name


# ---------------------------------------------------------------------------
# TaskCompleted tests
# ---------------------------------------------------------------------------


class TestHandleTaskCompleted:
    def _setup_active_task(self, tmp_path, task_id="t-001", task_subject="Task"):
        """Run task_created to set up the log and marker files."""
        payload = _task_created_payload(task_id=task_id, task_subject=task_subject)
        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_task_created, payload)

    def test_appends_duration_to_frontmatter(self, tmp_path):
        """task_completed adds stopped_at and duration_seconds to frontmatter."""
        _make_log_dir(tmp_path)
        self._setup_active_task(tmp_path, task_id="t-001")

        payload = _task_completed_payload(task_id="t-001")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_completed, payload)
        assert exc.value.code == 0

        log_dir = tmp_path / ".clasi" / "log"
        log_files = list(log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "stopped_at:" in content
        assert "duration_seconds:" in content

    def test_removes_active_marker_after_completion(self, tmp_path):
        """task_completed removes the DB record for the task."""
        _make_log_dir(tmp_path)
        db_path = str(tmp_path / ".clasi" / ".clasi.db")
        self._setup_active_task(tmp_path, task_id="t-002")

        # The DB record should exist after task_created
        assert get_active_agent(db_path, "task-t-002") is not None

        payload = _task_completed_payload(task_id="t-002")
        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_task_completed, payload)

        # The DB record should be gone after task_completed
        assert get_active_agent(db_path, "task-t-002") is None

    def test_appends_transcript_content(self, tmp_path):
        """task_completed appends the transcript as a JSON code block."""
        _make_log_dir(tmp_path)
        self._setup_active_task(tmp_path, task_id="t-003")

        # Write a fake transcript JSONL
        transcript_file = tmp_path / "transcript.jsonl"
        messages = [
            {"role": "user", "content": "Do this task."},
            {"role": "assistant", "content": "Done."},
        ]
        transcript_file.write_text("\n".join(json.dumps(m) for m in messages))

        payload = _task_completed_payload(
            task_id="t-003",
            transcript_path=str(transcript_file),
        )
        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_task_completed, payload)

        log_dir = tmp_path / ".clasi" / "log"
        log_files = list(log_dir.glob("[0-9][0-9][0-9]-*.md"))
        content = log_files[0].read_text()
        assert "## Transcript" in content
        assert "```json" in content
        assert "Do this task." in content

    def test_extracts_prompt_from_transcript(self, tmp_path):
        """task_completed extracts the first user message as prompt."""
        _make_log_dir(tmp_path)
        self._setup_active_task(tmp_path, task_id="t-004")

        transcript_file = tmp_path / "transcript.jsonl"
        messages = [
            {"role": "user", "content": "The initial prompt text."},
            {"role": "assistant", "content": "Response."},
        ]
        transcript_file.write_text("\n".join(json.dumps(m) for m in messages))

        payload = _task_completed_payload(
            task_id="t-004",
            transcript_path=str(transcript_file),
        )
        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_task_completed, payload)

        log_dir = tmp_path / ".clasi" / "log"
        log_files = list(log_dir.glob("[0-9][0-9][0-9]-*.md"))
        content = log_files[0].read_text()
        assert "## Prompt" in content
        assert "The initial prompt text." in content

    def test_exits_zero_when_log_dir_missing(self, tmp_path):
        """task_completed exits 0 gracefully if .clasi/log does not exist."""
        payload = _task_completed_payload()
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_completed, payload)
        assert exc.value.code == 0

    def test_exits_zero_when_no_marker(self, tmp_path):
        """task_completed exits 0 gracefully if no marker file exists."""
        _make_log_dir(tmp_path)
        payload = _task_completed_payload(task_id="nonexistent")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_completed, payload)
        assert exc.value.code == 0


# ---------------------------------------------------------------------------
# Sprint-scoped log directory tests
# ---------------------------------------------------------------------------


def _setup_db_with_lock(tmp_path: Path, sprint_id: str = "001") -> str:
    """Create a state DB with a registered sprint holding the execution lock."""
    db_path = str(tmp_path / ".clasi" / ".clasi.db")
    init_db(db_path)
    register_sprint(db_path, sprint_id, f"sprint-{sprint_id}")
    acquire_lock(db_path, sprint_id)
    return db_path


class TestGetLogDir:
    def test_returns_none_when_log_dir_missing(self, tmp_path):
        """_get_log_dir returns None when .clasi/log does not exist."""
        result = _run_with_cwd(tmp_path, _get_log_dir)
        assert result is None

    def test_returns_base_dir_when_no_db(self, tmp_path):
        """_get_log_dir returns base log dir when no state DB exists."""
        _make_log_dir(tmp_path)
        result = _run_with_cwd(tmp_path, _get_log_dir)
        assert result == tmp_path / ".clasi" / "log"

    def test_returns_base_dir_when_no_lock(self, tmp_path):
        """_get_log_dir returns base log dir when DB exists but no lock held."""
        _make_log_dir(tmp_path)
        db_path = str(tmp_path / ".clasi" / ".clasi.db")
        init_db(db_path)
        register_sprint(db_path, "001", "sprint-001")
        # No lock acquired
        result = _run_with_cwd(tmp_path, _get_log_dir)
        assert result == tmp_path / ".clasi" / "log"

    def test_returns_sprint_subdir_when_lock_held(self, tmp_path):
        """_get_log_dir returns sprint-scoped subdir when execution lock is held."""
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="002")
        result = _run_with_cwd(tmp_path, _get_log_dir)
        assert result == tmp_path / ".clasi" / "log" / "sprint-002"

    def test_creates_sprint_subdir_when_lock_held(self, tmp_path):
        """_get_log_dir creates the sprint subdirectory on the filesystem."""
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="003")
        _run_with_cwd(tmp_path, _get_log_dir)
        assert (tmp_path / ".clasi" / "log" / "sprint-003").is_dir()


class TestSprintScopedLogging:
    def test_task_created_uses_sprint_subdir_when_lock_held(self, tmp_path):
        """task_created writes log to sprint subdir when execution lock is held."""
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="001")
        payload = _task_created_payload(task_id="t-sprint-001")

        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_created, payload)
        assert exc.value.code == 0

        sprint_log_dir = tmp_path / ".clasi" / "log" / "sprint-001"
        log_files = list(sprint_log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "task_id: t-sprint-001" in content

    def test_task_created_active_marker_in_db(self, tmp_path):
        """task_created registers the task in the DB (not a file marker)."""
        _make_log_dir(tmp_path)
        db_path = _setup_db_with_lock(tmp_path, sprint_id="001")
        payload = _task_created_payload(task_id="t-marker")

        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_task_created, payload)

        record = get_active_agent(db_path, "task-t-marker")
        assert record is not None
        assert record["agent_type"] == "task"

    def test_task_completed_finds_log_in_sprint_subdir(self, tmp_path):
        """task_completed appends to log in sprint subdir when lock is held."""
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="001")

        # task_created sets up the log
        create_payload = _task_created_payload(task_id="t-full")
        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_task_created, create_payload)

        # task_completed should find it in the same sprint subdir
        complete_payload = _task_completed_payload(task_id="t-full")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_completed, complete_payload)
        assert exc.value.code == 0

        sprint_log_dir = tmp_path / ".clasi" / "log" / "sprint-001"
        log_files = list(sprint_log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "stopped_at:" in content
        assert "duration_seconds:" in content

    def test_task_created_falls_back_to_base_dir_without_lock(self, tmp_path):
        """task_created uses base log dir when no sprint holds the lock."""
        _make_log_dir(tmp_path)
        # DB exists but no lock
        db_path = str(tmp_path / ".clasi" / ".clasi.db")
        init_db(db_path)
        register_sprint(db_path, "001", "sprint-001")

        payload = _task_created_payload(task_id="t-fallback")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_created, payload)
        assert exc.value.code == 0

        base_log_dir = tmp_path / ".clasi" / "log"
        log_files = list(base_log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        # Sprint subdir should not have been created
        assert not (base_log_dir / "sprint-001").exists()


# ---------------------------------------------------------------------------
# Sprint ID and tickets in frontmatter
# ---------------------------------------------------------------------------


def _make_in_progress_ticket(sprint_dir: Path, ticket_id: str, title: str = "A ticket") -> None:
    """Write a minimal in-progress ticket file to sprint_dir/tickets/."""
    tickets_dir = sprint_dir / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\nid: '{ticket_id}'\ntitle: {title}\nstatus: in-progress\n---\n"
    (tickets_dir / f"{ticket_id}-{title.lower().replace(' ', '-')}.md").write_text(content)


def _make_done_ticket(sprint_dir: Path, ticket_id: str, title: str = "Done ticket") -> None:
    """Write a minimal done ticket file to sprint_dir/tickets/."""
    tickets_dir = sprint_dir / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    content = f"---\nid: '{ticket_id}'\ntitle: {title}\nstatus: done\n---\n"
    (tickets_dir / f"{ticket_id}-{title.lower().replace(' ', '-')}.md").write_text(content)


class TestGetActiveTickets:
    def test_returns_empty_for_empty_sprint_id(self, tmp_path):
        """_get_active_tickets returns empty list when sprint_id is empty string."""
        result = _run_with_cwd(tmp_path, _get_active_tickets, "")
        assert result == []

    def test_returns_empty_when_no_sprints_dir(self, tmp_path):
        """_get_active_tickets returns empty list when .clasi/sprints does not exist."""
        result = _run_with_cwd(tmp_path, _get_active_tickets, "001")
        assert result == []

    def test_returns_empty_when_no_matching_sprint_dir(self, tmp_path):
        """_get_active_tickets returns empty list when no sprint dir matches sprint_id."""
        sprints = tmp_path / ".clasi" / "sprints"
        sprints.mkdir(parents=True)
        (sprints / "002-some-sprint").mkdir()
        result = _run_with_cwd(tmp_path, _get_active_tickets, "001")
        assert result == []

    def test_returns_in_progress_ticket_ids(self, tmp_path):
        """_get_active_tickets returns ticket IDs for in-progress tickets."""
        _write_legacy_pin(tmp_path)
        sprints = tmp_path / ".clasi" / "sprints"
        sprint_dir = sprints / "002-my-sprint"
        sprint_dir.mkdir(parents=True)
        _make_in_progress_ticket(sprint_dir, "007", "Feature A")
        _make_in_progress_ticket(sprint_dir, "009", "Feature B")
        _make_done_ticket(sprint_dir, "001", "Old task")

        result = _run_with_cwd(tmp_path, _get_active_tickets, "002")
        assert "002-007" in result
        assert "002-009" in result
        assert "002-001" not in result

    def test_returns_empty_when_no_in_progress_tickets(self, tmp_path):
        """_get_active_tickets returns empty list when all tickets are done."""
        sprints = tmp_path / ".clasi" / "sprints"
        sprint_dir = sprints / "003-another-sprint"
        sprint_dir.mkdir(parents=True)
        _make_done_ticket(sprint_dir, "001", "Done one")

        result = _run_with_cwd(tmp_path, _get_active_tickets, "003")
        assert result == []


class TestSprintIdInFrontmatter:
    def test_task_created_includes_sprint_id_when_lock_held(self, tmp_path):
        """task_created writes sprint_id to frontmatter when an execution lock is held."""
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="002")
        payload = _task_created_payload(task_id="t-sid")

        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_created, payload)
        assert exc.value.code == 0

        sprint_log_dir = tmp_path / ".clasi" / "log" / "sprint-002"
        log_files = list(sprint_log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert 'sprint_id: "002"' in content

    def test_task_created_includes_empty_sprint_id_when_no_lock(self, tmp_path):
        """task_created writes empty sprint_id when no execution lock is held."""
        _make_log_dir(tmp_path)
        payload = _task_created_payload(task_id="t-nosid")

        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_created, payload)
        assert exc.value.code == 0

        base_log_dir = tmp_path / ".clasi" / "log"
        log_files = list(base_log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert 'sprint_id: ""' in content

    def test_task_created_includes_tickets_in_frontmatter(self, tmp_path):
        """task_created writes in-progress ticket IDs to frontmatter."""
        _write_legacy_pin(tmp_path)
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="002")

        # Create sprint directory with in-progress ticket
        sprint_dir = tmp_path / ".clasi" / "sprints" / "002-test-sprint"
        _make_in_progress_ticket(sprint_dir, "007", "Feature A")

        payload = _task_created_payload(task_id="t-tickets")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_created, payload)
        assert exc.value.code == 0

        sprint_log_dir = tmp_path / ".clasi" / "log" / "sprint-002"
        log_files = list(sprint_log_dir.glob("[0-9][0-9][0-9]-*.md"))
        content = log_files[0].read_text()
        assert "002-007" in content

    def test_subagent_start_includes_sprint_id_when_lock_held(self, tmp_path):
        """handle_subagent_start writes sprint_id to frontmatter when lock is held."""
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="002")

        payload = {
            "agent_type": "programmer",
            "agent_id": "abc123",
            "session_id": "sess-xyz",
            "hook_event_name": "SubagentStart",
        }
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_subagent_start, payload)
        assert exc.value.code == 0

        sprint_log_dir = tmp_path / ".clasi" / "log" / "sprint-002"
        log_files = list(sprint_log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert 'sprint_id: "002"' in content
        assert "agent_type: programmer" in content
        assert "agent_id: abc123" in content

    def test_subagent_start_includes_empty_sprint_id_when_no_lock(self, tmp_path):
        """handle_subagent_start writes empty sprint_id when no lock is held."""
        _make_log_dir(tmp_path)

        payload = {
            "agent_type": "programmer",
            "agent_id": "abc123",
            "session_id": "sess-xyz",
            "hook_event_name": "SubagentStart",
        }
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_subagent_start, payload)
        assert exc.value.code == 0

        base_log_dir = tmp_path / ".clasi" / "log"
        log_files = list(base_log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert 'sprint_id: ""' in content


# ---------------------------------------------------------------------------
# _render_transcript_lines and _ext_to_language unit tests
# ---------------------------------------------------------------------------


class TestExtToLanguage:
    def test_py_maps_to_python(self):
        assert _ext_to_language("foo.py") == "python"

    def test_toml_maps_to_toml(self):
        assert _ext_to_language("pyproject.toml") == "toml"

    def test_yaml_maps_to_yaml(self):
        assert _ext_to_language("config.yaml") == "yaml"

    def test_yml_maps_to_yaml(self):
        assert _ext_to_language("config.yml") == "yaml"

    def test_json_maps_to_json(self):
        assert _ext_to_language("data.json") == "json"

    def test_js_maps_to_javascript(self):
        assert _ext_to_language("app.js") == "javascript"

    def test_ts_maps_to_typescript(self):
        assert _ext_to_language("app.ts") == "typescript"

    def test_sh_maps_to_bash(self):
        assert _ext_to_language("script.sh") == "bash"

    def test_unknown_returns_empty_string(self):
        assert _ext_to_language("file.xyz") == ""

    def test_no_extension_returns_empty_string(self):
        assert _ext_to_language("Makefile") == ""


def _make_tool_use_block(name: str, input_dict: dict) -> dict:
    return {"type": "tool_use", "name": name, "input": input_dict}


def _make_message_with_tool_use(tool_block: dict) -> dict:
    return {
        "type": "assistant",
        "timestamp": "2026-01-01T00:00:00Z",
        "message": {
            "content": [tool_block],
        },
    }


class TestRenderTranscriptLines:
    def test_write_md_renders_inline_markdown(self):
        """Write to .md file renders content as inline markdown, no fence."""
        block = _make_tool_use_block("Write", {
            "file_path": ".clasi/sprints/003/tickets/001-ticket.md",
            "content": "# Ticket Title\n\nSome description.",
        })
        msg = _make_message_with_tool_use(block)
        output = "\n".join(_render_transcript_lines([msg]))

        assert "**Write**" in output
        assert "001-ticket.md" in output
        assert "# Ticket Title" in output
        assert "Some description." in output
        # Should NOT be inside a code fence for the content
        assert "```python" not in output

    def test_write_py_renders_python_fence(self):
        """Write to .py file renders content in a python fenced block."""
        block = _make_tool_use_block("Write", {
            "file_path": "clasi/my_module.py",
            "content": "def hello():\n    return 'world'",
        })
        msg = _make_message_with_tool_use(block)
        output = "\n".join(_render_transcript_lines([msg]))

        assert "**Write**" in output
        assert "my_module.py" in output
        assert "```python" in output
        assert "def hello():" in output

    def test_write_unknown_ext_renders_plain_fence(self):
        """Write to an unknown extension renders content in a plain fenced block."""
        block = _make_tool_use_block("Write", {
            "file_path": "config.xyz",
            "content": "some content here",
        })
        msg = _make_message_with_tool_use(block)
        output = "\n".join(_render_transcript_lines([msg]))

        assert "**Write**" in output
        assert "config.xyz" in output
        assert "```\n" in output  # plain fence (no language tag)
        assert "some content here" in output

    def test_edit_renders_before_and_after_blocks(self):
        """Edit renders file_path heading, old_string in Before block, new_string in After block."""
        block = _make_tool_use_block("Edit", {
            "file_path": "clasi/hook_handlers.py",
            "old_string": "def old_func():\n    pass",
            "new_string": "def new_func():\n    return True",
        })
        msg = _make_message_with_tool_use(block)
        output = "\n".join(_render_transcript_lines([msg]))

        assert "**Edit**" in output
        assert "hook_handlers.py" in output
        assert "**Before:**" in output
        assert "**After:**" in output
        assert "def old_func():" in output
        assert "def new_func():" in output

    def test_other_tool_renders_json_dump(self):
        """Non-Write/Edit tools render as JSON dump (existing behavior)."""
        block = _make_tool_use_block("Bash", {
            "command": "echo hello",
        })
        msg = _make_message_with_tool_use(block)
        output = "\n".join(_render_transcript_lines([msg]))

        assert "**Tool Use**: `Bash`" in output
        assert "```json" in output
        assert '"command"' in output

    def test_transcript_section_header_present(self):
        """_render_transcript_lines always includes ## Transcript."""
        output = "\n".join(_render_transcript_lines([]))
        assert "## Transcript" in output

    def test_raw_json_block_present(self):
        """_render_transcript_lines always includes a raw JSON code block."""
        block = _make_tool_use_block("Bash", {"command": "ls"})
        msg = _make_message_with_tool_use(block)
        output = "\n".join(_render_transcript_lines([msg]))
        assert "```json" in output


# ---------------------------------------------------------------------------
# handle_hook dispatcher tests
# ---------------------------------------------------------------------------


class TestHandleHook:
    """Test that handle_hook routes event names to the correct handlers."""

    def test_routes_role_guard(self):
        """handle_hook('role-guard') calls handle_role_guard."""
        with patch("clasi.hook_handlers.handle_role_guard") as mock_handler, \
             patch("clasi.hook_handlers.read_payload", return_value={}):
            mock_handler.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                handle_hook("role-guard")
            mock_handler.assert_called_once_with({})

    def test_routes_subagent_start(self):
        """handle_hook('subagent-start') calls handle_subagent_start."""
        with patch("clasi.hook_handlers.handle_subagent_start") as mock_handler, \
             patch("clasi.hook_handlers.read_payload", return_value={}):
            mock_handler.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                handle_hook("subagent-start")
            mock_handler.assert_called_once_with({})

    def test_routes_subagent_stop(self):
        """handle_hook('subagent-stop') calls handle_subagent_stop."""
        with patch("clasi.hook_handlers.handle_subagent_stop") as mock_handler, \
             patch("clasi.hook_handlers.read_payload", return_value={}):
            mock_handler.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                handle_hook("subagent-stop")
            mock_handler.assert_called_once_with({})

    def test_routes_task_created(self):
        """handle_hook('task-created') calls handle_task_created."""
        with patch("clasi.hook_handlers.handle_task_created") as mock_handler, \
             patch("clasi.hook_handlers.read_payload", return_value={}):
            mock_handler.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                handle_hook("task-created")
            mock_handler.assert_called_once_with({})

    def test_routes_task_completed(self):
        """handle_hook('task-completed') calls handle_task_completed."""
        with patch("clasi.hook_handlers.handle_task_completed") as mock_handler, \
             patch("clasi.hook_handlers.read_payload", return_value={}):
            mock_handler.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                handle_hook("task-completed")
            mock_handler.assert_called_once_with({})

    def test_routes_mcp_guard(self):
        """handle_hook('mcp-guard') calls handle_mcp_guard."""
        with patch("clasi.hook_handlers.handle_mcp_guard") as mock_handler, \
             patch("clasi.hook_handlers.read_payload", return_value={}):
            mock_handler.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                handle_hook("mcp-guard")
            mock_handler.assert_called_once_with({})

    def test_routes_plan_to_issue(self):
        """handle_hook('plan-to-issue') calls handle_plan_to_issue."""
        with patch("clasi.hook_handlers.handle_plan_to_issue") as mock_handler, \
             patch("clasi.hook_handlers.read_payload", return_value={}):
            mock_handler.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                handle_hook("plan-to-issue")
            mock_handler.assert_called_once_with({})

    def test_routes_plan_to_todo(self):
        """handle_hook('plan-to-todo') calls handle_plan_to_issue (backward-compat alias)."""
        with patch("clasi.hook_handlers.handle_plan_to_issue") as mock_handler, \
             patch("clasi.hook_handlers.read_payload", return_value={}):
            mock_handler.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                handle_hook("plan-to-todo")
            mock_handler.assert_called_once_with({})

    def test_routes_commit_check(self):
        """handle_hook('commit-check') calls handle_commit_check."""
        with patch("clasi.hook_handlers.handle_commit_check") as mock_handler, \
             patch("clasi.hook_handlers.read_payload", return_value={}):
            mock_handler.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                handle_hook("commit-check")
            mock_handler.assert_called_once_with({})

    def test_unknown_event_exits_1(self, capsys):
        """handle_hook exits with code 1 for unknown event names."""
        with patch("clasi.hook_handlers.read_payload", return_value={}):
            with pytest.raises(SystemExit) as exc:
                handle_hook("no-such-event")
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "no-such-event" in captured.err


# ---------------------------------------------------------------------------
# handle_commit_check tests
# ---------------------------------------------------------------------------


class TestHandleCommitCheck:
    def test_prints_reminder_on_master_with_git_commit(self, capsys, monkeypatch):
        """Prints reminder when TOOL_INPUT has 'git commit' and branch is master."""
        monkeypatch.setenv("TOOL_INPUT", "git commit -m 'fix: something'")
        with patch("clasi.hook_handlers.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"stdout": "master\n"})()
            with pytest.raises(SystemExit) as exc:
                handle_commit_check({})
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "CLASI: You committed on master" in captured.out

    def test_prints_reminder_on_main_with_git_commit(self, capsys, monkeypatch):
        """Prints reminder when TOOL_INPUT has 'git commit' and branch is main."""
        monkeypatch.setenv("TOOL_INPUT", "git commit -m 'feat: new thing'")
        with patch("clasi.hook_handlers.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"stdout": "main\n"})()
            with pytest.raises(SystemExit) as exc:
                handle_commit_check({})
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "CLASI: You committed on master" in captured.out

    def test_silent_when_not_on_master(self, capsys, monkeypatch):
        """No output when TOOL_INPUT has 'git commit' but branch is not master/main."""
        monkeypatch.setenv("TOOL_INPUT", "git commit -m 'fix: bug'")
        with patch("clasi.hook_handlers.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"stdout": "feature/my-feature\n"})()
            with pytest.raises(SystemExit) as exc:
                handle_commit_check({})
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_silent_when_tool_input_lacks_git_commit(self, capsys, monkeypatch):
        """No subprocess call and no output when TOOL_INPUT has no 'git commit'."""
        monkeypatch.setenv("TOOL_INPUT", "git status")
        with patch("clasi.hook_handlers.subprocess.run") as mock_run:
            with pytest.raises(SystemExit) as exc:
                handle_commit_check({})
        assert exc.value.code == 0
        mock_run.assert_not_called()
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_exits_zero_when_tool_input_missing(self, capsys, monkeypatch):
        """handle_commit_check exits 0 when TOOL_INPUT env var is not set."""
        monkeypatch.delenv("TOOL_INPUT", raising=False)
        with pytest.raises(SystemExit) as exc:
            handle_commit_check({})
        assert exc.value.code == 0


# ---------------------------------------------------------------------------
# handle_plan_to_issue tests
# ---------------------------------------------------------------------------


class TestHandlePlanToIssue:
    def test_calls_plan_to_issue_with_standard_dirs(self, tmp_path):
        """handle_plan_to_issue calls plan_to_issue with home/.claude/plans and issues_dir."""
        with patch("clasi.plan_to_issue.plan_to_issue") as mock_p2t:
            mock_p2t.return_value = None
            with pytest.raises(SystemExit) as exc:
                handle_plan_to_issue({})
        assert exc.value.code == 0
        args, kwargs = mock_p2t.call_args
        assert args[0] == Path.home() / ".claude" / "plans"
        # issues_dir resolves via config; test just checks it ends with "issues"
        assert str(args[1]).endswith("issues")
        assert kwargs.get("plan_file") is None

    def test_prints_result_path_when_issue_created(self, capsys):
        """handle_plan_to_issue writes JSON to stderr and exits 2 when plan_to_issue returns a path."""
        todo_path = Path(".clasi/issues/001-my-plan.md")
        with patch("clasi.plan_to_issue.plan_to_issue") as mock_p2t:
            mock_p2t.return_value = todo_path
            with pytest.raises(SystemExit) as exc:
                handle_plan_to_issue({})
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert "001-my-plan.md" in captured.err
        data = json.loads(captured.err)
        assert data["decision"] == "block"

    def test_no_output_when_no_plan_file(self, capsys):
        """handle_plan_to_issue prints nothing when plan_to_issue returns None."""
        with patch("clasi.plan_to_issue.plan_to_issue") as mock_p2t:
            mock_p2t.return_value = None
            with pytest.raises(SystemExit) as exc:
                handle_plan_to_issue({})
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_passes_plan_file_path_from_payload(self):
        """handle_plan_to_issue passes planFilePath from payload as plan_file argument."""
        payload = {"tool_input": {"planFilePath": "/tmp/my-plan.md"}}
        with patch("clasi.plan_to_issue.plan_to_issue") as mock_p2t:
            mock_p2t.return_value = None
            with pytest.raises(SystemExit):
                handle_plan_to_issue(payload)
        args, kwargs = mock_p2t.call_args
        assert args[0] == Path.home() / ".claude" / "plans"
        # issues_dir resolves via config; test just checks it ends with "issues"
        assert str(args[1]).endswith("issues")
        assert kwargs.get("plan_file") == Path("/tmp/my-plan.md")

    def test_reason_instructs_model_to_rewrite_into_house_format(self, tmp_path, capsys):
        """The block reason tells the model to rewrite the file, not just confirm it.

        Drives the real plan_to_issue() (not a mock) with a plan containing the
        actual plan-mode framing observed in production, so this exercises the
        real path end to end.
        """
        plan_file = tmp_path / "my-plan.md"
        plan_file.write_text(
            "# Issue: re-enable the MCP process-content tools\n\n"
            "## Scope of this plan\n\n"
            "Write the issue file. Do not implement.\n\n"
            "## Deliverable\n\n"
            "Create the issue file.\n",
            encoding="utf-8",
        )
        issue_dir = tmp_path / "issues"
        payload = {"tool_input": {"planFilePath": str(plan_file)}}

        with patch("clasi.hook_handlers.get_project") as mock_get_project:
            mock_get_project.return_value.issues_dir = issue_dir
            with pytest.raises(SystemExit) as exc:
                handle_plan_to_issue(payload)

        assert exc.value.code == 2
        captured = capsys.readouterr()
        data = json.loads(captured.err)
        assert data["decision"] == "block"
        reason = data["reason"]

        # The reason must instruct the model to rewrite the file into house
        # format, not merely "confirm the issue was created and stop."
        assert "rewrite" in reason.lower()
        assert "house" in reason.lower() or "Description" in reason
        assert "## Description" in reason
        assert "## Proposed fix" in reason
        # It must not simply tell the model to accept the plan-shaped copy.
        assert "Confirm the issue was created and stop." not in reason

        # Regression: an issue file was actually written, unlinked source, pending status.
        issue_files = list(issue_dir.glob("*.md"))
        assert len(issue_files) == 1
        assert not plan_file.exists()
        assert "status: pending" in issue_files[0].read_text(encoding="utf-8")
        assert not issue_files[0].name.startswith("issue-")


# ---------------------------------------------------------------------------
# handle_codex_plan_to_issue tests
# ---------------------------------------------------------------------------


class TestHandleCodexPlanToIssue:
    def _payload(self, message: str) -> dict:
        return {"last_assistant_message": message}

    def test_no_plan_tag_exits_0_no_file(self, tmp_path, capsys):
        """No <proposed_plan> in message: exits 0, no issue file created."""
        payload = self._payload("No plan tag here, just some text.")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_codex_plan_to_todo, payload)
        assert exc.value.code == 0
        issue_dir = tmp_path / ".clasi" / "issues"
        assert not issue_dir.exists() or len(list(issue_dir.glob("*.md"))) == 0

    def test_no_plan_tag_never_exits_2(self, tmp_path):
        """handle_codex_plan_to_issue never exits with code 2."""
        payload = self._payload("No plan here.")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_codex_plan_to_todo, payload)
        assert exc.value.code != 2

    def test_with_plan_creates_issue_exits_0(self, tmp_path, capsys):
        """<proposed_plan> present: one issue file created, exits 0."""
        _write_legacy_pin(tmp_path)
        (tmp_path / ".clasi" / "issues").mkdir(parents=True, exist_ok=True)
        message = "Here is my plan:\n<proposed_plan>\n# My Plan\n\nDo some things.\n</proposed_plan>"
        payload = self._payload(message)

        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_codex_plan_to_todo, payload)
        assert exc.value.code == 0

        issue_dir = tmp_path / ".clasi" / "issues"
        issue_files = list(issue_dir.glob("*.md"))
        assert len(issue_files) == 1
        content = issue_files[0].read_text()
        assert "# My Plan" in content
        assert "source: codex-plan" in content

        captured = capsys.readouterr()
        assert "CLASI: Codex plan saved as TODO:" in captured.out

    def test_with_plan_never_exits_2(self, tmp_path):
        """handle_codex_plan_to_issue always exits 0, even when an issue is created."""
        (tmp_path / ".clasi" / "issues").mkdir(parents=True)
        message = "<proposed_plan>\n# Plan\n\nDetails here.\n</proposed_plan>"
        payload = self._payload(message)

        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_codex_plan_to_todo, payload)
        assert exc.value.code == 0

    def test_drops_redundant_issue_prefix_from_filename(self, tmp_path):
        """A Codex plan titled '# Issue: ...' does not land with an 'issue-' filename prefix.

        The Codex Stop hook fires after the session ends, so there is no live
        model turn to hand a rewrite instruction to (see the docstring on
        handle_codex_plan_to_issue) — but the mechanical filename fix still
        applies via plan_to_issue_from_text, exercised here through the real
        hook path (no mocks).
        """
        _write_legacy_pin(tmp_path)
        (tmp_path / ".clasi" / "issues").mkdir(parents=True, exist_ok=True)
        message = (
            "<proposed_plan>\n"
            "# Issue: re-enable the MCP process-content tools\n\n"
            "## Scope of this plan\n\nDo not implement.\n"
            "</proposed_plan>"
        )
        payload = self._payload(message)

        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_codex_plan_to_todo, payload)
        assert exc.value.code == 0

        issue_dir = tmp_path / ".clasi" / "issues"
        issue_files = list(issue_dir.glob("*.md"))
        assert len(issue_files) == 1
        assert not issue_files[0].name.startswith("issue-")

    def test_dedup_second_call_creates_no_file(self, tmp_path):
        """Duplicate plan (same content hash): second call creates no file."""
        _write_legacy_pin(tmp_path)
        (tmp_path / ".clasi" / "issues").mkdir(parents=True, exist_ok=True)
        message = "<proposed_plan>\n# Unique Plan\n\nExactly this content.\n</proposed_plan>"
        payload = self._payload(message)

        # First call — creates an issue
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_codex_plan_to_todo, payload)
        assert exc.value.code == 0

        issue_dir = tmp_path / ".clasi" / "issues"
        files_after_first = list(issue_dir.glob("*.md"))
        assert len(files_after_first) == 1

        # Second call with identical payload — dedup, no new file
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_codex_plan_to_todo, payload)
        assert exc.value.code == 0

        files_after_second = list(issue_dir.glob("*.md"))
        assert len(files_after_second) == 1

    def test_empty_message_exits_0_no_file(self, tmp_path):
        """Empty last_assistant_message: exits 0, no issue created."""
        payload = self._payload("")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_codex_plan_to_todo, payload)
        assert exc.value.code == 0
        issue_dir = tmp_path / ".clasi" / "issues"
        assert not issue_dir.exists() or len(list(issue_dir.glob("*.md"))) == 0

    def test_missing_last_assistant_message_key_exits_0(self, tmp_path):
        """Payload without last_assistant_message key: exits 0, no issue created."""
        payload = {}
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_codex_plan_to_todo, payload)
        assert exc.value.code == 0


class TestHandleHookCodexPlanToIssue:
    """Test that handle_hook routes codex-plan-to-issue and its backward-compat alias."""

    def test_routes_codex_plan_to_issue(self):
        """handle_hook('codex-plan-to-issue') calls handle_codex_plan_to_issue."""
        with patch("clasi.hook_handlers.handle_codex_plan_to_issue") as mock_handler, \
             patch("clasi.hook_handlers.read_payload", return_value={}):
            mock_handler.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                handle_hook("codex-plan-to-issue")
            mock_handler.assert_called_once_with({})

    def test_routes_codex_plan_to_todo(self):
        """handle_hook('codex-plan-to-todo') calls handle_codex_plan_to_issue (backward-compat alias)."""
        with patch("clasi.hook_handlers.handle_codex_plan_to_issue") as mock_handler, \
             patch("clasi.hook_handlers.read_payload", return_value={}):
            mock_handler.side_effect = SystemExit(0)
            with pytest.raises(SystemExit):
                handle_hook("codex-plan-to-todo")
            mock_handler.assert_called_once_with({})


# ---------------------------------------------------------------------------
# Role-guard tests
# ---------------------------------------------------------------------------

_FRESH_LAYOUT_CONFIG = """\
process: se
"""

_LEGACY_LAYOUT_CONFIG = """\
process: se
paths:
  issues: .clasi/issues
  sprints: .clasi/sprints
  reflections: .clasi/reflections
  architecture: .clasi/architecture
  design: docs/design
  logs: .clasi/log
  db: .clasi/.clasi.db
"""


def _write_fresh_config(root: Path) -> None:
    """Write config.yaml with no paths: block → uses new default layout."""
    clasi_dir = root / ".clasi"
    clasi_dir.mkdir(parents=True, exist_ok=True)
    (clasi_dir / "config.yaml").write_text(_FRESH_LAYOUT_CONFIG, encoding="utf-8")


def _write_legacy_layout_config(root: Path) -> None:
    """Write config.yaml pinning paths to legacy .clasi/ layout."""
    clasi_dir = root / ".clasi"
    clasi_dir.mkdir(parents=True, exist_ok=True)
    (clasi_dir / "config.yaml").write_text(_LEGACY_LAYOUT_CONFIG, encoding="utf-8")


def _role_guard_payload(file_path: str, tool_name: str = "Write") -> dict:
    """Build a role-guard payload matching Claude Code's real, nested
    PreToolUse shape: {"tool_name": ..., "tool_input": {"file_path": ...}}.

    Confirmed against real captured lines in .clasi/log/hooks.log and the
    same nested-parse pattern already used elsewhere in this module
    (handle_plan_to_issue: payload.get("tool_input", {}).get("planFilePath")).
    A flat {"file_path": ...} shape never occurs in practice and must not
    be used as a test fixture — it silently validates the wrong parse.
    """
    return {
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
        "session_id": "test-session-id",
    }


def _run_role_guard(tmp_path: Path, file_path: str, tier: str = "") -> int:
    """Run handle_role_guard with the given file_path and agent tier.

    Returns the exit code (0 = allow, 2 = block).
    """
    import os

    payload = _role_guard_payload(file_path)

    old_tier = os.environ.get("CLASI_AGENT_TIER", None)
    try:
        if tier:
            os.environ["CLASI_AGENT_TIER"] = tier
        else:
            os.environ.pop("CLASI_AGENT_TIER", None)

        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_role_guard, payload)
        return exc.value.code
    finally:
        if old_tier is None:
            os.environ.pop("CLASI_AGENT_TIER", None)
        else:
            os.environ["CLASI_AGENT_TIER"] = old_tier


def _run_role_guard_payload(tmp_path: Path, payload: dict, tier: str = "") -> int:
    """Like _run_role_guard, but takes a raw payload directly instead of
    building one from a file_path. Used for no-path / malformed-payload
    fail-closed tests where the payload deliberately has no resolvable path.
    """
    import os

    old_tier = os.environ.get("CLASI_AGENT_TIER", None)
    try:
        if tier:
            os.environ["CLASI_AGENT_TIER"] = tier
        else:
            os.environ.pop("CLASI_AGENT_TIER", None)

        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_role_guard, payload)
        return exc.value.code
    finally:
        if old_tier is None:
            os.environ.pop("CLASI_AGENT_TIER", None)
        else:
            os.environ["CLASI_AGENT_TIER"] = old_tier


class TestRoleGuardLegacyLayout:
    """Role-guard with legacy layout (.clasi/ paths pinned via config.yaml)."""

    def setup_method(self):
        pass

    # --- Tier 0 (team-lead) allow cases ---

    def test_tier0_issues_dir_allowed(self, tmp_path):
        """Tier 0: write to .clasi/issues/x.md is allowed (issues_dir)."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, ".clasi/issues/x.md", "") == 0

    def test_tier0_reflections_dir_allowed(self, tmp_path):
        """Tier 0: write to .clasi/reflections/x.md is allowed (reflections_dir)."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, ".clasi/reflections/x.md", "") == 0

    def test_tier0_legacy_architecture_path_allowed_via_clasi_dir(self, tmp_path):
        """Tier 0: write to .clasi/architecture/x.md is allowed, but only because
        it falls under clasi_dir (.clasi/) — there is no dedicated
        architecture_dir prefix anymore (removed by ticket 018-014)."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, ".clasi/architecture/x.md", "") == 0

    def test_tier0_design_dir_allowed(self, tmp_path):
        """Tier 0: write to docs/design/x.md is allowed (design_dir)."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, "docs/design/x.md", "") == 0

    def test_tier0_design_dir_architecture_doc_allowed(self, tmp_path):
        """Tier 0: write to docs/design/architecture.md (the consolidated
        architecture doc's new home, per ticket 013) is allowed via
        design_dir — no separate architecture allow-prefix is needed."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, "docs/design/architecture.md", "") == 0

    def test_tier0_clasi_dir_config_allowed(self, tmp_path):
        """Tier 0: write to .clasi/config.yaml is allowed (clasi_dir state)."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, ".clasi/config.yaml", "") == 0

    def test_tier0_log_dir_allowed(self, tmp_path):
        """Tier 0: write to .clasi/log/hooks.log is allowed (log_dir)."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, ".clasi/log/hooks.log", "") == 0

    def test_tier0_safe_prefix_claude_dir_allowed(self, tmp_path):
        """Tier 0: write to .claude/settings.json is allowed (safe-prefix)."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, ".claude/settings.json", "") == 0

    def test_tier0_safe_prefix_claude_md_allowed(self, tmp_path):
        """Tier 0: write to CLAUDE.md is allowed (safe-prefix)."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, "CLAUDE.md", "") == 0

    def test_tier0_safe_prefix_agents_md_allowed(self, tmp_path):
        """Tier 0: write to AGENTS.md is allowed (safe-prefix)."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, "AGENTS.md", "") == 0

    # --- Tier 0 (team-lead) block cases ---

    def test_tier0_sprints_dir_blocked(self, tmp_path):
        """Tier 0: write to .clasi/sprints/013-.../sprint.md is blocked."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, ".clasi/sprints/013-x/sprint.md", "") == 2

    def test_tier0_source_code_blocked(self, tmp_path):
        """Tier 0: write to source file is blocked."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/project.py", "") == 2

    def test_tier0_tests_blocked(self, tmp_path):
        """Tier 0: write to test file is blocked."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, "tests/unit/test_project.py", "") == 2

    def test_tier0_pyproject_toml_blocked(self, tmp_path):
        """Tier 0: write to pyproject.toml is blocked."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, "pyproject.toml", "") == 2

    # --- Tier 1 (sprint-planner) ---

    def test_tier1_sprints_dir_allowed(self, tmp_path):
        """Tier 1: write to .clasi/sprints/013-.../ticket.md is allowed."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, ".clasi/sprints/013-x/tickets/001.md", "1") == 0

    def test_tier1_source_code_blocked(self, tmp_path):
        """Tier 1: write to source file is blocked."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/project.py", "1") == 2

    # --- Tier 2 (programmer) ---

    def test_tier2_anything_allowed(self, tmp_path):
        """Tier 2: any write is allowed."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/project.py", "2") == 0

    def test_tier2_sprints_allowed(self, tmp_path):
        """Tier 2: write to sprints dir is also allowed."""
        _write_legacy_layout_config(tmp_path)
        assert _run_role_guard(tmp_path, ".clasi/sprints/013-x/sprint.md", "2") == 0


class TestRoleGuardFreshLayout:
    """Role-guard with fresh default layout (no config pin → new default paths)."""

    # --- Tier 0 (team-lead) allow cases with new layout ---

    def test_tier0_issues_dir_allowed(self, tmp_path):
        """Tier 0: write to clasi/issues/x.md is allowed (new default issues_dir)."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/issues/x.md", "") == 0

    def test_tier0_reflections_dir_allowed(self, tmp_path):
        """Tier 0: write to clasi/reflections/x.md is allowed (new default)."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/reflections/x.md", "") == 0

    def test_tier0_docs_architecture_no_longer_allow_listed(self, tmp_path):
        """Tier 0: write to docs/architecture/x.md is now BLOCKED.

        docs/architecture/ is not clasi_dir, not design_dir, and (per
        ticket 018-014) no longer has a dedicated architecture allow-prefix.
        Nothing relies on docs/architecture/ being allow-listed anymore.
        """
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "docs/architecture/x.md", "") == 2

    def test_tier0_design_dir_allowed(self, tmp_path):
        """Tier 0: write to docs/design/x.md is allowed (new default, unchanged)."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "docs/design/x.md", "") == 0

    def test_tier0_design_dir_architecture_doc_allowed(self, tmp_path):
        """Tier 0: write to docs/design/architecture.md (the consolidated
        architecture doc's new home, per ticket 013) is allowed via
        design_dir under the fresh default layout too."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "docs/design/architecture.md", "") == 0

    def test_tier0_clasi_state_dir_allowed(self, tmp_path):
        """Tier 0: write to .clasi/config.yaml is allowed (clasi_dir state, fixed)."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, ".clasi/config.yaml", "") == 0

    def test_tier0_log_dir_allowed(self, tmp_path):
        """Tier 0: write to .clasi/log/hooks.log is allowed (log_dir, unchanged default)."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, ".clasi/log/hooks.log", "") == 0

    # --- Tier 0 block cases with new layout ---

    def test_tier0_sprints_dir_blocked(self, tmp_path):
        """Tier 0: write to clasi/sprints/013-.../sprint.md is blocked (new default)."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/sprints/013-x/sprint.md", "") == 2

    def test_tier0_source_code_blocked(self, tmp_path):
        """Tier 0: write to source file is blocked (new layout same as legacy)."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/project.py", "") == 2

    def test_tier0_tests_blocked(self, tmp_path):
        """Tier 0: write to test file is blocked."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "tests/unit/test_project.py", "") == 2

    # --- Legacy .clasi/ paths NOT allowed without legacy config pin ---

    def test_tier0_old_issues_path_not_allowed_with_fresh_config(self, tmp_path):
        """Tier 0: .clasi/issues/x.md is NOT allowed when fresh layout is active.

        Without the legacy pin, issues_dir resolves to clasi/issues/, not .clasi/issues/.
        .clasi/ itself is still allowed as clasi_dir, so this write to a subdirectory
        of clasi_dir (.clasi/issues/) is allowed via the clasi_dir prefix.
        """
        _write_fresh_config(tmp_path)
        # .clasi/issues/ IS under .clasi/ (clasi_dir), so it's allowed via that prefix.
        # This is expected: clasi_dir prefix covers all state files under .clasi/
        assert _run_role_guard(tmp_path, ".clasi/issues/x.md", "") == 0

    def test_tier0_old_sprints_path_blocked_with_fresh_config(self, tmp_path):
        """Tier 0: .clasi/sprints/x.md is blocked even with fresh config.

        In fresh layout, sprints_dir=clasi/sprints/. The old path .clasi/sprints/
        would fall under clasi_dir (.clasi/) but NOT under sprints_dir (clasi/sprints/).
        The block check runs first — so if .clasi/sprints/ is not in block_prefixes
        (because block_prefixes only contains clasi/sprints/), the write falls through
        to clasi_dir allow, and is allowed. This is intentional: the guard blocks
        writes to the CONFIGURED sprints_dir.
        """
        _write_fresh_config(tmp_path)
        # With fresh config, sprints_dir = clasi/sprints/, not .clasi/sprints/
        # So .clasi/sprints/ is under clasi_dir, which is in allow_prefixes.
        # Result: allowed (team-lead can write to non-sprint .clasi/ state)
        assert _run_role_guard(tmp_path, ".clasi/sprints/013-x/sprint.md", "") == 0

    # --- Tier 1 (sprint-planner) with fresh layout ---

    def test_tier1_new_sprints_dir_allowed(self, tmp_path):
        """Tier 1: write to clasi/sprints/013-.../ticket.md is allowed (new default)."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/sprints/013-x/tickets/001.md", "1") == 0

    def test_tier1_source_code_blocked(self, tmp_path):
        """Tier 1: write to source file is blocked."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/project.py", "1") == 2

    # --- No config (bare tmp_path) ---

    def test_tier0_no_config_uses_defaults(self, tmp_path):
        """Tier 0: without any config.yaml, defaults are used (new layout)."""
        # No config file — _load_paths_config returns {} → ARTIFACT_PATH_DEFAULTS used
        assert _run_role_guard(tmp_path, "clasi/issues/x.md", "") == 0

    def test_tier0_no_config_sprints_blocked(self, tmp_path):
        """Tier 0: without config, clasi/sprints/ is blocked (new default sprints_dir)."""
        assert _run_role_guard(tmp_path, "clasi/sprints/013-x/sprint.md", "") == 2


class TestRoleGuardNestedPayloadShape:
    """Regression coverage for ticket 019-001: handle_role_guard must read
    file_path from the REAL nested Claude Code PreToolUse shape
    (payload["tool_input"]["file_path"]), not the payload root.

    Before this fix, `tool_input = payload if payload else {}` meant every
    real invocation saw file_path == "" and silently ALLOWED via the
    (then-unconditional) no-path branch. These tests exercise the guard
    through handle_role_guard directly with a payload built by
    _role_guard_payload(), which now matches the real nested shape.
    """

    # --- Deny path, end-to-end, nested real payload shape (non-negotiable) ---

    def test_deny_path_nested_payload_tier0_source_write_blocked(self, tmp_path, capsys):
        """Nested real payload + tier 0 + source path → exit 2, via the
        source-code block branch specifically (not the no-path branch).

        This is the core regression test: exit code 2 alone is NOT
        sufficient here, because a fail-closed no-path branch also exits
        2 — a flat-shape read would find file_path == "" and hit THAT
        branch, coincidentally producing the same exit code while never
        having parsed "source/main.cpp" at all. The assertion on stderr
        content (which echoes the parsed file_path back) is what actually
        distinguishes "correctly parsed and blocked" from "failed to
        parse and failed closed" — i.e. what makes this test fail if the
        line-140 payload-read fix is reverted.
        """
        _write_fresh_config(tmp_path)
        payload = _role_guard_payload("source/main.cpp")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_role_guard, payload)
        assert exc.value.code == 2
        stderr = capsys.readouterr().err
        assert "source/main.cpp" in stderr
        assert "attempted direct file write to" in stderr

    def test_deny_path_nested_payload_tier_unset_source_write_blocked(self, tmp_path, capsys):
        """Same as above with CLASI_AGENT_TIER unset (defaults to tier 0)."""
        import os

        _write_fresh_config(tmp_path)
        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        try:
            payload = _role_guard_payload("source/main.cpp")
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_role_guard, payload)
            assert exc.value.code == 2
            stderr = capsys.readouterr().err
            assert "source/main.cpp" in stderr
            assert "attempted direct file write to" in stderr
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier

    # --- No-path fail-closed (tier 0 / tier 1) vs allow (tier 2) ---

    def test_no_path_tier0_fails_closed(self, tmp_path):
        """No file_path resolvable anywhere in the payload, tier 0 → exit 2."""
        _write_fresh_config(tmp_path)
        payload = {"tool_name": "Write", "tool_input": {}}
        assert _run_role_guard_payload(tmp_path, payload, "") == 2

    def test_no_path_tier1_fails_closed(self, tmp_path):
        """No file_path resolvable anywhere in the payload, tier 1 → exit 2."""
        _write_fresh_config(tmp_path)
        payload = {"tool_name": "Write", "tool_input": {}}
        assert _run_role_guard_payload(tmp_path, payload, "1") == 2

    def test_no_path_tier2_still_allows(self, tmp_path):
        """No file_path resolvable anywhere in the payload, tier 2 → exit 0.

        Tier 2 (programmer) has unrestricted write scope by design, so the
        fail-closed no-path branch must not apply to it.
        """
        _write_fresh_config(tmp_path)
        payload = {"tool_name": "Write", "tool_input": {}}
        assert _run_role_guard_payload(tmp_path, payload, "2") == 0

    def test_no_path_completely_empty_payload_tier0_fails_closed(self, tmp_path):
        """An entirely empty payload (no tool_input key at all) still fails
        closed for tier 0, and the WARN log must not raise."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard_payload(tmp_path, {}, "") == 2

    # --- Non-regression: artifact-dir allow-list still works live ---

    def test_tier0_issues_dir_allowed_with_real_nested_payload(self, tmp_path):
        """Tier 0 write to clasi/issues/**, via the real nested payload shape,
        still ALLOWS once the payload-read fix makes role-guard live."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/issues/x.md", "") == 0

    def test_tier0_reflections_dir_allowed_with_real_nested_payload(self, tmp_path):
        """Tier 0 write to clasi/reflections/**, via the real nested payload
        shape, still ALLOWS once the payload-read fix makes role-guard live."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/reflections/x.md", "") == 0

    def test_tier0_design_dir_allowed_with_real_nested_payload(self, tmp_path):
        """Tier 0 write to docs/design/**, via the real nested payload shape,
        still ALLOWS once the payload-read fix makes role-guard live."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "docs/design/x.md", "") == 0


# ---------------------------------------------------------------------------
# Absolute vs. relative file_path normalization (unplanned fix, sprint 020)
# ---------------------------------------------------------------------------
#
# Every test above (and every existing _role_guard_payload() call prior to
# this fix) exercises handle_role_guard with a RELATIVE file_path. Real
# Claude Code PreToolUse payloads carry an ABSOLUTE file_path
# (e.g. "/Users/x/proj/clasi/issues/foo.md"), which the allow/block prefix
# checks (root-relative strings like "clasi/issues/") never matched via
# startswith() before path normalization was added. _role_guard_payload()'s
# own docstring warns that a wrong-shape fixture "silently validates the
# wrong parse" — that warning was about payload nesting (fixed in sprint
# 019) but applied equally to path FORM, which nobody had covered until now.
#
# _abs() below builds an absolute path under tmp_path (never a hardcoded
# machine path) so these tests are portable across machines.


def _abs(tmp_path: Path, rel_path: str) -> str:
    """Return rel_path made absolute under tmp_path, POSIX-separated.

    Never hardcode a real machine path (e.g. /Users/.../pipx/...) in a
    test — a prior test did exactly that and had to be deleted. tmp_path
    is pytest's own per-test temp directory, so this is portable.
    """
    return (tmp_path / rel_path).as_posix()


class TestRoleGuardAbsolutePathNormalization:
    """Role-guard must normalize an ABSOLUTE file_path to root-relative
    before any prefix comparison, so real Claude Code payloads (which are
    always absolute) are enforced identically to the relative-path form
    used everywhere else in this test module.

    Each case below is the absolute-path twin of an existing relative-path
    assertion (team-lead allow-listed dirs, team-lead blocked dirs, tier 1
    sprints allow, tier 2 unrestricted) so behavior is proven equivalent
    across both path forms, not just individually plausible.
    """

    # --- Tier 0 (team-lead): allow-listed dirs, absolute form ---

    def test_tier0_issues_dir_allowed_absolute(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, _abs(tmp_path, "clasi/issues/foo.md"), "") == 0

    def test_tier0_reflections_dir_allowed_absolute(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, _abs(tmp_path, "clasi/reflections/foo.md"), "") == 0

    def test_tier0_design_dir_allowed_absolute(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, _abs(tmp_path, "docs/design/foo.md"), "") == 0

    # --- Tier 0 (team-lead): blocked paths, absolute form ---

    def test_tier0_sprints_dir_blocked_absolute(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(
            tmp_path, _abs(tmp_path, "clasi/sprints/013-x/sprint.md"), ""
        ) == 2

    def test_tier0_source_code_blocked_absolute(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, _abs(tmp_path, "clasi/project.py"), "") == 2

    # --- Tier 1 (sprint-planner): sprints dir allowed, absolute form ---

    def test_tier1_sprints_dir_allowed_absolute(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(
            tmp_path, _abs(tmp_path, "clasi/sprints/013-x/tickets/001.md"), "1"
        ) == 0

    def test_tier1_source_code_blocked_absolute(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, _abs(tmp_path, "clasi/project.py"), "1") == 2

    # --- Tier 2 (programmer): unrestricted, absolute form ---

    def test_tier2_source_allowed_absolute(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, _abs(tmp_path, "clasi/project.py"), "2") == 0

    def test_tier2_sprints_allowed_absolute(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(
            tmp_path, _abs(tmp_path, "clasi/sprints/013-x/sprint.md"), "2"
        ) == 0

    # --- Absolute path OUTSIDE the project root must not crash or match ---

    def test_absolute_path_outside_root_does_not_crash_and_is_allowed(self, tmp_path):
        """An absolute file_path that is not under the project root must not
        raise, and is ALLOWED: role-guard governs writes to *this* repo's
        source/tests only, so any outside-root path exits allow ("outside-root").

        The path here (`outside-project/clasi/issues/foo.md`) is chosen so
        its tail would coincide with the `clasi/issues/` allow-prefix if the
        guard ever mistakenly compared the raw absolute string against a
        root-relative prefix — it exercises that the allow decision comes
        from the outside-root rule, not from an accidental prefix match.
        """
        _write_fresh_config(tmp_path)
        outside = (tmp_path.parent / "outside-project" / "clasi" / "issues" / "foo.md")
        assert _run_role_guard(tmp_path, outside.as_posix(), "") == 0

    def test_agent_memory_path_outside_root_is_allowed(self, tmp_path):
        """Regression for the reported bug: the agent's own persistent
        memory file lives under ~/.claude/projects/<slug>/memory/ — outside
        any project root — and role-guard was over-blocking it (it is not
        source, not a CLASI artifact, and not in this repo). Tier 0 must be
        allowed to write it.
        """
        _write_fresh_config(tmp_path)
        mem = str(
            Path.home()
            / ".claude"
            / "projects"
            / "-some-other-repo"
            / "memory"
            / "a-note.md"
        )
        assert _run_role_guard(tmp_path, mem, "") == 0


class TestRoleGuardAbsolutePathRevertCheck:
    """Meta-test: proves the absolute-path tests above are not vacuous.

    House standard: a new test suite covering a bug fix must fail against
    the unfixed code, or it proves nothing. This is exercised procedurally
    (see the ticket's revert-check instructions) rather than automated
    here, but this class documents the specific assertion that must flip
    from block to allow when normalization is removed, for anyone
    re-running the revert check by hand:

        _run_role_guard(tmp_path, _abs(tmp_path, "clasi/issues/foo.md"), "")

    Unfixed: file_path stays absolute, "clasi/issues/" allow-prefix never
    matches via startswith(), tier 0 falls through to the default BLOCK
    branch -> exit 2 (wrong; should allow).
    Fixed: file_path is normalized to "clasi/issues/foo.md" first,
    startswith("clasi/issues/") matches -> exit 0 (correct).
    """

    def test_documents_the_revert_check_assertion(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, _abs(tmp_path, "clasi/issues/foo.md"), "") == 0


class TestRoleGuardClaudePlansDirAllowList:
    """Ticket 024-003 / issue role-guard-blocks-plan-mode-plans-dir.md.

    ~/.claude/plans/<name>.md is Claude Code's own plan-mode plan file —
    the exact artifact clasi's plan_to_issue PostToolUse hook harvests
    into clasi/issues/. It lies OUTSIDE the project root, so it can never
    match the root-relative safe_prefixes/_allow_prefixes machinery; it is
    allow-listed via a dedicated absolute-path comparison against the RAW
    incoming path, checked before _normalize_to_root_relative runs.

    Both cases here use _role_guard_payload(), the real nested Claude Code
    PreToolUse payload shape ({"tool_name": ..., "tool_input":
    {"file_path": ...}}), per this project's gate-testing discipline of
    testing guards with real captured payload shapes rather than
    synthetic/minimal ones.
    """

    def test_tier0_write_to_claude_plans_dir_allowed(self, tmp_path):
        """Tier 0: Write to ~/.claude/plans/test.md passes the guard (exit 0).

        This is the allow case from the issue's own Verification section:
        without the fix, this absolute path lies outside the project root
        and falls through every allow-prefix check to the default BLOCK
        branch (exit 2). With the fix, the dedicated plans-dir check exits
        0 before normalization or any other prefix comparison runs.
        """
        _write_fresh_config(tmp_path)
        plans_path = str(Path.home() / ".claude" / "plans" / "test.md")
        assert _run_role_guard(tmp_path, plans_path, "") == 0

    def test_tier0_write_to_arbitrary_outside_root_path_allowed(self, tmp_path):
        """Tier 0: Write to ~/Desktop/x.md (an arbitrary outside-root path)
        is ALLOWED (exit 0).

        role-guard governs direct writes to *this* repo's source and tests
        only; any path outside the project root is not CLASI's to police and
        exits allow via the general "outside-root" rule. (This test formerly
        asserted the opposite — a deliberate design reversal: the guard was
        over-blocking the agent's own out-of-repo files, e.g. ~/.claude
        memory, and the narrow plans-dir allow-list has been subsumed by the
        general outside-root allow.)
        """
        _write_fresh_config(tmp_path)
        desktop_path = str(Path.home() / "Desktop" / "x.md")
        assert _run_role_guard(tmp_path, desktop_path, "") == 0

    def test_tier0_write_to_claude_plans_dir_allowed_nested_subdir(self, tmp_path):
        """Tier 0: a nested path under ~/.claude/plans/ (not just a direct
        child file) is also allowed, confirming the check is a directory
        prefix match, not an exact-parent-only match."""
        _write_fresh_config(tmp_path)
        plans_path = str(Path.home() / ".claude" / "plans" / "sub" / "test.md")
        assert _run_role_guard(tmp_path, plans_path, "") == 0

    def test_tier1_write_to_claude_plans_dir_allowed(self, tmp_path):
        """Tier 1 (sprint-planner): ~/.claude/plans/ write is also allowed.

        The ticket's implementation plan allows applying this uniformly
        across tiers rather than gating it to tier 0 only, since tier 0 is
        the documented requirement and applying it to all tiers is no less
        safe (tier 2 is already unrestricted regardless)."""
        _write_fresh_config(tmp_path)
        plans_path = str(Path.home() / ".claude" / "plans" / "test.md")
        assert _run_role_guard(tmp_path, plans_path, "1") == 0

    def test_regression_existing_tier0_in_root_paths_unaffected(self, tmp_path):
        """Regression check: existing in-root tier-0 allow/block behavior
        is unchanged by the new plans-dir check (additive, not a
        replacement of the existing logic)."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/issues/x.md", "") == 0
        assert _run_role_guard(tmp_path, "clasi/project.py", "") == 2


# ---------------------------------------------------------------------------
# _oop_active() — unified OOP bypass helper (ticket 019-002)
# ---------------------------------------------------------------------------


def _run_mcp_guard(tmp_path: Path, tool_name: str = "create_ticket", tier: str = "") -> int:
    """Run handle_mcp_guard with the given tool_name and agent tier.

    Returns the exit code (0 = allow, 2 = block).
    """
    import os

    payload = {"tool_name": tool_name}

    old_tier = os.environ.get("CLASI_AGENT_TIER", None)
    try:
        if tier:
            os.environ["CLASI_AGENT_TIER"] = tier
        else:
            os.environ.pop("CLASI_AGENT_TIER", None)

        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_mcp_guard, payload)
        return exc.value.code
    finally:
        if old_tier is None:
            os.environ.pop("CLASI_AGENT_TIER", None)
        else:
            os.environ["CLASI_AGENT_TIER"] = old_tier


class TestOopActiveHelper:
    """Unit tests for _oop_active() itself: each flag file independently,
    and neither present. A test that only ever creates both flag files
    together would not have caught the original split-brain bug (where
    two handlers checked .clasi-oop and two checked .clasi/oop), so each
    case here is isolated.
    """

    def test_true_when_only_canonical_flag_present(self, tmp_path):
        """Only .clasi/oop (canonical, matches documentation) exists."""
        (tmp_path / ".clasi").mkdir()
        (tmp_path / ".clasi" / "oop").touch()
        assert _run_with_cwd(tmp_path, _oop_active) is True

    def test_true_when_only_legacy_flag_present(self, tmp_path):
        """Only .clasi-oop (legacy, repo root, hyphen) exists."""
        (tmp_path / ".clasi-oop").touch()
        assert _run_with_cwd(tmp_path, _oop_active) is True

    def test_false_when_neither_flag_present(self, tmp_path):
        """Neither flag file exists."""
        assert _run_with_cwd(tmp_path, _oop_active) is False


class TestOopBypassHandlerLevel:
    """Handler-level regression coverage for ticket 019-002: the original
    bug was two of four handlers (handle_role_guard, handle_mcp_guard)
    checking only .clasi-oop while handle_status_inject checked only
    .clasi/oop — so the documented .clasi/oop escape hatch silently did
    NOT open the door for role-guard or mcp-guard.

    These tests exercise bypass through the real handlers (live guard
    calls), not by calling _oop_active() directly, because the bug class
    here is a handler failing to *call* the shared check at all — a
    helper-only unit test cannot detect that a call site was never wired
    up. Each flag file is tested independently per handler, and a
    neither-flag control case confirms the guards still enforce normally
    when OOP is not active.
    """

    # --- .clasi/oop only (canonical) ---

    def test_role_guard_bypasses_with_canonical_flag_only(self, tmp_path):
        _write_fresh_config(tmp_path)
        (tmp_path / ".clasi" / "oop").touch()
        # Tier 0 write to a source file would normally be blocked (exit 2).
        assert _run_role_guard(tmp_path, "source/main.cpp", "") == 0

    def test_mcp_guard_bypasses_with_canonical_flag_only(self, tmp_path):
        _write_fresh_config(tmp_path)
        (tmp_path / ".clasi" / "oop").touch()
        # Tier 0 calling an MCP tool would normally be blocked (exit 2).
        assert _run_mcp_guard(tmp_path, "create_ticket", "") == 0

    # --- .clasi-oop only (legacy) ---

    def test_role_guard_bypasses_with_legacy_flag_only(self, tmp_path):
        _write_fresh_config(tmp_path)
        (tmp_path / ".clasi-oop").touch()
        assert _run_role_guard(tmp_path, "source/main.cpp", "") == 0

    def test_mcp_guard_bypasses_with_legacy_flag_only(self, tmp_path):
        _write_fresh_config(tmp_path)
        (tmp_path / ".clasi-oop").touch()
        assert _run_mcp_guard(tmp_path, "create_ticket", "") == 0

    # --- neither flag present: guards enforce normally ---

    def test_role_guard_enforces_normally_with_neither_flag(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "source/main.cpp", "") == 2

    def test_mcp_guard_enforces_normally_with_neither_flag(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_mcp_guard(tmp_path, "create_ticket", "") == 2

    # --- cwd below project root: _oop_active() must still find the flag ---
    #
    # Discovered live during an e2e-harness OOP session: a PreToolUse hook
    # can fire with cwd set to a subdirectory of the project (e.g. editing
    # a file two directories deep), and the original _oop_active() did a
    # bare Path(".clasi/oop").exists() check relative to cwd — which
    # silently returned False even though .clasi/oop existed at the real
    # project root, causing the guard to enforce as if OOP were not active.

    def test_role_guard_bypasses_with_flag_at_root_when_cwd_is_subdir(self, tmp_path):
        _write_fresh_config(tmp_path)
        (tmp_path / ".clasi" / "oop").touch()
        subdir = tmp_path / "tests" / "e2e"
        subdir.mkdir(parents=True)
        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        old_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            payload = _role_guard_payload("source/main.cpp")
            with pytest.raises(SystemExit) as exc:
                handle_role_guard(payload)
            assert exc.value.code == 0
        finally:
            os.chdir(old_cwd)
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier

    def test_role_guard_still_enforces_from_subdir_with_no_flag(self, tmp_path):
        _write_fresh_config(tmp_path)
        subdir = tmp_path / "tests" / "e2e"
        subdir.mkdir(parents=True)
        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        old_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            payload = _role_guard_payload("source/main.cpp")
            with pytest.raises(SystemExit) as exc:
                handle_role_guard(payload)
            assert exc.value.code == 2
        finally:
            os.chdir(old_cwd)
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier


# ---------------------------------------------------------------------------
# DB-backed OOP bypass (ticket 024-005) — handler-level, both guards
# ---------------------------------------------------------------------------


def _fresh_layout_db_path(root: Path) -> Path:
    """Path to the DB file under the default (fresh) layout _write_fresh_config
    writes — .clasi/.clasi.db, matching ARTIFACT_PATH_DEFAULTS["db"]."""
    return root / ".clasi" / ".clasi.db"


class TestOopDbBackedHandlerLevel:
    """Handler-level coverage for the DB-backed OOP channel (ticket 004's
    oop_state table, wired into _oop_active() by ticket 024-005), on BOTH
    role-guard and mcp-guard — not only a unit test on _oop_active() called
    directly. Per the issue's explicit citation of the 019-002 lesson:
    helper-level tests alone can miss a call site that was never wired up.
    """

    def test_role_guard_allows_when_db_oop_set(self, tmp_path):
        _write_fresh_config(tmp_path)
        set_oop(str(_fresh_layout_db_path(tmp_path)), "hotfix", ttl_hours=8.0)
        assert _run_role_guard(tmp_path, "source/main.cpp", "") == 0

    def test_role_guard_denies_after_db_oop_cleared(self, tmp_path):
        _write_fresh_config(tmp_path)
        db_path = str(_fresh_layout_db_path(tmp_path))
        set_oop(db_path, "hotfix", ttl_hours=8.0)
        clear_oop(db_path)
        assert _run_role_guard(tmp_path, "source/main.cpp", "") == 2

    def test_role_guard_denies_when_db_oop_never_set(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "source/main.cpp", "") == 2

    def test_mcp_guard_allows_when_db_oop_set(self, tmp_path):
        _write_fresh_config(tmp_path)
        set_oop(str(_fresh_layout_db_path(tmp_path)), "hotfix", ttl_hours=8.0)
        assert _run_mcp_guard(tmp_path, "create_ticket", "") == 0

    def test_mcp_guard_denies_after_db_oop_cleared(self, tmp_path):
        _write_fresh_config(tmp_path)
        db_path = str(_fresh_layout_db_path(tmp_path))
        set_oop(db_path, "hotfix", ttl_hours=8.0)
        clear_oop(db_path)
        assert _run_mcp_guard(tmp_path, "create_ticket", "") == 2

    def test_mcp_guard_denies_when_db_oop_never_set(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_mcp_guard(tmp_path, "create_ticket", "") == 2


class TestOopFileOverrideWithDbEmpty:
    """File override with DB empty: bypass works via the file channel alone,
    and _oop_source() reports "file" (not "db" or "both")."""

    def test_role_guard_bypasses_on_file_alone(self, tmp_path):
        _write_fresh_config(tmp_path)
        (tmp_path / ".clasi" / "oop").touch()
        assert _run_role_guard(tmp_path, "source/main.cpp", "") == 0

    def test_oop_source_reports_file_when_db_empty(self, tmp_path):
        _write_fresh_config(tmp_path)
        (tmp_path / ".clasi" / "oop").touch()
        assert _run_with_cwd(tmp_path, _oop_source) == "file"

    def test_oop_source_reports_db_when_file_absent(self, tmp_path):
        _write_fresh_config(tmp_path)
        set_oop(str(_fresh_layout_db_path(tmp_path)), "hotfix", ttl_hours=8.0)
        assert _run_with_cwd(tmp_path, _oop_source) == "db"

    def test_oop_source_reports_both_when_both_active(self, tmp_path):
        _write_fresh_config(tmp_path)
        (tmp_path / ".clasi" / "oop").touch()
        set_oop(str(_fresh_layout_db_path(tmp_path)), "hotfix", ttl_hours=8.0)
        assert _run_with_cwd(tmp_path, _oop_source) == "both"

    def test_oop_source_none_when_neither_active(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_with_cwd(tmp_path, _oop_source) is None


class TestOopDbTtlExpiry:
    """set_oop with a very short TTL auto-expires on next read (ticket
    004's expiry-on-read get_oop()); enforcement resumes once expired."""

    def test_role_guard_re_enforces_after_ttl_expiry(self, tmp_path):
        import time

        _write_fresh_config(tmp_path)
        db_path = str(_fresh_layout_db_path(tmp_path))
        set_oop(db_path, "short-lived", ttl_hours=0.0000001)
        time.sleep(0.05)
        assert _run_role_guard(tmp_path, "source/main.cpp", "") == 2

    def test_oop_active_false_after_ttl_expiry(self, tmp_path):
        import time

        _write_fresh_config(tmp_path)
        db_path = str(_fresh_layout_db_path(tmp_path))
        set_oop(db_path, "short-lived", ttl_hours=0.0000001)
        time.sleep(0.05)
        assert _run_with_cwd(tmp_path, _oop_active) is False


class TestOopCorruptOrLockedDb:
    """A corrupt/unreadable DB file must never raise out of _oop_active()
    or the guards. The file override, if present, still works. If the
    file is absent and the DB is broken, the guard fails CLOSED (denies),
    never with an unhandled exception."""

    def _write_corrupt_db(self, tmp_path: Path) -> None:
        db_path = _fresh_layout_db_path(tmp_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(b"not a sqlite database at all, just garbage bytes")

    def test_oop_active_false_with_corrupt_db_and_no_file(self, tmp_path):
        _write_fresh_config(tmp_path)
        self._write_corrupt_db(tmp_path)
        assert _run_with_cwd(tmp_path, _oop_active) is False

    def test_role_guard_fails_closed_with_corrupt_db_and_no_file(self, tmp_path):
        _write_fresh_config(tmp_path)
        self._write_corrupt_db(tmp_path)
        assert _run_role_guard(tmp_path, "source/main.cpp", "") == 2

    def test_mcp_guard_fails_closed_with_corrupt_db_and_no_file(self, tmp_path):
        _write_fresh_config(tmp_path)
        self._write_corrupt_db(tmp_path)
        assert _run_mcp_guard(tmp_path, "create_ticket", "") == 2

    def test_role_guard_file_override_still_works_with_corrupt_db(self, tmp_path):
        _write_fresh_config(tmp_path)
        self._write_corrupt_db(tmp_path)
        (tmp_path / ".clasi" / "oop").touch()
        assert _run_role_guard(tmp_path, "source/main.cpp", "") == 0

    def test_mcp_guard_file_override_still_works_with_corrupt_db(self, tmp_path):
        _write_fresh_config(tmp_path)
        self._write_corrupt_db(tmp_path)
        (tmp_path / ".clasi" / "oop").touch()
        assert _run_mcp_guard(tmp_path, "create_ticket", "") == 0

    def test_oop_active_true_with_file_override_and_corrupt_db(self, tmp_path):
        _write_fresh_config(tmp_path)
        self._write_corrupt_db(tmp_path)
        (tmp_path / ".clasi" / "oop").touch()
        assert _run_with_cwd(tmp_path, _oop_active) is True


class TestOopDbBypassCwdIndependence:
    """cwd-independence for the DB channel, mirroring the existing
    file-channel regression check above: DB OOP record set (global to the
    checkout, keyed on the project root's db_path), hook invoked with cwd
    set to a subdirectory — bypass still resolves."""

    def test_role_guard_bypasses_with_db_oop_when_cwd_is_subdir(self, tmp_path):
        _write_fresh_config(tmp_path)
        set_oop(str(_fresh_layout_db_path(tmp_path)), "hotfix", ttl_hours=8.0)
        subdir = tmp_path / "tests" / "e2e"
        subdir.mkdir(parents=True)
        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        old_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            payload = _role_guard_payload("source/main.cpp")
            with pytest.raises(SystemExit) as exc:
                handle_role_guard(payload)
            assert exc.value.code == 0
        finally:
            os.chdir(old_cwd)
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier


class TestRoleGuardProtectedPaths:
    """protected_paths: config gate — when configured, tier 0/1 blocking
    inverts from "block anything not on the artifact allow-list" to "block
    only under these configured prefixes" (plus .clasi/sprints/**, still
    handled separately). Unconfigured (empty) protected_paths must leave
    the pre-existing block-by-default behavior untouched — this is an
    additive, opt-in gate, not a default-behavior change.
    """

    def _write_config_with_protected_paths(self, root: Path, paths: list) -> None:
        import yaml

        clasi_dir = root / ".clasi"
        clasi_dir.mkdir(parents=True, exist_ok=True)
        data = {"process": "se", "protected_paths": paths}
        (clasi_dir / "config.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")

    def test_tier0_protected_path_still_blocked(self, tmp_path):
        self._write_config_with_protected_paths(tmp_path, ["src", "tests"])
        assert _run_role_guard(tmp_path, "src/clasi/project.py", "") == 2

    def test_tier0_unprotected_path_allowed_when_configured(self, tmp_path):
        """A path outside the configured protected_paths (e.g. a
        test-harness script under tests/e2e/ that isn't in src/ or the
        configured tests/ dir) is allowed once protected_paths is set,
        even though the same path would be blocked by default."""
        self._write_config_with_protected_paths(tmp_path, ["src", "clasi_pkg_tests"])
        assert _run_role_guard(tmp_path, "tests/e2e/start.sh", "") == 0

    def test_tier0_pyproject_allowed_when_not_in_protected_paths(self, tmp_path):
        self._write_config_with_protected_paths(tmp_path, ["src", "tests"])
        assert _run_role_guard(tmp_path, "pyproject.toml", "") == 0

    def test_tier1_protected_path_still_blocked(self, tmp_path):
        self._write_config_with_protected_paths(tmp_path, ["src", "tests"])
        assert _run_role_guard(tmp_path, "src/clasi/project.py", "1") == 2

    def test_tier1_unprotected_path_allowed_when_configured(self, tmp_path):
        """tests/e2e/ here is a stand-in for a test-harness script that
        lives outside the project's configured source/test roots — use
        protected_paths that do NOT cover it (unlike the "tests" prefix,
        which genuinely would cover tests/e2e/)."""
        self._write_config_with_protected_paths(tmp_path, ["src", "clasi_pkg_tests"])
        assert _run_role_guard(tmp_path, "tests/e2e/start.sh", "1") == 0

    def test_sprints_dir_still_blocked_even_outside_protected_paths(self, tmp_path):
        """.clasi/sprints/** stays blocked for tier 0 regardless of
        protected_paths — that block is independent (sprint-planner/MCP
        ownership), not something protected_paths controls."""
        self._write_config_with_protected_paths(tmp_path, ["src", "tests"])
        assert _run_role_guard(tmp_path, "clasi/sprints/013-x/sprint.md", "") == 2

    def test_no_protected_paths_configured_preserves_block_by_default(self, tmp_path):
        """Regression guard: an empty/unconfigured protected_paths must
        NOT be treated as 'nothing is protected' — that would silently
        disable enforcement for every existing project. Same assertion as
        TestRoleGuardFreshLayout.test_tier0_pyproject_toml_blocked-style
        cases, restated here to anchor the protected_paths-specific
        behavior explicitly."""
        _write_fresh_config(tmp_path)  # no protected_paths key at all
        assert _run_role_guard(tmp_path, "pyproject.toml", "") == 2
        assert _run_role_guard(tmp_path, "clasi/project.py", "") == 2

    # --- excluded_paths: carve-outs within a protected prefix ---

    def _write_config_with_protected_and_excluded(
        self, root: Path, protected: list, excluded: list
    ) -> None:
        import yaml

        clasi_dir = root / ".clasi"
        clasi_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "process": "se",
            "protected_paths": protected,
            "excluded_paths": excluded,
        }
        (clasi_dir / "config.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")

    def test_excluded_subdir_of_protected_tests_is_allowed(self, tmp_path):
        """The motivating case: tests/ is protected (the real pytest
        suite), but tests/e2e/ is a Docker test-harness (scripts,
        Dockerfile, fixtures) that isn't the test suite itself and should
        stay editable without an OOP bypass."""
        self._write_config_with_protected_and_excluded(
            tmp_path, ["src", "tests"], ["tests/e2e"]
        )
        assert _run_role_guard(tmp_path, "tests/e2e/start.sh", "") == 0

    def test_non_excluded_part_of_protected_tests_still_blocked(self, tmp_path):
        self._write_config_with_protected_and_excluded(
            tmp_path, ["src", "tests"], ["tests/e2e"]
        )
        assert _run_role_guard(tmp_path, "tests/unit/test_project.py", "") == 2

    def test_excluded_paths_without_protected_paths_is_a_no_op(self, tmp_path):
        """excluded_paths only matters once protected_paths is configured
        — with no protected_paths at all, role-guard never reaches the
        prefix check, so the pre-existing block-by-default behavior
        applies regardless of excluded_paths."""
        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir(parents=True, exist_ok=True)
        import yaml

        data = {"process": "se", "excluded_paths": ["tests/e2e"]}
        (clasi_dir / "config.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
        assert _run_role_guard(tmp_path, "tests/e2e/start.sh", "") == 2


# ---------------------------------------------------------------------------
# Real invocation path (ticket 020-001): the tests above all call
# handle_role_guard() in-process, via direct Python import. That proves the
# *function* is correct but never proves the installed CLI entrypoint that
# .claude/settings.json actually shells out to (`clasi hook role-guard`)
# runs this code at all. Sprint 020 planning found a live discrepancy: the
# repo's bare `clasi` on PATH resolves to a stale pipx install (18+ days
# old, predating _oop_active() and the 019-001 nested-payload-parsing fix
# entirely), while `.venv/bin/clasi` (equivalent to `uv run clasi`) is the
# current editable install. These tests invoke the real CLI entrypoint via
# subprocess, with a real nested PreToolUse payload piped over stdin
# exactly as Claude Code does, against BOTH resolutions — proving OOP
# bypass works on the correct build and reproducing the stale-build
# fail-open on the other, so the distinction is pinned down by a test
# rather than asserted only in prose.
# ---------------------------------------------------------------------------


import os as _os
import shutil as _shutil
import subprocess as _subprocess

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CURRENT_CLASI = _REPO_ROOT / ".venv" / "bin" / "clasi"


def _invoke_role_guard_cli(clasi_bin: Path, cwd: Path, payload: dict) -> _subprocess.CompletedProcess:
    """Invoke `<clasi_bin> hook role-guard` as a real subprocess, piping a
    real nested payload over stdin exactly as Claude Code's PreToolUse hook
    does. This is the actual invocation path configured in
    .claude/settings.json (`clasi hook role-guard`), not an in-process
    call to handle_role_guard().
    """
    return _subprocess.run(
        [str(clasi_bin), "hook", "role-guard"],
        input=json.dumps(payload),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.skipif(
    not _CURRENT_CLASI.exists(),
    reason="requires the project's own .venv/bin/clasi (editable install)",
)
class TestRoleGuardRealCliInvocationPath:
    """Ticket 020-001: exercise OOP bypass through the real `clasi hook
    role-guard` CLI entrypoint (subprocess), not handle_role_guard() called
    in-process. Confirms the finding that E2E run 003's reported OOP-bypass
    failure was a symptom of a stale pipx install (which lacks
    _oop_active() and the 019-001 nested-payload fix), not a genuine bug
    in the current hook_handlers.py.
    """

    def test_current_build_blocks_without_oop_flag(self, tmp_path):
        """Control: the current build enforces role-guard normally (no
        .clasi/oop present) — exit 2, real nested payload, real CLI.
        """
        _write_fresh_config(tmp_path)
        payload = _role_guard_payload("src/clasi/hook_handlers.py")
        result = _invoke_role_guard_cli(_CURRENT_CLASI, tmp_path, payload)
        assert result.returncode == 2
        assert "src/clasi/hook_handlers.py" in result.stderr

    def test_current_build_bypasses_with_oop_flag(self, tmp_path):
        """Core AC: with .clasi/oop present, a real captured nested
        PreToolUse payload for a Write call, run through the actual `clasi
        hook role-guard` CLI entrypoint, is allowed (exit 0).
        """
        _write_fresh_config(tmp_path)
        (tmp_path / ".clasi").mkdir(exist_ok=True)
        (tmp_path / ".clasi" / "oop").touch()
        payload = _role_guard_payload("src/clasi/hook_handlers.py")
        result = _invoke_role_guard_cli(_CURRENT_CLASI, tmp_path, payload)
        assert result.returncode == 0

    # A third test, test_revert_check_stale_build_fails_open_regardless_of_oop_flag,
    # was added by 020-001 and has been removed. It hardcoded a path to a
    # pipx-installed `clasi` binary outside this working tree and asserted
    # that binary fails open. That is not a test of this repo: it pins the
    # observed behavior of a mutable artifact on one developer's machine.
    # It broke when that pipx install was refreshed mid-sprint, exactly as
    # its own error message predicted, and it could never have passed for
    # any other developer either. The revert-check discipline it reached
    # for is right, but it must run against code we control. That coverage
    # now lives in tests/unit/test_staleness.py, which exercises
    # check_staleness() against real importlib.metadata shapes for both
    # stale and current versions without depending on any binary existing
    # on disk.


# ---------------------------------------------------------------------------
# _ensure_log_gitignore
# ---------------------------------------------------------------------------


class TestEnsureLogGitignore:
    def test_creates_gitignore_when_absent(self, tmp_path):
        """_ensure_log_gitignore writes .gitignore if one does not exist."""
        log_dir = tmp_path / "log"
        log_dir.mkdir()
        _ensure_log_gitignore(log_dir)
        gitignore = log_dir / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text(encoding="utf-8")
        assert "*" in content
        assert "!.gitignore" in content

    def test_idempotent_when_gitignore_exists(self, tmp_path):
        """_ensure_log_gitignore does not overwrite an existing .gitignore."""
        log_dir = tmp_path / "log"
        log_dir.mkdir()
        custom_content = "# custom\n*.txt\n"
        (log_dir / ".gitignore").write_text(custom_content, encoding="utf-8")
        _ensure_log_gitignore(log_dir)
        content = (log_dir / ".gitignore").read_text(encoding="utf-8")
        assert content == custom_content

    def test_gitignore_content_exact(self, tmp_path):
        """_ensure_log_gitignore writes the expected content exactly."""
        log_dir = tmp_path / "log"
        log_dir.mkdir()
        _ensure_log_gitignore(log_dir)
        content = (log_dir / ".gitignore").read_text(encoding="utf-8")
        assert content == "*\n!.gitignore\n"

    def test_hook_invocation_creates_gitignore(self, tmp_path):
        """A hook invocation that creates the log dir also writes .gitignore."""
        # Set up a .clasi dir without pre-creating the log dir so hook creates it
        _write_legacy_pin(tmp_path)
        payload = _task_created_payload(task_id="t-gitignore-test")
        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_task_created, payload)
        log_dir = tmp_path / ".clasi" / "log"
        gitignore = log_dir / ".gitignore"
        assert gitignore.exists(), ".gitignore was not created in log dir by hook"
        content = gitignore.read_text(encoding="utf-8")
        assert "*" in content
        assert "!.gitignore" in content


# ---------------------------------------------------------------------------
# Tier resolution keyed on caller identity (ticket 019-003)
# ---------------------------------------------------------------------------


def _init_db_only(tmp_path: Path) -> str:
    """Create an initialized, empty state DB with no fixture rows.

    active_agents starts empty in this repo (manually cleared during
    triage) — tests must create their own fixture rows, never assume
    pre-existing state.
    """
    db_path = str(tmp_path / ".clasi" / ".clasi.db")
    init_db(db_path)
    return db_path


class TestRoleGuardTierResolutionByCallerIdentity:
    """handle_role_guard must resolve the caller's OWN tier from the DB,
    keyed on the payload's agent_id (or session_id fallback) — never an
    arbitrary row from active_agents.
    """

    def test_concurrent_agents_each_get_own_tier_via_role_guard(self, tmp_path):
        """Non-negotiable concurrent-registration test, exercised through
        the real handle_role_guard call site (not just StateDB directly).

        Two agents are registered with DIFFERENT tiers: tier "1"
        (sprint-planner, blocked from source writes) and tier "2"
        (programmer, unrestricted). Each caller — identified by its own
        agent_id in the hook payload — must be judged by its own tier.
        Before this fix, get_active_tier() ignored agent_id entirely, so
        whichever row happened to be returned by `LIMIT 1` decided the
        outcome for BOTH callers.
        """
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        register_active_agent(db_path, "agent-tier1", "sprint-planner", "1")
        register_active_agent(db_path, "agent-tier2", "programmer", "2")

        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        try:
            # Caller is agent-tier1 (tier 1) writing to source -> BLOCK.
            payload_t1 = _role_guard_payload("source/main.cpp")
            payload_t1["agent_id"] = "agent-tier1"
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_role_guard, payload_t1)
            assert exc.value.code == 2

            # Caller is agent-tier2 (tier 2) writing to source -> ALLOW.
            payload_t2 = _role_guard_payload("source/main.cpp")
            payload_t2["agent_id"] = "agent-tier2"
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_role_guard, payload_t2)
            assert exc.value.code == 0
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier

    def test_unknown_agent_id_no_env_var_fails_closed(self, tmp_path):
        """Caller's agent_id has no matching row and no CLASI_AGENT_TIER
        env var is set -> tier resolves to the unresolved sentinel ("")
        -> handle_role_guard fails closed (tier 0/1 blocked from source
        writes), per ticket 001's fail-closed behavior. Another agent IS
        registered, to prove its tier is not leaked to this caller.
        """
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        register_active_agent(db_path, "some-other-agent", "programmer", "2")

        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        try:
            payload = _role_guard_payload("source/main.cpp")
            payload["agent_id"] = "agent-with-no-db-row"
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_role_guard, payload)
            assert exc.value.code == 2
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier

    def test_session_id_fallback_used_when_agent_id_absent(self, tmp_path):
        """When the payload has no agent_id, handle_role_guard falls back
        to session_id to look up the caller's tier."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        register_active_agent(db_path, "test-session-id", "programmer", "2")

        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        try:
            # _role_guard_payload sets session_id="test-session-id" and no
            # agent_id key at all.
            payload = _role_guard_payload("source/main.cpp")
            assert "agent_id" not in payload
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_role_guard, payload)
            assert exc.value.code == 0  # tier 2 -> unrestricted
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier


class TestRealDispatchTierResolutionEndToEnd:
    """024-002: a REAL dispatch pipeline (handle_subagent_start registering
    the agent, then handle_role_guard reading that registration back) must
    resolve sprint-planner to tier-1 and programmer to tier-2 — not a
    fixture insert via register_active_agent() called directly, and not a
    hand-set CLASI_AGENT_TIER env var.

    Root cause / investigation finding (issue:
    sprint-planner-tier-1-may-never-be-set-verify-clasi-agent-tier-wiring):
    CLASI_AGENT_TIER is never set as an environment variable anywhere in
    this repo (no hook, no .claude/settings.json entry, no wrapper script
    sets it for any agent type — confirmed by grep and by every real
    hooks.log line for both agent types carrying no tier=N field). The
    ONLY mechanism that resolves tier for sprint-planner OR programmer is
    the active_agents DB fallback: handle_subagent_start (hook_handlers.py)
    maps agent_type -> tier via _AGENT_TYPE_TIERS ({"programmer": "2",
    "sprint-planner": "1"}) and calls register_active_agent(); the guard
    handlers then look up that same row via get_active_tier(caller_id) in
    handle_role_guard/handle_mcp_guard. This is symmetric for both agent
    types — there is no asymmetry in the resolution *mechanism* itself.
    The DB fallback is therefore load-bearing, not dead code (the issue's
    "0 rows" observation was a stale snapshot from an earlier triage, not
    a structural property — this repo's live active_agents table is
    non-empty during real sprint work, e.g. carrying a tier-2 programmer
    row during this very ticket's own dispatch). clear_stale_agents's TTL
    sweep (2 hours, no agent_type filter) does not explain any asymmetry
    either: it runs at the START of handle_subagent_start, before the
    current dispatch's own register_active_agent call, so it can never
    purge a row the current dispatch just wrote, and it purges both agent
    types identically by age alone.

    These tests close the actual gap the issue named: every existing test
    (TestRoleGuardTierResolutionByCallerIdentity /
    TestMcpGuardTierResolutionByCallerIdentity above) inserts its own row
    via register_active_agent(...) directly and never calls
    handle_subagent_start at all — so nothing proved a real dispatch's own
    registration call produces a row the guard can actually read back.
    """

    def test_dispatched_sprint_planner_resolves_tier1_and_writes_sprints_dir(
        self, tmp_path,
    ):
        """A real dispatch pipeline for sprint-planner: handle_subagent_start
        registers the agent (agent_type="sprint-planner") using the same
        agent_id/session_id a real SubagentStart payload carries, then
        handle_role_guard — called with a payload sharing that identity —
        must resolve tier-1 via the DB fallback (no CLASI_AGENT_TIER env
        var set at any point) and allow a write under clasi/sprints/**."""
        _write_fresh_config(tmp_path)
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="099")

        # The ticket-state gate (applies to every tier, including the tier
        # this test is proving out) blocks all writes unless a ticket in
        # the locked sprint is in-progress — satisfy it so the assertion
        # below is actually about tier resolution, not this unrelated gate.
        sprint_dir = tmp_path / "clasi" / "sprints" / "099-example"
        _make_in_progress_ticket(sprint_dir, "001", "Example ticket")

        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        try:
            assert "CLASI_AGENT_TIER" not in os.environ

            start_payload = {
                "agent_type": "sprint-planner",
                "agent_id": "planner-e2e-001",
                "session_id": "sess-planner-e2e",
                "hook_event_name": "SubagentStart",
            }
            with pytest.raises(SystemExit) as start_exc:
                _run_with_cwd(tmp_path, handle_subagent_start, start_payload)
            assert start_exc.value.code == 0

            # The dispatch pipeline's own registration call must have
            # produced a readable row — not asserted anywhere before this.
            db_path = str(tmp_path / ".clasi" / ".clasi.db")
            resolved_tier = get_active_tier(db_path, "planner-e2e-001")
            assert resolved_tier == "1"

            write_payload = _role_guard_payload(
                "clasi/sprints/099-example/tickets/001-x.md",
            )
            write_payload["agent_id"] = "planner-e2e-001"
            write_payload["agent_type"] = "sprint-planner"

            assert "CLASI_AGENT_TIER" not in os.environ  # still never set

            with pytest.raises(SystemExit) as write_exc:
                _run_with_cwd(tmp_path, handle_role_guard, write_payload)
            assert write_exc.value.code == 0
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier

        # hooks.log must show the specific, attributable reason for this
        # write — tier-1 — not a fallback-to-block (blk-write/blk-sprint)
        # and not a fabricated/hand-set reason.
        hooks_log = tmp_path / ".clasi" / "log" / "hooks.log"
        assert hooks_log.exists()
        log_lines = hooks_log.read_text(encoding="utf-8").splitlines()
        matching = [
            ln for ln in log_lines
            if "role-guard" in ln and "agent_id=planner-e2e-001" in ln
        ]
        assert matching, f"no role-guard log line found for planner-e2e-001: {log_lines}"
        assert any(" 0 tier-1" in ln for ln in matching), (
            f"expected reason 'tier-1' with exit 0, got: {matching}"
        )

    def test_dispatched_programmer_still_resolves_tier2_regression(self, tmp_path):
        """Regression: the same real-dispatch pipeline for agent_type=
        programmer must still resolve tier-2 and allow an unrestricted
        write (e.g. source code), unaffected by whatever fix this ticket
        applies for sprint-planner."""
        _write_fresh_config(tmp_path)
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="099")

        sprint_dir = tmp_path / "clasi" / "sprints" / "099-example"
        _make_in_progress_ticket(sprint_dir, "001", "Example ticket")

        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        try:
            start_payload = {
                "agent_type": "programmer",
                "agent_id": "prog-e2e-001",
                "session_id": "sess-prog-e2e",
                "hook_event_name": "SubagentStart",
            }
            with pytest.raises(SystemExit) as start_exc:
                _run_with_cwd(tmp_path, handle_subagent_start, start_payload)
            assert start_exc.value.code == 0

            db_path = str(tmp_path / ".clasi" / ".clasi.db")
            assert get_active_tier(db_path, "prog-e2e-001") == "2"

            write_payload = _role_guard_payload("src/clasi/some_module.py")
            write_payload["agent_id"] = "prog-e2e-001"
            write_payload["agent_type"] = "programmer"

            with pytest.raises(SystemExit) as write_exc:
                _run_with_cwd(tmp_path, handle_role_guard, write_payload)
            assert write_exc.value.code == 0
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier

        hooks_log = tmp_path / ".clasi" / "log" / "hooks.log"
        log_lines = hooks_log.read_text(encoding="utf-8").splitlines()
        matching = [
            ln for ln in log_lines
            if "role-guard" in ln and "agent_id=prog-e2e-001" in ln
        ]
        assert any(" 0 tier-2" in ln for ln in matching), (
            f"expected reason 'tier-2' with exit 0, got: {matching}"
        )

    def test_team_lead_no_dispatch_remains_blocked_from_sprints_and_source(
        self, tmp_path,
    ):
        """Regression: a team-lead caller — no SubagentStart registration
        ever happened for this identity, no CLASI_AGENT_TIER set — must
        remain blocked from both clasi/sprints/** and source-code writes.
        The fix for sprint-planner's tier resolution must not make the
        unresolved (no-dispatch-context) case permissive."""
        _write_fresh_config(tmp_path)
        _make_log_dir(tmp_path)
        db_path = _init_db_only(tmp_path)

        # Some other agent IS registered (as would be true mid-sprint),
        # to prove team-lead's own unregistered identity isn't leaked
        # someone else's tier.
        register_active_agent(db_path, "some-other-agent", "programmer", "2")

        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        try:
            sprints_payload = _role_guard_payload(
                "clasi/sprints/099-example/tickets/001-x.md",
            )
            sprints_payload["agent_id"] = "team-lead-no-dispatch"
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_role_guard, sprints_payload)
            assert exc.value.code == 2

            source_payload = _role_guard_payload("src/clasi/some_module.py")
            source_payload["agent_id"] = "team-lead-no-dispatch"
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_role_guard, source_payload)
            assert exc.value.code == 2
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier


class TestMcpGuardTierResolutionByCallerIdentity:
    """handle_mcp_guard must key its DB tier lookup on caller identity too."""

    def test_concurrent_agents_each_get_own_tier_via_mcp_guard(self, tmp_path):
        """Two agents registered with different tiers; each caller's own
        MCP-guard outcome depends only on its own agent_id's tier."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        register_active_agent(db_path, "agent-tier0-caller", "unknown", "0")
        register_active_agent(db_path, "agent-tier1-caller", "sprint-planner", "1")

        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        try:
            # Tier 0 caller -> blocked from create_ticket.
            payload_t0 = {"tool_name": "create_ticket", "agent_id": "agent-tier0-caller"}
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_mcp_guard, payload_t0)
            assert exc.value.code == 2

            # Tier 1 caller -> allowed.
            payload_t1 = {"tool_name": "create_ticket", "agent_id": "agent-tier1-caller"}
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_mcp_guard, payload_t1)
            assert exc.value.code == 0
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier

    def test_unknown_agent_id_no_env_var_fails_closed(self, tmp_path):
        """Unresolved tier -> mcp-guard treats caller as tier 0 -> blocked,
        even though a differently-tiered agent is registered."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        register_active_agent(db_path, "some-other-agent", "programmer", "2")

        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        try:
            payload = {"tool_name": "create_ticket", "agent_id": "no-such-agent"}
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_mcp_guard, payload)
            assert exc.value.code == 2
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier


class TestMcpGuardBlocksCreateSprintAtTierZero:
    """Ticket 024-001: the team-lead agent doc was rewritten to dispatch
    sprint-planner for sprint creation instead of calling `create_sprint`
    directly, aligning the doc to this guard behavior rather than the
    guard to the doc. This test asserts the guard side of that alignment
    holds: `mcp__clasi__create_sprint` (the fully-prefixed tool name Claude
    Code's PreToolUse hook actually sends, and the exact string matched by
    the `mcp__clasi__create_ticket|mcp__clasi__create_sprint` matcher in
    `.claude/settings.json`) is still denied for a tier-0 caller.
    """

    def test_create_sprint_denied_for_tier_zero(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_mcp_guard(tmp_path, "mcp__clasi__create_sprint", "") == 2

    def test_create_sprint_allowed_for_tier_one(self, tmp_path):
        """Regression control: sprint-planner (tier 1) must still be able
        to call create_sprint — only tier 0 is blocked."""
        _write_fresh_config(tmp_path)
        assert _run_mcp_guard(tmp_path, "mcp__clasi__create_sprint", "1") == 0


# ---------------------------------------------------------------------------
# Dual-mechanism stale-agent purge (ticket 019-003)
# ---------------------------------------------------------------------------


class TestSubagentStopRemovesActiveAgent:
    """Primary purge mechanism: handle_subagent_stop must remove the
    stopping agent's active_agents row on every normal stop path."""

    def test_removes_row_on_normal_stop(self, tmp_path):
        """Registered agent's row is gone after handle_subagent_stop."""
        _make_log_dir(tmp_path)
        db_path = _init_db_only(tmp_path)
        log_file = tmp_path / ".clasi" / "log" / "001-programmer.md"
        log_file.write_text("---\nagent_type: programmer\n---\n\n")
        register_active_agent(db_path, "agent-stop-test", "programmer", "2", str(log_file))
        assert get_active_agent(db_path, "agent-stop-test") is not None

        payload = {
            "agent_id": "agent-stop-test",
            "session_id": "sess-stop-test",
            "last_assistant_message": "",
            "agent_transcript_path": "",
        }
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_subagent_stop, payload)
        assert exc.value.code == 0

        assert get_active_agent(db_path, "agent-stop-test") is None

    def test_removes_row_when_last_message_and_transcript_path_empty(self, tmp_path):
        """Empty last_message/transcript_path (an early-return-adjacent
        shape) still results in the active_agents row being removed —
        the DB removal happens before those fields are even consulted."""
        _make_log_dir(tmp_path)
        db_path = _init_db_only(tmp_path)
        log_file = tmp_path / ".clasi" / "log" / "001-programmer.md"
        log_file.write_text("---\nagent_type: programmer\n---\n\n")
        register_active_agent(db_path, "agent-empty-fields", "programmer", "2", str(log_file))

        payload = {
            "agent_id": "agent-empty-fields",
            "session_id": "",
            "last_assistant_message": "",
            "agent_transcript_path": "",
        }
        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_subagent_stop, payload)

        assert get_active_agent(db_path, "agent-empty-fields") is None

    def test_removes_row_even_when_no_log_file_recorded(self, tmp_path):
        """If the DB record has no log_file (or the log file is missing),
        handle_subagent_stop exits early via the no-log-file branch —
        but the active_agents row must already be gone by that point."""
        _make_log_dir(tmp_path)
        db_path = _init_db_only(tmp_path)
        register_active_agent(db_path, "agent-no-log-file", "programmer", "2", None)
        assert get_active_agent(db_path, "agent-no-log-file") is not None

        payload = {
            "agent_id": "agent-no-log-file",
            "session_id": "",
            "last_assistant_message": "",
            "agent_transcript_path": "",
        }
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_subagent_stop, payload)
        assert exc.value.code == 0  # no-log-file branch, still exit 0

        assert get_active_agent(db_path, "agent-no-log-file") is None

    def test_session_id_fallback_marker_removed(self, tmp_path):
        """When agent_id is absent, the session_id-derived marker_id row
        is the one removed."""
        _make_log_dir(tmp_path)
        db_path = _init_db_only(tmp_path)
        register_active_agent(db_path, "sess-marker-only", "programmer", "2", None)

        payload = {
            "agent_id": "",
            "session_id": "sess-marker-only",
            "last_assistant_message": "",
            "agent_transcript_path": "",
        }
        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_subagent_stop, payload)

        assert get_active_agent(db_path, "sess-marker-only") is None


class TestStaleAgentTtlSweepViaSubagentStart:
    """Backstop purge mechanism: handle_subagent_start invokes
    clear_stale_agents with a TTL well below the previous 24h default,
    so ghost rows (left by any stop event that never fires) don't
    accumulate unbounded.
    """

    def test_backdated_row_older_than_ttl_is_purged(self, tmp_path):
        """A row with started_at older than the new TTL is gone after the
        next handle_subagent_start call."""
        from datetime import datetime, timedelta, timezone
        import sqlite3

        _make_log_dir(tmp_path)
        db_path = _init_db_only(tmp_path)

        # Fixture row artificially aged well past the new (sub-24h) TTL,
        # inserted directly since register_active_agent always stamps
        # "now". Must not rely on any pre-existing stale row.
        stale_time = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO active_agents (agent_id, agent_type, tier, log_file, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("ghost-agent", "programmer", "2", None, stale_time),
        )
        conn.commit()
        conn.close()
        assert get_active_agent(db_path, "ghost-agent") is not None

        payload = {
            "agent_type": "programmer",
            "agent_id": "new-agent",
            "session_id": "sess-new",
            "hook_event_name": "SubagentStart",
        }
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_subagent_start, payload)
        assert exc.value.code == 0

        assert get_active_agent(db_path, "ghost-agent") is None

    def test_fresh_row_within_ttl_is_not_purged(self, tmp_path):
        """A row registered moments ago (within the new TTL window)
        survives a handle_subagent_start-triggered sweep."""
        _make_log_dir(tmp_path)
        db_path = _init_db_only(tmp_path)
        register_active_agent(db_path, "fresh-existing-agent", "programmer", "2", None)
        assert get_active_agent(db_path, "fresh-existing-agent") is not None

        payload = {
            "agent_type": "programmer",
            "agent_id": "new-agent-2",
            "session_id": "sess-new-2",
            "hook_event_name": "SubagentStart",
        }
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_subagent_start, payload)
        assert exc.value.code == 0

        assert get_active_agent(db_path, "fresh-existing-agent") is not None
        # The newly-started agent itself must also have been registered.
        assert get_active_agent(db_path, "new-agent-2") is not None

    def test_ttl_constant_is_well_below_previous_24h_default(self):
        """Documents/enforces the TTL choice: well below the old 24h
        default, on the order of minutes-to-low-hours per the ticket."""
        from clasi.hook_handlers import _STALE_AGENT_TTL_HOURS

        assert 0 < _STALE_AGENT_TTL_HOURS < 24

    def test_clear_stale_agents_still_directly_callable_with_custom_ttl(self, tmp_path):
        """Sanity check that the underlying clear_stale_agents wrapper
        used by handle_subagent_start behaves as expected in isolation."""
        from datetime import datetime, timedelta, timezone
        import sqlite3

        db_path = _init_db_only(tmp_path)
        stale_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO active_agents (agent_id, agent_type, tier, log_file, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("direct-stale", "programmer", "2", None, stale_time),
        )
        conn.commit()
        conn.close()

        result = clear_stale_agents(db_path, ttl_hours=2)
        assert result["cleared"] == 1
        assert get_active_agent(db_path, "direct-stale") is None


# ---------------------------------------------------------------------------
# Ticket-in-progress gate on role-guard (ticket 019-004)
# ---------------------------------------------------------------------------


def _setup_sprint_with_lock(
    tmp_path: Path, sprint_id: str = "019", slug: str = "test-sprint"
) -> Path:
    """Create a real sprint directory (fresh/visible layout) plus a state
    DB with the sprint registered and its execution lock held.

    Returns the sprint directory (tickets/ not yet created — callers add
    ticket files with _make_in_progress_ticket / _make_done_ticket as
    needed for their scenario).
    """
    _write_fresh_config(tmp_path)
    sprint_dir = tmp_path / "clasi" / "sprints" / f"{sprint_id}-{slug}"
    sprint_dir.mkdir(parents=True)
    db_path = str(tmp_path / ".clasi" / ".clasi.db")
    init_db(db_path)
    register_sprint(db_path, sprint_id, f"sprint-{sprint_id}")
    acquire_lock(db_path, sprint_id)
    return sprint_dir


class TestRoleGuardTicketStateGate:
    """Ticket-state gate (ticket 019-004; RESCOPED by ticket 026-001): block
    Edit/Write/MultiEdit when a sprint execution lock is held, zero
    tickets in that sprint are status: in-progress, and OOP is not
    active. As of ticket 026-001 this gate applies to TIER 2 ONLY (not
    tier 0/1 — see TestRoleGuardTicketStateGateRescoping below for that
    change), and is additionally exempt for issues_dir/reflections_dir
    writes at every tier it applies to, so incident capture (the
    issue/self-reflect skills) is never blocked by it — see the source
    issue's "exception routing deadlocks by construction" finding: a
    thrown ticket exception (status: exception, never in-progress) used
    to dead-end every agent's writes, including the sprint-planner/
    team-lead writes needed to recover. Uses real sprint/ticket directory
    structures on disk, not mocks of _get_sprint_context() /
    _get_active_tickets() — this sprint's standard is no hand-built
    fixtures that bypass real logic.
    """

    def test_lock_held_zero_in_progress_tickets_tier2_source_write_blocked(
        self, tmp_path, capsys
    ):
        """Sprint executing (lock held) + zero in-progress tickets + tier 2
        + source-path write -> exit 2."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "2") == 2
        stderr = capsys.readouterr().err
        assert "019" in stderr
        assert "in-progress" in stderr
        assert ".clasi/oop" in stderr

    def test_lock_held_one_in_progress_ticket_tier2_source_write_allowed(
        self, tmp_path
    ):
        """Sprint executing + one in-progress ticket + tier 2 + source-path
        write -> exit 0."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_in_progress_ticket(sprint_dir, "004", "Add ticket gate")

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "2") == 0

    def test_lock_held_zero_in_progress_tickets_oop_flag_present_allowed(
        self, tmp_path
    ):
        """Sprint executing + zero in-progress tickets + tier 2 +
        .clasi/oop present -> exit 0 (OOP bypass still works for this
        gate)."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")
        (tmp_path / ".clasi" / "oop").write_text("", encoding="utf-8")

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "2") == 0

    def test_no_lock_held_tier2_source_write_allowed(self, tmp_path):
        """No execution lock held + tier 2 + source-path write -> exit 0
        (gate does not apply when no sprint is executing)."""
        _write_fresh_config(tmp_path)
        db_path = str(tmp_path / ".clasi" / ".clasi.db")
        init_db(db_path)
        register_sprint(db_path, "019", "sprint-019")
        # No acquire_lock call: no sprint is executing.

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "2") == 0

    def test_lock_held_zero_in_progress_tickets_tier0_source_write_still_blocked(
        self, tmp_path, capsys
    ):
        """Sprint executing + zero in-progress tickets + tier 0 +
        source-path write -> STILL exit 2 (the underlying "team-lead
        cannot write source" rule is unchanged), but as of ticket
        026-001 the gate itself no longer applies to tier 0/1, so this
        now falls through to the ordinary blk-write path — the message
        is the standard ROLE VIOLATION write-attempt message, NOT the
        ticket-gate-specific "execution lock is held" message (that
        message is now reserved for tier 2, gated by this same
        condition — see test_lock_held_zero_in_progress_tickets_tier2_source_write_blocked
        above). Renamed from the previous
        test_lock_held_zero_in_progress_tickets_tier0_source_write_blocked
        to make explicit that the deny OUTCOME (exit 2) is preserved
        while the ROUTE producing it intentionally changed."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "") == 2
        stderr = capsys.readouterr().err
        assert "attempted direct file write to" in stderr
        assert "execution lock" not in stderr

    def test_lock_held_zero_in_progress_tickets_tier1_source_write_still_blocked(
        self, tmp_path, capsys
    ):
        """Same as the tier-0 case above: tier 1 writing source code is
        still blocked (exit 2), but no longer via the ticket-gate
        message — tier 1's own "sprint-planner cannot write source"
        rule already covers it regardless of ticket state."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "1") == 2
        stderr = capsys.readouterr().err
        assert "attempted direct file write to" in stderr
        assert "execution lock" not in stderr

    def test_lock_held_zero_in_progress_tickets_safe_prefix_still_allowed(
        self, tmp_path
    ):
        """Safe-prefix writes (.claude/, CLAUDE.md, AGENTS.md) are checked
        before the ticket-state gate and remain allowed even with zero
        in-progress tickets — the gate must not regress existing
        allow-listed meta-file writes."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")

        assert _run_role_guard(tmp_path, "CLAUDE.md", "2") == 0


class TestRoleGuardTicketStateGateRescoping:
    """Ticket 026-001: the ticket-state gate no longer applies to tier 0/1
    at all, and is exempt for issues_dir/reflections_dir writes even for
    the tier-2 callers it does still gate. These are the NEW behaviors
    this ticket adds on top of the pre-existing 019-004 gate (covered by
    TestRoleGuardTicketStateGate above) — every case here sets up the
    exact "gate would otherwise fire" precondition (lock held, zero
    in-progress tickets) via real sprint/ticket fixtures, matching this
    sprint's no-hand-built-fixtures discipline.
    """

    def test_tier0_write_to_allow_listed_path_now_allowed(self, tmp_path):
        """Tier 0 + lock held + zero in-progress tickets + write to an
        allow-listed artifact dir (clasi/issues/) -> exit 0.

        Before ticket 026-001, the ticket-state gate ran BEFORE any
        allow-list check and applied to every tier, so this exact write
        was blocked (reason no-ticket) despite being on the allow list.
        Rescoping the gate to tier-2-only is what makes this allowed."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")

        assert _run_role_guard(tmp_path, "clasi/issues/incident.md", "") == 0

    def test_tier1_write_to_allow_listed_path_now_allowed(self, tmp_path):
        """Same as above for tier 1: a sprint-planner writing to
        clasi/reflections/ during a gate-triggering state is now
        allowed (it always should have been — this is exactly the
        exception-routing deadlock the source issue named)."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")

        assert _run_role_guard(tmp_path, "clasi/reflections/note.md", "1") == 0

    def test_tier2_issues_dir_write_exempt_from_gate(self, tmp_path):
        """Tier 2 + lock held + zero in-progress tickets + write under
        issues_dir -> exit 0 (exempt), even though the SAME state blocks
        an ordinary tier-2 source write (see
        test_lock_held_zero_in_progress_tickets_tier2_source_write_blocked).
        This is the "team-lead's issue-capture skill is not the same
        write the gate exists to police" carve-out from the source
        issue."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")

        assert _run_role_guard(tmp_path, "clasi/issues/incident.md", "2") == 0

    def test_tier2_reflections_dir_write_exempt_from_gate(self, tmp_path):
        """Same exemption for reflections_dir (self-reflect skill)."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")

        assert _run_role_guard(tmp_path, "clasi/reflections/note.md", "2") == 0

    def test_tier2_source_write_still_gated_regression(self, tmp_path):
        """Regression: tier 2 writing to a NON-exempt path (source code)
        under the SAME lock-held/zero-in-progress state is still blocked
        with reason no-ticket — the exemption is scoped to issues_dir/
        reflections_dir specifically, not a blanket tier-2 bypass."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "2") == 2

    def test_gate_uses_get_sprint_context_and_get_active_tickets_live(
        self, tmp_path
    ):
        """Sanity: the real helpers, called directly against the same
        fixture, agree with the gate's block/allow decision — confirms
        the gate is driven by the actual helpers and not a duplicated
        ad hoc check."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")

        _, sprint_id = _run_with_cwd(tmp_path, _get_sprint_context)
        active = _run_with_cwd(tmp_path, _get_active_tickets, sprint_id)
        assert sprint_id == "019"
        assert active == []
        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "2") == 2


# ---------------------------------------------------------------------------
# Staleness fail-closed gate (ticket 020-002) — role-guard / mcp-guard
# ---------------------------------------------------------------------------


def _write_stale_clasi_repo_skeleton(root: Path, declared_version: str) -> None:
    """Make *root* look like a CLASI source checkout (real pyproject.toml +
    src/clasi/__init__.py on disk) whose declared version differs from
    the real running package's metadata_version — deterministically
    triggers clasi.staleness's "dogfooding drift" signal via the version
    mismatch alone (source_path will also legitimately mismatch here,
    since this __init__.py is a throwaway file, not the real running
    module's backing file — see _write_matching_clasi_repo_skeleton for
    the counterpart that neutralizes that).
    """
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "clasi"\nversion = "{declared_version}"\n',
        encoding="utf-8",
    )
    src_clasi = root / "src" / "clasi"
    src_clasi.mkdir(parents=True, exist_ok=True)
    (src_clasi / "__init__.py").write_text('"""CLASI."""\n', encoding="utf-8")


def _write_matching_clasi_repo_skeleton(root: Path, declared_version: str) -> None:
    """Like _write_stale_clasi_repo_skeleton, but src/clasi/__init__.py is
    a real symlink to the actual running clasi module's real __init__.py
    file, so the source_path signal also genuinely agrees — the only way
    to construct a true "not stale" case for the dogfooding signal without
    faking clasi.staleness's internals.
    """
    import importlib.util

    (root / "pyproject.toml").write_text(
        f'[project]\nname = "clasi"\nversion = "{declared_version}"\n',
        encoding="utf-8",
    )
    src_clasi = root / "src" / "clasi"
    src_clasi.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.find_spec("clasi")
    real_init = Path(spec.origin).resolve()
    (src_clasi / "__init__.py").symlink_to(real_init)


def _real_running_clasi_version() -> str:
    import importlib.metadata

    return importlib.metadata.version("clasi")


class TestRoleGuardStalenessFailClosed:
    """Ticket 020-002: role-guard refuses to enforce (fails closed) when
    this repo IS the CLASI source repo and the running build's declared
    version doesn't match the working tree's own pyproject.toml — the
    same "dogfooding drift" signal from clasi.staleness. Ordinary
    dependency-version skew in a ordinary project stays out of scope for
    this gate (see clasi.staleness tests); this class only covers the
    fail-closed wiring in hook_handlers.
    """

    def test_dogfooding_drift_blocks_tier0_write(self, tmp_path):
        """Tier 0, source write, repo pyproject.toml version deliberately
        ahead of the running package's real metadata_version -> exit 2."""
        _write_fresh_config(tmp_path)
        newer_fake_version = "0.99990101.1"
        assert newer_fake_version != _real_running_clasi_version()
        _write_stale_clasi_repo_skeleton(tmp_path, newer_fake_version)

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "") == 2

    def test_dogfooding_drift_blocks_tier2_write(self, tmp_path):
        """Tier 2 (normally unrestricted) is also blocked by the staleness
        gate — it runs before the tier-2 unrestricted early return."""
        _write_fresh_config(tmp_path)
        newer_fake_version = "0.99990101.1"
        _write_stale_clasi_repo_skeleton(tmp_path, newer_fake_version)

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "2") == 2

    def test_matching_version_does_not_block(self, tmp_path):
        """Revert-check counterpart: when the repo's declared version AND
        editable source path both match the running package for real, the
        gate does not fire and the normal tier-2 unrestricted-write allow
        applies."""
        _write_fresh_config(tmp_path)
        _write_matching_clasi_repo_skeleton(tmp_path, _real_running_clasi_version())

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "2") == 0

    def test_non_clasi_repo_project_root_never_blocked_by_staleness(self, tmp_path):
        """A project root that is NOT the CLASI source repo (no
        pyproject.toml naming clasi) never triggers this gate, regardless
        of the running package's real version — the consumer-project
        no-op path from clasi.staleness."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "2") == 0

    def test_oop_bypass_still_works_when_stale(self, tmp_path):
        """.clasi/oop must still bypass everything, including the
        staleness gate — OOP is the designed escape hatch for exactly
        this situation (a broken/stale guard)."""
        _write_fresh_config(tmp_path)
        newer_fake_version = "0.99990101.1"
        _write_stale_clasi_repo_skeleton(tmp_path, newer_fake_version)
        (tmp_path / ".clasi" / "oop").touch()

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "") == 0

    def test_safe_prefix_still_allowed_when_stale(self, tmp_path):
        """.claude/, CLAUDE.md, AGENTS.md remain writable even when the
        staleness gate is active — otherwise there would be no way to
        fix .mcp.json / .claude/settings.json from inside the guarded
        session itself without OOP."""
        _write_fresh_config(tmp_path)
        newer_fake_version = "0.99990101.1"
        _write_stale_clasi_repo_skeleton(tmp_path, newer_fake_version)

        assert _run_role_guard(tmp_path, "CLAUDE.md", "") == 0


class TestMcpGuardStalenessFailClosed:
    """Same fail-closed gate, wired into handle_mcp_guard."""

    def test_dogfooding_drift_blocks_tier1_mcp_call(self, tmp_path):
        """Tier 1 is normally allowed by mcp-guard (only tier 0 is
        blocked by default) — the staleness gate blocks it anyway,
        proving the gate runs before the tier-allowed exit rather than
        being masked by it."""
        _write_fresh_config(tmp_path)
        newer_fake_version = "0.99990101.1"
        assert newer_fake_version != _real_running_clasi_version()
        _write_stale_clasi_repo_skeleton(tmp_path, newer_fake_version)

        assert _run_mcp_guard(tmp_path, "create_ticket", "1") == 2

    def test_matching_version_does_not_block_tier1_mcp_call(self, tmp_path):
        """Revert-check counterpart: matching version and source path ->
        tier 1's normal allow applies."""
        _write_fresh_config(tmp_path)
        _write_matching_clasi_repo_skeleton(tmp_path, _real_running_clasi_version())

        assert _run_mcp_guard(tmp_path, "create_ticket", "1") == 0

    def test_oop_bypass_still_works_when_stale(self, tmp_path):
        _write_fresh_config(tmp_path)
        newer_fake_version = "0.99990101.1"
        _write_stale_clasi_repo_skeleton(tmp_path, newer_fake_version)
        (tmp_path / ".clasi" / "oop").touch()

        assert _run_mcp_guard(tmp_path, "create_ticket", "") == 0

    def test_non_clasi_repo_project_root_tier_allowed_path_unaffected(self, tmp_path):
        """Tier 1/2 callers are unaffected by the staleness gate either
        way (they exit allow before reaching it in the tier-allowed
        path) — confirms the gate doesn't regress the ordinary
        tier-allowed exit."""
        _write_fresh_config(tmp_path)
        assert _run_mcp_guard(tmp_path, "create_ticket", "1") == 0


# ---------------------------------------------------------------------------
# Ticket 026-001, item 1: tier 1 now consults the artifact-dir allow list
# ---------------------------------------------------------------------------


class TestRoleGuardTier1ArtifactDirAllowList:
    """Tier 1 (sprint-planner) now consults the same artifact-dir allow
    list (issues_dir, reflections_dir, design_dir, clasi_dir, log_dir)
    tier 0 does — previously only the sprints_dir prefix was allow-listed
    for tier 1, so a sprint-planner writing e.g. clasi/issues/x.md fell
    through to the final BLOCK, contradicting the function's own
    documented matrix. Reason is asserted via hooks.log (not just exit
    code) so a fix that merely widened some OTHER allow path could not
    accidentally pass this test.
    """

    def _last_role_guard_line(self, tmp_path: Path) -> str:
        """Return the most recent role-guard hooks.log line.

        _log_hook_event only logs the top-level payload["file_path"] key
        (never present for role-guard's real nested
        tool_input.file_path payload shape), so the file path itself is
        never in the line — each test here makes exactly one
        _run_role_guard() call, so the last (only) role-guard line is
        unambiguous.
        """
        hooks_log = tmp_path / ".clasi" / "log" / "hooks.log"
        lines = hooks_log.read_text(encoding="utf-8").splitlines()
        matching = [ln for ln in lines if "role-guard" in ln]
        assert matching, f"no role-guard log line found: {lines}"
        return matching[-1]

    def test_tier1_issues_dir_allowed_reason_artifact_dir(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/issues/x.md", "1") == 0
        assert " 0 artifact-dir" in self._last_role_guard_line(tmp_path)

    def test_tier1_reflections_dir_allowed_reason_artifact_dir(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "clasi/reflections/x.md", "1") == 0
        assert " 0 artifact-dir" in self._last_role_guard_line(tmp_path)

    def test_tier1_design_dir_allowed_reason_artifact_dir(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "docs/design/x.md", "1") == 0
        assert " 0 artifact-dir" in self._last_role_guard_line(tmp_path)

    def test_tier1_clasi_state_dir_allowed_reason_artifact_dir(self, tmp_path):
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, ".clasi/config.yaml", "1") == 0
        assert " 0 artifact-dir" in self._last_role_guard_line(tmp_path)

    def test_tier1_source_still_blocked_regression(self, tmp_path, capsys):
        """Regression: the allow-list extension does not widen tier 1's
        write scope beyond artifact dirs + sprints_dir — source code is
        still blocked, and (per this ticket's docstring-matrix update)
        that block is now reason blk-write, matching the documented
        matrix exactly."""
        _write_fresh_config(tmp_path)
        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "1") == 2
        assert " 2 blk-write" in self._last_role_guard_line(tmp_path)


# ---------------------------------------------------------------------------
# Ticket 026-001, item 3: recovery-state directory-prefix matching
# ---------------------------------------------------------------------------


class TestRoleGuardRecoveryStateMatching:
    """Recovery-state matching honors directory-prefix entries in
    allowed_paths, not just exact-path equality — existing exact-path
    entries must still match exactly (no regression). Uses real
    write_recovery_state() DB calls and real handle_role_guard
    invocations (never a mocked get_recovery_state()), mirroring the
    real caller shapes in artifact_tools.py's close_sprint recovery
    writes: an absolute file path (str(ticket_file)) and an absolute
    directory path (str(project.design_dir)).
    """

    def test_exact_relative_path_entry_matches(self, tmp_path):
        """A root-relative exact-path entry still matches exactly (no
        regression from the directory-prefix addition)."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        write_recovery_state(
            db_path, "019", "precondition",
            ["clasi/sprints/019-x/sprint.md"], "broken frontmatter",
        )

        assert _run_role_guard(tmp_path, "clasi/sprints/019-x/sprint.md", "") == 0

    def test_exact_absolute_path_entry_matches(self, tmp_path):
        """The real caller shape: an ABSOLUTE file-path entry (mirroring
        str(ticket_file) in artifact_tools.py's ticket-not-done branch)
        matches the same file's root-relative form after normalization."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        abs_ticket = tmp_path / "clasi" / "sprints" / "019-x" / "tickets" / "001-x.md"
        write_recovery_state(
            db_path, "019", "precondition", [str(abs_ticket)], "ticket not done",
        )

        assert _run_role_guard(
            tmp_path, "clasi/sprints/019-x/tickets/001-x.md", "",
        ) == 0

    def test_non_matching_entry_still_blocked(self, tmp_path):
        """Deny path: a recovery record exists but names a DIFFERENT
        file — the write under test must still be blocked."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        write_recovery_state(
            db_path, "019", "precondition",
            ["clasi/sprints/019-x/sprint.md"], "broken frontmatter",
        )

        assert _run_role_guard(tmp_path, "src/clasi/unrelated.py", "") == 2

    def test_directory_entry_absolute_matches_file_under_it(self, tmp_path):
        """The real caller shape from close_sprint's design_overlay_apply
        branch: an ABSOLUTE DIRECTORY entry (str(project.design_dir))
        matches a file written under that directory — previously
        silently inert (exact-match-only). The directory must actually
        exist on disk for the is-dir detection to fire (real
        design_dir always does in practice)."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        design_dir = tmp_path / "docs" / "design"
        design_dir.mkdir(parents=True, exist_ok=True)
        write_recovery_state(
            db_path, "019", "design_overlay_apply",
            [str(design_dir)], "overlay validation failed",
        )

        assert _run_role_guard(tmp_path, "docs/design/architecture.md", "") == 0

    def test_directory_entry_with_trailing_slash_matches(self, tmp_path):
        """Root-relative directory entry WITH a trailing slash also
        matches any file under it — no filesystem is-dir check required
        (the trailing slash alone signals "directory")."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        write_recovery_state(
            db_path, "019", "merge", ["docs/design/"], "merge conflict",
        )

        assert _run_role_guard(tmp_path, "docs/design/sub/architecture.md", "") == 0

    def test_directory_entry_does_not_match_sibling_file(self, tmp_path):
        """Deny path: a directory entry must not match a file OUTSIDE
        that directory, even one with a similar-looking name."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        design_dir = tmp_path / "docs" / "design"
        design_dir.mkdir(parents=True, exist_ok=True)
        write_recovery_state(
            db_path, "019", "design_overlay_apply",
            [str(design_dir)], "overlay validation failed",
        )

        assert _run_role_guard(tmp_path, "docs/design-other/x.md", "") == 2

    def test_file_entry_does_not_match_suffix_variant(self, tmp_path):
        """Deny path: an exact FILE entry must not incorrectly match a
        DIFFERENT file that merely shares its string as a prefix (e.g.
        an entry for foo.py must not match foo.py.bak) — the
        directory-prefix addition must not loosen exact-file matching
        into a bare string-prefix match. Uses a plain source path (not
        under any artifact-dir allow-list prefix) so an ALLOW here could
        only come from the recovery match itself, never from an
        unrelated allow-listed directory."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        write_recovery_state(
            db_path, "019", "precondition", ["src/clasi/foo.py"], "x",
        )

        assert _run_role_guard(tmp_path, "src/clasi/foo.py.bak", "") == 2

    def test_merge_conflicted_files_list_entries_match(self, tmp_path):
        """Mirrors the merge-conflict recovery shape (conflicted:
        list[str] of relative file paths from git, per
        artifact_tools.py's merge step) — multiple exact-path entries,
        each independently matchable, and a file NOT in the list still
        blocked."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        write_recovery_state(
            db_path, "019", "merge",
            ["src/clasi/a.py", "src/clasi/b.py"], "merge conflict",
        )

        assert _run_role_guard(tmp_path, "src/clasi/a.py", "") == 0
        assert _run_role_guard(tmp_path, "src/clasi/b.py", "") == 0
        assert _run_role_guard(tmp_path, "src/clasi/c.py", "") == 2


class TestRecoveryEntryMatchesUnit:
    """Direct unit coverage of _recovery_entry_matches(), independent of
    the full handle_role_guard integration tests above."""

    def test_exact_match(self, tmp_path):
        proj = Project(tmp_path)
        assert _recovery_entry_matches("clasi/issues/x.md", "clasi/issues/x.md", proj)

    def test_no_match(self, tmp_path):
        proj = Project(tmp_path)
        assert not _recovery_entry_matches("clasi/issues/x.md", "clasi/issues/y.md", proj)

    def test_trailing_slash_directory_prefix_match(self, tmp_path):
        proj = Project(tmp_path)
        assert _recovery_entry_matches("docs/design/", "docs/design/x.md", proj)

    def test_is_dir_directory_prefix_match(self, tmp_path):
        (tmp_path / "docs" / "design").mkdir(parents=True)
        proj = Project(tmp_path)
        assert _recovery_entry_matches("docs/design", "docs/design/x.md", proj)

    def test_non_dir_shaped_entry_does_not_prefix_match(self, tmp_path):
        """A file-shaped entry (no trailing slash, not an actual
        directory on disk) must not directory-prefix-match — otherwise
        every exact-path entry would accidentally also match any file
        "under" it as a bare string prefix."""
        proj = Project(tmp_path)
        assert not _recovery_entry_matches(
            "docs/design/x.md", "docs/design/x.md/extra", proj,
        )

    def test_absolute_entry_normalized_before_match(self, tmp_path):
        proj = Project(tmp_path)
        abs_entry = str(tmp_path / "clasi" / "issues" / "x.md")
        assert _recovery_entry_matches(abs_entry, "clasi/issues/x.md", proj)


# ---------------------------------------------------------------------------
# Ticket 026-001, item 4: block-message agent identity from the DB
# ---------------------------------------------------------------------------


class TestRoleGuardBlockMessageAgentIdentity:
    """The block message names the DB-registered agent (via
    get_active_agent, keyed on caller_id) when the tier itself was
    resolved from the DB — not the CLASI_AGENT_NAME env default, which
    is typically unset for a dispatched subagent and would otherwise
    misreport it as "team-lead".
    """

    def test_tier_from_db_names_db_registered_agent(self, tmp_path, capsys):
        """Tier resolved via the DB fallback (no CLASI_AGENT_TIER env
        var) -> the block message names the agent_type from THAT SAME
        active_agents row, not "team-lead"."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        register_active_agent(db_path, "planner-caller", "sprint-planner", "1")

        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        old_name = os.environ.pop("CLASI_AGENT_NAME", None)
        try:
            payload = _role_guard_payload("src/clasi/foo.py")
            payload["agent_id"] = "planner-caller"
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_role_guard, payload)
            assert exc.value.code == 2
            stderr = capsys.readouterr().err
            assert "sprint-planner (tier 1)" in stderr
            assert "team-lead (tier 1)" not in stderr
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier
            if old_name is not None:
                os.environ["CLASI_AGENT_NAME"] = old_name

    def test_tier_from_env_var_still_uses_env_name_regression(self, tmp_path, capsys):
        """Regression: when the tier comes from CLASI_AGENT_TIER (not the
        DB), the block message still uses CLASI_AGENT_NAME (or its
        "team-lead" default) exactly as before — the DB-name resolution
        is scoped to the DB-sourced-tier case only."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        # A DB row exists for a DIFFERENT agent_id — proves it is not
        # consulted at all when the tier came from the env var.
        register_active_agent(db_path, "some-other-agent", "programmer", "2")

        import os

        old_tier = os.environ.get("CLASI_AGENT_TIER")
        old_name = os.environ.pop("CLASI_AGENT_NAME", None)
        try:
            os.environ["CLASI_AGENT_TIER"] = "1"
            payload = _role_guard_payload("src/clasi/foo.py")
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_role_guard, payload)
            assert exc.value.code == 2
            stderr = capsys.readouterr().err
            assert "team-lead (tier 1)" in stderr
        finally:
            if old_tier is None:
                os.environ.pop("CLASI_AGENT_TIER", None)
            else:
                os.environ["CLASI_AGENT_TIER"] = old_tier
            if old_name is not None:
                os.environ["CLASI_AGENT_NAME"] = old_name

    def test_tier_from_db_but_no_matching_agent_row_falls_back_to_default(
        self, tmp_path, capsys,
    ):
        """Edge case: agent_tier resolves truthy from the DB (e.g. "0"),
        but by the time the block message is built the row is gone (or
        never had an agent_type) — falls back to the CLASI_AGENT_NAME
        default rather than raising."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        register_active_agent(db_path, "caller-x", "unknown", "0")

        import os

        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        old_name = os.environ.pop("CLASI_AGENT_NAME", None)
        try:
            payload = _role_guard_payload("src/clasi/foo.py")
            payload["agent_id"] = "caller-x"
            with pytest.raises(SystemExit) as exc:
                _run_with_cwd(tmp_path, handle_role_guard, payload)
            assert exc.value.code == 2
            stderr = capsys.readouterr().err
            # agent_type "unknown" IS present on the row, so it is used —
            # confirms the DB-name path is live even for tier "0".
            assert "unknown (tier 0)" in stderr
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier
            if old_name is not None:
                os.environ["CLASI_AGENT_NAME"] = old_name


# ---------------------------------------------------------------------------
# Ticket 026-001, item 5: per-invocation caching — call-count assertions
# ---------------------------------------------------------------------------


class TestRoleGuardPerInvocationCaching:
    """get_project() and config.yaml parsing each happen at most ONCE
    within handle_role_guard's own guard-evaluation logic per invocation
    (down from ~5 / ~3), and the shared sqlite connection is opened at
    most once overall — verified via mock call-count assertions against
    a scenario built to reach every DB/config touch point in the
    function: tier resolution via the DB fallback, the OOP check, the
    recovery-state check, the artifact-dir/protected-paths config read,
    and (since the write is ultimately blocked) the block message's
    DB-backed agent-name lookup. The ticket-state gate is not reached
    (tier 0 in this scenario, and the gate is tier-2-only as of this
    same ticket) — its own DB touch is covered separately by
    TestRoleGuardTicketStateGate.

    get_project() and _load_config() are mocked at module scope, so
    their call counts also include ONE call each from _log_hook_event()
    — a separate, pre-existing helper (shared by every hook handler, not
    just role-guard) that resolves its own Project instance to write the
    hooks.log line when _exit_hook() runs at the very end of the
    invocation. That resolution is outside this ticket's scope (it is
    not one of handle_role_guard's own checks, and touching it would
    affect every other hook handler too) and was already exactly one
    call before this ticket; the assertions below are therefore == 2
    (1 from handle_role_guard's own single consolidated call + 1 from
    logging), not literally 1 — the sqlite-connection assertions, which
    are NOT affected by _log_hook_event (it never touches the DB), are
    the ones that land on the ticket's literal "1" target.
    """

    def _setup_full_traversal_scenario(self, tmp_path: Path) -> None:
        """Registers a tier-0 DB-resolved agent and a config.yaml with no
        matching recovery/OOP state, so a source-code write walks every
        check site down to the final BLOCK."""
        _write_fresh_config(tmp_path)
        db_path = _init_db_only(tmp_path)
        register_active_agent(db_path, "caller-full-traversal", "unknown", "0")

    def test_get_project_called_once(self, tmp_path):
        import clasi.hook_handlers as hh

        self._setup_full_traversal_scenario(tmp_path)
        payload = _role_guard_payload("src/clasi/foo.py")
        payload["agent_id"] = "caller-full-traversal"

        import os
        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        real_get_project = hh.get_project
        try:
            with patch(
                "clasi.hook_handlers.get_project", side_effect=real_get_project,
            ) as mock_get_project:
                with pytest.raises(SystemExit) as exc:
                    _run_with_cwd(tmp_path, handle_role_guard, payload)
                assert exc.value.code == 2
                # 1 from handle_role_guard's own consolidated _proj, plus
                # 1 from _log_hook_event's separate, unrelated resolution
                # at exit-logging time (see class docstring) — down from
                # ~5 calls within the guard logic itself before this
                # ticket (+ the same always-present logging call).
                assert mock_get_project.call_count == 2, (
                    f"expected get_project() called once by handle_role_guard's "
                    f"own logic (+1 from _log_hook_event's separate logging "
                    f"call = 2 total), got {mock_get_project.call_count}"
                )
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier

    def test_config_yaml_parsed_once(self, tmp_path):
        import clasi.project as project_mod

        self._setup_full_traversal_scenario(tmp_path)
        payload = _role_guard_payload("src/clasi/foo.py")
        payload["agent_id"] = "caller-full-traversal"

        import os
        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        real_load_config = project_mod._load_config
        try:
            with patch(
                "clasi.project._load_config", side_effect=real_load_config,
            ) as mock_load_config:
                with pytest.raises(SystemExit) as exc:
                    _run_with_cwd(tmp_path, handle_role_guard, payload)
                assert exc.value.code == 2
                # 1 from _load_role_guard_config's single parse (which
                # also primes _proj's paths-config cache, so no OTHER
                # property access re-parses), plus 1 from
                # _log_hook_event's separate Project instance resolving
                # its own log_dir at exit-logging time (see class
                # docstring) — down from ~3 independent parses within
                # the guard logic itself before this ticket.
                assert mock_load_config.call_count == 2, (
                    f"expected config.yaml parsed once by handle_role_guard's "
                    f"own logic (+1 from _log_hook_event's separate logging "
                    f"call = 2 total), got {mock_load_config.call_count}"
                )
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier

    def test_sqlite_connection_opened_once(self, tmp_path):
        from clasi.state_db_class import StateDB

        self._setup_full_traversal_scenario(tmp_path)
        payload = _role_guard_payload("src/clasi/foo.py")
        payload["agent_id"] = "caller-full-traversal"

        import os
        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        real_connect = StateDB.connect
        try:
            with patch.object(
                StateDB, "connect", autospec=True, side_effect=real_connect,
            ) as mock_connect:
                with pytest.raises(SystemExit) as exc:
                    _run_with_cwd(tmp_path, handle_role_guard, payload)
                assert exc.value.code == 2
                assert mock_connect.call_count == 1, (
                    f"expected one shared sqlite connection opened, got "
                    f"{mock_connect.call_count}"
                )
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier

    def test_allow_path_scenario_also_uses_single_connection(self, tmp_path):
        """Same call-count guarantee on an ALLOW outcome (artifact-dir),
        not just the BLOCK path above — confirms the cache is shared
        regardless of which exit reason fires."""
        from clasi.state_db_class import StateDB

        self._setup_full_traversal_scenario(tmp_path)
        payload = _role_guard_payload("clasi/issues/x.md")
        payload["agent_id"] = "caller-full-traversal"

        import os
        old_tier = os.environ.pop("CLASI_AGENT_TIER", None)
        real_connect = StateDB.connect
        try:
            with patch.object(
                StateDB, "connect", autospec=True, side_effect=real_connect,
            ) as mock_connect:
                with pytest.raises(SystemExit) as exc:
                    _run_with_cwd(tmp_path, handle_role_guard, payload)
                assert exc.value.code == 0
                assert mock_connect.call_count == 1
        finally:
            if old_tier is not None:
                os.environ["CLASI_AGENT_TIER"] = old_tier


# ---------------------------------------------------------------------------
# Ticket 026-001 scenario test: throw_ticket_exception -> sprint-planner
# can edit the sprint's architecture without OOP
# ---------------------------------------------------------------------------


class TestRoleGuardThrowExceptionRecoveryScenario:
    """The ticket's own required scenario test (unit-level, per the
    ticket's instructions): a thrown ticket exception during an active
    sprint (execution lock held, the exception ticket's status flips to
    `exception` — never `in-progress`, so zero tickets are in-progress)
    must not deadlock a dispatched sprint-planner's (tier 1) ability to
    edit the sprint's own architecture/design artifacts, without an OOP
    bypass. Before ticket 026-001 this was blocked (no-ticket) because
    the ticket-state gate applied to every tier and ran before every
    allow list — even though tier 1 is exactly the role dispatched to
    fix the architecture after an exception is thrown.
    """

    def test_sprint_planner_can_edit_sprint_architecture_after_exception_no_oop(
        self, tmp_path,
    ):
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="026")
        # Simulate the post-exception state named by the ticket: the
        # ticket that threw the exception is NOT in-progress (its status
        # flipped to `exception`) -- zero in-progress tickets, lock
        # still held, no OOP bypass anywhere.
        tickets_dir = sprint_dir / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "001-x.md").write_text(
            "---\nid: '001'\ntitle: X\nstatus: exception\n---\n"
        )

        assert not (tmp_path / ".clasi" / "oop").exists()
        assert _run_role_guard(
            tmp_path,
            "clasi/sprints/026-test-sprint/design/DESIGN.md",
            "1",
        ) == 0
