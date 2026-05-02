---
status: done
---

# Disable parallel ticket execution and worktrees — mandate serial-only

## Why

Parallel programmer dispatch and worktree orchestration are unreliable in current usage — programmer agents working concurrently on the same sprint branch race on commits and the test suite, and the worktree lifecycle (create / branch / merge-back / cleanup) is not robust enough to make the path safe by default. Until a proper worktree process is designed and implemented (see the paired TODO at [define-proper-worktree-process-for-parallel-ticket-execution.md](define-proper-worktree-process-for-parallel-ticket-execution.md)), CLASI must default to and enforce strictly serial ticket execution. The serial path is no longer a "fallback" — it is THE path.

## Behavioral change

`execute-sprint` MUST dispatch one programmer agent per ticket in dependency order, one at a time, working directly on the sprint branch. No worktrees. No concurrent programmer agents.

## Files to update

- `clasi/plugin/skills/execute-sprint/SKILL.md` — Rewrite. Remove the parallel-worktree primary path. The current "Fallback: Serial Execution" section becomes the *only* path. Frontmatter `description` updated (no longer mentions "parallel worktrees"). Step 3 (Tasks subsystem) is replaced by direct sequential Agent dispatch — one ticket at a time, in dependency order.
- `clasi/plugin/skills/parallel-execution/SKILL.md` — Delete. Deprecation notes belong in commit history, not in the live skill set. (If the implementer prefers to preserve a stub, replace the file body with a single sentence pointing at this TODO and the paired worktree-process TODO. Default: delete.)
- `clasi/plugin/agents/team-lead/agent.md` lines 89–91 — Strip the parallel-execution language. The team-lead's step in "Execute TODOs Through a Sprint" becomes: "Invoke the `execute-sprint` skill, which dispatches programmer agents one at a time in dependency order."
- `clasi/plugin/agents/sprint-planner/agent.md` lines 161–163 — Strip "parallel execution groups" language. Tickets are still dependency-ordered, but there are no Groups. The sprint-planner produces a flat sequenced list. The dependency analysis itself stays — it still drives ordering — but the term "parallel" goes away.
- `clasi/plugin/instructions/worktree-protocol.md` — Delete. Worktrees are not currently used.
- `clasi/templates/sprint.md` line 64 — Remove the "Group" column from the ticket table and the "Tickets in the same group can execute in parallel" sentence. Tickets are listed in flat dependency order.
- `clasi/plugin/instructions/git-workflow.md` — Audit and remove any worktree references (currently minimal).
- `README.md` and `AGENTS.md` at repo root — No changes (no parallel/worktree references).
- `clasi/platforms/_rules.py` — No changes (no parallel/worktree references).

## Tests

- Search `tests/` for any test exercising parallel-execution or worktree behavior. Update or remove as needed.
- Add a documentation-lint test: grep the live skill set and agent definitions for the words "worktree" and "parallel" — both should be absent (or limited to a documented "this is disabled, see TODO" stub if `parallel-execution/SKILL.md` was kept).

## Out of scope

- Designing the eventual re-enable path. That's owned by [define-proper-worktree-process-for-parallel-ticket-execution.md](define-proper-worktree-process-for-parallel-ticket-execution.md), which would be a separate sprint after this one.
- Changing how the sprint-planner detects ticket independence. The dependency analysis stays; only the "parallel groups" framing is removed.
- Touching any non-CLASI code (`clasr`, etc.).

## Related

[define-proper-worktree-process-for-parallel-ticket-execution.md](define-proper-worktree-process-for-parallel-ticket-execution.md) — the paired TODO that designs a robust worktree process. Re-enabling parallel/worktree execution is gated on that TODO being fully implemented in a future sprint.

## Origin

Stakeholder request 2026-05-02, after sprint 014 was deliberately executed serially via the existing fallback path because parallel programmer dispatch was unreliable in practice.
