---
status: done
sprint: '031'
tickets:
- 031-003
- 031-004
---

# Relax tier-0/tier-1 write policy; make write scope discoverable

## Description

Stakeholder decision (Eric, 2026-08-19): the guard policy is stricter than
the process needs, and agents burn turns discovering their limits by being
blocked. Evidence from this repo's own `.clasi/log/hooks.log` (2,447
events): 68% of all hard blocks occur in retry bursts of ≥2 within 180
seconds (agents hit a gate, retry, re-route, hit it again — one recorded
case: team-lead blocked 3×, dispatched a sprint-planner to comply, planner
blocked 2× more); the OOP escape hatch carries more traffic than the gates
block (106 oop-bypass allows vs 68 blocks all-time, ~1 in 5 recent writes
under OOP); and the write gates are advisory anyway, since role-guard
matches only Edit|Write|MultiEdit and a Bash heredoc bypasses everything.

New tier-0 policy, decided: **block protected source paths and
`create_ticket`, allow everything else.** Specifically:

- Tier 0 may write ALL sprint files (whole `sprints_dir` unblocked;
  `blk-sprint` removed for tier 0).
- Tier 0 may call `create_sprint` directly. It only writes a template
  sprint.md; the current block forces a full sprint-planner dispatch per
  sprint, after which the team-lead must parse the sprint id out of the
  planner's free-text report — which the team-lead agent doc itself flags
  as "the most common way issue linkage silently fails." `create_ticket`
  stays blocked for tier 0 (ticket creation remains planner-owned).
- Tier 1 gets the artifact-dir allow list (design/issues/reflections/
  clasi/log), matching the role-guard docstring matrix that already
  documents this.

## Cause

- role-guard (`src/clasi/hook_handlers.py`, `handle_role_guard`): the
  artifact-dir allow list runs only for tier 0 (:598-614); tier 1's only
  allowance is `sprints_dir` (:618-620); tier 0 is blocked from
  `sprints_dir` (:598-610); everything not allow-listed falls through to an
  unconditional block (:647-669).
- mcp-guard matcher covers `create_ticket|create_sprint` but not
  `insert_sprint`, which also creates sprints — the create_sprint block is
  porous as well as costly.
- `clasi init` never writes `protected_paths`
  (`src/clasi/init_command.py:222-240`), despite the role-guard docstring
  claiming it does — so consumer projects run in the harsh block-by-default
  mode where everything not allow-listed is blocked for tiers 0/1.
- Agents have no way to learn their write scope except by being blocked:
  nothing at SubagentStart or in the status block states allowed/blocked
  prefixes.

## Proposed fix

1. `handle_role_guard`: remove the tier-0 `sprints_dir` block; run the
   artifact-dir allow list for tiers 0 AND 1; allow `sprints_dir` writes
   for all tiers. Update the docstring matrix to match the new
   implementation exactly.
2. mcp-guard hook matcher (plugin/hooks/hooks.json and installer): shrink
   to `mcp__clasi__create_ticket` only. This also ends the insert_sprint
   inconsistency.
3. `clasi init`: detect (or ask for) the project's source/test directories
   and write `protected_paths` to `.clasi/config.yaml`. Unconfigured
   projects keep today's block-by-default fall-through as the safety net.
4. Scope discoverability: inject a 3-4 line write-scope summary for the
   agent's tier at SubagentStart (and in the tier-0 status block): allowed
   prefixes, blocked prefixes, recovery route.
5. Doc alignment with the new policy:
   - `src/clasi/plugin/instructions/software-engineering.md:528-535`
     (internal-exception routing — team-lead editing the ticket plan
     becomes legal),
   - `src/clasi/schemas/se-process/instructions/sprint-plan.md` Phase 1
     (create_sprint / "Write sprint.md" steps become legal for tier 0),
   - team-lead `agent.md` (drop the sprint-id-parsing workaround; the
     team-lead calls `create_sprint` itself; sprint-planner dispatch
     remains the norm for planning CONTENT, now advisory rather than
     enforced).
6. Fix the block message to name the actual registered role: the tier is
   resolved from the state DB but the name comes from
   `os.environ.get("CLASI_AGENT_NAME", "team-lead")`
   (`hook_handlers.py:651`), producing self-contradictory messages like
   "team-lead (tier 1)". Resolve the name from the same source as the
   tier.

## Verification

- Regression tests per gate using real captured hook payloads, asserting
  both the allow AND the deny paths (prior guard bugs failed open
  silently): tier 0 + sprints_dir → allow; tier 0 + protected source →
  block; tier 0 + create_sprint → allow; tier 0 + create_ticket → block;
  tier 1 + design_dir → allow.
- `clasi init` on a fresh fixture project writes `protected_paths`.
- After a working session, mine `.clasi/log/hooks.log`: blk-sprint and
  blk-mcp bursts should disappear and oop-bypass traffic should drop
  toward zero.

## Related

- `guard-dead-ends-no-ticket-gate-scope-and-close-sprint-recovery.md` —
  companion issue: gate-ordering dead ends (same investigation).
- `hook-overhead-status-inject-dead-hooks-and-logging.md` — companion
  issue: hook latency and logging (same investigation).
- `role-guard-tier1-design-dir-and-initiation-skill-hardcoded-path.md` —
  the tier-1 artifact-dir change here subsumes root cause 1 of that issue
  and item 6 subsumes its "minor" finding; its root cause 2 (skill
  hardcodes `.clasi/design/`) remains separate and still needed.
- `role-guard-blocks-plan-mode-plans-dir.md` — documents the gate as
  "over-blocking and porous" (Bash-heredoc bypass).
