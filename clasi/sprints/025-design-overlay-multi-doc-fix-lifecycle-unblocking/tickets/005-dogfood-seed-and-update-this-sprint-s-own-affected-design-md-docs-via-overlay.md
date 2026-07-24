---
id: '005'
title: 'Dogfood: seed and update this sprint''s own affected DESIGN.md docs via overlay'
status: exception
use-cases:
- SUC-001
- SUC-002
depends-on:
- '001'
- '002'
- '003'
- '004'
github-issue: ''
issue: design-overlay-cannot-seed-multiple-colocated-design-md-per-sprint.md
completes_issue: true
exception:
  thrown_by: programmer
  thrown_at: '2026-07-24T17:48:07.476683+00:00'
  attempted: "Confirmed the sprint's design/ overlay directory does not yet exist\
    \ (clean seed, no stale reconciliation needed) and read all three canonical DESIGN.md\
    \ docs plus tickets 001/002's actual diffs to know precisely what to edit. Called\
    \ seed_sprint_design_overlay(\"025\", [\"src/clasi/DESIGN.md\", \"src/clasi/design/DESIGN.md\"\
    , \"src/clasi/tools/DESIGN.md\"]) exactly per the ticket's specified form. It\
    \ failed: FileNotFoundError on '.../docs/design/src/clasi/DESIGN.md' \u2014 i.e.\
    \ the live MCP connection resolved the co-located path as a bare filename relative\
    \ to docs/design/, which is the PRE-ticket-001 behavior (ticket 001's _resolve_overlay_doc_path\
    \ adds the '/' in doc_name path-separator branch that should have taken this path\
    \ to project.root instead). Verified via `ps` that this session's live `clasi\
    \ mcp` server processes (PIDs 96707/96719/96862/96866/97549/97556, all under .venv/bin/clasi\
    \ mcp per .mcp.json's `uv run clasi mcp`) started Thu Jul 23 13:13-13:14 \u2014\
    \ hours before ticket 001 (commit bce0e8d, 22:07) and ticket 002 (commit 826a768,\
    \ 22:26) landed today. Confirmed via direct venv-python import that the ON-DISK\
    \ src/clasi/tools/artifact_tools.py DOES have the correct post-fix _resolve_overlay_doc_path\
    \ (path-separator branch present, matches ticket 001's diff exactly) \u2014 so\
    \ the code is correct and untouched by me; only the long-lived in-memory server\
    \ process is stale. get_version() reports stale=false because clasi.staleness.check_staleness\
    \ only compares version strings (running __version__ vs importlib.metadata version),\
    \ and this sprint has made no version bump yet (bump is deferred to close_sprint\
    \ per current cadence) \u2014 so a version-string comparison cannot detect that\
    \ the running process's imported module state predates today's commits to the\
    \ same version. Checked for an alternate call path: no CLI wrapper exists for\
    \ seed_sprint_design_overlay (clasi tool --help / clasi design --help enumerate\
    \ no such command) as MCP-and-CLI-parity does for validate_design/clasi design\
    \ validate, so there is no way to invoke fixed code without going through the\
    \ stale MCP tool call."
  conflict: "Use-case boundary: this ticket is scoped as a pure consumer of the already-fixed\
    \ seed_sprint_design_overlay tool (sprint.md's \"Design-Overlay Dogfooding Decision\"\
    \ and the ticket's own framing: \"dogfoods the fix rather than working around\
    \ it\"); the hard constraints explicitly forbid touching the overlay machinery\
    \ source (artifact_tools.py/overlay.py/validator.py) and forbid hand-fabricating\
    \ the overlay outside the tool's own lifecycle. I cannot restart or reconnect\
    \ my own MCP client session (no session-management tool available to a leaf worker),\
    \ so I cannot make the live tool call reflect the on-disk, already-correct ticket-001/002\
    \ code. Proceeding by hand-writing the three overlay files/slugs/_sources.json\
    \ manifest entries to simulate what seed_sprint_design_overlay would produce would\
    \ fabricate the very proof this ticket exists to provide (SUC-001: \"confirming\
    \ tickets 001-003's fix works on a real case, not just test fixtures\") and would\
    \ violate the ticket's own rejected-alternative note in sprint.md (\"editing the\
    \ three canonical DESIGN.md files directly... is exactly the workaround pattern\
    \ issue 1 is about eliminating\" \u2014 hand-faking the overlay artifacts is the\
    \ same workaround pattern one layer further in). This is a process/infrastructure\
    \ wall (stale long-lived MCP server process vs. a staleness check that only compares\
    \ version strings, with no version bump yet this sprint to trip it) that a leaf\
    \ worker has no tool to clear, not a hard implementation problem I can out-work."
  surface: internal
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Dogfood: seed and update this sprint's own affected DESIGN.md docs via overlay

## Description

This repo has `design_docs: enabled` and `sources: [src/clasi]`. This
sprint's own changes (tickets 001-002) touch canonical docs at
`src/clasi/DESIGN.md` (root), `src/clasi/design/DESIGN.md`, and
`src/clasi/tools/DESIGN.md` — three co-located docs, which is exactly
the multi-doc case this sprint exists to fix. Per sprint.md's
"Design-Overlay Dogfooding Decision," seeding this sprint's own overlay
was deliberately deferred until after the multi-doc fix lands (tickets
001-002), its regression test passes (ticket 003), and the skill prose
describing the seed call is current (ticket 004) — seeding earlier
would hit the very collision being repaired.

This ticket is the last one: call `seed_sprint_design_overlay("025",
["src/clasi/DESIGN.md", "src/clasi/design/DESIGN.md",
"src/clasi/tools/DESIGN.md"])` (exact `doc_names` form per ticket 001's
accepted-forms fix) in one call, confirm three distinct overlay files
and manifest entries result, edit each seeded copy to reflect this
sprint's actual changes (the slug/manifest additions to
`design/DESIGN.md`'s and `tools/DESIGN.md`'s described contracts, and
whatever the root `DESIGN.md` needs updated to reflect), generate
diffs, and validate.

This closes the sprint's own design-doc update obligation using the
sprint's own fix rather than editing the three canonical files directly
(the workaround pattern issue 1 exists to eliminate).

## Acceptance Criteria

- [ ] `seed_sprint_design_overlay` is called once for all three
      affected docs; the sprint's `design/` overlay directory contains
      three distinct files with three distinct `_sources.json` entries
      (no collision, confirming tickets 001-003's fix works on a real
      case, not just test fixtures).
- [ ] Each seeded copy is edited to reflect this sprint's actual
      changes to that doc's described contract.
- [ ] `generate_diffs` produces a `.diff.md` sibling for each edited
      file.
- [ ] `clasi design validate --overlay` (or `validate_design`) passes
      against the sprint's overlay directory.
- [ ] No canonical `DESIGN.md` file under `src/clasi/` is edited
      directly outside the overlay lifecycle as part of this sprint.
- [ ] `apply` is deferred to sprint close (per the standard overlay
      lifecycle — the overlay stays as edited copies until
      `review_sprint_pre_execution`/close applies it), not run early
      by this ticket.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit tests/integration
  tests/system -k "overlay or design"`
- **New tests to write**: none — this ticket exercises the machinery
  built and tested in tickets 001-003 against real docs; it is a
  dogfooding/documentation ticket, not a code ticket.
- **Verification command**: `uv run pytest tests/unit tests/integration
  tests/system`
