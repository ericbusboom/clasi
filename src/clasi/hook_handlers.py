"""Claude Code hook event handlers.

Each handler reads stdin JSON (the hook payload from Claude Code),
performs the appropriate action, and exits with the correct code:
  - exit 0: allow (hook passes)
  - exit 2: block (hook rejects, stderr message fed back to model)

These are thin dispatchers — actual logic lives in dedicated modules.
"""

import json
import logging
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from clasi.project import Project, _load_config

logger = logging.getLogger(__name__)


def get_project() -> Project:
    """Return a Project instance rooted at the discovered project root.

    Resolves the root by walking up from the current working directory
    looking for a ``.clasi/`` directory (via ``_find_project_root``,
    shared with ``_oop_active()``) rather than assuming cwd already is
    the project root. A PreToolUse/PostToolUse hook can fire with cwd
    set to a subdirectory of the project (e.g. editing a file two
    directories deep) — before this, every ``Project`` property derived
    from this function's return value (``issues_dir``, ``sprints_dir``,
    ``db_path``, ``protected_paths``, ...) silently resolved against
    that wrong subdirectory instead of the real root. This was the
    structural root cause behind the narrower ``_oop_active()``-only fix
    (ticket 019-002): every OTHER caller of this function inherited the
    same no-upward-search assumption.

    Falls back to ``Path.cwd()`` unchanged when no ``.clasi/`` is found
    in any ancestor — matching ``_find_project_root``'s own documented
    fallback exactly, so a legitimate non-project cwd (e.g. an isolated
    ``tmp_path`` test fixture, or a real invocation outside any CLASI
    checkout) resolves identically to before this change.
    """
    return Project(_find_project_root(Path.cwd()))


def _normalize_to_root_relative(file_path: str, project: Optional[Project] = None) -> str:
    """Normalize *file_path* to a root-relative path string (POSIX separators).

    Claude Code's PreToolUse payloads carry ABSOLUTE file_path values, but
    role-guard's allow/block prefixes (built via the ``_prefix()`` helper in
    handle_role_guard) are root-relative strings like ``"clasi/issues/"``.
    Without normalizing first, ``str.startswith()`` never matches an
    absolute path against a relative prefix.

    Three cases, mirroring ``_prefix()``'s own relative_to/fallback pattern:
      - Absolute path under the project root -> root-relative path.
      - Absolute path outside the project root -> returned unchanged (as a
        plain string comparison); it cannot match any relative prefix, and
        must not raise or be coerced into accidentally matching one.
      - Already-relative path -> returned unchanged.

    *project*, when given, is used instead of calling ``get_project()`` —
    lets a caller that already resolved its own ``Project`` for the
    current invocation (e.g. ``handle_role_guard``'s per-invocation
    cache) reuse it instead of constructing a new one. Omitted (the
    default), behavior is unchanged.
    """
    p = Path(file_path)
    if not p.is_absolute():
        return file_path
    try:
        _proj = project if project is not None else get_project()
        return p.relative_to(_proj.root).as_posix()
    except ValueError:
        return file_path


# Internal marker key (ticket 029-009): read_payload() sets this on its
# returned {} fallback when stdin carried non-empty content that failed to
# parse as JSON, so that case can be told apart from a legitimately
# empty/absent payload (a tty with no piped stdin, or genuinely empty piped
# input) — both of which also fall through to a bare {} with no marker.
# HookPayload.from_dict / _log_hook_event surface this as a "bad-payload"
# hooks.log token. Never a real payload field — no handler reads it as one.
_BAD_PAYLOAD_KEY = "_bad_payload"


def read_payload() -> dict:
    """Read JSON payload from stdin.

    Ticket 029-009: when stdin held non-empty content that is not valid
    JSON, returns ``{_BAD_PAYLOAD_KEY: True}`` instead of a bare ``{}`` —
    see that constant's module comment. A genuinely empty/absent payload
    (isatty, or whitespace-only piped input) is unaffected and still
    returns plain ``{}``, so the two cases stay distinguishable downstream.
    """
    try:
        if sys.stdin.isatty():
            return {}
        data = sys.stdin.read()
        if not data.strip():
            return {}
        return json.loads(data)
    except json.JSONDecodeError:
        return {_BAD_PAYLOAD_KEY: True}
    except OSError:
        return {}


# ---------------------------------------------------------------------------
# Typed hook payload ingress (ticket 029-008)
# ---------------------------------------------------------------------------

# Tool names role-guard is registered for (Edit/Write/MultiEdit in the
# PreToolUse matcher — see this module's own header docstring). Scopes
# HookPayload.missing's file_path tracking to the one shape where an
# absent path is actually a meaningful signal, rather than every hook
# event (subagent-start/stop, mcp-guard, ...) accumulating a spurious
# "missing=file_path" token for a field that was never relevant to them.
_FILE_TOOL_NAMES = frozenset({"Edit", "Write", "MultiEdit"})


@dataclass(frozen=True)
class HookPayload:
    """Typed view over a hook's raw stdin JSON payload.

    Built once per invocation (:meth:`from_dict`) and consumed by every
    handler instead of each one hand-rolling its own ``payload.get(...)``
    extraction. This exists because the nested-then-flat file_path rule —
    Claude Code nests ``file_path``/``path``/``new_path`` under
    ``payload["tool_input"]`` for PreToolUse/PostToolUse events, not at
    the payload top level — had drifted between two independent
    implementations of the identical rule (``handle_role_guard`` and
    ``_log_hook_event``): the 876-event fail-open incident this ticket
    exists to make structurally impossible to repeat.

    Fields:
      tool_name: ``payload["tool_name"]``, or ``""``.
      tool_input: ``payload["tool_input"]`` when present and a dict;
        when the ``"tool_input"`` key is entirely absent, falls back to
        the payload itself (mirrors ``handle_role_guard``'s pre-existing
        idiom, so a flat/synthetic payload with a top-level file_path
        still resolves); ``{}`` for a missing/empty payload, or for a
        ``"tool_input"`` value that is present but not a dict — this
        last case is the one deliberate hardening this dataclass adds
        over the pre-ticket per-site code (which would raise): no real
        Claude Code payload has ever sent a non-dict ``tool_input``, and
        the isinstance-guarded fallback removes a crash surface without
        changing any behavior the existing test suite exercises.
      file_path: the single nested-then-flat resolution —
        ``tool_input.get("file_path") or .get("path") or
        .get("new_path") or ""`` — matching ``handle_role_guard``'s
        pre-existing pattern exactly.
      caller_id / caller_id_source: ``payload["agent_id"] or
        payload["session_id"] or ""``, with ``caller_id_source``
        recording which one supplied it (``"agent_id"``,
        ``"session_id"``, or ``""`` if neither was present).
      agent_id / session_id: the raw, individual top-level values (not
        collapsed) — kept distinct from ``caller_id`` because at least
        one call site (``handle_subagent_start``'s log-file frontmatter)
        needs the un-combined ``agent_id`` specifically, without
        ``caller_id``'s session_id fallback.
      agent_type: ``payload["agent_type"]``, or ``""`` (handlers apply
        their own "unknown"-style default, matching pre-existing
        per-site behavior — not baked in here since it is only one
        handler's convention).
      transcript_path: ``payload["agent_transcript_path"]``, or ``""``.
      last_assistant_message: ``payload["last_assistant_message"]``, or
        ``""``.
      plan_file_path: ``payload["tool_input"]["planFilePath"]`` —
        resolved via ``handle_plan_to_issue``'s own pre-existing (and
        deliberately different) fallback: ``payload.get("tool_input",
        {})``, defaulting to ``{}`` rather than the whole payload when
        ``"tool_input"`` is absent. Kept as its own independent
        resolution rather than reusing the ``tool_input`` field above,
        since the two fallbacks genuinely differ and this ticket must
        not change either one's existing behavior.
      task_id / task_subject: ``payload["task_id"]`` /
        ``payload["task_subject"]``, or ``""`` — vestigial fields from a
        lifecycle retired in sprint 026, kept only because
        ``_log_hook_event`` still logs them when present.
      missing: expected-but-absent fields, currently just ``"file_path"``
        for an Edit/Write/MultiEdit tool call that resolved to no path
        at all — the exact shape of the 876-event incident. A handler
        that cares surfaces this into its own ``decisions`` list (see
        ``handle_role_guard``), which ``_exit_hook`` already appends to
        the hooks.log line — reusing that existing mechanism rather than
        adding a second one.
      bad_payload: ``True`` when the raw payload carries
        ``_BAD_PAYLOAD_KEY`` (ticket 029-009) — set by ``read_payload()``
        when stdin held non-empty content that failed to parse as JSON.
        ``_log_hook_event`` surfaces this as a "bad-payload" hooks.log
        token unconditionally (every handler's exit line), so a
        malformed-JSON case is distinguishable from a legitimately empty
        payload without every handler having to check for it itself.
    """

    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    file_path: str = ""
    caller_id: str = ""
    caller_id_source: str = ""
    agent_id: str = ""
    session_id: str = ""
    agent_type: str = ""
    transcript_path: str = ""
    last_assistant_message: str = ""
    plan_file_path: str = ""
    task_id: str = ""
    task_subject: str = ""
    missing: list = field(default_factory=list)
    bad_payload: bool = False

    @staticmethod
    def from_dict(payload: Optional[dict]) -> "HookPayload":
        """Build a HookPayload from a raw hook payload dict.

        Named ``from_dict`` rather than the issue's suggested
        ``from_stdin(raw: str)`` — the issue's own text allows either,
        "whichever composes better with the existing read_payload()".
        ``read_payload()`` already does the stdin read, JSON parse, and
        error handling and returns a ``dict``, so a caller composes this
        as ``HookPayload.from_dict(read_payload())`` with no duplicated
        parsing logic.
        """
        payload = payload or {}

        tool_name = payload.get("tool_name") or ""

        # Nested-then-flat resolution (role-guard / _log_hook_event's
        # shared, previously-duplicated rule): falls back to the payload
        # itself when no "tool_input" key exists at all, so a flat
        # synthetic payload with a top-level file_path still resolves.
        # A "tool_input" key that IS present (even {}) is authoritative
        # — a top-level file_path is never consulted in that case.
        tool_input = payload.get("tool_input", payload) if payload else {}
        if not isinstance(tool_input, dict):
            tool_input = {}

        file_path = (
            tool_input.get("file_path")
            or tool_input.get("path")
            or tool_input.get("new_path")
            or ""
        )

        agent_id = payload.get("agent_id") or ""
        session_id = payload.get("session_id") or ""
        if agent_id:
            caller_id, caller_id_source = agent_id, "agent_id"
        elif session_id:
            caller_id, caller_id_source = session_id, "session_id"
        else:
            caller_id, caller_id_source = "", ""

        # handle_plan_to_issue's own, deliberately different fallback:
        # {} (NOT the whole payload) when "tool_input" is absent.
        _plan_input = payload.get("tool_input", {})
        if not isinstance(_plan_input, dict):
            _plan_input = {}
        plan_file_path = _plan_input.get("planFilePath") or ""

        missing: list = []
        if tool_name in _FILE_TOOL_NAMES and not file_path:
            missing.append("file_path")

        return HookPayload(
            tool_name=tool_name,
            tool_input=tool_input,
            file_path=file_path,
            caller_id=caller_id,
            caller_id_source=caller_id_source,
            agent_id=agent_id,
            session_id=session_id,
            agent_type=payload.get("agent_type") or "",
            transcript_path=payload.get("agent_transcript_path") or "",
            last_assistant_message=payload.get("last_assistant_message") or "",
            plan_file_path=plan_file_path,
            task_id=payload.get("task_id") or "",
            task_subject=payload.get("task_subject") or "",
            missing=missing,
            bad_payload=bool(payload.get(_BAD_PAYLOAD_KEY)),
        )


def _find_project_root(start: Path) -> Path:
    """Walk up from *start* looking for a `.clasi/` directory.

    Returns the first ancestor (inclusive of *start*) containing
    ``.clasi/``, or *start* unchanged if none is found — preserving the
    historical cwd-is-root assumption as the fallback so behavior is
    unchanged when *start* already is the project root.
    """
    for candidate in (start, *start.parents):
        if (candidate / ".clasi").is_dir():
            return candidate
    return start


def _oop_file_active(root: Path) -> bool:
    """Return True if the OOP override *file* is present at *root*.

    Checks ``.clasi/oop`` (canonical) then the legacy ``.clasi-oop``
    (repo root, hyphen) sibling.
    """
    return (root / ".clasi" / "oop").exists() or (root / ".clasi-oop").exists()


def _oop_db_record(
    root: Path, conn: Optional[sqlite3.Connection] = None,
) -> Optional[dict]:
    """Return the DB-backed OOP bypass record for *root*, or None.

    Resolves ``db_path`` through ``Project(root).db_path`` — the same
    config-aware resolution every other DB read in this module uses — so a
    configured non-default db location is honored. Wrapped in
    ``try/except Exception: pass`` and gated on ``db_path.exists()`` first:
    a missing, corrupt, or locked database must never raise out of this
    helper. Expiry-on-read (deleting a stale record and warning on stderr)
    is handled by ``StateDB.get_oop`` itself (ticket 004).

    If *conn* is given, it is reused instead of opening a new connection
    (see ``_oop_active``'s docstring for the invariant that makes this
    safe) — used by ``handle_role_guard``'s per-invocation cache.
    """
    try:
        db_path = Project(root).db_path
        if not db_path.exists():
            return None
        from clasi.state_db_class import StateDB

        return StateDB(db_path).get_oop(conn=conn)
    except Exception:
        return None


def _oop_active(conn: Optional[sqlite3.Connection] = None) -> bool:
    """Return True if out-of-process (OOP) bypass is active for this project.

    Two independent channels, checked in this order:

    1. **File override** (unconditional, checked first): ``.clasi/oop``
       (canonical) or the legacy ``.clasi-oop`` sibling, resolved against
       the discovered project root. This is the stakeholder-decided fire
       axe (2026-07-16) — its entire value is that it needs no working
       subsystem to function, so it is never gated behind or merged with
       the DB check.
    2. **DB record** (``oop_state`` table, ticket 004): a live
       ``set_oop()`` record read via ``state_db.get_oop()``, expiring
       automatically on read via its own TTL. A broken/missing DB can
       never make this raise — see ``_oop_db_record``.

    Returns True if either channel fires.

    Resolves the project root by walking up from the current working
    directory (see ``_find_project_root``) rather than assuming cwd is the
    repo root — a PreToolUse hook can fire with cwd set to a subdirectory
    (e.g. editing a file two directories deep), and a bare relative-path
    check silently returns False in that case even though the flag file
    exists at the real project root. This was confirmed to make
    `.clasi/oop` invisible to this check when cwd was `tests/e2e/` while
    the flag lived at the repo root. The DB channel is resolved against
    this SAME discovered root (via ``Project(root).db_path``), not a bare
    cwd-relative path, for the same cwd-independence.

    Note: ``get_project()`` elsewhere in this module now performs the same
    upward search (sprint 029 / ticket 003 generalized this helper's
    approach to it), so both this function and ``get_project()`` resolve
    the same root from the same cwd. This helper still resolves its own
    root directly via ``_find_project_root`` rather than calling
    ``get_project()``, so it has no dependency on ``get_project()``'s
    behavior and both channels stay cwd-independent on their own terms.

    This is the single result and root-resolution point for OOP bypass. No
    handler in this module may check either flag-file path or the DB
    directly — always call this helper (or ``_oop_source()`` for reporting),
    so the two channels can never drift out of sync and the cwd-vs-root
    resolution is never duplicated.

    *conn*, when given, is reused for the DB-record channel's lookup
    instead of opening a new connection — used by ``handle_role_guard``'s
    per-invocation cache. This is safe only when *conn* was opened
    against the SAME root this function resolves internally, above.
    ``handle_role_guard``'s own use satisfies that: it only ever passes a
    connection it opened against ``get_project()``'s root (plain cwd, no
    upward search), and that connection only exists when cwd's own
    ``.clasi/.clasi.db`` already exists — which is only possible when cwd
    itself contains ``.clasi/``, in which case ``_find_project_root(cwd)``
    trivially returns cwd unchanged (it checks cwd itself before walking
    up any parent), so the two roots are guaranteed identical in that
    case. Omitted (the default), behavior is unchanged: this function
    resolves its own root and the DB-record lookup opens (and closes) its
    own connection.
    """
    root = _find_project_root(Path.cwd())
    return _oop_file_active(root) or _oop_db_record(root, conn=conn) is not None


def _oop_source() -> Optional[str]:
    """Return which OOP bypass channel(s) are active: "file", "db", or None.

    Mirrors ``_oop_active()``'s root resolution and check order exactly.
    When BOTH channels are active simultaneously, returns "both" — callers
    that need a single primary source string should treat "both" as
    file-primary (the file is the unconditional override), but the status
    block (``_oop_status_lines``) reports each active channel on its own
    line rather than collapsing to one, per the issue's "never reconcile
    silently" reporting contract.
    """
    root = _find_project_root(Path.cwd())
    file_active = _oop_file_active(root)
    db_record = _oop_db_record(root)
    if file_active and db_record is not None:
        return "both"
    if file_active:
        return "file"
    if db_record is not None:
        return "db"
    return None


def _format_ago(iso_timestamp: str) -> str:
    """Format an ISO-8601 UTC timestamp as a short human-readable "ago" string."""
    try:
        then = datetime.fromisoformat(iso_timestamp)
        delta = datetime.now(timezone.utc) - then
        total_seconds = int(delta.total_seconds())
        if total_seconds < 60:
            return f"{max(total_seconds, 0)}s"
        minutes = total_seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h"
        days = hours // 24
        return f"{days}d"
    except (ValueError, TypeError):
        return "unknown"


def _format_in(iso_timestamp: str) -> str:
    """Format an ISO-8601 UTC timestamp as a short human-readable "in" string."""
    try:
        then = datetime.fromisoformat(iso_timestamp)
        delta = then - datetime.now(timezone.utc)
        total_seconds = int(delta.total_seconds())
        if total_seconds <= 0:
            return "now"
        if total_seconds < 60:
            return f"{total_seconds}s"
        minutes = total_seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h"
        days = hours // 24
        return f"{days}d"
    except (ValueError, TypeError):
        return "unknown"


def _oop_status_lines() -> list[str]:
    """Return the status-block lines describing the active OOP bypass.

    Empty list if OOP is not active. Follows the issue's exact reporting
    contract (section 4): the DB channel names reason/age/expiry, the file
    channel has no audit record and says so, and when both channels are
    active both lines are emitted — never reconciled into one.
    """
    root = _find_project_root(Path.cwd())
    lines: list[str] = []
    db_record = _oop_db_record(root)
    if db_record is not None:
        ago = _format_ago(db_record["set_at"])
        expires_in = _format_in(db_record["expires_at"])
        lines.append(
            f'OOP active (DB): set {ago} ago — "{db_record["reason"]}" — '
            f"expires {expires_in}."
        )
    if _oop_file_active(root):
        lines.append(
            "OOP active (override file .clasi/oop). No audit record — "
            "if this is stale, remove the file."
        )
    return lines


# ---------------------------------------------------------------------------
# Log directory protection
# ---------------------------------------------------------------------------


def _ensure_log_gitignore(log_dir: Path) -> None:
    """Write a .gitignore in log_dir if one does not already exist.

    Prevents transcript logs (which may contain live secrets) from being
    accidentally committed. Idempotent — preserves any existing .gitignore.
    """
    gitignore = log_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n!.gitignore\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Hook activity log
# ---------------------------------------------------------------------------


def _log_hook_event(
    event_type: str, payload: dict, exit_code: int, reason: str,
    decisions: Optional[list[str]] = None,
) -> None:
    """Append a single line to .clasi/log/hooks.log.

    Called just before sys.exit(). Includes the exit code and a
    fixed-width 12-char reason code.

    Creates .clasi/log/ if .clasi/ exists. Wraps everything in
    try/except so logging never causes a hook to fail.

    Timestamp format (ticket 026-004): ``%Y-%m-%dT%H:%M:%SZ`` — a date
    component was added because the previous ``%H:%M:%SZ``-only format
    made multi-day log analysis impossible (every day's events looked
    identical). Still a single whitespace-free token, so the line
    remains splittable on whitespace exactly as before.

    file_path/path/new_path resolution (ticket 026-004): Claude Code
    nests these under ``payload["tool_input"]`` for PreToolUse/
    PostToolUse events (the same shape ``handle_role_guard`` resolves
    from) — NOT at the payload top level. Reading them from the top
    level (the previous behavior) meant essentially no blocked-write log
    line ever recorded which file was blocked. Mirrors
    ``handle_role_guard``'s own ``payload.get("tool_input", payload)``
    idiom so a payload with no ``tool_input`` key at all (e.g. a flat
    synthetic payload) still resolves the fields from the top level.

    decisions (ticket 028-005 — "Guard Decision Trail"): an optional,
    ordered list of short, informal decision-trail tokens (e.g.
    ``tier=2(db)``, ``match=clasi/issues/``, ``gate=ticket-state:no-
    ticket``) explaining *why* a guard reached this exit — hooks.log
    previously recorded only *what* was decided. Tokens are appended
    verbatim after the existing key_fields, space-joined the same way
    key_fields itself is. ``None`` (the default) or an empty list
    produces exactly today's line shape — additive, not a format
    break for any pre-existing caller.

    Deny-payload dump (ticket 028-005): whenever ``exit_code == 2``,
    the full ``payload`` dict is also written as JSON to
    ``<log_dir>/denied/<timestamp>-<event_type>.json`` (the same
    timestamp as this line, for correlation) so a denial can be
    inspected/replayed in full — the hooks.log line itself only ever
    carries a handful of summarized key fields.

    Payload ingress (ticket 029-008): the file_path/path/new_path and
    top-level field extraction below now goes through one
    ``HookPayload.from_dict(payload)`` call instead of this function's
    own previously-independent copy of the nested-then-flat rule (the
    exact duplication that had drifted from ``handle_role_guard``'s copy
    and produced the 876-event fail-open incident this ticket exists to
    prevent from recurring). The function's own ``payload: dict``
    parameter is unchanged — many existing tests call this function
    directly with a raw dict, and the deny-payload dump above needs the
    verbatim raw payload regardless — only the internal field-extraction
    logic changed.

    ``bad-payload`` token (ticket 029-009): when ``hp.bad_payload`` is
    True (the raw payload carries ``_BAD_PAYLOAD_KEY``, set by
    ``read_payload()`` for a non-empty, unparseable-as-JSON stdin body),
    ``"bad-payload"`` is unconditionally prepended to ``key_fields`` here
    — every handler's hooks.log line for that invocation carries it, not
    only role-guard/mcp-guard's own ``decisions`` list, so a malformed
    payload is distinguishable from a legitimately empty one regardless
    of which handler processed it.
    """
    try:
        _proj = get_project()
        if not _proj.clasi_dir.exists():
            return
        log_dir = _proj.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        _ensure_log_gitignore(log_dir)

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        reason_fixed = f"{reason:<12.12}"

        hp = HookPayload.from_dict(payload)
        key_fields: list[str] = []

        if hp.bad_payload:
            key_fields.append("bad-payload")

        if hp.tool_name:
            key_fields.append(f"tool_name={hp.tool_name}")

        for key in ("file_path", "path", "new_path"):
            value = hp.tool_input.get(key)
            if value:
                key_fields.append(f"{key}={value}")

        for key, value in (
            ("task_id", hp.task_id),
            ("task_subject", hp.task_subject),
            ("agent_type", hp.agent_type),
            ("agent_id", hp.agent_id),
            ("session_id", hp.session_id),
        ):
            if value:
                key_fields.append(f"{key}={value}")

        tier = os.environ.get("CLASI_AGENT_TIER", "")
        name = os.environ.get("CLASI_AGENT_NAME", "")
        if tier or name:
            key_fields.append(f"tier={tier or '0'} name={name or 'team-lead'}")

        if decisions:
            key_fields.extend(decisions)

        line = f"{timestamp} {event_type:<16} {exit_code} {reason_fixed} {' '.join(key_fields)}\n"
        hooks_log = log_dir / "hooks.log"
        with open(hooks_log, "a", encoding="utf-8") as f:
            f.write(line)

        if exit_code == 2:
            denied_dir = log_dir / "denied"
            denied_dir.mkdir(parents=True, exist_ok=True)
            _ensure_log_gitignore(denied_dir)
            denied_file = denied_dir / f"{timestamp}-{event_type}.json"
            denied_file.write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8",
            )
    except Exception:
        pass  # Logging must never cause a hook to fail


def _exit_hook(
    event_type: str, payload: dict, exit_code: int, reason: str,
    decisions: Optional[list[str]] = None,
) -> None:
    """Log the hook event and exit with the given code."""
    _log_hook_event(event_type, payload, exit_code, reason, decisions=decisions)
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# Role Guard — PreToolUse hook for Edit/Write/MultiEdit
# ---------------------------------------------------------------------------


def _recovery_entry_matches(entry: str, file_path: str, project: Project) -> bool:
    """Return True if *file_path* (already root-relative) is covered by
    *entry*, a single item from a recovery record's ``allowed_paths``.

    Entries may be written as absolute paths (e.g. ``str(project.design_dir)``
    — see ``artifact_tools.py``'s ``close_sprint`` recovery writes),
    root-relative paths, or root-relative paths with a trailing slash.
    *entry* is normalized to root-relative via the same helper used for
    the incoming ``file_path`` (``_normalize_to_root_relative``) before
    comparison, so an absolute entry under *project*'s own root matches
    correctly.

    Two ways to match (ticket 026-001):
      - Exact: ``file_path == the normalized entry``.
      - Directory-prefix: the normalized entry is "directory-shaped" (ends
        with ``"/"``, or resolves to an actual directory on disk) and
        ``file_path`` starts with ``entry + "/"``. This is what makes a
        directory entry (e.g. ``str(project.design_dir)``) cover every
        file under it — per the ticket's "a trailing-slash or is-dir
        entry matches any file under it". Previously only exact-path
        equality was checked, so directory entries were silently inert.
    """
    normalized = _normalize_to_root_relative(entry, project=project)
    if file_path == normalized:
        return True
    stripped = normalized.rstrip("/")
    if not stripped:
        return False
    try:
        is_dir_shaped = normalized.endswith("/") or (project.root / stripped).is_dir()
    except OSError:
        is_dir_shaped = normalized.endswith("/")
    return is_dir_shaped and file_path.startswith(stripped + "/")


def _load_role_guard_config(project: Project) -> tuple[list[str], list[str]]:
    """Read ``.clasi/config.yaml`` exactly once and return
    ``(protected_paths, excluded_paths)``, normalized identically to
    ``Project.protected_paths`` / ``Project.excluded_paths``.

    Also primes *project*'s own lazy paths-config cache slot (the one
    ``Project._path_config()`` checks) from this SAME parse, so a later
    ``project.issues_dir`` / ``.sprints_dir`` / ``.design_dir`` / etc.
    access — which normally triggers its own independent config.yaml
    parse the first time any of those properties is read — reuses this
    read instead. Combined, this is what gets one ``handle_role_guard``
    invocation down to a single config.yaml parse (previously 3: one
    each for the ``paths:`` map, ``protected_paths:``, and
    ``excluded_paths:`` keys, each read independently by their own
    Project property/loader).

    Safe because *project* is a ``Project`` instance this one hook
    invocation constructs and owns exclusively — nothing else observes
    or reuses its cache slots, and this helper never writes
    config.yaml back out (unlike ``Project.set_design_docs_opt_in``'s
    read-modify-write, which must always see a fresh read and is
    untouched by this helper or by priming ``_paths``).
    """
    data = _load_config(project.root)

    if project._paths is None:
        paths = data.get("paths")
        project._paths = paths if isinstance(paths, dict) else {}

    def _normalize(raw: object) -> list[str]:
        if not isinstance(raw, list):
            return []
        result: list[str] = []
        for rel in raw:
            rel = str(rel).strip("/")
            if rel:
                result.append(rel + "/")
        return result

    return (
        _normalize(data.get("protected_paths")),
        _normalize(data.get("excluded_paths")),
    )


def handle_role_guard(payload: dict) -> None:
    """Enforce directory write scopes based on agent tier.

    Allowed/blocked write matrix
    ─────────────────────────────────────────────────────────────────────────
    Path                             tier 0   tier 1   tier 2   OOP
    ───────────────────────────────  ──────   ──────   ──────   ───
    ~/.claude/plans/**               ALLOW    ALLOW    ALLOW    ALLOW
    .claude/**  /  CLAUDE.md         ALLOW    ALLOW    ALLOW    ALLOW
    AGENTS.md                        ALLOW    ALLOW    ALLOW    ALLOW
    issues_dir / reflections_dir     ALLOW    ALLOW    ALLOW*   ALLOW
    design_dir / clasi_dir / log_dir ALLOW    ALLOW    ALLOW    ALLOW
    .clasi/sprints/**                ALLOW    ALLOW    ALLOW    ALLOW
    Source / tests / config          BLOCK    BLOCK    ALLOW*   ALLOW
    (anything else, in-root)         BLOCK    BLOCK    ALLOW*   ALLOW
    (anything outside project root)  ALLOW    ALLOW    ALLOW    ALLOW
    ─────────────────────────────────────────────────────────────────────────
    * Tier 2 is additionally subject to the ticket-state gate below;
      issues_dir/reflections_dir are exempt from that gate, every other
      tier-2 write is unrestricted only once the gate has cleared.

    As of sprint 026 (ticket 001), tier 1 consults the same artifact-dir
    allow list (issues_dir, reflections_dir, design_dir, clasi_dir,
    log_dir) tier 0 does — previously only the sprints_dir prefix was
    allow-listed for tier 1, contradicting this table's own intent (a
    sprint-planner writing e.g. an incident reflection fell through to
    the final BLOCK).

    Outside-root writes are ALLOWED for every tier. role-guard governs
    direct writes to *this* repo's source and tests only; a path outside
    the project root (the agent's ~/.claude memory and plan files, home-dir
    scratch, an unrelated checkout) is not CLASI's to police and exits
    allow with reason "outside-root". The ~/.claude/plans/** absolute-path
    allow-list below is now subsumed by this rule and kept only so its
    "claude-plans-dir" reason keeps appearing in logs.

    "Source / tests / config" above means: when Project.protected_paths is
    NOT configured (the default — no `protected_paths:` key in
    config.yaml), anything not on the tier-0/1 allow list is blocked, same
    as always. When protected_paths IS configured (typically written by
    `clasi init` after detecting/being told the project's source and test
    directories), the meaning flips for tier 0/1: ONLY paths under those
    configured prefixes (plus .clasi/sprints/**, still handled separately)
    are blocked — everything else (test-harness scripts, misc repo
    tooling, docs) is allowed even without an OOP bypass. See the
    protected_paths gate below, after the tier-1 sprints-dir check.

    Tier 0 = team-lead / interactive session (CLASI_AGENT_TIER unset or "0")
    Tier 1 = sprint-planner
    Tier 2 = programmer
    OOP    = .clasi/oop (or legacy .clasi-oop) present in cwd (out-of-process bypass)

    Ticket-state gate (ticket 026-001: rescoped to tier 2 only): if a
    sprint execution lock is held (via _get_sprint_context()) and zero
    tickets in that sprint are `status: in-progress` (via
    _get_active_tickets()), a TIER-2 write is blocked — unless
    _oop_active() is True, or the write falls under issues_dir /
    reflections_dir (exempt for every tier reached by this gate, so
    incident capture via the issue/self-reflect skills is never blocked
    by it). Previously this gate applied to every tier and ran before
    every allow list: since throw_ticket_exception sets a ticket's status
    to `exception`, never `in-progress`, that made every agent's writes —
    including the sprint-planner/team-lead writes needed to actually
    recover from the exception — dead-end the moment one was thrown.
    Tier 0/1 writes are no longer gated by ticket-state at all; their own
    allow/block rules above already determine their outcome. This gate
    is skipped entirely when no execution lock is held.

    Recovery-state bypass: allows specific paths recorded in the state DB
    during sprint recovery (e.g. resolving merge conflicts, or a
    close_sprint precondition failure that names the file to fix). Each
    entry in `allowed_paths` may be an exact file path OR a directory
    (absolute or root-relative, with or without a trailing slash) — a
    directory entry matches any file under it, not just an exact string
    (ticket 026-001; previously directory entries were silently inert,
    since only exact-path equality was checked). See
    _recovery_entry_matches().

    Block-message agent identity (ticket 026-001): when the caller's tier
    was resolved from the state DB (get_active_tier(), keyed on
    caller_id) rather than the CLASI_AGENT_TIER env var, the final block
    message also resolves the agent's display name from the SAME DB
    record (get_active_agent(), same caller_id key) instead of the
    CLASI_AGENT_NAME env default — which is typically unset for a
    DB-dispatched subagent and would otherwise misreport it as
    "team-lead".

    Per-invocation caching (ticket 026-001): this function resolves one
    Project instance, its parsed config.yaml, and (lazily, on first
    need) one sqlite connection, and reuses them for every check above
    instead of re-resolving/reconnecting at each check site (previously:
    ~5 get_project() calls, ~3 config.yaml parses, ~4 sqlite connections
    per invocation). A hook invocation is a single, one-shot CLI process
    — see DESIGN.md's "hook invocation is a single process lifetime"
    invariant — so this cache never outlives the call and there is
    nothing to invalidate across invocations.

    No path resolvable from the payload (neither the nested
    tool_input.file_path/path/new_path shape nor a flat fallback) fails
    CLOSED for tier 0/1 — directory-scope enforcement is meaningless
    without a path to check, so the safe default is to block, not allow.
    Tier 2 is unaffected (already unrestricted) and still exits 0.

    Exits with code 0 (allow) or 2 (block).  Code 1 is reserved for
    unknown event names in the dispatcher.

    Payload ingress (ticket 029-008): reads via one ``HookPayload.from_dict``
    call instead of hand-rolling the nested-then-flat file_path resolution
    itself — this is the exact rule that had drifted between this
    function and ``_log_hook_event`` and produced the 876-event fail-open
    incident. ``file_path`` below is reassigned by several later steps
    (root-relative normalization, etc.) — it starts as a local variable
    copy of ``hp.file_path``, not the frozen dataclass field itself.
    """
    hp = HookPayload.from_dict(payload)
    file_path = hp.file_path

    # Per-invocation cache: one Project instance, its parsed config, and
    # (lazily, on first need) one sqlite3 connection, reused by every
    # check below instead of each check site calling get_project() /
    # re-parsing config.yaml / opening its own connection.
    #
    # _load_role_guard_config() MUST run here, immediately after
    # get_project(), before ANY _proj.<property> access (including
    # _proj.db_path, touched a few lines down by _conn()) — it primes
    # _proj's own lazy paths-config cache from the one config.yaml parse
    # it does, so every later _proj.issues_dir / .db_path / .sprints_dir
    # / etc. access (each of which would otherwise independently
    # re-parse config.yaml the first time it's read) reuses that same
    # parse instead. Priming after some other property had already
    # triggered its own independent parse would defeat the whole point.
    #
    # _conn() only opens a connection the first time it is actually
    # needed (and never for a db_path that doesn't exist yet —
    # sqlite3.connect() itself would create an empty file as a side
    # effect, which none of the existing per-site `db_path.exists()`
    # guards ever did), so fast-exit paths that need no DB access at all
    # (claude-plans-dir, no-path, outside-root) pay nothing extra.
    _proj = get_project()
    _protected_paths, _excluded_paths = _load_role_guard_config(_proj)
    _db_conn: Optional[sqlite3.Connection] = None

    # Decision trail (ticket 028-005): short, informal tokens appended by
    # each check as it evaluates, so a hooks.log line records *why* a
    # decision was reached, not just *what* it was. Read (not reassigned)
    # by the _exit closure below, so no `nonlocal` is needed there.
    #
    # HookPayload.missing (ticket 029-008) is surfaced into this SAME
    # mechanism rather than a second parallel logging channel — any
    # expected-but-absent field it found (currently just file_path for
    # an Edit/Write/MultiEdit call) appears in every hooks.log line this
    # invocation produces, not only the no-path block below.
    decisions: list[str] = []
    if hp.missing:
        decisions.extend(f"missing={m}" for m in hp.missing)

    def _conn() -> Optional[sqlite3.Connection]:
        nonlocal _db_conn
        if _db_conn is None and _proj.db_path.exists():
            try:
                _db_conn = _proj.db.connect()
            except Exception:
                pass
        return _db_conn

    def _exit(code: int, reason: str) -> None:
        """Close the shared connection (if any), then exit the hook."""
        if _db_conn is not None:
            try:
                _db_conn.close()
            except Exception:
                pass
        _exit_hook("role-guard", payload, code, reason, decisions=decisions)

    # Claude Code's own plan-mode plan file (~/.claude/plans/<name>.md).
    # This lies outside the project root, so the general outside-root
    # allow below (reason "outside-root") already covers it. This narrower
    # pre-normalization check is retained only so its distinct
    # "claude-plans-dir" reason keeps appearing in logs for anyone grepping
    # for plan-file writes specifically — it is otherwise redundant.
    if file_path:
        try:
            _plans_dir = Path.home() / ".claude" / "plans"
            if Path(file_path).is_absolute() and (
                Path(file_path) == _plans_dir
                or _plans_dir in Path(file_path).parents
            ):
                decisions.append("match=claude-plans-dir")
                _exit(0, "claude-plans-dir")
        except (OSError, ValueError):
            # Malformed path string — fall through to normal handling
            # rather than raising out of a guard hook.
            pass

    # Normalize to a root-relative path string before any prefix comparison.
    # Claude Code sends ABSOLUTE file_path values (e.g.
    # "/Users/x/proj/clasi/issues/foo.md"), but every prefix this function
    # compares against (_prefix() below, and the historical allow/block
    # lists) is root-relative (e.g. "clasi/issues/"). Without this
    # normalization, startswith() never matches for real Claude Code
    # payloads and every tier-0/tier-1 allow-listed write is blocked. Runs
    # before the no-path check, recovery-state lookup, and safe_prefixes
    # check so all downstream comparisons see the same relative form.
    if file_path:
        file_path = _normalize_to_root_relative(file_path, project=_proj)

    caller_id = hp.caller_id

    agent_tier = os.environ.get("CLASI_AGENT_TIER", "")

    # If no env var, check the DB for the caller's own active-agent tier.
    # Keyed on caller_id — never a filter-less lookup, which with
    # concurrent agents would return an arbitrary agent's tier. Tracks
    # whether the tier came from the DB, so the block message at the end
    # can resolve the SAME record's agent name instead of the
    # CLASI_AGENT_NAME env default.
    _tier_source_db = False
    if not agent_tier:
        try:
            if _proj.db_path.exists():
                agent_tier = _proj.db.get_active_tier(caller_id, conn=_conn())
                if agent_tier:
                    _tier_source_db = True
        except Exception:
            pass

    decisions.append(f"tier={agent_tier or '0'}{'(db)' if _tier_source_db else ''}")

    # No path in payload — nothing to guard against. This must be fail
    # CLOSED for tier 0/1: directory-scope enforcement cannot be applied
    # without a path, and silently allowing here is exactly how the
    # payload-shape bug (reading file_path from the wrong nesting level)
    # went undetected. Tier 2 already has unrestricted write scope by
    # design once the ticket-state gate below has been checked, so
    # no-path is moot there — exempted here rather than exiting early,
    # so the ticket-state gate (which applies to tier 2) still runs for
    # tier 2 regardless of whether a path was resolved.
    if not file_path and agent_tier != "2":
        # payload.keys() here is a diagnostic-only listing (never used
        # for a decision) — it stays a direct read of the raw payload
        # this function still legitimately owns as its own parameter,
        # rather than adding a `raw_keys` field to HookPayload just for
        # one warning line's sake.
        present_keys = sorted(payload.keys()) if payload else []
        logger.warning(
            "role-guard: no file_path resolved from payload "
            "(tier=%s, payload keys=%s) — failing closed",
            agent_tier or "0", present_keys,
        )
        # decisions already carries "missing=file_path" from hp.missing
        # above when tool_name was Edit/Write/MultiEdit; a payload with
        # an unrecognized/absent tool_name still fails closed here (the
        # exit code and reason are unaffected either way), it just won't
        # carry that specific decision token.
        _exit(2, "no-path")

    # Outside-root writes are ALLOWED for every tier. CLASI's role-guard
    # governs one thing: direct writes to *this* repo's source and tests.
    # Anything outside the project root — the agent's own ~/.claude memory
    # and plan files, home-dir scratch, an unrelated checkout — is simply
    # not CLASI's business to police, and blocking it only cripples the
    # agent's legitimate work (e.g. persisting a memory file). Detection is
    # exact: _normalize_to_root_relative rewrites in-root absolute paths to
    # a relative form and returns everything else unchanged, so a path that
    # is STILL absolute here could not be made root-relative and therefore
    # lies outside the root. (An empty file_path never reaches this point —
    # the no-path gate above already handled it.) This supersedes the
    # narrow ~/.claude/plans/** allow-list above, which is retained only so
    # its specific "claude-plans-dir" reason keeps appearing in logs.
    if file_path and Path(file_path).is_absolute():
        decisions.append("match=outside-root")
        _exit(0, "outside-root")

    # OOP bypass: .clasi/oop (or legacy .clasi-oop) enables direct writes
    # for any tier. Used for out-of-process changes reviewed manually by
    # the team-lead. Reuses the shared connection (see _oop_active's
    # docstring for why this is safe).
    if _oop_active(conn=_conn()):
        decisions.append("match=oop-bypass")
        _exit(0, "oop-bypass")

    # Recovery state bypass: allows specific paths during sprint recovery
    # (e.g. resolving merge conflicts) when recorded in the state DB.
    # Matches directory-prefix entries as well as exact paths — see
    # _recovery_entry_matches().
    if _proj.db_path.exists():
        try:
            recovery = _proj.db.get_recovery_state(conn=_conn())
            if recovery and any(
                _recovery_entry_matches(entry, file_path, _proj)
                for entry in recovery.get("allowed_paths", [])
            ):
                decisions.append("match=recovery-state")
                _exit(0, "recovery")
        except Exception:
            pass

    # Safe prefixes: always allowed for any tier (configuration / meta files).
    # .claude/ — Claude Code settings, hooks, rules
    # CLAUDE.md — project coding instructions
    # AGENTS.md — agent instructions
    safe_prefixes = [".claude/", "CLAUDE.md", "AGENTS.md"]
    for prefix in safe_prefixes:
        if file_path == prefix or file_path.startswith(prefix):
            decisions.append(f"match={prefix}")
            _exit(0, "safe-prefix")

    # Staleness fail-closed gate: when this repo IS the CLASI source repo
    # (clasi.staleness._is_clasi_source_repo) and the running hook build
    # does not match this repo's own working tree ("dogfooding drift"),
    # block rather than silently enforce nothing. This is deliberately
    # narrower than the full staleness report: ordinary dependency-version
    # skew in a consumer project (signal 1, ambient importlib.metadata
    # drift) stays warn-only — it is too common and too blunt a signal to
    # fail closed on for every project that merely depends on clasi. Only
    # the structural "this repo is running a build of itself that isn't
    # its own source" case (signal 2) fails closed here, because that is
    # exactly the condition that let sprint 019's entire enforcement story
    # run inert while reporting success. Checked after OOP/recovery/
    # safe-prefix so the escape hatches for fixing the stale pointer
    # itself (.clasi/oop, editing .claude/ or .mcp.json via OOP) are never
    # blocked by the same staleness they exist to let you repair.
    from clasi import __version__ as _running_version
    from clasi.staleness import check_staleness

    _staleness = check_staleness(_proj.root, _running_version)
    if _staleness.repo_version is not None and any(
        "does not match this repo's editable source" in r
        or "is not running this working tree's code" in r
        for r in _staleness.reasons
    ):
        print(_staleness.warning(), file=sys.stderr)
        print(
            "CLASI ROLE VIOLATION: refusing to enforce role-guard from a "
            "stale build of this repo's own tooling. Fix .mcp.json / "
            ".claude/settings.json to invoke the editable install, or run "
            "`clasi oop on --reason '...'` to bypass (emergency fallback: "
            "create .clasi/oop if clasi itself is broken).",
            file=sys.stderr,
        )
        decisions.append("gate=stale-guard")
        _exit(2, "stale-guard")

    # _protected_paths / _excluded_paths were already resolved at the top
    # of this function (see _load_role_guard_config() there) — reused
    # here and by the protected_paths gate further down.

    # Build allow/block prefix sets from live Project properties.
    # Each prefix is root-relative so it matches the file_path strings
    # Claude Code sends (which are also root-relative).
    def _prefix(p: Path) -> str:
        """Return root-relative directory prefix with trailing slash.

        Falls back to the string representation of the path if it is not
        under the project root (e.g. the user configured an absolute path
        outside the repo).
        """
        try:
            return str(p.relative_to(_proj.root)) + "/"
        except ValueError:
            return str(p) + "/"

    _issues_prefix = _prefix(_proj.issues_dir)
    _reflections_prefix = _prefix(_proj.reflections_dir)
    _allow_prefixes = [
        _issues_prefix,
        _reflections_prefix,
        _prefix(_proj.design_dir),
        _prefix(_proj.clasi_dir),   # state files: config.yaml, log/, .clasi.db
        _prefix(_proj.log_dir),
    ]
    _block_prefixes = [
        _prefix(_proj.sprints_dir),
    ]

    # Ticket-state gate: tier-2 only (rescoped by ticket 026-001), and
    # exempt for issues_dir/reflections_dir writes even for tier 2 — see
    # the docstring above for the full rationale (exception-routing
    # deadlock).
    #
    # Ticket 029-010: also exempt for a tier-2 write to a ticket's OWN
    # .md file under this sprint's own tickets/ tree — both tickets/*.md
    # (the still-mid-transition case, e.g. an agent flips its own ticket
    # to status: done and then needs to check off its acceptance
    # criteria in the same file before it is moved) and tickets/done/*.md
    # (the reported bug: recording after-the-fact evidence, like a
    # benchmark citation, on a ticket already relocated to done/).
    # _get_active_tickets only ever recognizes "status: in-progress"
    # tickets still sitting directly in tickets/ (see its docstring), so
    # neither case can ever be satisfied by starting/resuming a ticket —
    # this gate would otherwise be permanently unsatisfiable for them.
    # A ticket file is process bookkeeping, not the production
    # source/tests this gate exists to police — the same reasoning that
    # already justifies the issues_dir/reflections_dir exemption above.
    if agent_tier == "2" and not (
        file_path.startswith(_issues_prefix) or file_path.startswith(_reflections_prefix)
    ):
        _sprint_log_dir, _sprint_id = _get_sprint_context(project=_proj, conn=_conn())
        _tickets_prefix = None
        if _sprint_id:
            _sprint_dir = _resolve_sprint_dir(_sprint_id, project=_proj)
            if _sprint_dir is not None:
                _tickets_prefix = _prefix(_sprint_dir / "tickets")
        if (
            _tickets_prefix is not None
            and file_path.startswith(_tickets_prefix)
            and file_path.endswith(".md")
        ):
            decisions.append("gate=ticket-state:tickets-exempt")
        elif _sprint_id:
            active_tickets = _get_active_tickets(_sprint_id, project=_proj)
            if not active_tickets:
                print(
                    f"CLASI ROLE VIOLATION: sprint {_sprint_id} execution lock "
                    "is held but no ticket is in-progress.\n"
                    "Start or resume a ticket via the execute-ticket flow, or "
                    "run `clasi oop on --reason '...'` to bypass (emergency "
                    "fallback: .clasi/oop).",
                    file=sys.stderr,
                )
                decisions.append("gate=ticket-state:no-ticket")
                _exit(2, "no-ticket")
            else:
                decisions.append("gate=ticket-state:ok")
        else:
            decisions.append("gate=ticket-state:skipped")

    # Tier 2 (programmer) can write anywhere — that's their job.
    # Checked after the ticket-state gate above (and after the no-path /
    # OOP / recovery / safe-prefix checks) so programmer subagents are
    # still subject to the ticket-state gate; this early return only
    # fires once that gate has confirmed either no lock is held, a
    # ticket is in-progress, or the write is issues/reflections-exempt.
    if agent_tier == "2":
        _exit(0, "tier-2")

    if agent_tier in ("", "0", "1"):
        # Check allow list: issues, reflections, design, clasi state, log.
        # Tier 1 was added here by ticket 026-001 — see the docstring
        # matrix note above.
        for alw in _allow_prefixes:
            if file_path.startswith(alw):
                decisions.append(f"match={alw}")
                _exit(0, "artifact-dir")

    # Sprint directories: tier 0 (team-lead) and tier 1 (sprint-planner)
    # may both write here directly (stakeholder decision, 2026-08-19 —
    # see clasi/issues/report-guard-friction-slowness-relax-tier-0-
    # restrictions.md). `create_ticket` remains MCP-gated separately
    # (mcp-guard) since ticket creation stays planner-owned; this is
    # only the role-guard file-write path.
    # All other paths (source, tests, config) are blocked — dispatch to tier 2.
    _sprints_prefix = _block_prefixes[0]
    if agent_tier in ("", "0", "1") and file_path.startswith(_sprints_prefix):
        decisions.append(f"match={_sprints_prefix}")
        _exit(0, "tier-1")

    # protected_paths gate: when the stakeholder has explicitly configured
    # protected_paths: in config.yaml (typically at `clasi init`, pointing
    # at the project's actual source/test directories), tier 0/1 writes
    # are blocked ONLY under those prefixes (plus sprints_dir, already
    # handled above) — anything else (test harnesses, docs, misc repo
    # tooling that isn't product source or tests) is allowed through.
    #
    # An empty protected_paths (the "not configured" case — see
    # Project.protected_paths) is deliberately NOT treated as "nothing is
    # protected": that would silently disable enforcement for every
    # existing project that hasn't re-run `clasi init` since this feature
    # shipped. Only an explicitly non-empty list switches to this
    # allow-by-default mode; otherwise control falls through to the
    # pre-existing block-by-default behavior below.
    if _protected_paths:
        # excluded_paths carves out subdirectories of a protected prefix
        # that aren't actually source/tests (e.g. tests/e2e/ Docker
        # harness scripts under a protected tests/ root) — checked first
        # so an exclusion always wins over a broader protected prefix.
        if any(file_path.startswith(p) for p in _excluded_paths):
            decisions.append("match=excluded-path")
            _exit(0, "excluded-path")
        if not any(file_path.startswith(p) for p in _protected_paths):
            decisions.append("gate=protected-paths:outside")
            _exit(0, "outside-protected-paths")
        decisions.append("gate=protected-paths:inside")

    # --- BLOCK ---
    # If we reach here, the write is not permitted for this tier.
    # tier 0 / unset: source code, tests, config, non-clasi docs → BLOCK
    # tier 1:         source code, tests, config, non-sprint docs  → BLOCK
    agent_name = os.environ.get("CLASI_AGENT_NAME", "team-lead")
    if _tier_source_db and _proj.db_path.exists():
        # Tier was resolved from the DB, not the env var — name the
        # SAME DB-registered agent rather than the (typically unset for
        # a dispatched subagent) CLASI_AGENT_NAME default.
        try:
            _record = _proj.db.get_active_agent(caller_id, conn=_conn())
            if _record and _record.get("agent_type"):
                agent_name = _record["agent_type"]
        except Exception:
            pass
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
    decisions.append("gate=no-allow-match")
    _exit(2, "blk-write")


# ---------------------------------------------------------------------------
# MCP Guard — PreToolUse hook for create_ticket / create_sprint
# ---------------------------------------------------------------------------


def handle_mcp_guard(payload: dict) -> None:
    """Block Tier 0 (team-lead) from calling artifact-creation MCP tools directly.

    The sprint-planner (Tier 1) and programmer (Tier 2) are allowed.
    OOP bypass: if .clasi/oop (or legacy .clasi-oop) exists, allow all tiers.

    Payload ingress (ticket 029-008): reads tool_name/caller_id via one
    HookPayload.from_dict call — see handle_role_guard's matching note.
    """
    hp = HookPayload.from_dict(payload)

    # Decision trail (ticket 028-005): see handle_role_guard's matching
    # comment — short, informal tokens appended as each check evaluates.
    decisions: list[str] = []

    # OOP bypass
    if _oop_active():
        decisions.append("match=oop-bypass")
        _exit_hook("mcp-guard", payload, 0, "oop-bypass", decisions=decisions)

    # Staleness fail-closed gate — see the matching gate and rationale in
    # handle_role_guard. Same narrow scope: only the structural "this repo
    # is running a build of itself that isn't its own source" signal fails
    # closed; ordinary dependency-version skew stays warn-only.
    from clasi import __version__ as _running_version
    from clasi.staleness import check_staleness

    _staleness = check_staleness(get_project().root, _running_version)
    if _staleness.repo_version is not None and any(
        "does not match this repo's editable source" in r
        or "is not running this working tree's code" in r
        for r in _staleness.reasons
    ):
        print(_staleness.warning(), file=sys.stderr)
        print(
            "CLASI ROLE VIOLATION: refusing to enforce mcp-guard from a "
            "stale build of this repo's own tooling. Fix .mcp.json / "
            ".claude/settings.json to invoke the editable install, or run "
            "`clasi oop on --reason '...'` to bypass (emergency fallback: "
            "create .clasi/oop if clasi itself is broken).",
            file=sys.stderr,
        )
        decisions.append("gate=stale-guard")
        _exit_hook("mcp-guard", payload, 2, "stale-guard", decisions=decisions)

    caller_id = hp.caller_id

    agent_tier = os.environ.get("CLASI_AGENT_TIER", "")

    # If no env var, check the DB for the caller's own active-agent tier.
    # Keyed on caller_id — never a filter-less lookup, which with
    # concurrent agents would return an arbitrary agent's tier.
    _tier_source_db = False
    if not agent_tier:
        try:
            db_path_tier = get_project().db_path
            if db_path_tier.exists():
                from clasi.state_db import get_active_tier
                agent_tier = get_active_tier(str(db_path_tier), caller_id)
                if agent_tier:
                    _tier_source_db = True
        except Exception:
            pass

    decisions.append(f"tier={agent_tier or '0'}{'(db)' if _tier_source_db else ''}")

    # Only tiers 1 (sprint-planner) and 2 (programmer) are allowed to call
    # artifact-creation MCP tools directly — an explicit ALLOWLIST (ticket
    # 029-009). Before this it was a denylist (`agent_tier not in ("",
    # "0")`): any UNRECOGNIZED tier string ("3", "junk", a future tier
    # that doesn't exist yet, or a corrupted/garbage DB value) fell
    # through to ALLOW by default — the same "unanticipated input
    # defaults to the unsafe action" shape as the crash class this ticket
    # closes elsewhere. Tier 0 (team-lead) and any unrecognized value now
    # both fall through to the block below.
    if agent_tier in ("1", "2"):
        _exit_hook("mcp-guard", payload, 0, "tier-allowed", decisions=decisions)

    tool_name = hp.tool_name
    print(
        f"CLASI ROLE VIOLATION: team-lead cannot call {tool_name} directly.\n"
        "Dispatch to sprint-planner agent to create planning artifacts.",
        file=sys.stderr,
    )
    decisions.append("gate=tier-0-blocked")
    _exit_hook("mcp-guard", payload, 2, "blk-mcp", decisions=decisions)


# ---------------------------------------------------------------------------
# Log directory resolution
# ---------------------------------------------------------------------------


def _get_sprint_context(
    project: Optional[Project] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> tuple[Optional[Path], str]:
    """Return (log_dir, sprint_id) for the current sprint context.

    log_dir is None if the clasi_dir does not exist (handlers should exit 0).
    If an execution lock is held, log_dir is a sprint-scoped subdirectory
    (.clasi/log/sprint-{sprint_id}/), creating it if needed.
    Otherwise log_dir is .clasi/log.
    sprint_id is the active sprint ID string, or empty string if none.

    *project* and *conn*, when given, are used instead of calling
    ``get_project()`` / opening a new connection — lets a caller that
    already resolved its own ``Project`` (and, if needed, an open
    connection) for the current invocation (e.g. ``handle_role_guard``'s
    per-invocation cache) reuse both. Both default to None, preserving
    this function's original independent resolution for every other
    caller (status-inject, subagent-start, subagent-stop, ...).
    """
    _proj = project if project is not None else get_project()
    if not _proj.clasi_dir.exists():
        return None, ""
    log_base = _proj.log_dir
    log_base.mkdir(parents=True, exist_ok=True)
    _ensure_log_gitignore(log_base)

    db_path = _proj.db_path
    if db_path.exists():
        try:
            lock = _proj.db.get_lock_holder(conn=conn)
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

    Returns None if clasi_dir does not exist (handlers should exit 0).
    If an execution lock is held, returns a sprint-scoped subdirectory
    (.clasi/log/sprint-{sprint_id}/), creating it if needed.
    Otherwise returns .clasi/log.
    """
    log_dir, _ = _get_sprint_context()
    return log_dir


def _resolve_sprint_dir(sprint_id: str, project: Optional[Project] = None) -> Optional[Path]:
    """Return the sprint directory matching *sprint_id*, or None if not found.

    Scans ``sprints_dir`` for a directory whose name starts with
    ``"{sprint_id}-"`` (the standard ``NNN-slug`` sprint directory naming
    convention). Factored out of :func:`_get_active_tickets` (ticket
    029-010) so the role-guard ticket-state gate's ``tickets/`` exemption
    can resolve the same sprint directory without duplicating this
    ``iterdir()`` scan.

    *project*, when given, is used instead of calling ``get_project()`` —
    same convention as :func:`_get_active_tickets`.
    """
    if not sprint_id:
        return None
    try:
        sprints_base = (project if project is not None else get_project()).sprints_dir
        if not sprints_base.exists():
            return None
        for candidate in sprints_base.iterdir():
            if candidate.is_dir() and candidate.name.startswith(f"{sprint_id}-"):
                return candidate
    except Exception:
        return None
    return None


def _get_active_tickets(sprint_id: str, project: Optional[Project] = None) -> list[str]:
    """Return a list of in-progress ticket IDs for the given sprint.

    Scans the sprints_dir for the sprint directory matching sprint_id, then
    reads tickets/ for files with status: in-progress in their frontmatter.
    Returns ticket IDs in the format "{sprint_id}-{ticket_id}" (e.g. "002-007").
    Returns an empty list on any error or if no in-progress tickets found.

    *project*, when given, is used instead of calling ``get_project()`` —
    lets a caller that already resolved its own ``Project`` for the
    current invocation reuse it. Omitted (the default), behavior is
    unchanged.
    """
    if not sprint_id:
        return []
    try:
        sprint_dir = _resolve_sprint_dir(sprint_id, project=project)
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
# Status injection — UserPromptSubmit hook
# ---------------------------------------------------------------------------


def _add_gate_imperative(narrowed: dict, sprint_id: str, active_tickets: list[str]) -> None:
    """Append the ticket-gate imperative sentence to *narrowed*'s notes, in place.

    When a sprint execution lock is held (``sprint_id`` is non-empty) and no
    ticket in that sprint is ``in-progress`` (``active_tickets`` is empty),
    source edits are gated closed by the role-guard ticket-state gate
    (ticket 004). Callers other than tier-2 already see that gate as a
    BLOCK on their next write; this note makes the same fact visible
    up-front in the status block, so the agent does not need to attempt a
    write just to discover the gate.  Names both sanctioned exits: resume
    or start a ticket via execute-ticket, or run ``clasi oop on --reason``
    (checked only via the shared :func:`_oop_active` helper — never
    reimplemented; the ``.clasi/oop`` file remains the emergency fallback).

    No-op if a ticket is active, no sprint is executing, or OOP bypass is
    already active (the gate does not apply in that case).
    """
    if not sprint_id or active_tickets or _oop_active():
        return
    notes = narrowed.setdefault("notes", {})
    imperative = (
        f"Sprint {sprint_id} execution lock is held but no ticket is "
        "in-progress: source edits are gated closed (role-guard "
        "ticket-state gate). Start or resume a ticket via the "
        "execute-ticket flow, or run `clasi oop on --reason '...'` to "
        "bypass (emergency fallback: .clasi/oop)."
    )
    existing_focus = notes.get("current_focus", "")
    notes["current_focus"] = (
        f"{existing_focus} {imperative}".strip() if existing_focus else imperative
    )


def _trim_empty_preflight_sprints(narrowed: dict) -> None:
    """Drop ``available_transitions`` from sprint entries with zero
    tickets, in place (sprint 026 / ticket 003).

    A sprint with ``tickets.total == 0`` cannot be in the ``ticketed``,
    ``executing``, ``review``, or ``closed`` states (all four require at
    least one ticket file — see ``is_at_least_one_ticket`` in
    ``sprint.yaml``), so it is necessarily still in an early, empty
    pre-flight state (``open``/``planned``/``pre-flight``) with nothing
    for anyone to act on right now. Its ``available_transitions`` list
    (each entry carrying a nested ``blocked_by`` list) measured as about
    61% of a typical injected status block's byte size and is pure noise
    for that state — nobody is currently blocked on firing a transition
    for a sprint that has no tickets yet.

    Sprints with at least one ticket (``tickets.total > 0``, including
    the currently-executing sprint) are never touched — their
    ``available_transitions``/``blocked_by`` detail is exactly the
    "next step" information the status block exists to surface.
    """
    for sprint_entry in narrowed.get("sprints", []):
        tickets = sprint_entry.get("tickets") or {}
        if tickets.get("total", 0) == 0:
            sprint_entry.pop("available_transitions", None)


# Agent role string (as consumed by _build_status_block / narrow_status)
# -> CLASI tier. Distinct from _AGENT_TYPE_TIERS below (keyed on the raw
# SubagentStart `agent_type` payload field instead of the already-resolved
# role) because the two call sites hand _write_scope_block different
# strings: handle_subagent_start converts agent_type -> role via
# _AGENT_TYPE_TO_ROLE before calling _build_status_block, and
# handle_status_inject reads the role directly from $CLASI_AGENT_NAME.
_ROLE_TO_TIER = {"team-lead": "0", "sprint-planner": "1", "programmer": "2"}


def _write_scope_block(agent: str, project: Project) -> str:
    """Return a short, tier-scoped write-scope summary (ticket 031-004).

    An agent previously had no way to learn its write scope except by
    being blocked first by :func:`handle_role_guard` — this surfaces the
    SAME policy that function enforces (post ticket-003 relaxation: tier
    0/1 blocked only under configured ``protected_paths`` — or, when
    unconfigured, the pre-existing artifact-allow-list-then-block
    fallback; tier 2 unrestricted by directory, gated only by the
    ticket-state lock) as a 3-4 line human-readable summary. Folded into
    the same status block string both :func:`handle_status_inject`
    (tier 0, every prompt) and :func:`handle_subagent_start` (tier 1/2,
    on dispatch) already print, via :func:`_build_status_block`.

    DISPLAY only: reads ``Project.protected_paths`` (the same config
    ``handle_role_guard`` reads) purely to describe the policy, and never
    calls into or otherwise influences that function's actual decision
    logic — ticket 031-004 explicitly scopes out touching the
    role-guard/mcp-guard gates themselves.

    Cheap by construction, since this also runs on the status-inject hot
    path (fires on every UserPromptSubmit, sub-200ms budget, zero
    subprocess spawns): one ``Project.protected_paths`` property read
    (a single config.yaml parse, no subprocess, no directory walk).
    Never raises — returns ``""`` on any failure so a broken summary
    never takes down the rest of the status block.
    """
    try:
        tier = _ROLE_TO_TIER.get(agent, "0")
        oop_line = (
            "- OOP recovery: `clasi oop on --reason '...'` "
            "(emergency: .clasi/oop)"
        )

        if tier == "2":
            lines = [
                "## CLASI write scope",
                "",
                "- tier 2 (programmer) allowed: anywhere in the project — that's the role",
                "- tier 2 blocked: nothing by directory; gated by an active "
                "ticket lock while a sprint execution lock is held "
                "(issues/reflections exempt)",
                oop_line,
                "",
            ]
            return "\n".join(lines)

        role_label = "sprint-planner (tier 1)" if tier == "1" else "team-lead (tier 0)"
        protected = project.protected_paths
        if protected:
            allowed = "everywhere else in the project (protected_paths is configured)"
            blocked = ", ".join(p.rstrip("/") for p in protected)
        else:
            allowed = (
                "issues/reflections/design/sprints/.clasi state dirs, "
                "anything outside the project root"
            )
            blocked = (
                "everything else (protected_paths not configured — run "
                "`clasi init` to scope this to your project's actual "
                "source/test dirs)"
            )

        lines = [
            "## CLASI write scope",
            "",
            f"- {role_label} allowed: {allowed}",
            f"- {role_label} blocked: {blocked}",
            oop_line,
            "",
        ]
        return "\n".join(lines)
    except Exception:
        logger.warning("write-scope summary: failed to build", exc_info=True)
        return ""


def _build_status_block(agent: str, skip_inconsistencies: bool = False) -> str:
    """Build a ``## CLASI status`` fenced YAML block for *agent*.

    Resolves the active ``sprint_id`` via :func:`_get_sprint_context` and,
    for the ``programmer`` role, the active ``ticket_id`` via
    :func:`_get_active_tickets`, then threads both into
    :func:`~clasi.status.narrow_status` so the returned view is actually
    scoped to the requesting agent (rather than always the team-lead's
    full view, which is what passing no ids produces).

    The status-block assembly excludes ``done/`` sprints and tickets
    (``exclude_done=True``) — this hook path is the only caller that opts
    into that; on-demand callers (MCP tools) still see full history. It
    also drops ``available_transitions``/``blocked_by`` detail for any
    sprint with zero tickets (see :func:`_trim_empty_preflight_sprints`)
    — the same "hook path only" scoping as ``exclude_done``.

    *skip_inconsistencies*, when True, skips
    :func:`~clasi.status.inconsistency.detect_inconsistencies` (measured
    at about 400ms). Only :func:`handle_status_inject` (the
    ``UserPromptSubmit`` hook, fired on every prompt) passes True;
    :func:`handle_subagent_start` leaves it False, and the ``clasi
    status`` CLI / ``get_status`` MCP tool never go through this function
    at all — they call :func:`~clasi.status.build_status` directly with
    the default ``skip_inconsistencies=False``.

    Returns an empty string if building fails (e.g. no status data
    available). Never raises — callers rely on this being safe. Failures
    are logged as a warning so a broken status hook is observable instead
    of silently indistinguishable from "nothing to report".

    Prepends a staleness warning (see :mod:`clasi.staleness`) whenever the
    running ``clasi hook`` invocation is stale relative to the project it
    is serving — this is the actual production invocation path (bare
    ``clasi hook status-inject`` from ``.claude/settings.json``), so this
    is where drift like the one that voided sprint 019's enforcement is
    actually visible to the operator, on every turn.

    Appends a ``## CLASI write scope`` summary (see :func:`_write_scope_block`,
    ticket 031-004) after the fenced YAML block, tier-scoped from *agent*
    the same way the status block itself is — this is what makes the
    write-scope summary appear both in handle_status_inject's tier-0
    output (every prompt) and handle_subagent_start's tier-1/2 output (on
    dispatch), from this one call site. Silently omitted (not appended)
    if it fails to build; the YAML status block above is unaffected
    either way.
    """
    staleness_block = ""
    try:
        from clasi import __version__ as _running_version
        from clasi.staleness import check_staleness

        report = check_staleness(get_project().root, _running_version)
        if report.stale:
            staleness_block = f"## CLASI staleness warning\n\n{report.warning()}\n\n"
    except Exception:
        logger.warning("status-inject: staleness check failed", exc_info=True)

    try:
        from clasi.status import build_status, narrow_status
        from clasi.status.formatting import to_yaml

        project = get_project()
        _, sprint_id = _get_sprint_context()

        active_tickets = _get_active_tickets(sprint_id) if sprint_id else []
        ticket_id = active_tickets[0] if agent == "programmer" and active_tickets else None

        full = build_status(
            project, agent=agent, sprint_id=sprint_id or None,
            ticket_id=ticket_id, exclude_done=True,
            skip_inconsistencies=skip_inconsistencies,
        )
        narrowed = narrow_status(
            full, agent=agent, sprint_id=sprint_id or None, ticket_id=ticket_id,
        )
        _add_gate_imperative(narrowed, sprint_id, active_tickets)
        _trim_empty_preflight_sprints(narrowed)
        yaml_text = to_yaml(narrowed)
        block = f"{staleness_block}## CLASI status\n\n```yaml\n{yaml_text}```\n"
        scope_block = _write_scope_block(agent, project)
        if scope_block:
            block += f"\n{scope_block}"
        return block
    except Exception:
        logger.warning("status-inject: failed to build status block", exc_info=True)
        return staleness_block


def handle_status_inject(payload: dict) -> None:
    """Inject a ``## CLASI status`` block for the ``UserPromptSubmit`` event.

    Reads ``$CLASI_AGENT_NAME`` to determine the agent scope (default:
    ``team-lead``).  Calls :func:`build_status` + :func:`narrow_status`,
    serializes to YAML, and prints the fenced block to stdout so Claude Code
    prepends it to the context window.

    Silent no-op (exit 0, no output) only if ``.clasi/`` does not exist
    (project not CLASI-initialized).

    This is the hot per-prompt path (fires on every ``UserPromptSubmit``),
    so it calls :func:`_build_status_block` with ``skip_inconsistencies=True``
    — the ``detect_inconsistencies`` pass (about 400ms) is skipped here
    only; ``clasi status`` and the ``project-status`` skill still run it.

    When OOP bypass is active (either channel — file or DB, see
    ``_oop_active``/``_oop_status_lines``), this NEVER goes silent: it
    emits a minimal, non-empty status block naming the active channel(s),
    and reason/age/expiry where the channel has that metadata (the DB
    channel does; the bare file marker does not). An active bypass being
    invisible on every prompt was the prior (deliberately changed)
    behavior — a forgotten flag must stay visible, not silently void
    enforcement forever.
    """
    project = get_project()
    if not project.clasi_dir.exists():
        _exit_hook("status-inject", payload, 0, "no-clasi")
    if _oop_active():
        lines = _oop_status_lines()
        block = "## CLASI status\n\n" + "\n".join(lines) + "\n"
        print(block)
        _exit_hook("status-inject", payload, 0, "oop-bypass")

    agent = os.environ.get("CLASI_AGENT_NAME", "team-lead")
    block = _build_status_block(agent, skip_inconsistencies=True)
    if block:
        print(block)
    _exit_hook("status-inject", payload, 0, "injected")


# ---------------------------------------------------------------------------
# Subagent lifecycle logging — SubagentStart / SubagentStop
# ---------------------------------------------------------------------------

# Maps agent_type values to CLASI agent role names for status narrowing.
_AGENT_TYPE_TO_ROLE = {
    "programmer": "programmer",
    "sprint-planner": "sprint-planner",
}

# Backstop TTL (hours) for active_agents rows, swept from handle_subagent_start.
# This project's subagents run for minutes, occasionally low hours for a long
# ticket; a 24h-old "active" row (the old StateDB default) is never a real
# in-flight agent, only a ghost left by a stop event that was missed (crash,
# kill -9, hook misconfiguration). 2 hours is comfortably above the longest
# normal single-agent run observed in this project while still purging
# ghosts within the same working session rather than letting them survive
# for a full day and keep skewing get_active_tier lookups for other callers
# who happen to share no agent_id filter (pre-Part-A) or simply pollute the
# table indefinitely (post-Part-A, ghosts no longer corrupt lookups but
# still accumulate rows forever without this sweep).
_STALE_AGENT_TTL_HOURS = 2


def handle_subagent_start(payload: dict) -> None:
    """Log when a subagent starts and prepend a CLASI status block.

    Creates a log file in .clasi/log/ with frontmatter. The stop
    hook appends the transcript to this same file.

    Also emits a ``## CLASI status`` block to stdout (unless the project
    is not CLASI-initialized or ``.clasi/oop`` exists), scoped to the
    subagent's role as inferred from ``agent_type`` in the payload.

    Payload ingress (ticket 029-008): reads via one HookPayload.from_dict
    call. ``agent_id`` below stays the RAW, un-combined value (written
    verbatim into the log file's frontmatter) — deliberately distinct
    from ``marker_id`` a few lines down, which uses the combined
    ``caller_id`` (agent_id falling back to session_id) for DB
    registration, matching this function's pre-existing behavior exactly.
    """
    hp = HookPayload.from_dict(payload)
    log_dir, sprint_id = _get_sprint_context()
    if log_dir is None:
        _exit_hook("sub-start", payload, 0, "no-log-dir")

    agent_type = hp.agent_type or "unknown"
    agent_id = hp.agent_id
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
    marker_id = hp.caller_id or "unknown"
    try:
        db_path = get_project().db_path
        if db_path.exists() or (db_path.parent.exists()):
            from clasi.state_db import register_active_agent, clear_stale_agents

            # Backstop purge: handle_subagent_stop is the primary removal
            # path (removes by marker_id on every stop), but this sweep
            # catches ghosts left by any stop event that never fires
            # (crash, kill -9, hook misconfiguration). Runs on every
            # subagent dispatch — cheap, and keeps active_agents from
            # accumulating unbounded rows in normal operation.
            clear_stale_agents(str(db_path), ttl_hours=_STALE_AGENT_TTL_HOURS)

            register_active_agent(
                str(db_path), marker_id, agent_type, tier, str(log_file)
            )
    except Exception:
        pass

    # Prepend status block — scoped to the subagent's role.
    # Silent if OOP bypass is active (.clasi/oop or legacy .clasi-oop).
    if not _oop_active():
        agent_role = _AGENT_TYPE_TO_ROLE.get(agent_type, "team-lead")
        block = _build_status_block(agent_role)
        if block:
            print(block)

    _exit_hook("sub-start", payload, 0, "logged")


def handle_subagent_stop(payload: dict) -> None:
    """Append transcript to the log file created by subagent-start.

    Payload ingress (ticket 029-008): reads via one HookPayload.from_dict
    call — see handle_role_guard's matching note.
    """
    hp = HookPayload.from_dict(payload)
    log_dir = _get_log_dir()
    if log_dir is None:
        _exit_hook("sub-stop", payload, 0, "no-log-dir")

    last_message = hp.last_assistant_message
    transcript_path = hp.transcript_path
    stop_time = datetime.now(timezone.utc)

    # Find the log file from the DB record written by subagent-start
    marker_id = hp.caller_id or "unknown"
    log_file = None
    started_at = None
    try:
        db_path = get_project().db_path
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
    lines.extend(["", "# Raw JSON Transcript", "", "```json", pretty, "```", ""])
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


# ---------------------------------------------------------------------------
# Plan-to-Issue — PostToolUse hook for ExitPlanMode
# ---------------------------------------------------------------------------


def handle_plan_to_issue(payload: dict) -> None:
    """Convert the most recent plan file to a CLASI issue.

    Calls plan_to_issue() with the standard directories and prints the
    path of the created issue file if one was created.

    Routed through ``_exit_hook`` (ticket 028-005) instead of raw
    ``sys.exit`` so ``plan-to-issue`` events finally appear in
    ``hooks.log`` — previously zero ever did.

    Payload ingress (ticket 029-008): reads via one HookPayload.from_dict
    call — ``plan_file_path`` uses its own distinct fallback (``{}`` when
    ``tool_input`` is absent, not the whole payload) — see
    ``HookPayload.from_dict``'s docstring.
    """
    from clasi.plan_to_issue import plan_to_issue

    hp = HookPayload.from_dict(payload)
    plan_file = Path(hp.plan_file_path) if hp.plan_file_path else None

    result = plan_to_issue(
        Path.home() / ".claude" / "plans",
        get_project().issues_dir,
        plan_file=plan_file,
    )
    if result:
        print(
            json.dumps({
                "decision": "block",
                "reason": (
                    f"CLASI: Plan saved as issue: {result}. "
                    "This file is a verbatim copy of the plan and is NOT yet in "
                    "house issue format — rewrite it now, in place, before doing "
                    "anything else. The reader is a future sprint-planner with no "
                    "session context, not the session that just ran.\n\n"
                    "Rewrite steps:\n"
                    "1. Read the file at the path above.\n"
                    "2. Reshape its body into the house issue format: `# Title`, "
                    "then `## Description`, `## Cause`, `## Proposed fix`, "
                    "`## Verification`, `## Related` (omit any section with "
                    "nothing to say).\n"
                    "3. Drop plan-mode-only sections and framing that address the "
                    "planning session rather than the issue's reader — e.g. "
                    "'Scope of this plan', 'Do not implement', 'Deliverable', "
                    "'Files to touch (this plan)', or any instruction to create "
                    "the issue file that this document already is.\n"
                    "4. Keep the `status: pending` frontmatter unchanged.\n"
                    "5. If the filename starts with a redundant `issue-` prefix "
                    "(it already lives in the issues directory), rename the file "
                    "to drop that prefix.\n"
                    "6. Do NOT implement the issue's contents. Confirm the "
                    "rewritten issue file was saved and stop."
                ),
            }),
            file=sys.stderr,
        )
        _exit_hook("plan-to-issue", payload, 2, "rewrite-req")
    _exit_hook("plan-to-issue", payload, 0, "no-file")


# Backward-compatible alias
handle_plan_to_todo = handle_plan_to_issue


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


# Event names sprint 026 (ticket 004) retired end to end: their
# hooks.json / .claude/settings.json registrations, handler functions,
# _ROUTING_TABLE entries, and cli.py Choice entries were all removed as
# dead code (0 of 2,447 logged hook events, ever). Hook registrations are
# snapshotted at session start, or baked into a consumer project's
# .claude/settings.json by whatever `clasi init` last wrote there — both
# upgrade on a different schedule than the CLI itself. A session or
# install can therefore still invoke one of these names long after the
# code that served it is gone; sprint 027 (ticket 001) makes that a
# graceful no-op (exit 0, one stderr deprecation line, a hooks.log entry)
# instead of the hard error every other unrecognized name still gets.
#
# This is a small, explicitly named allowlist for *known* retirements,
# not a blanket catch-all for any unrecognized name — a typo in a brand
# new registration must keep failing loudly. See this sprint's
# design/DESIGN.md ("Design Rationale") for why the catch-all
# alternative was rejected. The allowlist is a bridge to re-running
# `clasi init` (which drops these from a fresh install), not a
# permanent mechanism — expect it to need pruning as these retirements
# age out of realistic installed-registration lifetimes.
_RETIRED_EVENTS = frozenset({"commit-check", "task-created", "task-completed"})


def handle_hook(event: str) -> None:
    """Read stdin JSON and dispatch to the correct hook handler.

    Routes the event name to the appropriate handler function. A name in
    _RETIRED_EVENTS no-ops (exit 0, one stderr deprecation line, a
    hooks.log entry) instead of erroring — see that set's docstring.
    Exits with code 1 for any other unrecognized event name, unchanged.
    """
    payload = read_payload()

    _ROUTING_TABLE = {
        "role-guard": handle_role_guard,
        "subagent-start": handle_subagent_start,
        "subagent-stop": handle_subagent_stop,
        "mcp-guard": handle_mcp_guard,
        "plan-to-issue": handle_plan_to_issue,
        "plan-to-todo": handle_plan_to_issue,  # backward-compatible alias
        "status-inject": handle_status_inject,
    }

    handler = _ROUTING_TABLE.get(event)
    if handler is None:
        if event in _RETIRED_EVENTS:
            print(
                f"clasi hook: '{event}' is retired and no longer does "
                "anything; re-run `clasi init` to refresh this project's "
                "hook registrations.",
                file=sys.stderr,
            )
            _exit_hook(event, payload, 0, "retired-evt")
        print(f"clasi hook: unknown event '{event}'", file=sys.stderr)
        sys.exit(1)

    if event in ("role-guard", "mcp-guard"):
        # Guard fail-closed exception boundary (ticket 029-009): any
        # exception raised inside role-guard/mcp-guard's dispatch — a
        # genuine crash, never the guard's own normal allow/deny exit
        # (see the SystemExit note below) — is caught, logged, and
        # converted into a hard block: _exit_hook(event, payload, 2,
        # "guard-crash"). That call already performs both the hooks.log
        # "guard-crash" line (with the same payload dump every other
        # exit-2 decision gets — see _log_hook_event's deny-payload-dump
        # docstring) AND sys.exit(2), so it supersedes the separate
        # _log_hook_event(...) + bare `raise` pair this block used to be.
        # A full traceback is captured via logger.exception BEFORE that
        # exit, so the crash's actual cause remains recoverable from
        # ordinary log output even though the single-line hooks.log
        # record itself only ever carries the fixed "guard-crash" reason
        # token, not the traceback text.
        #
        # This converts sprint 028 ticket 005's deliberate catch/log/
        # re-raise-UNCHANGED contract (git show 5b3079b) into the
        # fail-closed one that ticket explicitly reserved for this
        # sprint: previously ANY unanticipated bug inside a guard was a
        # silent, unlogged ALLOW once the exception propagated past this
        # dispatcher — this repo's own hooks.log holds 876 historical
        # `role-guard 0 no-path` events from exactly that failure class.
        # After this change, the identical bug is a loud, logged BLOCK
        # instead. `.clasi/oop` (file-checked first, unconditional, and
        # itself unaffected by anything in this guard chain) remains the
        # escape hatch for a project that hits an unexpected block.
        #
        # SystemExit — the guard's own normal allow/deny exit via
        # _exit_hook — is a BaseException, not an Exception, so it is
        # never intercepted here; only a genuine internal crash is.
        try:
            handler(payload)
        except Exception:
            logger.exception(
                "%s: guard-internal exception — failing closed", event,
            )
            _exit_hook(event, payload, 2, "guard-crash")
    else:
        handler(payload)
