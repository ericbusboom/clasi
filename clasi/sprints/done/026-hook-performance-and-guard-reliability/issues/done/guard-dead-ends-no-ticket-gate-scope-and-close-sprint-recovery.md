---
status: done
sprint: '026'
tickets:
- 026-001
- 026-002
---

# Guard dead ends: no-ticket gate scope, close_sprint recovery state, prefix matching

## Description

Three guard behaviors produce hard dead ends — an agent is blocked with no
in-process route forward — independent of any policy question. These are
bugs against the guards' own design intent. Empirically, `no-ticket` is the
burstiest block reason in this repo's `.clasi/log/hooks.log` (25 blocks, 15
of them in retry bursts; one programmer burned 3 tool calls and 22 seconds
discovering the gate).

1. **Exception routing deadlocks by construction.** The ticket-state gate
   (`handle_role_guard`, `src/clasi/hook_handlers.py:547-559`) blocks ALL
   tiers when a sprint execution lock is held and no ticket is
   `in-progress`, and it runs before every allow list.
   `throw_ticket_exception` sets ticket status to `exception` — not
   `in-progress` — so the moment an exception is thrown, every write by
   every agent is blocked: the sprint-planner dispatched to fix the
   architecture, and the team-lead's issue/reflection writes. The `issue`
   and `self-reflect` skills are unavailable exactly when something has
   gone wrong.

2. **close_sprint hands out recovery instructions it blocks.** Two
   precondition-failure branches (frontmatter fence error, sprint-id
   mismatch; `src/clasi/tools/artifact_tools.py:1468-1502`) tell the caller
   to edit `sprint.md` and retry, but return `recovery.recorded: False,
   allowed_paths: []` — so the role-guard recovery bypass
   (`hook_handlers.py:482-491`) cannot fire, and the named file is exactly
   what role-guard blocks. The ticket-not-done branch (:1533-1552) DOES
   write recovery state — the mechanism exists, it just isn't applied to
   these two branches.

3. **Recovery-state matching is exact-path only.**
   `hook_handlers.py:488` compares `file_path in recovery["allowed_paths"]`
   exactly, but at least one writer stores a directory
   (`artifact_tools.py:1795` stores `str(project.design_dir)`), which can
   never match a file write. Directory entries in `allowed_paths` are
   silently inert.

## Cause

- The ticket-state gate was added to stop untracked programmer commits
  (its stated rationale: a sprint landing commits with no ticket ever
  in-progress) but was placed before the tier checks and allow lists, so
  it also gates the recovery agents and incident-capture artifacts.
- The two close_sprint branches predate (or missed) the recovery-state
  mechanism used by the ticket-not-done branch.
- `allowed_paths` semantics were never defined for directories; writers
  assume prefix semantics, the reader implements exact match.

## Proposed fix

1. Scope the ticket-state gate to tier 2 only (its original purpose), and
   exempt `issues_dir` and `reflections_dir` for all tiers so incident
   capture is never blocked. Decided by the stakeholder 2026-08-19.
2. In `_close_sprint_full`, make the frontmatter-fence and id-mismatch
   branches write recovery state with the offending `sprint.md` path in
   `allowed_paths` (pattern already present at `artifact_tools.py:1533-1552`).
3. Make recovery matching honor directory prefixes as well as exact paths
   (normalize entries; a trailing-slash or is-dir entry matches any file
   under it).

## Verification

- Test: execution lock held, zero in-progress tickets → tier-2 source
  write blocked (`no-ticket`); tier-0/1 writes allowed; issue/reflection
  writes allowed for all tiers. Use real captured payloads and assert both
  allow and deny paths.
- Test: `close_sprint` against a sprint.md with a broken frontmatter fence
  → response includes populated `allowed_paths`, and a follow-up guarded
  Edit of that file passes with reason `recovery`.
- Test: recovery record containing a directory entry → file write under
  that directory passes.
- Scenario test: throw_ticket_exception → dispatched sprint-planner can
  edit the sprint's architecture without OOP.

## Related

- `report-guard-friction-slowness-relax-tier-0-restrictions.md` —
  companion policy issue from the same investigation (its tier-0
  relaxation makes item 2 mostly moot for tier 0, but dispatched planners
  still need it).
- `hook-overhead-status-inject-dead-hooks-and-logging.md` — companion
  performance/observability issue.
