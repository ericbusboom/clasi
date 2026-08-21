---
id: '004'
title: Fix installers to merge, not overwrite (.mcp.json, CLAUDE.md, hooks, rules,
  migrate)
status: open
use-cases: ["SUC-001"]
depends-on: ["001"]
github-issue: ''
issue:
- installers-must-merge-not-overwrite.md
- clasi-init-reverts-this-repos-own-mcp-config-to-the-consumer-default.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix installers to merge, not overwrite (.mcp.json, CLAUDE.md, hooks, rules, migrate)

## Description

Combines two closely-related issues into one ticket (`installers-must-merge-not-overwrite.md`
and `clasi-init-reverts-this-repos-own-mcp-config-to-the-consumer-default.md`)
— the second is explicitly "the specific, previously-observed instance"
of the first's F1 finding, naming the same function and the same fix.
Fixing F1 once satisfies both issues' acceptance/verification sections;
see sprint.md's Design Rationale for why these were combined rather
than ticketed twice.

Four destructive installer behaviors, verified against the live code
during planning, share one root cause — write-wholesale instead of
merge-or-compare:

1. **`.mcp.json` reverts this repo's own dogfooding config.**
   `init_command.py`'s `_detect_mcp_command(target)` (`del target`s its
   only argument) always returns `{"command": "clasi", "args": ["mcp"]}`.
   In this repo, whose committed `.mcp.json` carries `uv run clasi mcp`,
   every `clasi init`/`migrate` silently reverts it — this is the
   2026-07-16 incident: the next MCP session connected to a stale pipx
   build missing nine tools.
2. **`clasi uninstall` deletes the whole CLAUDE.md.** Verified:
   `platforms/claude.py`'s uninstall path calls
   `_links.unlink_alias(target / "CLAUDE.md")` for CLAUDE.md, but
   `strip_section(target / "AGENTS.md")` two lines later for AGENTS.md
   — an exact asymmetry. CLAUDE.md is written as a regular file holding
   a marker block specifically so other tools can manage their own
   blocks in the same file (per `_write_claude_md`'s own docstring);
   uninstall currently destroys all of it, not just CLASI's block.
3. **`clasi init` clobbers user hooks.** `claude.py`'s hooks-install
   step does `settings["hooks"] = new_hooks` — a wholesale replace of
   the entire hooks object in `.claude/settings.json`, silently
   deleting any user-defined hook on every `clasi init`.
4. **`_create_rules` always writes, contradicting its own docstring.**
   Verified: the docstring says "Idempotent: compares content before
   writing and skips unchanged files"; the function body loops over
   `RULES.items()` and unconditionally calls `path.write_text(content)`
   plus `echo "Wrote: ..."` for every file, every time. Combined with
   (1), local rule edits are silently reverted on the next init.

A fifth related fix, from `04-cli-install-platforms.md` F11: `clasi
migrate`'s `run_migrate` always finishes with `run_init(target,
claude=True)` (verified: `migrate_command.py`'s tail), force-installing
Claude even on a Codex-only-installed repo.

**Scoped down from the original issue by ticket 001**: the installers
issue's F4 ("multi-platform install stomps resolved skills," fixed via
"one shared canonical-skill writer used by all three installers")
required a second/third installer to exist to reproduce — ticket 001
archives Codex/Copilot, leaving only `claude.py` in master. Building a
three-way shared-writer abstraction for a scenario that can no longer
occur in master is speculative generality this ticket deliberately does
not add (see sprint.md's Design Rationale, "Decision: drop F4's
three-way shared canonical-skill writer requirement"). This ticket
**depends on ticket 001** landing first for exactly this reason — do
not start this ticket until 001 is done.

## Acceptance Criteria

- [ ] `.mcp.json`: if a `clasi` server entry already exists in any
      form, `_update_mcp_json`/`_detect_mcp_command` leave it untouched
      rather than unconditionally overwriting it with the consumer
      default. A regression test runs `clasi init` against a checkout
      carrying the `uv run clasi mcp` form and asserts it survives.
- [ ] A separate regression test runs `clasi init` against a scratch
      project with no `uv` and no `[project]` table in `pyproject.toml`
      and asserts the bare `{"command": "clasi", "args": ["mcp"]}`
      default is still produced — the consumer-project rationale from
      `_detect_mcp_command`'s original docstring must still hold.
- [ ] `clasi uninstall --claude` strips only CLASI's marker block from
      CLAUDE.md via `strip_section`, matching what AGENTS.md's
      uninstall path already does correctly — not
      `_links.unlink_alias`. A regression test asserts other-tool
      content in CLAUDE.md (content outside CLASI's marker block)
      survives `clasi uninstall`.
- [ ] `clasi init`'s hooks-install step merges per event type — only
      hook entries identifiable as CLASI's (command starts with `clasi
      hook`) are added/replaced; any other entry under the same event
      key is left in place. A regression test asserts a user-defined
      hook (any event, non-`clasi hook` command) survives `clasi init`.
- [ ] `_create_rules` compares each rule file's existing on-disk content
      against the canonical body before writing, and skips (no write,
      no "Wrote:" echo) when they already match — matching its own
      docstring's existing claim.
- [ ] `clasi migrate`'s `run_migrate` refreshes only currently-installed
      platforms (as of this ticket, effectively "Claude, if `.claude/`
      exists" — Codex/Copilot are gone per ticket 001) instead of
      unconditionally calling `run_init(target, claude=True)`.
- [ ] After this ticket, `get_version()`/the running MCP server in this
      repo reflects the working tree's version with the `stale` field
      present following a `clasi init` — confirms the dogfood config
      survived end-to-end, not just in the `.mcp.json` file content
      (this is `clasi-init-reverts...`'s own third verification
      criterion; check it manually if a fully-automated check isn't
      practical within this ticket's scope, and say so explicitly
      rather than silently skipping it).
- [ ] Full suite passes.

## Implementation Plan

### Approach

1. Fix `_detect_mcp_command`/`_update_mcp_json` first (highest-impact,
   the one with a real historical incident). Two viable approaches per
   the standalone issue's own "Proposed fix" section, in preference
   order: (a) detect the dogfooding case (target repo has
   `pyproject.toml` with `name = "clasi"`, or `src/clasi/mcp_server.py`
   exists) and return the `uv run` form for it; (b) never overwrite a
   *differing* existing entry, regardless of whether it's recognized as
   "this repo." The issue recommends doing both — (a) fixes the known
   case precisely, (b) protects any customized config generally. Prefer
   both if the implementation cost is low; if only one fits the
   ticket's time budget, prefer (b) since it's the more general
   guarantee this ticket's acceptance criteria are actually testing.
2. Fix CLAUDE.md uninstall: swap `_links.unlink_alias(target /
   "CLAUDE.md")` for `strip_section(target / "CLAUDE.md")`, mirroring
   the AGENTS.md line immediately below it.
3. Fix hooks merge: read existing `settings.json`'s `hooks` object,
   merge new CLASI entries per event type instead of replacing the
   whole object. Identify "CLASI's" entries by command prefix (`clasi
   hook`), per the issue's own fix direction.
4. Fix `_create_rules`: read each target file's existing content (if
   present) before writing; skip the write when it matches the
   canonical body exactly.
5. Fix `migrate_command.py`'s `run_migrate` tail: detect which
   platform(s) are actually installed (check for `.claude/`,
   post-ticket-001 the only platform directory that can exist) and call
   `run_init` only for those, instead of hardcoding `claude=True`.
6. Add the four/five regression tests named in Acceptance Criteria.
7. Run the full suite; then, if practical within this environment,
   manually verify the end-to-end `get_version()` staleness check in
   this actual repo after a real `clasi init` run (the sixth acceptance
   criterion) — this is the one criterion that validates the fix
   against the very incident that motivated it, not just against a
   scratch fixture.

### Files to Modify

- `src/clasi/init_command.py` (`_detect_mcp_command`, `_update_mcp_json`)
- `src/clasi/platforms/claude.py` (CLAUDE.md uninstall path, hooks
  merge, `_create_rules`)
- `src/clasi/migrate_command.py` (`run_migrate`'s platform-refresh tail)
- Test files: `tests/unit/test_init_command.py`,
  `tests/unit/test_platform_claude.py`,
  `tests/unit/test_uninstall_command.py` (or wherever CLAUDE.md
  uninstall is currently tested — verify exact file),
  `tests/unit/test_migrate_command.py` (verify exact filename)

### Testing Plan

- **Existing tests to run**: `uv run pytest tests/unit/test_init_command.py
  tests/unit/test_platform_claude.py tests/unit/test_uninstall_command.py
  tests/unit/test_cli_init.py -v` — the installer-adjacent unit tests
  this ticket's changes touch most directly. Add the migrate test file
  once its exact name is confirmed.
- **New tests to write**: the five regression tests named in Acceptance
  Criteria (dogfood-config survives, scratch-consumer default still
  bare, other-tool CLAUDE.md content survives uninstall, user hooks
  survive init, migrate refreshes only installed platforms).
- **Verification command**: `uv run pytest tests/unit/ -k "init or
  uninstall or migrate or platform_claude" -v`

### Documentation Updates

- `platforms/DESIGN.md`'s canonical location already has this sprint's
  overlay-edited content describing the merge-not-overwrite invariant
  (Section 3's new bullet, `design/platforms-DESIGN.md` in this
  sprint's directory) — applied at sprint close, no direct edit needed
  by this ticket.
- If `_create_rules`'s docstring itself needs wording adjustment beyond
  "now actually does what it already claimed," update it; otherwise
  leave it (it was already correct in intent, just not in
  implementation).

## Process Notes

- Guards fail closed. If a role-guard or mcp-guard block is hit while
  working this ticket, **STOP and report it** — do not route around it.
  Reporting a block is a successful outcome of this ticket's work, not
  a failure.
- Tier-2 (in-progress-ticket) write scope covers this ticket's own file
  under the locked sprint's `tickets/` tree, plus `src/` and `tests/`.
- **Do not start this ticket before ticket 001 is `done`.** If you find
  yourself starting this ticket and ticket 001 is still `open` or
  `in-progress`, stop and report to team-lead rather than proceeding
  out of dependency order — this ticket's F4 scope-reduction reasoning
  assumes 001's archival has already landed.
