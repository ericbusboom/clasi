---
id: '005'
title: Fix unreachable/drifted rule paths and add rule-reachability test
status: done
use-cases:
- SUC-006
- SUC-010
depends-on:
- '004'
github-issue: ''
issue: enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix unreachable/drifted rule paths and add rule-reachability test

## Description

Claude Code's `.claude/rules/*.md` frontmatter supports only a positive
`paths:` glob array — no `exclude:` key, no negated globs (verified
against official docs at https://code.claude.com/docs/en/memory.md,
"Path-specific rules"; not assumed). A rule fires only when Claude reads
a file matching one of its `paths:` patterns; a rule with no `paths:` key
loads unconditionally at launch (same priority as CLAUDE.md).

Three of the five generated rules in `platforms/claude.py`'s `RULES`
dict (and `platforms/copilot.py`'s equivalent `_PATH_RULES`) are
dead or drifted as a result:

1. **`source-code.md`**: `paths: [src/clasi/**, src/clasr/**, tests/**]`
   — CLASI's own layout, stamped into every `clasi init` target. In any
   project without a `src/clasi/` or `src/clasr/` directory (every
   downstream project), this rule is **unreachable** — it can never
   match any file. Fix: drop `paths:` entirely so the rule loads
   unconditionally. Move the path exclusions (`.clasi/`, `.claude/`,
   `docs/`, `*.md`) into `SOURCE_CODE_BODY`'s prose — there is no glob
   that expresses "everything except these four directories."
2. **`clasi-artifacts.md`**: `paths: [.clasi/**]` — but artifacts moved
   to visible `clasi/**` in sprint 013; `.clasi/` now holds only state
   files (`config.yaml`, `log/`, `.clasi.db`). This rule has never fired
   on an edit to `clasi/sprints/**` since that migration. Fix: re-scope
   `paths:` to `clasi/**` (a straightforward positive-glob correction —
   `clasi/**` is a real, matchable path, unlike `source-code.md`'s
   situation).
3. **`todo-dir.md`**: generator (`platforms/claude.py:58`,
   `platforms/copilot.py`) still emits `paths: [.clasi/issues/**]`, but
   this repo's on-disk `.claude/rules/todo-dir.md` has already been
   hand-corrected to `paths: [clasi/issues/**]` — the generator and the
   installed file have silently diverged. Fix the generator only; the
   on-disk value in this repo is already correct and does not need
   changing (verify it still matches after the generator fix, but do not
   assume it needs edits — confirm by reading it first).

Then add the general test that would have caught all three before any of
them shipped: after a fresh `clasi init` into a scratch/temp project,
assert every generated rule file that carries a `paths:` key has at
least one pattern that matches a real path in that project. This targets
the failure *class* (a generated rule that cannot match reality), not
each instance — the single most valuable new test in this sprint per
the sprint's Test Strategy.

**Also update `SOURCE_CODE_BODY`** in `platforms/_rules.py`: state that a
commit message is not a process action — only an MCP call moves a
ticket. (This was already planned as part of defect 4/SUC-006 and is
unrelated to the reachability fix, but belongs in the same file edit.)

**This repo is self-affected**: since CLASI dogfoods its own tooling,
this repo's own `.claude/rules/source-code.md` and `clasi-artifacts.md`
must be regenerated (or hand-updated to match the new generator output)
as part of this ticket's own delivery — do not leave this repo running
stale rule content while the generator is fixed only for future
`clasi init` targets.

**Bootstrap note**: this ticket executes after ticket 004, meaning
role-guard's ticket-state gate is now fully live for tier 2. Normal
`execute-ticket` flow (ticket marked `in-progress` before writing) is
unaffected. If you hit an unexpected block while working this ticket,
see ticket 004's bootstrap-risk note — confirm the ticket is
`in-progress`, and use `.clasi/oop` only if something is genuinely broken
in the gate itself, not as a routine workaround.

Root cause reference: `clasi/issues/enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md`
defect 4/5, broadened during architecture review (see
`architecture-update.md` §2, "Why responsibility 5 changed scope").

## Acceptance Criteria

- [x] `platforms/claude.py` `RULES["source-code.md"]` no longer includes
      a `paths:` key — the rule loads unconditionally.
- [x] `platforms/_rules.SOURCE_CODE_BODY` states the `.clasi/`,
      `.claude/`, `docs/`, `*.md` exclusions in prose, and states that a
      commit message is not a process action (only an MCP call moves a
      ticket).
- [x] `platforms/copilot.py`'s equivalent `source-code` entry is fixed
      the same way (no scoped `applyTo:`/`paths:` restricting it to
      CLASI's own layout — check what "unconditional" means in
      Copilot's instructions-file format, which may differ from Claude
      Code's; document the equivalent if the mechanism differs).
- [x] `platforms/claude.py` `RULES["clasi-artifacts.md"]` emits
      `paths: [clasi/**]` (or an equivalent covering `clasi/sprints/**`,
      `clasi/issues/**`, `clasi/reflections/**`), not `.clasi/**`.
- [x] `platforms/copilot.py`'s equivalent entry fixed the same way.
- [x] `platforms/claude.py` `RULES["todo-dir.md"]` emits
      `paths: [clasi/issues/**]`, not `.clasi/issues/**`. Verified this
      repo's on-disk `.claude/rules/todo-dir.md` already has the correct
      value (read it first) and needs no change, only the generator did.
- [x] New test: after `clasi init` into a fresh scratch/temp project,
      for every generated `.claude/rules/*.md` file with a `paths:` key,
      assert at least one pattern matches a real path that exists in
      that project.
- [x] Test specifically confirms `source-code.md` demonstrably fires
      (present in context, no `paths:` key) in a scratch repo whose code
      lives under `source/` (not `src/clasi/`) — the acceptance bar
      specified as non-negotiable during architecture review.
- [x] This repo's own `.claude/rules/source-code.md` and
      `clasi-artifacts.md` are regenerated or hand-corrected to match
      the new generator output (verify via `clasi init --force` on this
      repo, or by direct comparison, per implementer's judgment — but
      the files on disk in `/Volumes/Proj/proj/ai-projects/clasi` must
      reflect the fix, not just the generator source).

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_platforms*.py -v`
  (or wherever platform-installer tests currently live — locate via
  `grep -rl "RULES\[" tests/`).
- **New tests to write**: rule-path-reachability test (general, covers
  all three rules); `source-code.md`-fires-in-non-CLASI-layout test;
  regenerated on-disk rule content verification for this repo.
- **Verification command**: `uv run pytest tests/unit/test_platforms*.py -v`;
  manually: `clasi init` into
  `/private/tmp/claude-*/scratch-reachability-check` with a `source/`
  directory, inspect the generated `.claude/rules/*.md` files.
