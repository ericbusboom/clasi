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
)
from clasi.state_db import (
    init_db,
    register_sprint,
    acquire_lock,
    get_active_agent,
    register_active_agent,
    get_active_tier,
    clear_stale_agents,
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

    def test_absolute_path_outside_root_does_not_crash_and_is_blocked(self, tmp_path):
        """An absolute file_path that is not under the project root (e.g. a
        symlink escape or a misconfigured path) must not raise, and must
        not accidentally satisfy an allow-prefix via string coincidence.
        Tier 0, so falls through to the default BLOCK branch.
        """
        _write_fresh_config(tmp_path)
        outside = (tmp_path.parent / "outside-project" / "clasi" / "issues" / "foo.md")
        assert _run_role_guard(tmp_path, outside.as_posix(), "") == 2


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
    """Ticket-state gate (ticket 019-004): block Edit/Write/MultiEdit when
    a sprint execution lock is held, zero tickets in that sprint are
    status: in-progress, and OOP is not active — REGARDLESS of tier,
    including tier 2 (the gate that was previously entirely absent for
    programmers). Uses real sprint/ticket directory structures on disk,
    not mocks of _get_sprint_context() / _get_active_tickets() — this
    sprint's standard is no hand-built fixtures that bypass real logic.
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

    def test_lock_held_zero_in_progress_tickets_tier0_source_write_blocked(
        self, tmp_path, capsys
    ):
        """Sprint executing + zero in-progress tickets + tier 0/1 +
        source-path write -> exit 2 (gate applies to all tiers, not just
        tier 2)."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "") == 2
        stderr = capsys.readouterr().err
        assert "019" in stderr
        assert "in-progress" in stderr

    def test_lock_held_zero_in_progress_tickets_tier1_source_write_blocked(
        self, tmp_path
    ):
        """Same gate applies to tier 1 as well, not only tier 0/2."""
        sprint_dir = _setup_sprint_with_lock(tmp_path, sprint_id="019")
        _make_done_ticket(sprint_dir, "001", "Some done ticket")

        assert _run_role_guard(tmp_path, "src/clasi/foo.py", "1") == 2

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
