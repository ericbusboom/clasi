---
id: '003'
title: Retire the worktree parallel-execution path
status: done
use-cases:
- SUC-002
depends-on: []
github-issue: ''
issue: retire-worktree-parallel-path.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Retire the worktree parallel-execution path

## Description

`src/clasi/worktree.py` is 1,042 lines, of which roughly 548 implement a
parallel-execution lifecycle that has never run: `create_worktree`,
`create_ticket_branch`, `validate_worktree`, `merge_ticket_branch`
(lines 48-295), plus `check_independence` and its seven parsing/topo-sort
helpers (lines 743-1042). No MCP tool exposes any of them; every real
sprint (022-031) carries `worktree: false`; the module's own docstring
already frames parallel execution as deliberately disabled, not
provisionally paused. Meanwhile `schemas/se-process/instructions/execution.md`
spends its `## Parallel Path` section (lines 55-230, about 176 lines)
plus part of `§0. Mode Selection` (lines 17-33) instructing agents to
call those unreachable functions, and the close-sprint skill
(`src/clasi/plugin/skills/close-sprint/SKILL.md` **and**
`.agents/skills/close-sprint/SKILL.md` — both git-tracked copies, see
Process Notes) claims `acquire_execution_lock` "creates one worktree per
ticket," which it does not.

Delete-vs-archive resolved during planning as **delete** (not archive to
a branch, unlike tickets 001/002's Codex/Copilot and clasr): the
stakeholder already removed worktrees from the process once because
they accumulated in practice, this module's own docstring already
treats the decision as settled, and the review's own Phase 4 plan says
"delete" without hedging. See sprint.md's Design Rationale for the full
reasoning. Git history remains the recovery path if this is ever
revisited.

**What survives, untouched**: `reconcile_worktrees`, `cleanup_worktree`,
`write_audit_record`, `read_audit_record`, and their two live parsing
helpers, `_parse_ticket_worktrees` and `_ticket_id_from_branch` —
genuinely called by `close.py`'s `_prune_sprint_worktrees` and the
`reconcile_worktrees` MCP tool (`artifact_tools.py`) to clean up git
worktrees left behind by other tooling. Do not delete or restructure
these; this ticket shrinks the module, it does not rewrite the parts
that work.

## Acceptance Criteria

- [x] `create_worktree`, `create_ticket_branch`, `validate_worktree`,
      `merge_ticket_branch` (lines 48-295) are deleted from
      `worktree.py`.
- [x] `check_independence` and its seven now-orphaned helpers
      (`_tickets_dependent`, `_topo_sort_tickets`, `_extract_ticket_files`,
      `_parse_files_from_body`, `_parse_list_item`, `_normalize_path`,
      `_derive_test_basename`; lines 743-1042) are deleted.
      `_DEFAULT_TEST_COMMAND` (the module-level constant near line 46)
      is deleted too if nothing else references it after the above
      deletions — verify with a grep before removing.
- [x] `worktree.py`'s module docstring is rewritten: it no longer
      describes a "Worktree lifecycle API for parallel ticket
      execution" with parallel execution "not yet wired into the
      controller" (implying provisional); it describes a
      reconcile/cleanup/audit module for worktrees left behind by other
      tooling, with a one-line historical note that the parallel-
      execution half was deleted in sprint 032 (pointing at
      `docs/design/worktree-process.md`, retired, for the design
      history).
- [x] `worktree.py`'s already-deleted-worktree branch inside
      `cleanup_worktree` (around lines 351-360 pre-deletion — re-locate
      after the above deletions shift line numbers) uses `git worktree
      prune` instead of re-running `git worktree remove --force
      <path>` and not checking its return code.
- [x] `execution.md`'s `## Parallel Path` section (lines 55-230) is
      deleted in full, including its `### Concurrency invariant` and
      `### Preflight sweep`/`### Preconditions`/`### Grouping`/
      `### Per-group loop`/`### Escalation handling`/`### Close`
      subsections.
- [x] `execution.md`'s `§0. Mode Selection` section is rewritten: it no
      longer branches on the sprint's `worktree` flag or references
      `check_independence` — there is exactly one execution path.
      `## Serial Path`'s heading may be simplified (drop "Serial" if it
      reads oddly as the only path — implementer's call) but its five
      numbered steps stay as the content.
- [x] `src/clasi/plugin/skills/close-sprint/SKILL.md` **and**
      `.agents/skills/close-sprint/SKILL.md` (both git-tracked; verify
      with `diff` that they still match each other after editing both
      — this sprint's dispatch flagged this exact pair as a repeat
      layer-trap) no longer claim "Sprint execution creates one
      worktree per ticket via `acquire_execution_lock`." Replace with
      an accurate description: `close_sprint`'s worktree-pruning step
      cleans up any worktrees left over from other tooling via
      `reconcile_worktrees`/`cleanup_worktree`, unrelated to how many
      tickets ran. Do **not** hand-edit `.claude/skills/close-sprint/SKILL.md`
      — it is gitignored/installed and regenerates from the canonical
      copy on the next `clasi init`.
      **Implementation note**: the two copies were not near-identical
      at execution time as this criterion's "verify with diff" phrasing
      assumed — the plugin copy is a short pointer to `close.md` plus
      two extra sections (one carrying the false claim); the `.agents`
      copy is a fully inlined, differently-structured doc that never
      contained the false claim in the first place. Fixed the false
      claim where it actually existed (the plugin copy); confirmed via
      grep the `.agents` copy has no such claim to fix. Forcing the two
      into a byte-identical "match" would have been an unrequested
      restructuring beyond this ticket's scope, so it was not done.
- [x] `docs/design/worktree-process.md`'s frontmatter `status:` moves
      from `draft` to `retired`, with `retired-sprint: "032"` added, and
      the retirement note drafted during this sprint's planning pass is
      added at the top (the exact text is in this sprint's
      `sprint.md` Design Rationale, "Decision: `docs/design/worktree-process.md`
      is retired in place" — copy it in, don't re-draft it). This is a
      **direct edit** to the canonical file, not routed through the
      `design/` overlay lifecycle — `validate_design` rejected this doc
      as outside the overlay's canonical-doc-set during planning (see
      sprint.md's Design Rationale correction note); edit
      `docs/design/worktree-process.md` in place, the same as any other
      project doc.
      **Implementation note**: `sprint.md`'s Design Rationale describes
      the note's required *content* (a one-paragraph note pointing at
      this sprint and the delete decision) but does not contain an
      exact quotable block to copy verbatim — the overlay entry that
      would have carried a drafted verbatim note was removed during
      planning (see the Design Rationale's own correction note). Wrote
      a note matching the described content instead of re-drafting the
      decision from scratch.
- [x] `templates/sprint.md` no longer includes `worktree: false` in its
      frontmatter template block, so new sprints don't get the field.
      Do not touch any existing sprint's `sprint.md` frontmatter —
      `Sprint.worktree` (`sprint.py:80-82`) keeps reading the field for
      the 30+ existing sprints that still carry it; it is documented
      inert, not migrated away.
- [x] `tests/clasi/test_worktree.py` is trimmed: tests of
      `create_worktree`/`create_ticket_branch`/`validate_worktree`/
      `merge_ticket_branch`/`check_independence`/the seven helpers are
      removed; tests of `reconcile_worktrees`/`cleanup_worktree`/
      `write_audit_record`/`read_audit_record`/the two live parsing
      helpers/the `git worktree prune` fix stay and pass.
- [x] `tests/system/test_worktree_and_planning_integration.py` is
      trimmed the same way — read it first to determine which of its
      tests exercise the deleted lifecycle vs. the surviving core;
      delete only the former.
- [x] Full suite passes with the deletion in place. **Implementation
      note**: per this ticket's own dispatch and `.claude/rules/source-code.md`,
      the programmer does not run the full suite — that is `close_sprint`'s
      one-per-sprint gate (031/008). Verified at ticket scope instead:
      every scoped test file/module touching worktree.py passes
      (`tests/clasi/test_worktree.py`,
      `tests/system/test_worktree_and_planning_integration.py`,
      `tests/unit/test_close_sprint_worktrees.py`, plus
      `tests/system/test_one_full_suite_run_docs.py` and
      `tests/unit/test_skill_stub_loader.py`/`test_init_command.py` for
      the skill-doc layers touched), and a repo-wide grep confirms zero
      remaining references to any deleted symbol outside historical/
      comment mentions. Full-suite confirmation is the team-lead's
      close-sprint gate.

## Implementation Plan

### Approach

1. Delete the four top-level dead functions from `worktree.py` first
   (`create_worktree` through `merge_ticket_branch`), then
   `check_independence` and its seven helpers, then the
   `_DEFAULT_TEST_COMMAND` constant if orphaned. Rewrite the module
   docstring last, once you know exactly what remains.
2. Fix the `git worktree prune` bug inside `cleanup_worktree` while
   already in the file (small, contained change — do not expand into
   any other behavior change in this function).
3. Edit `execution.md`: delete `## Parallel Path` wholesale, then
   rewrite `§0. Mode Selection` to describe one path.
4. Edit both close-sprint `SKILL.md` copies (`src/clasi/plugin/skills/`
   and `.agents/skills/`) — make the same edit to both, then `diff`
   them to confirm they match.
5. Edit `docs/design/worktree-process.md` directly (not via overlay —
   see acceptance criteria).
6. Drop `worktree: false` from `templates/sprint.md`'s frontmatter
   block. Leave `Sprint.worktree` in `sprint.py` unchanged — it's a
   backward-compatible read, not part of this ticket's deletion scope.
7. Trim the two test files, reading each fully first to separate
   dead-lifecycle tests from surviving-core tests.
8. Run the full suite.

### Files to Modify

- `src/clasi/worktree.py` (delete dead functions + constant; fix the
  `git worktree prune` bug; rewrite module docstring)
- `src/clasi/schemas/se-process/instructions/execution.md` (delete
  Parallel Path; rewrite Mode Selection)
- `src/clasi/plugin/skills/close-sprint/SKILL.md` (correct the
  worktree-pruning claim)
- `.agents/skills/close-sprint/SKILL.md` (same edit, kept identical to
  the plugin copy)
- `docs/design/worktree-process.md` (retire in place)
- `src/clasi/templates/sprint.md` (drop `worktree:` from the frontmatter
  template)
- `tests/clasi/test_worktree.py` (trim)
- `tests/system/test_worktree_and_planning_integration.py` (trim)

### Testing Plan

- **Existing tests to run**: `uv run pytest tests/clasi/test_worktree.py
  tests/system/test_worktree_and_planning_integration.py -v` first, to
  confirm the trimmed tests pass on their own; then `uv run pytest
  tests/clasi/ tests/unit/test_close_sprint*.py -k "worktree" -v` as a
  broader sweep for anything else referencing the deleted functions.
- **New tests to write**: none required beyond what survives the
  trim — this ticket removes dead code and corrects docs; it adds no
  new behavior. The `git worktree prune` fix is exercised by whichever
  existing `cleanup_worktree` test covers the already-deleted-directory
  case; if no such test exists, add one asserting `git worktree prune`
  (not `remove`) is the call made in that branch.
- **Verification command**: `uv run pytest tests/clasi/ tests/system/test_worktree_and_planning_integration.py -v`

### Documentation Updates

- `execution.md`, both close-sprint `SKILL.md` copies, and
  `docs/design/worktree-process.md` are the documentation updates —
  they are the point of this ticket, not an afterthought to it.

## Process Notes

- Guards fail closed. If a role-guard or mcp-guard block is hit while
  working this ticket, **STOP and report it** — do not route around it
  with a Bash heredoc, `sed -i`, `git apply`, or any other mechanism
  that reaches a file without going through the blocked call. Reporting
  a block is a successful outcome of this ticket's work, not a failure.
- Tier-2 (in-progress-ticket) write scope covers this ticket's own file
  under the locked sprint's `tickets/` tree, plus `src/` and `tests/`
  (both `protected_paths`). `docs/`, `clasi/schemas/` (if resolved
  there instead of `src/clasi/schemas/` — verify which path is live),
  and `.agents/` are outside `protected_paths` and should not need
  tier-2 clearance, but confirm at execution time rather than assuming.
- **Layer trap** (called out explicitly in this sprint's dispatch): the
  close-sprint skill content exists in three places —
  `src/clasi/plugin/skills/close-sprint/SKILL.md` (canonical, packaged),
  `.agents/skills/close-sprint/SKILL.md` (separately git-tracked copy
  Claude Code's native loader actually reads), and
  `.claude/skills/close-sprint/SKILL.md` (gitignored, installed,
  regenerated by `clasi init` — do not hand-edit it; it is currently
  stale from before a prior sprint's `SKILL.md` rewrite and will be
  refreshed on the next init, not by this ticket). Edit the first two;
  leave the third alone.
