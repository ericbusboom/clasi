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
    _get_log_dir,
    _get_active_tickets,
    _render_transcript_lines,
    _ext_to_language,
)
from clasi.state_db import init_db, register_sprint, acquire_lock, get_active_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_log_dir(tmp_path: Path) -> Path:
    log_dir = tmp_path / "docs" / "clasi" / "log"
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

        log_dir = tmp_path / "docs" / "clasi" / "log"
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
        db_path = str(tmp_path / "docs" / "clasi" / ".clasi.db")
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
        db_path = str(tmp_path / "docs" / "clasi" / ".clasi.db")
        payload = _task_created_payload(task_id="t-10")

        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, handle_task_created, payload)

        log_dir = tmp_path / "docs" / "clasi" / "log"
        log_files = list(log_dir.glob("[0-9][0-9][0-9]-*.md"))
        record = get_active_agent(db_path, "task-t-10")
        assert record is not None
        # The record stores the log file path (relative or absolute).
        # Verify it refers to the same filename as the created log file.
        assert Path(record["log_file"]).name == log_files[0].name

    def test_exits_zero_when_log_dir_missing(self, tmp_path):
        """task_created exits 0 gracefully if docs/clasi/log does not exist."""
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

        log_dir = tmp_path / "docs" / "clasi" / "log"
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

        log_dir = tmp_path / "docs" / "clasi" / "log"
        log_files = list(log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "stopped_at:" in content
        assert "duration_seconds:" in content

    def test_removes_active_marker_after_completion(self, tmp_path):
        """task_completed removes the DB record for the task."""
        _make_log_dir(tmp_path)
        db_path = str(tmp_path / "docs" / "clasi" / ".clasi.db")
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

        log_dir = tmp_path / "docs" / "clasi" / "log"
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

        log_dir = tmp_path / "docs" / "clasi" / "log"
        log_files = list(log_dir.glob("[0-9][0-9][0-9]-*.md"))
        content = log_files[0].read_text()
        assert "## Prompt" in content
        assert "The initial prompt text." in content

    def test_exits_zero_when_log_dir_missing(self, tmp_path):
        """task_completed exits 0 gracefully if docs/clasi/log does not exist."""
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
    db_path = str(tmp_path / "docs" / "clasi" / ".clasi.db")
    init_db(db_path)
    register_sprint(db_path, sprint_id, f"sprint-{sprint_id}")
    acquire_lock(db_path, sprint_id)
    return db_path


class TestGetLogDir:
    def test_returns_none_when_log_dir_missing(self, tmp_path):
        """_get_log_dir returns None when docs/clasi/log does not exist."""
        result = _run_with_cwd(tmp_path, _get_log_dir)
        assert result is None

    def test_returns_base_dir_when_no_db(self, tmp_path):
        """_get_log_dir returns base log dir when no state DB exists."""
        _make_log_dir(tmp_path)
        result = _run_with_cwd(tmp_path, _get_log_dir)
        assert result == Path("docs/clasi/log")

    def test_returns_base_dir_when_no_lock(self, tmp_path):
        """_get_log_dir returns base log dir when DB exists but no lock held."""
        _make_log_dir(tmp_path)
        db_path = str(tmp_path / "docs" / "clasi" / ".clasi.db")
        init_db(db_path)
        register_sprint(db_path, "001", "sprint-001")
        # No lock acquired
        result = _run_with_cwd(tmp_path, _get_log_dir)
        assert result == Path("docs/clasi/log")

    def test_returns_sprint_subdir_when_lock_held(self, tmp_path):
        """_get_log_dir returns sprint-scoped subdir when execution lock is held."""
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="002")
        result = _run_with_cwd(tmp_path, _get_log_dir)
        assert result == Path("docs/clasi/log/sprint-002")

    def test_creates_sprint_subdir_when_lock_held(self, tmp_path):
        """_get_log_dir creates the sprint subdirectory on the filesystem."""
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="003")
        _run_with_cwd(tmp_path, _get_log_dir)
        assert (tmp_path / "docs" / "clasi" / "log" / "sprint-003").is_dir()


class TestSprintScopedLogging:
    def test_task_created_uses_sprint_subdir_when_lock_held(self, tmp_path):
        """task_created writes log to sprint subdir when execution lock is held."""
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="001")
        payload = _task_created_payload(task_id="t-sprint-001")

        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_created, payload)
        assert exc.value.code == 0

        sprint_log_dir = tmp_path / "docs" / "clasi" / "log" / "sprint-001"
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

        sprint_log_dir = tmp_path / "docs" / "clasi" / "log" / "sprint-001"
        log_files = list(sprint_log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "stopped_at:" in content
        assert "duration_seconds:" in content

    def test_task_created_falls_back_to_base_dir_without_lock(self, tmp_path):
        """task_created uses base log dir when no sprint holds the lock."""
        _make_log_dir(tmp_path)
        # DB exists but no lock
        db_path = str(tmp_path / "docs" / "clasi" / ".clasi.db")
        init_db(db_path)
        register_sprint(db_path, "001", "sprint-001")

        payload = _task_created_payload(task_id="t-fallback")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_created, payload)
        assert exc.value.code == 0

        base_log_dir = tmp_path / "docs" / "clasi" / "log"
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
        """_get_active_tickets returns empty list when docs/clasi/sprints does not exist."""
        result = _run_with_cwd(tmp_path, _get_active_tickets, "001")
        assert result == []

    def test_returns_empty_when_no_matching_sprint_dir(self, tmp_path):
        """_get_active_tickets returns empty list when no sprint dir matches sprint_id."""
        sprints = tmp_path / "docs" / "clasi" / "sprints"
        sprints.mkdir(parents=True)
        (sprints / "002-some-sprint").mkdir()
        result = _run_with_cwd(tmp_path, _get_active_tickets, "001")
        assert result == []

    def test_returns_in_progress_ticket_ids(self, tmp_path):
        """_get_active_tickets returns ticket IDs for in-progress tickets."""
        sprints = tmp_path / "docs" / "clasi" / "sprints"
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
        sprints = tmp_path / "docs" / "clasi" / "sprints"
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

        sprint_log_dir = tmp_path / "docs" / "clasi" / "log" / "sprint-002"
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

        base_log_dir = tmp_path / "docs" / "clasi" / "log"
        log_files = list(base_log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert 'sprint_id: ""' in content

    def test_task_created_includes_tickets_in_frontmatter(self, tmp_path):
        """task_created writes in-progress ticket IDs to frontmatter."""
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="002")

        # Create sprint directory with in-progress ticket
        sprint_dir = tmp_path / "docs" / "clasi" / "sprints" / "002-test-sprint"
        _make_in_progress_ticket(sprint_dir, "007", "Feature A")

        payload = _task_created_payload(task_id="t-tickets")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, handle_task_created, payload)
        assert exc.value.code == 0

        sprint_log_dir = tmp_path / "docs" / "clasi" / "log" / "sprint-002"
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

        sprint_log_dir = tmp_path / "docs" / "clasi" / "log" / "sprint-002"
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

        base_log_dir = tmp_path / "docs" / "clasi" / "log"
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
            "file_path": "docs/clasi/sprints/003/tickets/001-ticket.md",
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
