# Review: Hooks & guards (agent report, verbatim)

## Fail-open inventory

Terminology: "open" = action allowed despite guard intent; "closed" = action blocked. Claude Code harness semantics matter throughout: for PreToolUse hooks **only exit 2 blocks** — exit 1, an uncaught traceback, a spawn failure, or a timeout all let the tool call proceed.

| # | Location | Trigger | Direction | Logged? | Fix |
|---|----------|---------|-----------|---------|-----|
| 1 | `hook_handlers.py:570-576` (`handle_role_guard`) | `payload["tool_input"]` present but **not a dict** (e.g. `null`) → `None.get()` → uncaught `AttributeError` → exit 1 | **OPEN** (harness treats non-2 as allow) | No — traceback to stderr only, no hooks.log line | `isinstance(tool_input, dict)` check; top-level try/except in guard handlers that exits 2 (F1) |
| 2 | `hook_handlers.py:1800-1835` (`handle_hook`) | **Any** uncaught exception in `handle_role_guard`/`handle_mcp_guard` → exit ≠ 2 | **OPEN** | No hooks.log entry (crash bypasses `_exit_hook`) | Wrap guard events in try/except → `_exit_hook(evt, payload, 2, "guard-crash")` |
| 3 | `.claude/settings.json:39-49` + harness | `uv run` fails to spawn (lock drift, broken venv, rebuild), or role-guard exceeds its 5s timeout (sqlite busy-wait alone can eat 5s — F4) | **OPEN** | Nothing in hooks.log (process never ran or was killed) | Shorter internal DB timeout (`sqlite3.connect(timeout=1)`); watchdog line written first, reason patched at exit |
| 4 | `hook_handlers.py:703-704` `outside-root` allow + `get_project()` at 25-27 (no upward root discovery) + `_normalize_to_root_relative` fallback 58-59 | Hook process cwd ≠ repo root → every absolute in-root path fails `relative_to` → classified outside-root → **every write allowed** | **OPEN** | Yes, but as benign-looking `outside-root` | Give `get_project()` the `_find_project_root` upward walk `_oop_active` already has; log `outside-root` with the raw path |
| 5 | `hook_handlers.py:1023-1031` (`_get_sprint_context`, `except Exception: pass`) | DB locked/corrupt during ticket-state gate lookup → `sprint_id=""` → **tier-2 ticket-state gate silently skipped** (role-guard:808-823) | **OPEN** (the only gate tier 2 has) | No | Log a warning naming the skipped gate; optionally fail closed for tier 2 when the lock table is unreadable |
| 6 | `hook_handlers.py:977` (`handle_mcp_guard`) | `agent_tier not in ("", "0")` → any garbage env value (`"3"`, `"junk"`) allows | **OPEN** | Yes, as `tier-allowed` | Allowlist: `if agent_tier in ("1", "2")` |
| 7 | `hook_handlers.py:1364` (`marker_id = agent_id or session_id`) + role-guard:652 caller_id resolution | A subagent-start payload lacking `agent_id` registers its tier under the **shared parent `session_id`**; team-lead's own writes then resolve tier 2 for up to 2h | **OPEN** (latent) | Only as normal-looking `tier-2` | Never key a tier row on bare `session_id`; refuse registration (or tier "0") when `agent_id` is absent |
| 8 | `hook_handlers.py:732-735` safe prefixes | `.claude/` (hook wiring, settings, rules) is writable by **every tier** — any agent can edit out the guards themselves | **OPEN** by design, but unbounded | Yes (`safe-prefix`) | Log safe-prefix writes to settings/hooks with a distinct reason; consider excluding settings/hook files from safe-prefix for tiers 1-2 |
| 9 | `.claude/settings.json:41` matcher `Edit|Write|MultiEdit` | File writes via **Bash** (`tee`, `sed -i`, redirects, `git apply`) and NotebookEdit never trigger role-guard | **OPEN** (whole guard bypassable) | No | Accept as documented limitation or add a Bash matcher with a cheap heuristic; don't pretend the guard is airtight |
| 10 | `hook_handlers.py:62-72` (`read_payload`) | Malformed stdin JSON → `{}` | Closed for tier 0/1 (no-path, exit 2); **OPEN for env-tier-2** | Final reason logged; the JSON failure itself is not | Log a `bad-payload` token when stdin was non-empty but unparseable |
| 11 | `hook_handlers.py:663-670, 967-974` tier DB lookup `except: pass` | DB error → tier `""` → treated tier 0 | Closed (blocks legit subagents — the "tier 1 may never be set" friction issue) | No | Log the swallowed exception + `tier=unresolved(db-error)` |
| 12 | `hook_handlers.py:717-726` recovery lookup `except: pass` | DB error → recovery bypass unavailable | Closed (recovery deadlock friction) | No | Log skip |
| 13 | `hook_handlers.py:752-770, 937-958` staleness gate | `importlib.metadata` returns "unknown", or repo pyproject unreadable → gate can't fire | **OPEN** — warn-only by design for signal 1 | stderr warning only | Acceptable; document |
| 14 | `hook_handlers.py:1100-1111` (`_get_active_tickets` `except: return []`) | Any ticket-scan error while lock held → gate sees zero tickets | Closed (spurious tier-2 block) | No | Log; distinguish "scan failed" from "no tickets" |
| 15 | `hook_handlers.py:1725` + `plan_to_issue.py:59-64,94` | `tool_input.planFilePath` missing (payload-shape drift) → falls back to **newest file in ~/.claude/plans and deletes it** | **Destructive fallback**; can eat another session's plan | **No hooks.log at all** — plan handlers use raw `sys.exit`, never `_exit_hook` (confirmed: zero plan-to-issue lines in 3,021 logged events) | Drop the newest-file fallback; route both plan handlers through `_exit_hook` |
| 16 | `hook_handlers.py:367-368` (`_log_hook_event` `except: pass`) | Any logging failure | Audit trail silently lost | No | Emit one stderr line on log-write failure |
| 17 | `status/reader.py` (every method) + `reporter.py` | All reader methods return safe defaults on any exception → status can silently report wrong states (DB busy → `sprint_phase("")`) | Info-plane fail-open | No | Count swallowed exceptions per build; surface `degraded: true` in the status block |
| 18 | `status/narrowing.py:75-78` | Unknown agent role → full team-lead view (`general-purpose` subagents get full view via `_AGENT_TYPE_TO_ROLE` default at hook_handlers:1300, 1387) | Info-plane open (scope leak) | No | Default unknown roles to the narrowest view |

Historical validation: `.clasi/log/hooks.log` contains **876 `role-guard 0 no-path` allow events** (all pre-026) — the file_path-at-wrong-nesting-level bug ran fail-open for weeks. Post-026 dated lines show zero `no-path` events and healthy reason distribution (112 tier-2, 15 tier-1, 6 blk-write).

## Findings

**F1 — critical / correctness — `hook_handlers.py:1800-1835`, `:570`**: Guard handlers have no top-level exception boundary, and the harness treats any non-2 exit as allow, so *every unanticipated bug in the guard is an unlogged allow*. Fix: in `handle_hook`, wrap `role-guard`/`mcp-guard` dispatch in `try/except Exception` → log traceback → `_exit_hook(event, payload, 2, "guard-crash")`. ~10 lines; converts the whole crash class from silent-open to loud-closed.

**F2 — critical / correctness — `hook_handlers.py:25-27, 58-59, 703-704`**: `get_project()` is `Project(Path.cwd())` with no upward `.clasi/` discovery, while the outside-root rule allows any path that can't be made root-relative; a hook invoked with cwd below the root turns role-guard into allow-everything with benign `outside-root` log lines. The OOP helpers already walk up (`_find_project_root`). Highest-leverage single fix: make `get_project()` use `_find_project_root`.

**F3 — major / correctness — `hook_handlers.py:808-823` + `:1023-1031`**: The tier-2 ticket-state gate — the only constraint tier 2 has — evaporates whenever `get_lock_holder` throws (swallowed → `("", log_base)`). Fix: log the swallowed exception; for tier 2 with an unreadable lock table, fail closed with `gate-db-error`.

**F4 — major / correctness+speed — `state_db_class.py:135-141` + every `conn=None` read (e.g. `:526-529`)**: Every default-connection DB *read* calls `init()` first, which runs `executescript(_SCHEMA)` — a **write transaction** — and `_connect` uses the default 5s busy timeout. With parallel agents, write-lock contention can (a) stall role-guard past its 5s harness timeout → killed → fail open, and (b) raise into the broad excepts of F3/#11. Fix: drop `init()` from read paths; `timeout=1`.

**F5 — major / correctness — `hook_handlers.py:1725` + `plan_to_issue.py:94`**: On ExitPlanMode, a missing `planFilePath` silently degrades to "convert and **delete** the newest file in ~/.claude/plans" — a destructive guess; and neither plan handler writes hooks.log. Fix: require `planFilePath` from the ExitPlanMode hook (exit 0 + stderr note otherwise); route through `_exit_hook`.

**F6 — major / quality — `tests/unit/test_hook_handlers.py`**: Role-guard coverage is now decent (shared `_role_guard_payload` helper encoding the real nested shape, deny-path tests, null-shape fail-closed tests). Two gaps: (a) no captured-payload **corpus** — verbatim JSON captured from each real event, replayed through `read_payload`→handler, would catch harness-side shape changes (the actual historical failure mode); (b) SubagentStart/Stop shapes asserted only against hand-built dicts. Fix: `tests/fixtures/hook_payloads/*.json` captured via a one-line tee in the hook command + parametrized replay test.

**F7 — major / simplicity — six ad-hoc payload parsers**: `handle_role_guard:570-576`, `_log_hook_event:341-356`, `handle_mcp_guard:960-980`, `handle_subagent_start:1333-1335`, `handle_subagent_stop:1401-1404`, `handle_plan_to_issue:1725` each hand-roll extraction; the file-path rule exists twice and drifted once already (026-004). Fix — one typed ingress point: frozen `HookPayload` dataclass built once in `handle_hook` (`from_stdin(raw)`), fields `tool_name`, `tool_input`, `file_path` (single nested-then-flat resolution), `caller_id` (+`caller_id_source`), `agent_type`, `transcript_path`, `last_assistant_message`, `plan_file_path`, and `missing: list[str]` appended to the log line by `_exit_hook`. Plain dataclass, not pydantic — keeps sprint 027's import-cost win.

**F8 — major / correctness — `hook_handlers.py:1316, 1376`**: `_STALE_AGENT_TTL_HOURS = 2` sweeps *any* row older than 2h at every subagent start — a legitimately long-running programmer (>2h ticket) loses its tier mid-run and every subsequent source write blocks as tier 0, with no message why. Fix: sweep on `last_seen` (touch the row from role-guard's existing tier lookup) or raise TTL and prune on stop.

**F9 — minor / correctness — `hook_handlers.py:977`**: mcp-guard's `not in ("", "0")` allows any unrecognized tier string; role-guard's equivalent happens to block. One-line allowlist fix.

**F10 — minor / quality — `status/reporter.py:516-539`**: `_last_matching_state_from_error` recovers state by regex+`ast.literal_eval` **on the exception's message text**; any wording change silently degrades every ambiguous sprint to `"unknown"`. Fix: give the exception a `.matching_states` attribute.

**F11 — minor / simplicity — `dispatch_log.py` + `plugin/skills/dispatch-subagent/SKILL.md:57-87`**: `dispatch_log.py` has **zero production callers**; the MCP tools it backed (`log_subagent_dispatch`, `update_dispatch_log`) were removed, yet the shipped skill still says "you MUST call `log_subagent_dispatch`… If unavailable, STOP." Every by-the-book dispatch dead-ends or the instruction is ignored. Also: it imports `clasi.mcp_server` (FastMCP) just for `get_project`; `_next_sequence` has a filename race under parallel dispatch. Fix: delete the module and rewrite the skill section, or reinstate a minimal MCP tool; import `get_project` from a lighter module.

**F12 — minor / speed — `hook_handlers.py:1386-1390`**: `handle_subagent_start` builds the status block with `skip_inconsistencies=False` (175ms vs 167ms now, scales with drift count). Pass `skip_inconsistencies=True` to match status-inject.

**F13 — minor / simplicity — `hook_handlers.py` (1,835 lines)**: One module mixes guards, status injection, OOP policy, lifecycle logging, a ~150-line markdown transcript renderer, and the dispatcher; `handle_role_guard` is a 455-line function of ordered imperative checks under a 105-line docstring matrix. Churn rate is a symptom. Fix: extract the transcript renderer; split role-guard's rule evaluation into a pure `decide(path, tier, ctx) -> (code, reason)` function (unit-testable; natural home for F7's typed payload and the decision log).

## Hot-path latency budget

Measured (M-series, warm caches, current tree):

**Per prompt (`status-inject`, 10s timeout):** `uv run` + imports ~40-70ms; `_oop_active` ~5-10ms; `_build_status_block` **~167ms** (list_sprints + frontmatter reads + 3 state-machine YAML loads + per-sprint DB `get_sprint_state` each with own connect+init + predicate evaluation + yaml dump; git spawns ~0 via ref-file fast path); `_exit_hook` ~2ms. **Total ~220-260ms wall** — near the 027 target; acceptable.

**Per edit (`role-guard`, 5s timeout):** startup ~40-70ms + config parse + staleness ~1ms + 0-3 sqlite lookups ≈ **~60-110ms typical**; worst case tier-2-with-lock adds a full `tickets/*.md` scan. Danger is the tail: F4's per-read `init()` write transactions × 5s busy timeout can consume the whole harness budget under contention → timeout → fail open.

**Full `clasi status` (not a hook): 4.7-5.1s** — inconsistency pass + un-excluded done-sprint history; fine on demand.

**Top reductions:** (1) F4 — remove `init()` from read paths, `timeout=1`; (2) share one DB connection across a whole status build (reader methods each open fresh); (3) cache the three `load_machine` YAML parses at module level in the reporter; (4) reuse the invocation's `Project` in `_log_hook_event`.

**Daemon/socket verdict: not justified.** Remaining ~200ms is real work, not spawn overhead (~40-70ms); guard path ~100ms against a 5s budget. A persistent daemon reintroduces the stale-runtime failure class this repo was burned by twice. Trimming is enough.

## Top structural recommendations

1. **Fail-closed exception boundary for guards** (F1, ~10 lines): try/except in `handle_hook` → exit 2 + `guard-crash`. Highest reliability payoff per line.
2. **Upward project-root discovery in `get_project()`** (F2, small): reuse `_find_project_root`; closes the cwd-dependent allow-everything hole.
3. **One typed payload ingress + decision-trail logging** (F7 + medium): `HookPayload` parsed once; `_exit_hook` gains per-invocation `decisions: list[str]` tokens (`tier=2(db)`, `gate=ticket-state:skipped(db-error)`, `missing=[file_path]`) on the existing hooks.log line; plan handlers routed through `_exit_hook`. Makes hooks.log answer *why*, the substrate the E2E instrumentation needs.
4. **DB reads stop writing; short busy timeout; shared connection in the status reader** (F4, medium): removes the contention-driven fail-open tail.
5. **Captured-payload corpus + replay tests; reconcile the dispatch-log story** (F6 + F11, medium): verbatim JSON fixtures per event replayed through handlers; delete or reinstate `dispatch_log` tooling so the shipped skill stops mandating a nonexistent MCP tool with a hard STOP.
