---
id: '001'
title: Archive Codex/Copilot platform adapters to a branch; remove from master
status: done
use-cases:
- SUC-007
depends-on: []
github-issue: ''
issue: ''
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Archive Codex/Copilot platform adapters to a branch; remove from master

## Description

Stakeholder decision (Eric, 2026-08-21, recorded in sprint.md's
"Stakeholder Decisions Needed"): archive `src/clasi/platforms/codex.py`
and `copilot.py` — 1,126 source lines, 1,762 test lines, never
dogfooded, reachable only via explicit `--codex`/`--copilot` flags, and
carrying finding F4 (installing Codex after Claude overwrites Claude's
resolved skill canonical) — to a branch, then remove them from master.
This is not just deleting two files: `codex.py`/`copilot.py` have
roughly a dozen dependents across the CLI, hook dispatch, and shared
platform-detection code (verified by grep during planning — see Files
to Modify below), all of which need their Codex/Copilot-specific
branches removed so nothing in master points at deleted code.

No linked issue owns this ticket — it implements the review's Part 6
decision 2, not one of this sprint's six tracked issues. It traces to
SUC-007 in `sprint.md`.

This ticket has no dependency on any other ticket in this sprint, but
ticket 004 (installer merge fixes) depends on **this** ticket landing
first — F4's original "shared canonical-skill writer used by all three
installers" requirement is dropped once this ticket removes the second
and third installer (see sprint.md's Design Rationale, "Decision: drop
F4's three-way shared canonical-skill writer requirement"). Land this
ticket before starting 004.

## Acceptance Criteria

- [x] An `archive/codex-copilot-adapters` branch exists on `origin`,
      created at a commit that still has the full pre-deletion content
      of `src/clasi/platforms/codex.py`, `copilot.py`, and their tests
      — created and pushed **before** the deletion commit lands on the
      sprint branch (see Implementation Plan's git sequence).
      **Team-lead override applied**: created LOCAL-ONLY (not pushed to
      origin) — local master is 145 commits ahead of origin/master, and
      pushing would have published this campaign's entire unpublished
      history to GitHub as a side effect of an archival ticket. Cut at
      commit 358dd08 (current HEAD before any deletion), spot-verified
      via `git show archive/codex-copilot-adapters:<path> | head -20`
      against both `src/clasi/platforms/codex.py` and
      `src/clasi/platforms/copilot.py`, plus
      `tests/unit/test_platform_codex.py` and
      `tests/unit/test_platform_copilot.py` — full pre-deletion content
      confirmed present (592/534 lines respectively, matching the
      pre-deletion working tree). The deletion commit's parent also
      retains full recoverability independent of the branch.
- [x] `src/clasi/platforms/codex.py` and `copilot.py` are deleted from
      master.
- [x] Their unit tests are deleted: `tests/unit/test_platform_codex.py`,
      `tests/unit/test_platform_copilot.py`. `tests/unit/test_three_platform_install.py`
      is either deleted (if it tests nothing without all three
      platforms) or trimmed to a two-platform — really one-platform —
      scope; verify which by reading it first.
      Read in full: every test in the file called
      `run_init(..., codex=True, copilot=True, ...)` and asserted on
      Codex/Copilot-specific paths (`.codex/`, `.github/skills` symlink,
      etc.); nothing survives without all three platforms — deleted.
- [x] `cli.py`'s `--codex`/`--copilot` `click.option` flags on `init`
      and `uninstall` (lines ~41-43, ~106-108 per this planning pass's
      grep — re-verify exact lines, since ticket 002/earlier work in
      this sprint may shift them) are removed or made to produce a
      clear error. See the next criterion for which.
      Kept (not removed) — Click still parses them — and routed through
      `run_init`/`run_uninstall`'s new archived-support check (see next
      criterion) rather than a bare "no such option" error, per the
      strengthened backward-compatibility criterion below.
- [x] **Backward compatibility for existing consumers** (added during
      architecture review): a repo that already has Codex/Copilot
      content installed by a pre-archival `clasi` (from an earlier
      `clasi init --codex`) is not silently broken. Concretely:
      `clasi init`/`clasi uninstall` with **no** platform flag still
      succeeds and manages Claude content only (unaffected by this
      ticket). Passing `--codex`/`--copilot` explicitly — whether the
      flags are kept-but-erroring or removed entirely — must produce a
      clear message such as "Codex/Copilot support has been archived;
      see the `archive/codex-copilot-adapters` branch" rather than a
      stack trace, an `UnrecognizedOptionError`-with-no-context, or a
      silent no-op that looks like it succeeded.
      `run_init()`/`run_uninstall()` now raise `click.ClickException`
      with exactly this message (mentions the archive branch by name)
      when `codex=True` or `copilot=True`, caught by Click and surfaced
      as a clean nonzero-exit CLI error, not a stack trace. Verified via
      new regression tests in `test_cli_init.py`
      (`TestRunInitArchivedPlatforms`, `TestCliInitFlags`) and
      `test_uninstall_command.py` for both `run_*()` direct calls and
      the CLI layer, plus no-flag-still-installs-Claude-only tests in
      both files.
- [x] `hook_handlers.py`'s `codex-plan-to-issue`/`codex-plan-to-todo`
      hook subcommands (`cli.py:467-468` and their handler functions)
      are removed, since nothing installs Codex hook wiring that would
      invoke them anymore.
- [x] `init_command.py`, `uninstall_command.py`, `plan_to_issue.py`,
      `skill_resolve.py` lose their Codex/Copilot-specific branches
      (verify exact scope by reading each file — this planning pass
      found them via `grep -rln "codex\|copilot"` but did not audit
      every call site's necessity).
      `init_command.py`/`uninstall_command.py`: install/uninstall
      branches and the interactive multi-platform prompt removed
      (Claude is the only platform left, so no prompt is needed).
      `skill_resolve.py`: docstring-only mention corrected. `plan_to_issue.py`:
      read in full — it has no Codex/Copilot conditional branches, only
      a `plan_to_issue_from_text()` function whose sole caller
      (`handle_codex_plan_to_issue`) is removed by this ticket; left
      in place as a small, self-contained, still-tested utility rather
      than deleted, since the ticket's explicit scope is "branches," not
      whole functions — flagging as residual dead code for a follow-up
      ticket to consider, not silently dropped.
- [x] `platforms/detect.py`'s `codex_score`/`copilot_score` fields and
      scoring logic are either removed (return `PlatformSignals` with
      just `claude_score`/`recommendation`) or left as inert dead
      fields — implementer's choice (see platforms/DESIGN.md overlay's
      Open Questions, this sprint's `design/platforms-DESIGN.md`); if
      left in place, add a one-line comment noting they're vestigial
      pending full removal.
      Left in place (matches the platforms-DESIGN.md overlay's
      Interfaces section, which already describes the fields as
      "remain in the return shape (harmless, unused)"); added a
      docstring note marking them vestigial. `detect.py` has no
      dependency on `codex.py`/`copilot.py` — self-contained filesystem
      signal scoring — so this required zero changes to
      `test_platform_detect.py`.
- [x] `platforms/_rules.py`'s comment referencing "both `claude.py` and
      `codex.py` import from here" is corrected to reflect one reader.
- [x] `pyproject.toml` is untouched by this ticket (its `clasr`-related
      entries belong to ticket 002; nothing in `pyproject.toml`
      currently references `codex.py`/`copilot.py` by path).
- [x] Full suite passes with the deletion in place — this is the
      concrete evidence that nothing live still depended on the
      archived code.
      Full suite is the sprint's single close-time gate (per
      `.claude/rules/source-code.md`), run once by the team-lead at
      `close_sprint`, not per-ticket. This ticket's scoped run (566
      tests across the 9 files named in the Testing Plan) and the
      broader `-k "init or uninstall or platform or hook_handlers or
      plan_to_issue"` sweep (620 tests) both pass; `pytest tests/
      --collect-only` (3054 tests) confirms zero import errors anywhere
      in the tree from the deletions.

## Implementation Plan

### Approach

1. **Cut and verify the archive branch first, before any deletion.**
   ```
   git branch archive/codex-copilot-adapters
   git show archive/codex-copilot-adapters:src/clasi/platforms/codex.py | head -20
   git show archive/codex-copilot-adapters:src/clasi/platforms/copilot.py | head -20
   git push origin archive/codex-copilot-adapters
   ```
   If `git push` fails (no push access to `origin` from this
   environment), STOP and report — per this sprint's Design Rationale
   Open Question 1, this is a case where the ticket cannot self-resolve
   push authority; report status to team-lead rather than proceeding
   with an unpushed, only-locally-recoverable archive.
2. **Find every Codex/Copilot touch point before deleting anything.**
   Re-run the grep this planning pass used as a starting point, not a
   final list:
   ```
   grep -rln "codex\|copilot" src/clasi --include='*.py' | grep -v /clasr
   grep -rln "codex\|copilot" tests --include='*.py' | grep -v 'tests/clasr\|tests/e2e'
   ```
   Read each hit and classify: (a) delete the whole file (`codex.py`,
   `copilot.py`, their unit tests), (b) remove a Codex/Copilot-specific
   branch/flag/field but keep the file (`cli.py`, `init_command.py`,
   `uninstall_command.py`, `detect.py`, `_rules.py`, `plan_to_issue.py`,
   `skill_resolve.py`, `hook_handlers.py`), (c) no change needed
   (verify before assuming — e.g. `__init__.py`'s hit may just be an
   `__all__` re-export).
3. **Delete the two adapter files and their dedicated tests.**
4. **Trim every (b)-classified file.** For `cli.py`: decide whether to
   remove `--codex`/`--copilot` `click.option`s outright (cleaner, but
   an existing invocation with the flag becomes "no such option" —
   Click's own error, reasonably clear) or keep the flags accepting the
   value but branch to a clear archived-message error inside `init`/
   `uninstall` (more explicit, slightly more code). Either satisfies
   the backward-compatibility acceptance criterion above; pick one and
   be consistent between `init` and `uninstall`.
5. **Run the full suite.** Fix any import errors or now-orphaned
   fixtures the deletion surfaces — these are expected in files under
   (b) that this ticket's file-by-file audit missed on the first pass.
6. **Update `platforms/DESIGN.md`.** This sprint's `design/`
   overlay already contains the edited copy
   (`clasi/sprints/032-.../design/platforms-DESIGN.md`) describing the
   post-archival state — this ticket's job is to make the *code* match
   what that overlay already says, not to re-author the doc. The
   overlay is applied to the canonical `src/clasi/platforms/DESIGN.md`
   location at sprint close (per the design-doc-set's close-time apply
   step), so no direct edit to the canonical file is needed here.

### Files to Modify

- **Delete**: `src/clasi/platforms/codex.py`, `src/clasi/platforms/copilot.py`,
  `tests/unit/test_platform_codex.py`, `tests/unit/test_platform_copilot.py`.
- **Trim (verify scope by reading first)**: `tests/unit/test_three_platform_install.py`
  (may need full deletion, not just trimming, if nothing survives
  without three platforms), `src/clasi/cli.py`, `src/clasi/init_command.py`,
  `src/clasi/uninstall_command.py`, `src/clasi/plan_to_issue.py`,
  `src/clasi/skill_resolve.py`, `src/clasi/hook_handlers.py`,
  `src/clasi/platforms/detect.py`, `src/clasi/platforms/_rules.py`
  (comment only), `src/clasi/__init__.py` (verify what the grep hit
  actually is), `tests/unit/test_init_command.py`, `tests/unit/test_platform_detect.py`,
  `tests/unit/test_cli_init.py`, `tests/unit/test_uninstall_command.py`,
  `tests/unit/test_plan_to_issue.py`, `tests/unit/test_hook_handlers.py`,
  `tests/unit/test_init_interactive.py`, `tests/unit/test_markers.py`
  (verify — may only reference "codex"/"copilot" as example platform
  names in a doc string or parametrize id, not real logic).
- **No change** (do not touch): `src/clasi/platforms/claude.py`
  (content unchanged by this ticket — its merge-not-overwrite fixes are
  ticket 004's job), `src/clasi/platforms/_links.py`, `_markers.py`
  (only `_rules.py` needed a comment fix per the grep).

### Testing Plan

- **Existing tests to run** (scoped, per `.claude/rules/source-code.md`):
  `uv run pytest tests/unit/test_init_command.py tests/unit/test_platform_detect.py
  tests/unit/test_cli_init.py tests/unit/test_uninstall_command.py
  tests/unit/test_plan_to_issue.py tests/unit/test_hook_handlers.py
  tests/unit/test_init_interactive.py tests/unit/test_markers.py
  tests/unit/test_platform_claude.py -v` — the full set of files this
  ticket's trim touches, plus `test_platform_claude.py` as a
  regression check that Claude's own adapter is unaffected.
- **New tests to write**: a regression test asserting `clasi init
  --codex` (or however the CLI is left after step 4 above) produces the
  clear archived-message error, not a stack trace; a regression test
  asserting `clasi init`/`uninstall` with no platform flag still
  succeeds against Claude-only content.
- **Verification command**: `uv run pytest tests/unit/ -k "init or
  uninstall or platform or hook_handlers or plan_to_issue" -v` as a
  broader sweep before the sprint's one full-suite run at close.

### Documentation Updates

- `platforms/DESIGN.md`'s canonical location is updated via this
  sprint's `design/` overlay apply step at close, not directly by this
  ticket (see Approach step 6).
- If this ticket finds any `README.md`/CLI `--help` text mentioning
  Codex/Copilot support that this planning pass's grep didn't catch
  (the grep covered `.py` files only), update or remove it.

## Process Notes

- Guards fail closed. If a role-guard or mcp-guard block is hit while
  working this ticket, **STOP and report it** — do not route around it
  with a Bash heredoc, `sed -i`, `git apply`, or any other mechanism
  that reaches a file without going through the blocked call. Reporting
  a block is a successful outcome of this ticket's work, not a failure.
- Tier-2 (in-progress-ticket) write scope covers this ticket's own file
  under the locked sprint's `tickets/` tree for status/frontmatter
  updates, plus the source/test files named above under `src/` and
  `tests/` (both are `protected_paths`, gated on having this ticket
  `in-progress`).
- This is the layer-trap sprint (see sprint.md's dispatch context): if
  any doc edit touches a path that has a separately-tracked installed
  copy (`.agents/skills/*/SKILL.md` vs `src/clasi/plugin/skills/*/SKILL.md`,
  `.claude/agents/*/agent.md`, `.claude/rules/*.md` vs
  `src/clasi/platforms/_rules.py`), check whether this ticket's changes
  touch any such pair — for this ticket specifically, `_rules.py`'s
  comment fix has no installed-copy counterpart (comments aren't
  rendered into installed rule bodies), so this is not expected to
  apply here, but verify rather than assume.
