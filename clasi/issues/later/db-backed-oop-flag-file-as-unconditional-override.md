---
status: pending
---

# DB-backed OOP flag, file as unconditional override

## Description

The OOP (out-of-process) bypass is a zero-byte marker file, checked by
`_oop_active()` (`src/clasi/hook_handlers.py:68-80`) via **bare relative
paths** — `Path(".clasi/oop")` — which resolve against the hook process's cwd,
not the project root.

Two defects, one observed live and one structural:

1. **The cwd bug (observed 2026-07-16)**: a hook fired while the shell sat in
   `tests/e2e/`; the guard looked for `tests/e2e/.clasi/oop`, found nothing,
   and blocked a write the stakeholder had explicitly authorized by setting
   the flag at the repo root. The flag was on; the check looked in the wrong
   place.
2. **The flag is mute and immortal**: no record of who set it, when, or why —
   and a forgotten flag disables all enforcement silently and forever. Sprints
   019-020 had five set/remove cycles with zero audit trail; the team-lead
   checked for stray flags after every dispatch precisely because a leftover
   would have quietly voided the guards for the rest of the sprint.

**Stakeholder decision (2026-07-16): DB as primary, file as unconditional
override.** The DB channel gets auditability (reason, timestamps), TTL
self-healing, and cwd-independence via `Project.db_path`. The file stays as
the fire axe — the escape that must keep working when the DB layer itself is
broken (a live concern: `active_agents` is a DB mechanism that silently never
populated). Scope is **global to the checkout with a TTL**, not per-session —
session-identity plumbing is currently broken (see
`sprint-planner-tier-1-may-never-be-set-verify-clasi-agent-tier-wiring.md`).
Divergence between DB and file is **reported loudly** in the status block,
never reconciled silently.

## Cause

- `_oop_active()` is the lone check in `hook_handlers.py` that consults the
  filesystem via implicit-relative paths; everything else routes through
  `Project` properties anchored at the root.
- The file mechanism has no metadata surface at all — it is an empty file, so
  there is nothing to audit and nothing to expire.

## Proposed fix

### 1. New `oop_state` singleton table

Append to `_SCHEMA` (`src/clasi/state_db_class.py:35-77`), following the
`recovery_state` pattern (`id INTEGER PRIMARY KEY CHECK (id = 1)`):

```sql
CREATE TABLE IF NOT EXISTS oop_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    set_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
```

No migration machinery needed — the schema is `CREATE TABLE IF NOT EXISTS`
run by `StateDB.init()` on every mutating call, so the table auto-appears.

TTL default **8 hours** (recovery_state's 24h at `state_db_class.py:90` is the
precedent, but enforcement disabled unattended for a full day is exactly the
failure mode being killed). Expiry enforced on read like `get_recovery_state`
(`:512-548`): a read past `expires_at` deletes the row and warns on stderr.

### 2. StateDB methods + wrappers

On `StateDB`, modeled on `acquire_lock`/`release_lock`/`get_lock_holder`
(`:334-477`) and `write_recovery_state`'s `INSERT OR REPLACE` (`:479-510`):

- `set_oop(reason: str, ttl_hours: float = 8.0) -> dict`
- `clear_oop() -> dict`
- `get_oop() -> dict | None` (deletes-and-warns when expired)

Module-level one-liner wrappers in `src/clasi/state_db.py`, added to
`__all__`, matching the existing pattern.

### 3. `_oop_active()` rewrite — the core change

1. **File override first, project-rooted**:
   `(get_project().root / ".clasi/oop").exists()` or the legacy `.clasi-oop`
   sibling → active, source `"file"`. This fixes the cwd bug and keeps the
   file as the unconditional emergency path needing no working DB.
2. **Then DB**: `get_oop(str(get_project().db_path))` non-None → active,
   source `"db"`. Wrapped in `try/except Exception: pass` plus
   `db_path.exists()`, matching every other DB read in the module — a broken
   DB must never make the check raise.
3. Neither → inactive.

Add `_oop_source() -> "file" | "db" | None` for reporting. Keep
`_oop_active() -> bool` so the five call sites (`hook_handlers.py:255, 435,
622, 714, 815`) are unchanged.

**Caveat to record in the docstring**: `get_project()` is itself cwd-based
(`Project(Path.cwd())`, no upward search), so root-anchoring fixes the
subdirectory case only when cwd IS the project root — which is how Claude Code
invokes hooks. Fixing project discovery is a separate issue, not this one.

### 4. Loud reporting in the status block

When OOP is active, the notes section states source and age:

- DB: `OOP active (DB): set <ago> ago — "<reason>" — expires <in>.`
- File: `OOP active (override file .clasi/oop). No audit record — if this is
  stale, remove the file.`
- Both: report both lines. Never reconcile silently.

Behavior change: `handle_status_inject` currently emits **nothing** when OOP
is active (`:714-715`) — an active bypass is invisible on every prompt. Change
to emit a minimal block carrying exactly the OOP line. Tests in
`tests/unit/test_status/test_hook_injection.py` asserting the empty-output
path must be updated to assert the minimal block.

### 5. CLI: `clasi oop on|off|status`

New `@cli.group()` in `src/clasi/cli.py` mirroring the `sprint` group (`:268`)
and `status`'s project-resolution pattern (`:209-242`):

- `clasi oop on [--reason TEXT] [--ttl-hours FLOAT]` — reason required
  (prompt if omitted).
- `clasi oop off` — clears the DB row AND removes any flag files (with
  notice): "off" means off everywhere.
- `clasi oop status` — source, reason, age, expiry.

### 6. Docs — generator sources only (`.claude/` is gitignored; five 019/020 tickets hit this drift)

- `src/clasi/platforms/_rules.py` — `MCP_REQUIRED_BODY` (18-29),
  `CLASI_ARTIFACTS_BODY` (38-39), `SOURCE_CODE_BODY` (59-60), `TODO_DIR_BODY`
  (75-76): primary instruction becomes `clasi oop on --reason '...'`; the
  `.clasi/oop` file stays documented as the emergency path for when CLASI's
  own tooling is broken.
- Guard error strings in `hook_handlers.py` (309, 332, 456, 629): same
  rewording.
- `src/clasi/plugin/skills/oop/SKILL.md`: add an "Enabling the bypass"
  section (currently never mentions the mechanism).
- Regenerate this repo's on-disk `.claude/rules/*.md`; verify by read.

### Suggested ticket split

Three tickets: (1) StateDB table + methods + wrappers + DB tests;
(2) `_oop_active()` rewrite + status-block reporting + handler tests including
the cwd regression; (3) CLI group + docs rewording + regeneration. 2 and 3
depend on 1.

### Out of scope, deliberately

- Per-session scoping (blocked on session-identity plumbing; the schema does
  not preclude a later `session_id` column).
- Fixing `get_project()`'s no-upward-search assumption (separate issue).
- An MCP toggle tool (CLI suffices; can ride `artifact_tools.py:1868-1925`'s
  pattern later).
- Removing legacy `.clasi-oop` read support (tolerate-on-read stays, per
  019-002).

## Verification

- Full suite green (`uv run pytest --no-cov -q`, baseline 2580+).
- Live from repo root: `uv run clasi oop on --reason test` → role-guard allows
  a source write (exit 0, `oop-bypass`); `clasi oop status` shows reason/age;
  status block carries the OOP line; `clasi oop off` → guard blocks (exit 2).
- **The cwd regression that motivated this**: flag set at root, invoke
  `uv run clasi hook role-guard` with cwd = a subdirectory — bypass works
  (fails against today's code; this is the revert-check per house standard).
- File override with DB empty: `touch .clasi/oop` → bypass works, status block
  carries the "override file, no audit record" line.
- TTL: `clasi oop on --ttl-hours 0.0001` → row auto-expires on next read,
  guard enforcing again.
- Handler-level tests for the DB flag on both role-guard and mcp-guard (the
  019-002 lesson: helper-level tests cannot catch an unwired call site).
- Broken-DB test: corrupt/locked DB file → file override still works, no
  exception.

## Related

- The cwd bug fired live on 2026-07-16 during e2e Dockerfile work; the OOP
  flag was set at the root and a hook running from `tests/e2e/` ignored it.
- `019-002` unified the split-brain flag files behind `_oop_active()` — this
  issue is the next step for the same mechanism, and its tolerate-legacy
  contract carries forward.
- `sprint-planner-tier-1-may-never-be-set-verify-clasi-agent-tier-wiring.md` —
  why per-session scoping is deferred.
- `020-002` chose fail-closed for stale guards with the escape hatches
  deliberately checked first; the file-override-first ordering here preserves
  that reasoning: the escape must never depend on the machinery it escapes.
