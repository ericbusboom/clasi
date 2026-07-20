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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from clasi.project import Project

logger = logging.getLogger(__name__)


def get_project() -> Project:
    """Return a Project instance rooted at the current working directory."""
    return Project(Path.cwd())


def _normalize_to_root_relative(file_path: str) -> str:
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
    """
    p = Path(file_path)
    if not p.is_absolute():
        return file_path
    try:
        return p.relative_to(get_project().root).as_posix()
    except ValueError:
        return file_path


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


def _oop_active() -> bool:
    """Return True if out-of-process (OOP) bypass is active for this project.

    Checks ``.clasi/oop`` first (canonical — matches the documented escape
    hatch in ``.claude/rules/*.md`` and the ``oop`` skill), then falls back
    to the legacy ``.clasi-oop`` (repo root, hyphen) so any session already
    relying on the old flag file keeps working.

    Resolves the project root by walking up from the current working
    directory (see ``_find_project_root``) rather than assuming cwd is the
    repo root — a PreToolUse hook can fire with cwd set to a subdirectory
    (e.g. editing a file two directories deep), and a bare relative-path
    check silently returns False in that case even though the flag file
    exists at the real project root. This was confirmed to make
    `.clasi/oop` invisible to this check when cwd was `tests/e2e/` while
    the flag lived at the repo root.

    This is the single result and root-resolution point for OOP bypass. No
    handler in this module may check either flag-file path directly —
    always call this helper, so the two flag files can never drift out of
    sync and the cwd-vs-root resolution is never duplicated.
    """
    root = _find_project_root(Path.cwd())
    return (root / ".clasi" / "oop").exists() or (root / ".clasi-oop").exists()


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
) -> None:
    """Append a single line to .clasi/log/hooks.log.

    Called just before sys.exit(). Includes the exit code and a
    fixed-width 12-char reason code.

    Creates .clasi/log/ if .clasi/ exists. Wraps everything in
    try/except so logging never causes a hook to fail.
    """
    try:
        _proj = get_project()
        if not _proj.clasi_dir.exists():
            return
        log_dir = _proj.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        _ensure_log_gitignore(log_dir)

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

    Allowed/blocked write matrix
    ─────────────────────────────────────────────────────────────────────────
    Path                          tier 0   tier 1   tier 2   OOP
    ────────────────────────────  ──────   ──────   ──────   ───
    ~/.claude/plans/**            ALLOW    ALLOW    ALLOW    ALLOW
    .claude/**  /  CLAUDE.md      ALLOW    ALLOW    ALLOW    ALLOW
    AGENTS.md                     ALLOW    ALLOW    ALLOW    ALLOW
    .clasi/  (non-sprint)         ALLOW    ALLOW    ALLOW    ALLOW
    .clasi/sprints/**             BLOCK    ALLOW    ALLOW    ALLOW
    Source / tests / config       BLOCK    BLOCK    ALLOW    ALLOW
    (anything else)               BLOCK    BLOCK    ALLOW    ALLOW
    ─────────────────────────────────────────────────────────────────────────

    ~/.claude/plans/** (the harness plan-mode plan file, and the exact
    artifact clasi's own plan_to_issue PostToolUse hook harvests) is
    allow-listed via an absolute-path comparison against the RAW incoming
    path, checked before any root-relative normalization — it lies outside
    the project root and can never be expressed as a root-relative prefix.
    This is the only outside-root path allow-listed; every other
    outside-root path still fails closed for tier 0/1 (tier 2 is already
    unrestricted regardless).

    "Source / tests / config" above means: when Project.protected_paths is
    NOT configured (the default — no `protected_paths:` key in
    config.yaml), anything not on the tier-0 allow list is blocked, same
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

    Ticket-state gate (applies to ALL tiers, including tier 2): if a
    sprint execution lock is held (via _get_sprint_context()) and zero
    tickets in that sprint are `status: in-progress` (via
    _get_active_tickets()), the write is blocked — unless _oop_active()
    is True. This gate is skipped entirely when no execution lock is
    held. It runs BEFORE the tier-2 unrestricted-write early return, so
    a programmer with no in-progress ticket during an active sprint is
    blocked exactly like any other tier.

    No path resolvable from the payload (neither the nested
    tool_input.file_path/path/new_path shape nor a flat fallback) fails
    CLOSED for tier 0/1 — directory-scope enforcement is meaningless
    without a path to check, so the safe default is to block, not allow.
    Tier 2 is unaffected (already unrestricted) and still exits 0.

    Exits with code 0 (allow) or 2 (block).  Code 1 is reserved for
    unknown event names in the dispatcher.
    """
    tool_input = payload.get("tool_input", payload) if payload else {}
    file_path = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("new_path")
        or ""
    )

    # Claude Code's own plan-mode plan file (~/.claude/plans/<name>.md) is
    # written by team-lead (tier 0) and is the exact artifact clasi's own
    # plan_to_issue PostToolUse hook harvests into clasi/issues/. It lies
    # OUTSIDE the project root by construction, so it can never be expressed
    # as a root-relative prefix and can never match safe_prefixes/
    # _allow_prefixes below — those are built from Project properties that
    # are always root-relative. This check must run against the RAW
    # incoming absolute path, BEFORE _normalize_to_root_relative runs: that
    # normalization either rewrites an absolute path to root-relative (if
    # it happens to be under the project root — never true here) or leaves
    # it as an unchanged absolute string when it's outside the root, which
    # is what would reach this comparison if it ran after normalization.
    # Comparing pre-normalization keeps this allow-list a narrow absolute-
    # path prefix check, not a root-relative one, and keeps it independent
    # of whatever the project root happens to be. Deliberately narrow: only
    # this one absolute prefix is allow-listed here, so no other
    # outside-root path is affected (see the outside-root fail-closed
    # default below, and the regression test asserting an arbitrary
    # outside-root path like ~/Desktop/x.md is still blocked).
    if file_path:
        try:
            _plans_dir = Path.home() / ".claude" / "plans"
            if Path(file_path).is_absolute() and (
                Path(file_path) == _plans_dir
                or _plans_dir in Path(file_path).parents
            ):
                _exit_hook("role-guard", payload, 0, "claude-plans-dir")
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
        file_path = _normalize_to_root_relative(file_path)

    caller_id = (payload or {}).get("agent_id") or (payload or {}).get("session_id") or ""

    agent_tier = os.environ.get("CLASI_AGENT_TIER", "")

    # If no env var, check the DB for the caller's own active-agent tier.
    # Keyed on caller_id — never a filter-less lookup, which with
    # concurrent agents would return an arbitrary agent's tier.
    if not agent_tier:
        try:
            db_path_tier = get_project().db_path
            if db_path_tier.exists():
                from clasi.state_db import get_active_tier
                agent_tier = get_active_tier(str(db_path_tier), caller_id)
        except Exception:
            pass

    # No path in payload — nothing to guard against. This must be fail
    # CLOSED for tier 0/1: directory-scope enforcement cannot be applied
    # without a path, and silently allowing here is exactly how the
    # payload-shape bug (reading file_path from the wrong nesting level)
    # went undetected. Tier 2 already has unrestricted write scope by
    # design once the ticket-state gate below has been checked, so
    # no-path is moot there — exempted here rather than exiting early,
    # so the ticket-state gate (which applies to tier 2 too) still runs
    # for tier 2 regardless of whether a path was resolved.
    if not file_path and agent_tier != "2":
        present_keys = sorted(payload.keys()) if payload else []
        logger.warning(
            "role-guard: no file_path resolved from payload "
            "(tier=%s, payload keys=%s) — failing closed",
            agent_tier or "0", present_keys,
        )
        _exit_hook("role-guard", payload, 2, "no-path")

    # OOP bypass: .clasi/oop (or legacy .clasi-oop) enables direct writes
    # for any tier. Used for out-of-process changes reviewed manually by
    # the team-lead.
    if _oop_active():
        _exit_hook("role-guard", payload, 0, "oop-bypass")

    # Recovery state bypass: allows specific paths during sprint recovery
    # (e.g. resolving merge conflicts) when recorded in the state DB.
    db_path = get_project().db_path
    if db_path.exists():
        try:
            from clasi.state_db import get_recovery_state

            recovery = get_recovery_state(str(db_path))
            if recovery and file_path in recovery["allowed_paths"]:
                _exit_hook("role-guard", payload, 0, "recovery")
        except Exception:
            pass

    # Safe prefixes: always allowed for any tier (configuration / meta files).
    # .claude/ — Claude Code settings, hooks, rules
    # CLAUDE.md — project coding instructions
    # AGENTS.md — agent instructions
    safe_prefixes = [".claude/", "CLAUDE.md", "AGENTS.md"]
    for prefix in safe_prefixes:
        if file_path == prefix or file_path.startswith(prefix):
            _exit_hook("role-guard", payload, 0, "safe-prefix")

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

    _staleness = check_staleness(get_project().root, _running_version)
    if _staleness.repo_version is not None and any(
        "does not match this repo's editable source" in r
        or "is not running this working tree's code" in r
        for r in _staleness.reasons
    ):
        print(_staleness.warning(), file=sys.stderr)
        print(
            "CLASI ROLE VIOLATION: refusing to enforce role-guard from a "
            "stale build of this repo's own tooling. Fix .mcp.json / "
            ".claude/settings.json to invoke the editable install, or set "
            ".clasi/oop to bypass.",
            file=sys.stderr,
        )
        _exit_hook("role-guard", payload, 2, "stale-guard")

    # Ticket-state gate: if a sprint execution lock is held but zero
    # tickets in that sprint are `status: in-progress`, block the write
    # regardless of tier — including tier 2. This is the gate that was
    # missing entirely: tier 2 previously exited allow (see below) before
    # any ticket-state logic could run, which is exactly how a sprint
    # could land untracked commits with no ticket ever marked
    # in-progress. Skipped entirely when no execution lock is held (no
    # sprint executing); already-bypassed OOP requests exited above via
    # the oop-bypass check, so no separate _oop_active() re-check is
    # needed here — reaching this point means OOP is not active.
    _sprint_log_dir, _sprint_id = _get_sprint_context()
    if _sprint_id:
        active_tickets = _get_active_tickets(_sprint_id)
        if not active_tickets:
            print(
                f"CLASI ROLE VIOLATION: sprint {_sprint_id} execution lock "
                "is held but no ticket is in-progress.\n"
                "Start or resume a ticket via the execute-ticket flow, "
                "or set .clasi/oop to bypass.",
                file=sys.stderr,
            )
            _exit_hook("role-guard", payload, 2, "no-ticket")

    # Tier 2 (programmer) can write anywhere — that's their job.
    # Checked after the ticket-state gate above (and after the no-path /
    # OOP / recovery / safe-prefix checks) so programmer subagents are
    # still subject to the ticket-state gate; this early return only
    # fires once that gate has confirmed either no lock is held or a
    # ticket is in-progress.
    if agent_tier == "2":
        _exit_hook("role-guard", payload, 0, "tier-2")

    # Build allow/block prefix sets from live Project properties.
    # Each prefix is root-relative so it matches the file_path strings
    # Claude Code sends (which are also root-relative).
    _proj = get_project()

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

    _allow_prefixes = [
        _prefix(_proj.issues_dir),
        _prefix(_proj.reflections_dir),
        _prefix(_proj.design_dir),
        _prefix(_proj.clasi_dir),   # state files: config.yaml, log/, .clasi.db
        _prefix(_proj.log_dir),
    ]
    _block_prefixes = [
        _prefix(_proj.sprints_dir),
    ]

    if agent_tier in ("", "0"):
        # Check block list first: sprints_dir is owned by sprint-planner/MCP.
        for blk in _block_prefixes:
            if file_path.startswith(blk):
                # Sprint artifacts are owned by sprint-planner (tier 1) and
                # managed via MCP tools. Direct edits are blocked to prevent
                # process violations (e.g. bypassing ticket status transitions).
                print(
                    "CLASI ROLE VIOLATION: team-lead cannot directly edit sprint artifacts.\n"
                    "Use MCP tools (create_sprint, create_ticket, update_ticket_status, etc.).",
                    file=sys.stderr,
                )
                _exit_hook("role-guard", payload, 2, "blk-sprint")
        # Check allow list: issues, reflections, architecture, design, clasi state.
        for alw in _allow_prefixes:
            if file_path.startswith(alw):
                _exit_hook("role-guard", payload, 0, "artifact-dir")

    # Sprint-planner (tier 1) can write to sprint directories they own.
    # All other paths (source, tests, config) are blocked — dispatch to tier 2.
    _sprints_prefix = _block_prefixes[0]
    if agent_tier == "1" and file_path.startswith(_sprints_prefix):
        _exit_hook("role-guard", payload, 0, "tier-1")

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
    _protected = _proj.protected_paths
    if _protected:
        # excluded_paths carves out subdirectories of a protected prefix
        # that aren't actually source/tests (e.g. tests/e2e/ Docker
        # harness scripts under a protected tests/ root) — checked first
        # so an exclusion always wins over a broader protected prefix.
        if any(file_path.startswith(p) for p in _proj.excluded_paths):
            _exit_hook("role-guard", payload, 0, "excluded-path")
        if not any(file_path.startswith(p) for p in _protected):
            _exit_hook("role-guard", payload, 0, "outside-protected-paths")

    # --- BLOCK ---
    # If we reach here, the write is not permitted for this tier.
    # tier 0 / unset: source code, tests, config, non-clasi docs → BLOCK
    # tier 1:         source code, tests, config, non-sprint docs  → BLOCK
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
    OOP bypass: if .clasi/oop (or legacy .clasi-oop) exists, allow all tiers.
    """
    # OOP bypass
    if _oop_active():
        _exit_hook("mcp-guard", payload, 0, "oop-bypass")

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
            ".claude/settings.json to invoke the editable install, or set "
            ".clasi/oop to bypass.",
            file=sys.stderr,
        )
        _exit_hook("mcp-guard", payload, 2, "stale-guard")

    caller_id = (payload or {}).get("agent_id") or (payload or {}).get("session_id") or ""

    agent_tier = os.environ.get("CLASI_AGENT_TIER", "")

    # If no env var, check the DB for the caller's own active-agent tier.
    # Keyed on caller_id — never a filter-less lookup, which with
    # concurrent agents would return an arbitrary agent's tier.
    if not agent_tier:
        try:
            db_path_tier = get_project().db_path
            if db_path_tier.exists():
                from clasi.state_db import get_active_tier
                agent_tier = get_active_tier(str(db_path_tier), caller_id)
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

    log_dir is None if the clasi_dir does not exist (handlers should exit 0).
    If an execution lock is held, log_dir is a sprint-scoped subdirectory
    (.clasi/log/sprint-{sprint_id}/), creating it if needed.
    Otherwise log_dir is .clasi/log.
    sprint_id is the active sprint ID string, or empty string if none.
    """
    _proj = get_project()
    if not _proj.clasi_dir.exists():
        return None, ""
    log_base = _proj.log_dir
    log_base.mkdir(parents=True, exist_ok=True)
    _ensure_log_gitignore(log_base)

    db_path = _proj.db_path
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

    Returns None if clasi_dir does not exist (handlers should exit 0).
    If an execution lock is held, returns a sprint-scoped subdirectory
    (.clasi/log/sprint-{sprint_id}/), creating it if needed.
    Otherwise returns .clasi/log.
    """
    log_dir, _ = _get_sprint_context()
    return log_dir


def _get_active_tickets(sprint_id: str) -> list[str]:
    """Return a list of in-progress ticket IDs for the given sprint.

    Scans the sprints_dir for the sprint directory matching sprint_id, then
    reads tickets/ for files with status: in-progress in their frontmatter.
    Returns ticket IDs in the format "{sprint_id}-{ticket_id}" (e.g. "002-007").
    Returns an empty list on any error or if no in-progress tickets found.
    """
    if not sprint_id:
        return []
    try:
        sprints_base = get_project().sprints_dir
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
    or start a ticket via execute-ticket, or set ``.clasi/oop`` (checked
    only via the shared :func:`_oop_active` helper — never reimplemented).

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
        "execute-ticket flow, or set .clasi/oop to bypass."
    )
    existing_focus = notes.get("current_focus", "")
    notes["current_focus"] = (
        f"{existing_focus} {imperative}".strip() if existing_focus else imperative
    )


def _build_status_block(agent: str) -> str:
    """Build a ``## CLASI status`` fenced YAML block for *agent*.

    Resolves the active ``sprint_id`` via :func:`_get_sprint_context` and,
    for the ``programmer`` role, the active ``ticket_id`` via
    :func:`_get_active_tickets`, then threads both into
    :func:`~clasi.status.narrow_status` so the returned view is actually
    scoped to the requesting agent (rather than always the team-lead's
    full view, which is what passing no ids produces).

    The status-block assembly excludes ``done/`` sprints and tickets
    (``exclude_done=True``) — this hook path is the only caller that opts
    into that; on-demand callers (MCP tools) still see full history.

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
        )
        narrowed = narrow_status(
            full, agent=agent, sprint_id=sprint_id or None, ticket_id=ticket_id,
        )
        _add_gate_imperative(narrowed, sprint_id, active_tickets)
        yaml_text = to_yaml(narrowed)
        return f"{staleness_block}## CLASI status\n\n```yaml\n{yaml_text}```\n"
    except Exception:
        logger.warning("status-inject: failed to build status block", exc_info=True)
        return staleness_block


def handle_status_inject(payload: dict) -> None:
    """Inject a ``## CLASI status`` block for the ``UserPromptSubmit`` event.

    Reads ``$CLASI_AGENT_NAME`` to determine the agent scope (default:
    ``team-lead``).  Calls :func:`build_status` + :func:`narrow_status`,
    serializes to YAML, and prints the fenced block to stdout so Claude Code
    prepends it to the context window.

    Silent no-op (exit 0, no output) if:
    - ``.clasi/`` does not exist (project not CLASI-initialized).
    - ``.clasi/oop`` exists (out-of-process bypass).
    """
    project = get_project()
    if not project.clasi_dir.exists():
        _exit_hook("status-inject", payload, 0, "no-clasi")
    if _oop_active():
        _exit_hook("status-inject", payload, 0, "oop-bypass")

    agent = os.environ.get("CLASI_AGENT_NAME", "team-lead")
    block = _build_status_block(agent)
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
# Task lifecycle — TaskCreated / TaskCompleted
# ---------------------------------------------------------------------------


def handle_task_created(payload: dict) -> None:
    """Log when a programmer task starts.

    Creates a log file in .clasi/log/ with frontmatter and writes an
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
        db_path = get_project().db_path
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
        db_path = get_project().db_path
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


def handle_codex_plan_to_issue(payload: dict) -> None:
    """Convert a Codex plan tag in last_assistant_message to a CLASI issue.

    Reads ``last_assistant_message`` from the payload, extracts the content
    between ``<proposed_plan>`` and ``</proposed_plan>`` tags, and calls
    ``plan_to_issue_from_text`` to write a pending issue file.

    Always exits 0 — the Codex Stop hook fires after the session has ended,
    so there is nothing to block. Unlike ``handle_plan_to_issue`` (the Claude
    Code ``ExitPlanMode`` path), there is no live model turn left to hand a
    "rewrite this into house format" instruction to, so the option 1 fix
    (block-and-hand-off, see `handle_plan_to_issue`) does not apply here.
    ``plan_to_issue_from_text`` still gets the mechanical, non-brittle part
    of the fix — stripping a redundant ``issue-`` filename prefix — but the
    resulting file may still carry plan-shaped prose that needs a later
    manual or sprint-planner-side reshape.
    """
    import re

    from clasi.plan_to_issue import plan_to_issue_from_text

    message = payload.get("last_assistant_message", "")
    match = re.search(r"<proposed_plan>(.*?)</proposed_plan>", message, re.DOTALL)
    if not match:
        sys.exit(0)

    plan_text = match.group(1).strip()
    issue_dir = get_project().issues_dir
    result = plan_to_issue_from_text(plan_text, issue_dir)
    if result:
        print(f"CLASI: Codex plan saved as TODO: {result}")
    sys.exit(0)


# Backward-compatible alias
handle_codex_plan_to_todo = handle_codex_plan_to_issue


def handle_plan_to_issue(payload: dict) -> None:
    """Convert the most recent plan file to a CLASI issue.

    Calls plan_to_issue() with the standard directories and prints the
    path of the created issue file if one was created.
    """
    from clasi.plan_to_issue import plan_to_issue

    plan_file_str = payload.get("tool_input", {}).get("planFilePath")
    plan_file = Path(plan_file_str) if plan_file_str else None

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
        sys.exit(2)
    sys.exit(0)


# Backward-compatible alias
handle_plan_to_todo = handle_plan_to_issue


# ---------------------------------------------------------------------------
# Commit check — PostToolUse hook for Bash (git commit on master/main)
# ---------------------------------------------------------------------------


def handle_commit_check(payload: dict) -> None:
    """Print a reminder when a git commit is made on master or main.

    Reads TOOL_INPUT from the environment. If it contains 'git commit'
    and the current branch is master or main, prints a reminder message.
    Never blocks — always exits 0.
    """
    tool_input = os.environ.get("TOOL_INPUT", "")
    if "git commit" in tool_input:
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
            )
            branch = result.stdout.strip()
            if branch in ("master", "main"):
                print(
                    "CLASI: You committed on master. Call tag_version() to bump the version."
                )
        except (OSError, subprocess.SubprocessError):
            pass
    sys.exit(0)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def handle_hook(event: str) -> None:
    """Read stdin JSON and dispatch to the correct hook handler.

    Routes the event name to the appropriate handler function. Exits with
    code 1 for unknown event names.
    """
    payload = read_payload()

    _ROUTING_TABLE = {
        "role-guard": handle_role_guard,
        "subagent-start": handle_subagent_start,
        "subagent-stop": handle_subagent_stop,
        "task-created": handle_task_created,
        "task-completed": handle_task_completed,
        "mcp-guard": handle_mcp_guard,
        "plan-to-issue": handle_plan_to_issue,
        "plan-to-todo": handle_plan_to_issue,  # backward-compatible alias
        "codex-plan-to-issue": handle_codex_plan_to_issue,
        "codex-plan-to-todo": handle_codex_plan_to_issue,  # backward-compatible alias
        "commit-check": handle_commit_check,
        "status-inject": handle_status_inject,
    }

    handler = _ROUTING_TABLE.get(event)
    if handler is None:
        print(f"clasi hook: unknown event '{event}'", file=sys.stderr)
        sys.exit(1)

    handler(payload)
