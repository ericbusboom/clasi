"""Claude Code hook event handlers.

Each handler reads stdin JSON (the hook payload from Claude Code),
performs the appropriate action, and exits with the correct code:
  - exit 0: allow (hook passes)
  - exit 2: block (hook rejects, stderr message fed back to model)

These are thin dispatchers — actual logic lives in dedicated modules.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def handle_hook(event: str) -> None:
    """Dispatch a hook event to the appropriate handler."""
    payload = _read_payload()

    handlers = {
        "role-guard": _handle_role_guard,
        "subagent-start": _handle_subagent_start,
        "subagent-stop": _handle_subagent_stop,
        "task-created": _handle_task_created,
        "task-completed": _handle_task_completed,
    }

    handler = handlers.get(event)
    if handler is None:
        print(f"Unknown hook event: {event}", file=sys.stderr)
        sys.exit(1)

    handler(payload)


def _read_payload() -> dict:
    """Read JSON payload from stdin."""
    try:
        data = sys.stdin.read()
        if not data.strip():
            return {}
        return json.loads(data)
    except (json.JSONDecodeError, OSError):
        return {}


# ---------------------------------------------------------------------------
# Role Guard — PreToolUse hook for Edit/Write/MultiEdit
# ---------------------------------------------------------------------------


def _handle_role_guard(payload: dict) -> None:
    """Enforce directory write scopes based on agent tier.

    Tier 0 (team-lead / interactive session): can write to docs/clasi/,
    .claude/, CLAUDE.md, AGENTS.md.
    Tier 1 (sprint-planner): can write to docs/clasi/sprints/<sprint>/.
    Tier 2 (programmer): can write anywhere within scope_directory.
    """
    tool_input = payload if payload else {}
    file_path = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("new_path")
        or ""
    )

    if not file_path:
        sys.exit(0)  # Can't determine path, allow

    agent_tier = os.environ.get("CLASI_AGENT_TIER", "")

    # Programmer (tier 2) can write — that's their job
    if agent_tier == "2":
        sys.exit(0)

    # OOP bypass
    if Path(".clasi-oop").exists():
        sys.exit(0)

    # Recovery state bypass
    db_path = Path("docs/clasi/.clasi.db")
    if db_path.exists():
        try:
            from clasi.state_db import get_recovery_state

            recovery = get_recovery_state(str(db_path))
            if recovery and file_path in recovery["allowed_paths"]:
                sys.exit(0)
        except Exception:
            pass

    # Safe prefixes for any tier
    safe_prefixes = [".claude/", "CLAUDE.md", "AGENTS.md"]
    for prefix in safe_prefixes:
        if file_path == prefix or file_path.startswith(prefix):
            sys.exit(0)

    # Team-lead (tier 0 or unset) can write to docs/clasi/ but NOT sprints/
    if agent_tier in ("", "0") and file_path.startswith("docs/clasi/"):
        if file_path.startswith("docs/clasi/sprints/"):
            print(
                "CLASI ROLE VIOLATION: team-lead cannot directly edit sprint artifacts.\n"
                "Use MCP tools (create_sprint, create_ticket, update_ticket_status, etc.).",
                file=sys.stderr,
            )
            sys.exit(2)
        sys.exit(0)

    # Sprint-planner (tier 1) can write to sprint directories
    if agent_tier == "1" and file_path.startswith("docs/clasi/sprints/"):
        sys.exit(0)

    # Block — determine who's violating
    agent_name = os.environ.get("CLASI_AGENT_NAME", "team-lead")
    print(
        f"CLASI ROLE VIOLATION: {agent_name} (tier {agent_tier or '0'}) "
        f"attempted direct file write to: {file_path}",
        file=sys.stderr,
    )
    print(
        "Dispatch to the appropriate agent for this write:",
        file=sys.stderr,
    )
    if agent_tier == "1":
        print("- programmer agent for source code and tests", file=sys.stderr)
    else:
        print(
            "- sprint-planner agent for sprint/architecture/ticket artifacts",
            file=sys.stderr,
        )
        print("- programmer agent for source code and tests", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Log directory resolution
# ---------------------------------------------------------------------------


def _get_log_dir() -> Optional[Path]:
    """Return the log directory to use for the current sprint context.

    Returns None if docs/clasi/log does not exist (handlers should exit 0).
    If an execution lock is held, returns a sprint-scoped subdirectory
    (docs/clasi/log/sprint-{sprint_id}/), creating it if needed.
    Otherwise returns docs/clasi/log.
    """
    base = Path("docs/clasi/log")
    if not base.exists():
        return None

    db_path = Path("docs/clasi/.clasi.db")
    if db_path.exists():
        try:
            from clasi.state_db import get_lock_holder

            lock = get_lock_holder(str(db_path))
            if lock and lock.get("sprint_id"):
                sprint_dir = base / f"sprint-{lock['sprint_id']}"
                sprint_dir.mkdir(parents=True, exist_ok=True)
                return sprint_dir
        except Exception:
            pass

    return base


# ---------------------------------------------------------------------------
# Subagent lifecycle logging — SubagentStart / SubagentStop
# ---------------------------------------------------------------------------


def _handle_subagent_start(payload: dict) -> None:
    """Log when a subagent starts.

    Creates a log file in docs/clasi/log/ with frontmatter. The stop
    hook appends the transcript to this same file.
    """
    log_dir = _get_log_dir()
    if log_dir is None:
        sys.exit(0)

    agent_type = payload.get("agent_type", "unknown")
    agent_id = payload.get("agent_id", "")
    session_id = payload.get("session_id", "")
    timestamp = datetime.now(timezone.utc).isoformat()

    # Create the log file
    _next = _next_log_number(log_dir)
    log_file = log_dir / f"{_next:03d}-{agent_type}.md"

    lines = [
        "---",
        f"agent_type: {agent_type}",
        f"agent_id: {agent_id}",
        f"started_at: {timestamp}",
        "---",
        "",
        f"# Subagent: {agent_type}",
        "",
    ]
    log_file.write_text("\n".join(lines))

    # Write a marker so stop can find this log file
    marker_dir = log_dir / ".active"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_id = agent_id or session_id or "unknown"
    marker = marker_dir / f"{marker_id}.json"
    marker.write_text(
        json.dumps(
            {
                "log_file": str(log_file),
                "started_at": timestamp,
            },
            indent=2,
        )
    )

    sys.exit(0)


def _handle_subagent_stop(payload: dict) -> None:
    """Append transcript to the log file created by subagent-start."""
    log_dir = _get_log_dir()
    if log_dir is None:
        sys.exit(0)

    agent_id = payload.get("agent_id", "")
    session_id = payload.get("session_id", "")
    last_message = payload.get("last_assistant_message", "")
    transcript_path = payload.get("agent_transcript_path", "")
    stop_time = datetime.now(timezone.utc)

    # Find the log file from the start marker
    marker_dir = log_dir / ".active"
    marker_id = agent_id or session_id or "unknown"
    marker = marker_dir / f"{marker_id}.json"

    log_file = None
    started_at = None
    if marker.exists():
        try:
            start_info = json.loads(marker.read_text())
            log_file = Path(start_info["log_file"])
            started_at = start_info.get("started_at")
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        marker.unlink(missing_ok=True)

    if not log_file or not log_file.exists():
        sys.exit(0)

    # Build content to append
    lines = []

    # Add duration to frontmatter by rewriting the file
    if started_at:
        try:
            duration_s = (stop_time - datetime.fromisoformat(started_at)).total_seconds()
            content = log_file.read_text(encoding="utf-8")
            content = content.replace(
                "---\n\n",
                f"stopped_at: {stop_time.isoformat()}\n"
                f"duration_seconds: {duration_s:.1f}\n"
                "---\n\n",
                1,
            )
            log_file.write_text(content, encoding="utf-8")
        except (ValueError, OSError):
            pass

    # Extract prompt from transcript
    prompt = ""
    if transcript_path:
        prompt = _extract_prompt_from_transcript(transcript_path)

    if prompt:
        lines.extend(["## Prompt", "", prompt, ""])

    if last_message:
        lines.extend(["## Result", "", last_message, ""])

    # Append full transcript as pretty-printed JSON array
    if transcript_path:
        transcript_file = Path(transcript_path)
        if transcript_file.exists():
            try:
                transcript_content = transcript_file.read_text(encoding="utf-8")
                messages = []
                for line in transcript_content.splitlines():
                    if line.strip():
                        messages.append(json.loads(line))
                pretty = json.dumps(messages, indent=2)
                lines.extend([
                    "## Transcript",
                    "",
                    "```json",
                    pretty,
                    "```",
                    "",
                ])
            except OSError:
                pass

    if lines:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

    sys.exit(0)


# ---------------------------------------------------------------------------
# Task lifecycle — TaskCreated / TaskCompleted
# ---------------------------------------------------------------------------


def _handle_task_created(payload: dict) -> None:
    """Log when a programmer task starts.

    Creates a log file in docs/clasi/log/ with frontmatter and writes an
    .active/task-{task_id}.json marker so task_completed can find it.
    """
    log_dir = _get_log_dir()
    if log_dir is None:
        sys.exit(0)

    task_id = payload.get("task_id", "")
    task_subject = payload.get("task_subject", "")
    teammate_name = payload.get("teammate_name", "")
    timestamp = datetime.now(timezone.utc).isoformat()

    # Create the log file
    _next = _next_log_number(log_dir)
    safe_subject = task_subject[:40].replace("/", "-").replace(" ", "-").lower() if task_subject else "task"
    log_file = log_dir / f"{_next:03d}-{safe_subject}.md"

    lines = [
        "---",
        f"task_id: {task_id}",
        f"task_subject: {task_subject}",
        f"teammate_name: {teammate_name}",
        f"started_at: {timestamp}",
        "---",
        "",
        f"# Task: {task_subject}",
        "",
    ]
    log_file.write_text("\n".join(lines))

    # Write a marker so task_completed can find this log file
    marker_dir = log_dir / ".active"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker = marker_dir / f"task-{task_id}.json"
    marker.write_text(
        json.dumps(
            {
                "log_file": str(log_file),
                "started_at": timestamp,
            },
            indent=2,
        )
    )

    sys.exit(0)


def _handle_task_completed(payload: dict) -> None:
    """Append transcript to the log file created by task_created.

    Finds the .active marker, appends duration to frontmatter, extracts
    the prompt from the transcript, and appends the transcript content.
    """
    log_dir = _get_log_dir()
    if log_dir is None:
        sys.exit(0)

    task_id = payload.get("task_id", "")
    transcript_path = payload.get("transcript_path", "")
    stop_time = datetime.now(timezone.utc)

    # Find the log file from the start marker
    marker_dir = log_dir / ".active"
    marker = marker_dir / f"task-{task_id}.json"

    log_file = None
    started_at = None
    if marker.exists():
        try:
            start_info = json.loads(marker.read_text())
            log_file = Path(start_info["log_file"])
            started_at = start_info.get("started_at")
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        marker.unlink(missing_ok=True)

    if not log_file or not log_file.exists():
        sys.exit(0)

    # Add duration to frontmatter by rewriting the file
    if started_at:
        try:
            duration_s = (stop_time - datetime.fromisoformat(started_at)).total_seconds()
            content = log_file.read_text(encoding="utf-8")
            content = content.replace(
                "---\n\n",
                f"stopped_at: {stop_time.isoformat()}\n"
                f"duration_seconds: {duration_s:.1f}\n"
                "---\n\n",
                1,
            )
            log_file.write_text(content, encoding="utf-8")
        except (ValueError, OSError):
            pass

    lines = []

    # Extract prompt from transcript
    prompt = ""
    if transcript_path:
        prompt = _extract_prompt_from_transcript(transcript_path)

    if prompt:
        lines.extend(["## Prompt", "", prompt, ""])

    # Append full transcript as pretty-printed JSON array
    if transcript_path:
        transcript_file = Path(transcript_path)
        if transcript_file.exists():
            try:
                transcript_content = transcript_file.read_text(encoding="utf-8")
                messages = []
                for line in transcript_content.splitlines():
                    if line.strip():
                        messages.append(json.loads(line))
                pretty = json.dumps(messages, indent=2)
                lines.extend([
                    "## Transcript",
                    "",
                    "```json",
                    pretty,
                    "```",
                    "",
                ])
            except OSError:
                pass

    if lines:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

    sys.exit(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_prompt_from_transcript(transcript_path: str) -> str:
    """Extract the initial user prompt from a subagent transcript.

    The transcript is a JSONL file where each line is a message object.
    The first message with role "user" contains the prompt sent to the
    subagent.
    """
    path = Path(transcript_path)
    if not path.exists():
        return ""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            msg = json.loads(line)
            if msg.get("role") == "user":
                # The content may be a string or a list of content blocks
                content = msg.get("content", "")
                if isinstance(content, list):
                    parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block["text"])
                        elif isinstance(block, str):
                            parts.append(block)
                    return "\n".join(parts)
                return str(content)
    except (json.JSONDecodeError, OSError, KeyError):
        pass
    return ""


def _next_log_number(log_dir: Path) -> int:
    """Find the next sequential log number in a directory."""
    existing = sorted(log_dir.glob("[0-9][0-9][0-9]-*.md"))
    if not existing:
        return 1
    try:
        last = int(existing[-1].name[:3])
        return last + 1
    except (ValueError, IndexError):
        return 1
