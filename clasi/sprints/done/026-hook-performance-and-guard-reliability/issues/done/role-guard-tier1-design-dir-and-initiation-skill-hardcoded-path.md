---
status: done
sprint: '026'
tickets:
- 026-001
- 026-005
---

# role-guard blocks tier-1 from configured design dir; project-initiation skill hardcodes .clasi/design/

Field bug report from a consumer project (pxt-nezha-diffdrive, clasi
0.20260724.1, `paths.design: docs/design`, no `protected_paths:`).
Standard project initiation failed: the team-lead dispatched a
sprint-planner (tier 1) per the project-initiation skill to author
overview.md / specification.md / usecases.md, and every Write the
subagent attempted was blocked by the role-guard PreToolUse hook. A
~20-minute authoring run ended with the finished documents parked in a
scratchpad and the `initialize` transition still blocked. All three
root causes below are confirmed against the current source.

## Root cause 1: tier 1 has no allow-list entry for artifact dirs

In `handle_role_guard()` (src/clasi/hook_handlers.py):

- `_allow_prefixes` (issues_dir, reflections_dir, design_dir,
  clasi_dir, log_dir; built at line 587) is only consulted inside
  `if agent_tier in ("", "0"):` (line 598).
- Tier 1's only allowance is the sprints prefix:
  `if agent_tier == "1" and file_path.startswith(_sprints_prefix)`
  (line 619).
- With no `protected_paths:` configured, control falls through to the
  unconditional BLOCK at line 647.

This contradicts the docstring matrix at the top of the same function
(lines 330-341), which documents `.clasi/ (non-sprint)` as ALLOW for
every tier including tier 1. Net effect: the one agent the
project-initiation skill assigns to write the initiation documents
(sprint-planner, tier 1) is the one tier that cannot write them
anywhere — tier 0 and tier 2 both can. The sanctioned recovery
(dispatching a nested sprint-planner) hits the identical block, so
there is no in-process path forward.

## Root cause 2: project-initiation skill hardcodes .clasi/design/

The skill text (`src/clasi/plugin/skills/project-initiation/SKILL.md`,
lines 25, 38, 42, 48, 59 — and the `get_skill_definition` copy served
over MCP) instructs writing the three documents to `.clasi/design/`.
But `Project.design_dir` is configurable via `paths.design`, and its
DEFAULT is already `docs/design/` (src/clasi/project.py:192-194) — so
the hardcoded path is wrong even for default-config projects, not just
custom ones. The state-machine predicate `is_overview_present`
resolves through `overview_exists()`
(src/clasi/status/reader.py:86-95), which checks
`design_dir / "overview.md"`. A skill-compliant write to
`.clasi/design/overview.md` therefore leaves `initialize` permanently
blocked even if root cause 1 were fixed. The skill should derive the
destination from the configured design path (e.g. via `get_status` or
an MCP tool that reports `Project.design_dir`), not name a literal
path.

## Minor: block message names the wrong role

The block message read `team-lead (tier 1)` — self-contradictory. The
tier is resolved from the state DB (registered by the SubagentStart
hook, keyed on agent_id), but the display name comes from
`os.environ.get("CLASI_AGENT_NAME", "team-lead")`
(src/clasi/hook_handlers.py:651), which is not propagated to
subagents. When the tier comes from the DB, the name should too. The
mismatch sent diagnosis down the wrong path: it looks like role
registration failed entirely, when actually the tier registered fine
and the missing allow-list entry is the real problem.

## Expected behavior

- A sprint-planner (tier 1) dispatched by project-initiation can write
  the initiation documents to the configured design dir (and, per the
  docstring matrix, to the other non-sprint artifact dirs).
- The project-initiation skill writes to `Project.design_dir`, not a
  hardcoded `.clasi/design/`.
- The role-guard block message names the actual registered role when
  the tier was resolved from the state DB.
- The docstring matrix and the implementation in `handle_role_guard()`
  agree.

## Steps to reproduce

1. `clasi init` a project with `paths.design: docs/design` in
   `.clasi/config.yaml`, no `protected_paths:`.
2. From a tier-0 team-lead session, dispatch a sprint-planner subagent
   instructed per the project-initiation skill.
3. Subagent attempts Write to `.clasi/design/overview.md` → blocked,
   reason `blk-write`, message names `team-lead (tier 1)`.
4. Note also that a successful write there would not satisfy
   `is_overview_present`, which watches `docs/design/overview.md`.

## Workaround used in the field

The team-lead (tier 0) placed the sprint-planner-authored files into
`docs/design/` via the guarded Write tool, which role-guard allows
(reason `artifact-dir` — the tier-0 allow list). The project then
advanced uninitialized → planning, confirming `docs/design/` is the
path the state machine actually watches.

## Fix sketch

1. In `handle_role_guard()`, extend the `_allow_prefixes` check to
   tier 1 (i.e. run it for `agent_tier in ("", "0", "1")`), keeping
   the tier-0 sprints-dir block above it scoped to tier 0 only, so the
   implementation matches the documented matrix. Add a regression test
   using a real captured payload asserting tier 1 + design_dir →
   allow, and tier 1 + source path → still blocked (prior role-guard
   bugs failed open silently — test the deny path with real captured
   payloads, not synthetic ones).
2. Replace every literal `.clasi/design/` in
   `plugin/skills/project-initiation/SKILL.md` (and any sibling
   agent/skill docs found by `grep -rl '\.clasi/design'` —
   sprint-roadmap, architecture-authoring, project-status,
   sprint-planner agent docs, software-engineering.md,
   migrate_command.py) with instructions to resolve the configured
   design dir.
3. In the block message, resolve the display name from the same source
   as the tier: when the tier came from the state DB, look up the
   registered agent name for `caller_id` instead of falling back to
   the `CLASI_AGENT_NAME` env default.
