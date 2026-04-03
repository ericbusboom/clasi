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


def read_payload() -> dict:
    """Read JSON payload from stdin."""
    try:
        if sys.stdin.isatty():
            return {}
        data = sys.stdin.read()
        if not data.strip():
            return {}
        return json.loads(data)
    except (json.JSONDecodeError, OSError):
        return {}


# ---------------------------------------------------------------------------
# Hook activity log
# ---------------------------------------------------------------------------


def _log_hook_event(
    event_type: str, payload: dict, exit_code: int, reason: str,
) -> None:
    """Append a single line to docs/clasi/log/hooks.log.

    Called just before sys.exit(). Includes the exit code and a
    fixed-width 12-char reason code.

    Creates docs/clasi/log/ if docs/clasi/ exists. Wraps everything in
    try/except so logging never causes a hook to fail.
    """
    try:
        base = Path("docs/clasi")
        if not base.exists():
            return
        log_dir = base / "log"
        log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
        reason_fixed = f"{reason:<12.12}"

        # Build a short summary of key payload fields
        key_fields: list[str] = []
        for key in ("tool_name", "file_path", "path", "new_path", "task_id",
                    "task_subject", "agent_type", "agent_id", "session_id"):
            value = payload.get(key)
            if value:
                key_fields.append(f"{key}={value}")

        tier = os.environ.get("CLASI_AGENT_TIER", "")
        name = os.environ.get("CLASI_AGENT_NAME", "")
        if tier or name:
            key_fields.append(f"tier={tier or '0'} name={name or 'team-lead'}")

        line = f"{timestamp} {event_type:<16} {exit_code} {reason_fixed} {' '.join(key_fields)}\n"
        hooks_log = log_dir / "hooks.log"
        with open(hooks_log, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass  # Logging must never cause a hook to fail


def _exit_hook(
    event_type: str, payload: dict, exit_code: int, reason: str,
) -> None:
    """Log the hook event and exit with the given code."""
    _log_hook_event(event_type, payload, exit_code, reason)
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Role Guard — PreToolUse hook for Edit/Write/MultiEdit
# ---------------------------------------------------------------------------


def handle_role_guard(payload: dict) -> None:
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
        _exit_hook("role-guard", payload, 0, "no-path")

    agent_tier = os.environ.get("CLASI_AGENT_TIER", "")

    # If no env var, check the DB for the active agent tier
    if not agent_tier:
        try:
            db_path_tier = Path("docs/clasi/.clasi.db")
            if db_path_tier.exists():
                from clasi.state_db import get_active_tier
                agent_tier = get_active_tier(str(db_path_tier))
        except Exception:
            pass

    # Programmer (tier 2) can write — that's their job
    if agent_tier == "2":
        _exit_hook("role-guard", payload, 0, "tier-2")

    # OOP bypass
    if Path(".clasi-oop").exists():
        _exit_hook("role-guard", payload, 0, "oop-bypass")

    # Recovery state bypass
    db_path = Path("docs/clasi/.clasi.db")
    if db_path.exists():
        try:
            from clasi.state_db import get_recovery_state

            recovery = get_recovery_state(str(db_path))
            if recovery and file_path in recovery["allowed_paths"]:
                _exit_hook("role-guard", payload, 0, "recovery")
        except Exception:
            pass

    # Safe prefixes for any tier
    safe_prefixes = [".claude/", "CLAUDE.md", "AGENTS.md"]
    for prefix in safe_prefixes:
        if file_path == prefix or file_path.startswith(prefix):
            _exit_hook("role-guard", payload, 0, "safe-prefix")

    # Team-lead (tier 0 or unset) can write to docs/clasi/ but NOT sprints/
    if agent_tier in ("", "0") and file_path.startswith("docs/clasi/"):
        if file_path.startswith("docs/clasi/sprints/"):
            print(
                "CLASI ROLE VIOLATION: team-lead cannot directly edit sprint artifacts.\n"
                "Use MCP tools (create_sprint, create_ticket, update_ticket_status, etc.).",
                file=sys.stderr,
            )
            _exit_hook("role-guard", payload, 2, "blk-sprint")
        _exit_hook("role-guard", payload, 0, "clasi-docs")

    # Sprint-planner (tier 1) can write to sprint directories
    if agent_tier == "1" and file_path.startswith("docs/clasi/sprints/"):
        _exit_hook("role-guard", payload, 0, "tier-1")

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
    _exit_hook("role-guard", payload, 2, "blk-write")


# ---------------------------------------------------------------------------
# MCP Guard — PreToolUse hook for create_ticket / create_sprint
# ---------------------------------------------------------------------------


def handle_mcp_guard(payload: dict) -> None:
    """Block Tier 0 (team-lead) from calling artifact-creation MCP tools directly.

    The sprint-planner (Tier 1) and programmer (Tier 2) are allowed.
    OOP bypass: if .clasi-oop exists, allow all tiers.
    """
    # OOP bypass
    if Path(".clasi-oop").exists():
        _exit_hook("mcp-guard", payload, 0, "oop-bypass")

    agent_tier = os.environ.get("CLASI_AGENT_TIER", "")

    # If no env var, check the DB for the active agent tier
    if not agent_tier:
        try:
            db_path_tier = Path("docs/clasi/.clasi.db")
            if db_path_tier.exists():
                from clasi.state_db import get_active_tier
                agent_tier = get_active_tier(str(db_path_tier))
        except Exception:
            pass

    # Only block Tier 0 (team-lead / interactive session)
    if agent_tier not in ("", "0"):
        _exit_hook("mcp-guard", payload, 0, "tier-allowed")

    tool_name = payload.get("tool_name", "")
    print(
        f"CLASI ROLE VIOLATION: team-lead cannot call {tool_name} directly.\n"
        "Dispatch to sprint-planner agent to create planning artifacts.",
        file=sys.stderr,
    )
    _exit_hook("mcp-guard", payload, 2, "blk-mcp")


# ---------------------------------------------------------------------------
# Log directory resolution
# ---------------------------------------------------------------------------


def _get_sprint_context() -> tuple[Optional[Path], str]:
    """Return (log_dir, sprint_id) for the current sprint context.

    log_dir is None if docs/clasi/log does not exist (handlers should exit 0).
    If an execution lock is held, log_dir is a sprint-scoped subdirectory
    (docs/clasi/log/sprint-{sprint_id}/), creating it if needed.
    Otherwise log_dir is docs/clasi/log.
    sprint_id is the active sprint ID string, or empty string if none.
    """
    base = Path("docs/clasi")
    if not base.exists():
        return None, ""
    log_base = base / "log"
    log_base.mkdir(exist_ok=True)

    db_path = Path("docs/clasi/.clasi.db")
    if db_path.exists():
        try:
            from clasi.state_db import get_lock_holder

            lock = get_lock_holder(str(db_path))
            if lock and lock.get("sprint_id"):
                sprint_id = lock["sprint_id"]
                sprint_dir = log_base / f"sprint-{sprint_id}"
                sprint_dir.mkdir(parents=True, exist_ok=True)
                return sprint_dir, sprint_id
        except Exception:
            pass

    return log_base, ""


def _get_log_dir() -> Optional[Path]:
    """Return the log directory to use for the current sprint context.

    Returns None if docs/clasi does not exist (handlers should exit 0).
    If an execution lock is held, returns a sprint-scoped subdirectory
    (docs/clasi/log/sprint-{sprint_id}/), creating it if needed.
    Otherwise returns docs/clasi/log.
    """
    log_dir, _ = _get_sprint_context()
    return log_dir


def _get_active_tickets(sprint_id: str) -> list[str]:
    """Return a list of in-progress ticket IDs for the given sprint.

    Scans docs/clasi/sprints/{sprint_dir}/tickets/ for files with
    status: in-progress in their frontmatter. Returns ticket IDs in the
    format "{sprint_id}-{ticket_id}" (e.g. "002-007").
    Returns an empty list on any error or if no in-progress tickets found.
    """
    if not sprint_id:
        return []
    try:
        sprints_base = Path("docs/clasi/sprints")
        if not sprints_base.exists():
            return []

        # Find the sprint directory matching this sprint_id
        sprint_dir = None
        for candidate in sprints_base.iterdir():
            if candidate.is_dir() and candidate.name.startswith(f"{sprint_id}-"):
                sprint_dir = candidate
                break
        if sprint_dir is None:
            return []

        tickets_dir = sprint_dir / "tickets"
        if not tickets_dir.exists():
            return []

        active_tickets = []
        for ticket_file in tickets_dir.glob("*.md"):
            try:
                content = ticket_file.read_text(encoding="utf-8")
                if "status: in-progress" in content:
                    # Extract ticket id from frontmatter
                    ticket_id = None
                    in_frontmatter = False
                    for line in content.splitlines():
                        if line.strip() == "---":
                            if not in_frontmatter:
                                in_frontmatter = True
                            else:
                                break
                        elif in_frontmatter and line.startswith("id:"):
                            raw = line[3:].strip().strip("'\"")
                            ticket_id = raw
                            break
                    if ticket_id:
                        active_tickets.append(f"{sprint_id}-{ticket_id}")
                    else:
                        # Fall back to filename prefix
                        name = ticket_file.stem
                        prefix = name.split("-")[0] if "-" in name else name
                        active_tickets.append(f"{sprint_id}-{prefix}")
            except OSError:
                continue

        return sorted(active_tickets)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Subagent lifecycle logging — SubagentStart / SubagentStop
# ---------------------------------------------------------------------------


def handle_subagent_start(payload: dict) -> None:
    """Log when a subagent starts.

    Creates a log file in docs/clasi/log/ with frontmatter. The stop
    hook appends the transcript to this same file.
    """
    log_dir, sprint_id = _get_sprint_context()
    if log_dir is None:
        _exit_hook("sub-start", payload, 0, "no-log-dir")

    agent_type = payload.get("agent_type", "unknown")
    agent_id = payload.get("agent_id", "")
    session_id = payload.get("session_id", "")
    timestamp = datetime.now(timezone.utc).isoformat()

    active_tickets = _get_active_tickets(sprint_id)
    tickets_str = ", ".join(active_tickets)

    # Maps agent_type to CLASI tier: programmer=2, sprint-planner=1, else 0.
    _AGENT_TYPE_TIERS = {"programmer": "2", "sprint-planner": "1"}
    tier = _AGENT_TYPE_TIERS.get(agent_type, "0")

    # Create the log file
    _next = _next_log_number(log_dir)
    log_file = log_dir / f"{_next:03d}-{agent_type}.md"

    lines = [
        "---",
        f"agent_type: {agent_type}",
        f"agent_id: {agent_id}",
        f'sprint_id: "{sprint_id}"',
        f'tickets: "{tickets_str}"',
        f"started_at: {timestamp}",
        "---",
        "",
        f"# Subagent: {agent_type}",
        "",
    ]
    log_file.write_text("\n".join(lines))

    # Register in DB so stop hook can find the log file and tier guard can check tier
    marker_id = agent_id or session_id or "unknown"
    try:
        db_path = Path("docs/clasi/.clasi.db")
        if db_path.exists() or (db_path.parent.exists()):
            from clasi.state_db import register_active_agent
            register_active_agent(
                str(db_path), marker_id, agent_type, tier, str(log_file)
            )
    except Exception:
        pass

    _exit_hook("sub-start", payload, 0, "logged")


def handle_subagent_stop(payload: dict) -> None:
    """Append transcript to the log file created by subagent-start."""
    log_dir = _get_log_dir()
    if log_dir is None:
        _exit_hook("sub-stop", payload, 0, "no-log-dir")

    agent_id = payload.get("agent_id", "")
    session_id = payload.get("session_id", "")
    last_message = payload.get("last_assistant_message", "")
    transcript_path = payload.get("agent_transcript_path", "")
    stop_time = datetime.now(timezone.utc)

    # Find the log file from the DB record written by subagent-start
    marker_id = agent_id or session_id or "unknown"
    log_file = None
    started_at = None
    try:
        db_path = Path("docs/clasi/.clasi.db")
        if db_path.exists():
            from clasi.state_db import get_active_agent, remove_active_agent
            record = get_active_agent(str(db_path), marker_id)
            if record:
                if record.get("log_file"):
                    log_file = Path(record["log_file"])
                started_at = record.get("started_at")
            remove_active_agent(str(db_path), marker_id)
    except Exception:
        pass

    if not log_file or not log_file.exists():
        _exit_hook("sub-stop", payload, 0, "no-log-file")

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

    # Append transcript as markdown + raw JSON
    if transcript_path:
        transcript_file = Path(transcript_path)
        if transcript_file.exists():
            try:
                transcript_content = transcript_file.read_text(encoding="utf-8")
                messages = []
                for line in transcript_content.splitlines():
                    if line.strip():
                        messages.append(json.loads(line))
                lines.extend(_render_transcript_lines(messages))
            except OSError:
                pass

    if lines:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

    _exit_hook("sub-stop", payload, 0, "logged")


# ---------------------------------------------------------------------------
# Task lifecycle — TaskCreated / TaskCompleted
# ---------------------------------------------------------------------------


def handle_task_created(payload: dict) -> None:
    """Log when a programmer task starts.

    Creates a log file in docs/clasi/log/ with frontmatter and writes an
    .active/task-{task_id}.json marker so task_completed can find it.
    """
    log_dir, sprint_id = _get_sprint_context()
    if log_dir is None:
        _exit_hook("task-created", payload, 0, "no-log-dir")

    task_id = payload.get("task_id", "")
    task_subject = payload.get("task_subject", "")
    teammate_name = payload.get("teammate_name", "")
    timestamp = datetime.now(timezone.utc).isoformat()

    active_tickets = _get_active_tickets(sprint_id)
    tickets_str = ", ".join(active_tickets)

    # Create the log file
    _next = _next_log_number(log_dir)
    safe_subject = task_subject[:40].replace("/", "-").replace(" ", "-").lower() if task_subject else "task"
    log_file = log_dir / f"{_next:03d}-{safe_subject}.md"

    lines = [
        "---",
        f"task_id: {task_id}",
        f"task_subject: {task_subject}",
        f"teammate_name: {teammate_name}",
        f'sprint_id: "{sprint_id}"',
        f'tickets: "{tickets_str}"',
        f"started_at: {timestamp}",
        "---",
        "",
        f"# Task: {task_subject}",
        "",
    ]
    log_file.write_text("\n".join(lines))

    # Register in DB so task_completed can find the log file
    task_marker_id = f"task-{task_id}"
    try:
        db_path = Path("docs/clasi/.clasi.db")
        if db_path.exists() or (db_path.parent.exists()):
            from clasi.state_db import register_active_agent
            register_active_agent(
                str(db_path), task_marker_id, "task", "2", str(log_file)
            )
    except Exception:
        pass

    _exit_hook("task-created", payload, 0, "logged")


def handle_task_completed(payload: dict) -> None:
    """Append transcript to the log file created by task_created.

    Finds the .active marker, appends duration to frontmatter, extracts
    the prompt from the transcript, and appends the transcript content.
    """
    log_dir = _get_log_dir()
    if log_dir is None:
        _exit_hook("task-done", payload, 0, "no-log-dir")

    task_id = payload.get("task_id", "")
    transcript_path = payload.get("transcript_path", "")
    stop_time = datetime.now(timezone.utc)

    # Find the log file from the DB record written by task_created
    task_marker_id = f"task-{task_id}"
    log_file = None
    started_at = None
    try:
        db_path = Path("docs/clasi/.clasi.db")
        if db_path.exists():
            from clasi.state_db import get_active_agent, remove_active_agent
            record = get_active_agent(str(db_path), task_marker_id)
            if record:
                if record.get("log_file"):
                    log_file = Path(record["log_file"])
                started_at = record.get("started_at")
            remove_active_agent(str(db_path), task_marker_id)
    except Exception:
        pass

    if not log_file or not log_file.exists():
        _exit_hook("task-done", payload, 0, "no-log-file")

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

    # Append transcript as markdown + raw JSON
    if transcript_path:
        transcript_file = Path(transcript_path)
        if transcript_file.exists():
            try:
                transcript_content = transcript_file.read_text(encoding="utf-8")
                messages = []
                for line in transcript_content.splitlines():
                    if line.strip():
                        messages.append(json.loads(line))
                lines.extend(_render_transcript_lines(messages))
            except OSError:
                pass

    if lines:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

    _exit_hook("task-done", payload, 0, "logged")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ext_to_language(path: str) -> str:
    """Map a file path's extension to a fenced-code-block language tag.

    Returns an empty string for unknown extensions.
    """
    ext = Path(path).suffix.lower()
    mapping = {
        ".py": "python",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".js": "javascript",
        ".ts": "typescript",
        ".sh": "bash",
    }
    return mapping.get(ext, "")


def _render_transcript_lines(messages: list) -> list[str]:
    """Render transcript messages as markdown followed by raw JSON.

    Returns a list of lines for the ``## Transcript`` section:
    first a human-readable markdown rendering of each message,
    then the full JSON dump in a fenced code block.
    """
    lines: list[str] = ["## Transcript", "", "---", ""]

    for msg in messages:
        timestamp = msg.get("timestamp", "")
        msg_type = msg.get("type", "")
        git_branch = msg.get("gitBranch", "")
        user_type = msg.get("userType", "")
        cwd = msg.get("cwd", "")
        inner = msg.get("message", {})
        model = inner.get("model", "")
        stop_reason = inner.get("stop_reason", "")

        # Header
        lines.append(f"### {msg_type} — {timestamp}")
        lines.append("")

        # Metadata table
        meta = []
        if git_branch:
            meta.append(f"branch: `{git_branch}`")
        if user_type:
            meta.append(f"userType: {user_type}")
        if cwd:
            meta.append(f"cwd: `{cwd}`")
        if model:
            meta.append(f"model: {model}")
        if stop_reason:
            meta.append(f"stop_reason: {stop_reason}")
        if meta:
            lines.append(" | ".join(meta))
            lines.append("")

        # Content
        content = inner.get("content", msg.get("content", ""))
        if isinstance(content, str) and content:
            lines.append(content)
            lines.append("")
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type", "")
                if block_type == "text":
                    lines.append(block.get("text", ""))
                    lines.append("")
                elif block_type == "tool_use":
                    name = block.get("name", "")
                    tool_input = block.get("input", {})
                    if name == "Write":
                        file_path = tool_input.get("file_path", "")
                        content = tool_input.get("content", "")
                        lines.append(f"> **Write**: `{file_path}`")
                        lines.append("")
                        if content:
                            # Truncate very long content
                            MAX_CHARS = 3000
                            truncated = content
                            suffix = ""
                            if len(content) > MAX_CHARS:
                                truncated = content[:MAX_CHARS]
                                suffix = "\n... (truncated)"
                            ext = Path(file_path).suffix.lower()
                            if ext == ".md":
                                # Render markdown inline, no code fence
                                lines.append(truncated + suffix)
                            else:
                                lang = _ext_to_language(file_path)
                                lines.append(f"```{lang}")
                                lines.append(truncated + suffix)
                                lines.append("```")
                    elif name == "Edit":
                        file_path = tool_input.get("file_path", "")
                        old_string = tool_input.get("old_string", "")
                        new_string = tool_input.get("new_string", "")
                        lines.append(f"> **Edit**: `{file_path}`")
                        lines.append("")
                        lines.append("**Before:**")
                        lines.append("```")
                        lines.append(old_string)
                        lines.append("```")
                        lines.append("")
                        lines.append("**After:**")
                        lines.append("```")
                        lines.append(new_string)
                        lines.append("```")
                    else:
                        lines.append(f"> **Tool Use**: `{name}`")
                        if tool_input:
                            compact = json.dumps(tool_input, indent=2)
                            # Truncate long tool inputs
                            input_lines = compact.splitlines()
                            if len(input_lines) > 15:
                                input_lines = input_lines[:15] + ["  ..."]
                            lines.append("> ```json")
                            for il in input_lines:
                                lines.append(f"> {il}")
                            lines.append("> ```")
                    lines.append("")
                elif block_type == "tool_result":
                    tool_id = block.get("tool_use_id", "")
                    result_content = block.get("content", "")
                    lines.append(f"> **Tool Result** (id: `{tool_id}`)")
                    if isinstance(result_content, str) and result_content:
                        result_preview = result_content[:500]
                        if len(result_content) > 500:
                            result_preview += "..."
                        lines.append("> ```")
                        for rl in result_preview.splitlines():
                            lines.append(f"> {rl}")
                        lines.append("> ```")
                    lines.append("")

        lines.append("---")
        lines.append("")

    # Raw JSON
    pretty = json.dumps(messages, indent=2)
    lines.extend(["", "```json", pretty, "```", ""])
    return lines


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
