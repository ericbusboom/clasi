---
status: in-progress
sprint: 019
tickets:
- 019-001
- 019-002
- 019-003
- 019-004
- 019-005
- 019-006
- 019-007
---

# CLASI enforcement guards fail open: role-guard payload shape, tier resolution, and rule scope

## Description

Investigation of a process-bypass reflection in `radio-robot-elite`
(sprint 101: eight commits landed with the tracker frozen at `roadmap`, no
tickets moved, no lock acquired) found that the incident was **not** an agent
ignoring instructions. Every guard meant to stop it was already installed and
silently failing open.

The reflection filed root cause as `ignored-instruction` and proposed, as its
systemic fix, "consider a PreToolUse hook on Edit/Write that blocks when no
ticket is in-progress." **That hook already existed**, on the correct matcher,
in that repo. It has never blocked anything in any session.

This is a cluster of defects sharing one shape: **a guard that cannot resolve
its input, and treats the unresolved case as ALLOW.** Every failure logs a
confident-looking success line.

### 1. `role-guard` fails open on every invocation (critical)

`src/clasi/hook_handlers.py:140` reads `file_path` from the payload root;
Claude Code nests it under `tool_input`. `file_path` is therefore always `""`,
and line 148 short-circuits to `_exit_hook(..., 0, "no-path")` — allow.

Reproduced:

```
echo '{"tool_name":"Write","tool_input":{"file_path":"source/main.cpp"}}' \
  | clasi hook role-guard   -> exit 0   (real Claude Code shape: ALLOWED)
echo '{"file_path":"source/main.cpp"}' | clasi hook role-guard
                            -> exit 2   (flat shape, tests only: blocked)
```

Every `role-guard` line in `.clasi/log/hooks.log` is `0 no-path`, including
tier-0 `Write`s. The same file reads the nested shape correctly at line 1014
(`payload.get("tool_input", {}).get("planFilePath")`), so this is an isolated
slip, not a design misunderstanding.

The tier matrix in the `handle_role_guard` docstring (lines 118-133) reads as a
hard security boundary. It is a no-op.

### 2. Tests encode the bug

`_role_guard_payload()` in `tests/unit/test_hook_handlers.py` (~line 1095)
hand-builds the **flat** shape `{"file_path": ...}`. The suite is green against
a dead gate. A hand-written fixture cannot detect a wrong-shape assumption —
it only restates it.

### 3. Tier resolution returns an arbitrary agent's tier (critical)

`StateDB.get_active_tier` (`src/clasi/state_db_class.py:643`):

```sql
SELECT tier FROM active_agents LIMIT 1
```

No `WHERE agent_id = ?`, no ordering. It answers "what tier is *somebody*?",
not "what tier am *I*?" — then applies that tier to the calling agent. With
concurrent agents (normal for this project) the result is arbitrary.

Compounded by **no cleanup**: `active_agents` accumulates ghosts of agents that
exited weeks ago. `clear_stale_agents` (24h TTL) exists but is evidently never
called.

Live state, this repo:
```
sprint-planner-dispatch-1|sprint-planner|1|2026-05-25T22:06:12
afcc06892c8e70d87       |sprint-planner|1|2026-05-27T18:55:34
a3aaecb17cd8adc51       |programmer    |2|2026-06-27T14:43:46
```
`LIMIT 1` returns tier `1` — a **May 25 ghost** decides the identity of every
caller today. In `radio-robot-elite` the table holds five stale `programmer`
rows (Jul 8-12), so `LIMIT 1` returns tier `2` and mcp-guard **allows
everything** — the same bug with the opposite symptom.

This produced a user-visible misdiagnosis: an agent hit a bogus
"team-lead cannot call create_sprint", concluded "SubagentStart only fires for
synchronous dispatches", and adopted "always dispatch role agents
synchronously" as a rule. That is false — `sub-start` fires for background
agents (verified in both repos' logs; e.g. robot repo logs `sub-start` for
`sprint-planner` at 18:00:29Z). Re-dispatching synchronously appeared to fix it
only because it wrote a fresh row that won the `LIMIT 1` lottery. The two real
`blk-mcp` events in that repo carry **no `agent_id` and no `agent_type`** —
bare sessions, not background agents.

### 4. The ticket rule matches nothing in most projects

`src/clasi/platforms/claude.py:55` stamps
`paths: src/clasi/**, src/clasr/**, tests/**` — **CLASI's own source layout** —
into every project `clasi init` touches. `radio-robot-elite` keeps code in
`source/`, `host/`, `libraries/`; neither `src/clasi` nor `src/clasr` exists
there. The one rule stating "you must have a ticket in-progress" was out of
scope for every file edited during sprint 101.

Same defect in `src/clasi/platforms/copilot.py:210`.

### 5. OOP flag is split-brain

- `role-guard` (line 171) and `mcp-guard` (line 285) check **`.clasi-oop`**
  (repo root, hyphen).
- `status-inject` (line 463), `subagent-start` (line 543), all five rule
  templates in `platforms/_rules.py`, and the `oop` skill document
  **`.clasi/oop`** (inside dir, slash).

The documented escape hatch does not open the enforced door. This likely
explains the reflection's "I deferred instead of opting out" — the sanctioned
exit didn't work either.

### 6. No gate on ticket state at all

`source-code.md` has always promised "you must have a ticket in `in-progress`".
No handler queries ticket status. `role-guard` checks *role/tier* only, and
tier 2 (programmer) is allowed to write anywhere — so a programmer writing with
no in-progress ticket, which is exactly the sprint-101 failure, is permitted
even with the payload bug fixed.

### 7. Status block is 34KB of noise carrying no instruction

`clasi hook status-inject` emits 34,467 bytes on **every prompt** — all 18
sprints and 84 tickets including `done/` archives; 144 lines about reopening
already-closed tickets; roughly 5% concerns the active sprint. It contains no
imperative of any kind. At 33.5KB it overflows the inline threshold and is
spilled to a file, so it never reaches context as intended.

Its 18 `state_drift` warnings are themselves bogus: the sprint state machine
has no `done` state, so every archived sprint reports drift forever — training
readers to ignore the block.

`_build_status_block` also swallows all errors (`except Exception: return ""`),
so a broken status hook is indistinguishable from a healthy one. Narrowing is
dead code on this path: `narrow_status` is called without `sprint_id`/
`ticket_id`, so every agent gets the full firehose.

## Proposed fix

1. **`hook_handlers.py`** — read `payload.get("tool_input", payload)`, keeping
   the flat fallback. Make the no-path branch **fail closed** for Edit/Write:
   log WARN with payload keys and block, rather than allow.
2. **`state_db_class.py`** — add `WHERE agent_id = ?` keyed off the payload's
   `agent_id`/`session_id`. Fail **closed** on an unresolvable tier instead of
   borrowing a stranger's. Purge stale rows; call `clear_stale_agents` (or
   unregister reliably on `SubagentStop`).
3. **Ticket gate** — block source writes when no ticket is `in-progress` and no
   OOP flag, applying to **tier 2 as well**. Reuse existing
   `_get_sprint_context()` (~318) and `_get_active_tickets()` (~363).
4. **`platforms/claude.py:55` + `copilot.py:210`** — re-scope `source-code.md`
   to `"**"` minus artifact/meta dirs (`.clasi/`, `.claude/`, `docs/`, `*.md`).
   A rule matching too much is recoverable noise; one matching nothing is
   invisible. Verify Claude Code rules support `exclude:`; else state exclusions
   in the body.
5. **`_oop_active()` helper** — canonical `.clasi/oop` (what every doc
   promises), accept legacy `.clasi-oop`. Use in all four handlers.
6. **`status/reporter.py`** — exclude `done/` sprints and tickets; fix the
   `done`-vs-`closed` mismatch driving 18 bogus drift entries; thread real
   `sprint_id`/`ticket_id` into `narrow_status`; add the missing imperative
   (when a sprint is executing with no in-progress ticket, state that source
   edits are gated and name the two exits); replace the silent
   `except Exception` with a logged warning. Target well under 5KB.
7. **`SOURCE_CODE_BODY`** in `platforms/_rules.py` — state that a commit
   message is not a process action; only an MCP call moves a ticket.

## Tests

The test strategy is the part that let this survive, and matters most:

- Replace `_role_guard_payload()` with a **real captured payload** from
  `.clasi/log/hooks.log`. No hand-built fixtures for guard input.
- Assert the **deny path** explicitly (nested payload + tier 0 + source path →
  exit 2). A guard whose block branch is never exercised end-to-end is untested.
- Ticket-gate test: sprint executing, zero in-progress tickets, tier 2, source
  write → exit 2; with a ticket in-progress → exit 0.
- Tier test with **concurrent registrations** — a single-agent test passes
  trivially, which is why this survived.
- OOP test for **both** filenames.
- Size assertion on the **real** (unmocked) status block; existing tests all
  mock `_build_status_block` and so never saw 34KB.
- New deny tests must **fail when the line-140 fix is reverted**. A guard test
  that passes against the bug is worthless.

## Verification

```
# must now be 2
echo '{"tool_name":"Write","tool_input":{"file_path":"source/main.cpp"}}' \
  | clasi hook role-guard; echo "exit=$?"

touch .clasi/oop   # -> exit 0; repeat with .clasi-oop; remove both
clasi hook status-inject | wc -c   # -> under 5KB
grep role-guard .clasi/log/hooks.log   # -> reasons other than no-path
```

Run `clasi init` into a scratch repo with code in `source/` and confirm
`source-code.md` covers `source/main.cpp`.

## Out of scope

`commit-check` (PostToolUse, reads `os.environ["TOOL_INPUT"]` which is likely
never set — and PostToolUse cannot block anyway) and the stale
`clasi/issues/**` path in `todo-dir.md`. Both real; neither caused 101.

## Related

- `radio-robot-elite/clasi/reflections/2026-07-14-sprint-101-process-bypass.md`
  — should be amended: category `ignored-instruction` is wrong; the proposed
  hook already existed and was failing open. Its behavioral lessons stand.
