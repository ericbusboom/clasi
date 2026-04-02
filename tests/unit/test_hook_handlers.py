"""Tests for TaskCreated and TaskCompleted hook handlers."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from clasi.hook_handlers import _handle_task_created, _handle_task_completed, _get_log_dir
from clasi.state_db import init_db, register_sprint, acquire_lock


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
            _run_with_cwd(tmp_path, _handle_task_created, payload)
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
        """task_created writes .active/task-{id}.json marker."""
        _make_log_dir(tmp_path)
        payload = _task_created_payload(task_id="t-42")

        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, _handle_task_created, payload)

        marker = tmp_path / "docs" / "clasi" / "log" / ".active" / "task-t-42.json"
        assert marker.exists()
        data = json.loads(marker.read_text())
        assert "log_file" in data
        assert "started_at" in data

    def test_marker_log_file_points_to_created_log(self, tmp_path):
        """The marker's log_file path matches the created log file."""
        _make_log_dir(tmp_path)
        payload = _task_created_payload(task_id="t-10")

        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, _handle_task_created, payload)

        log_dir = tmp_path / "docs" / "clasi" / "log"
        log_files = list(log_dir.glob("[0-9][0-9][0-9]-*.md"))
        marker = log_dir / ".active" / "task-t-10.json"
        data = json.loads(marker.read_text())
        # The marker stores the log file path (relative or absolute).
        # Verify it refers to the same filename as the created log file.
        assert Path(data["log_file"]).name == log_files[0].name

    def test_exits_zero_when_log_dir_missing(self, tmp_path):
        """task_created exits 0 gracefully if docs/clasi/log does not exist."""
        payload = _task_created_payload()
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, _handle_task_created, payload)
        assert exc.value.code == 0

    def test_log_filename_derived_from_subject(self, tmp_path):
        """Log filename slug is derived from task_subject."""
        _make_log_dir(tmp_path)
        payload = _task_created_payload(task_subject="My Great Task")

        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, _handle_task_created, payload)

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
            _run_with_cwd(tmp_path, _handle_task_created, payload)

    def test_appends_duration_to_frontmatter(self, tmp_path):
        """task_completed adds stopped_at and duration_seconds to frontmatter."""
        _make_log_dir(tmp_path)
        self._setup_active_task(tmp_path, task_id="t-001")

        payload = _task_completed_payload(task_id="t-001")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, _handle_task_completed, payload)
        assert exc.value.code == 0

        log_dir = tmp_path / "docs" / "clasi" / "log"
        log_files = list(log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "stopped_at:" in content
        assert "duration_seconds:" in content

    def test_removes_active_marker_after_completion(self, tmp_path):
        """task_completed removes the .active marker file."""
        _make_log_dir(tmp_path)
        self._setup_active_task(tmp_path, task_id="t-002")

        marker = tmp_path / "docs" / "clasi" / "log" / ".active" / "task-t-002.json"
        assert marker.exists()

        payload = _task_completed_payload(task_id="t-002")
        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, _handle_task_completed, payload)

        assert not marker.exists()

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
            _run_with_cwd(tmp_path, _handle_task_completed, payload)

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
            _run_with_cwd(tmp_path, _handle_task_completed, payload)

        log_dir = tmp_path / "docs" / "clasi" / "log"
        log_files = list(log_dir.glob("[0-9][0-9][0-9]-*.md"))
        content = log_files[0].read_text()
        assert "## Prompt" in content
        assert "The initial prompt text." in content

    def test_exits_zero_when_log_dir_missing(self, tmp_path):
        """task_completed exits 0 gracefully if docs/clasi/log does not exist."""
        payload = _task_completed_payload()
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, _handle_task_completed, payload)
        assert exc.value.code == 0

    def test_exits_zero_when_no_marker(self, tmp_path):
        """task_completed exits 0 gracefully if no marker file exists."""
        _make_log_dir(tmp_path)
        payload = _task_completed_payload(task_id="nonexistent")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, _handle_task_completed, payload)
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
            _run_with_cwd(tmp_path, _handle_task_created, payload)
        assert exc.value.code == 0

        sprint_log_dir = tmp_path / "docs" / "clasi" / "log" / "sprint-001"
        log_files = list(sprint_log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "task_id: t-sprint-001" in content

    def test_task_created_active_marker_in_sprint_subdir(self, tmp_path):
        """task_created places .active marker inside sprint subdir."""
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="001")
        payload = _task_created_payload(task_id="t-marker")

        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, _handle_task_created, payload)

        marker = tmp_path / "docs" / "clasi" / "log" / "sprint-001" / ".active" / "task-t-marker.json"
        assert marker.exists()

    def test_task_completed_finds_log_in_sprint_subdir(self, tmp_path):
        """task_completed appends to log in sprint subdir when lock is held."""
        _make_log_dir(tmp_path)
        _setup_db_with_lock(tmp_path, sprint_id="001")

        # task_created sets up the log
        create_payload = _task_created_payload(task_id="t-full")
        with pytest.raises(SystemExit):
            _run_with_cwd(tmp_path, _handle_task_created, create_payload)

        # task_completed should find it in the same sprint subdir
        complete_payload = _task_completed_payload(task_id="t-full")
        with pytest.raises(SystemExit) as exc:
            _run_with_cwd(tmp_path, _handle_task_completed, complete_payload)
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
            _run_with_cwd(tmp_path, _handle_task_created, payload)
        assert exc.value.code == 0

        base_log_dir = tmp_path / "docs" / "clasi" / "log"
        log_files = list(base_log_dir.glob("[0-9][0-9][0-9]-*.md"))
        assert len(log_files) == 1
        # Sprint subdir should not have been created
        assert not (base_log_dir / "sprint-001").exists()
