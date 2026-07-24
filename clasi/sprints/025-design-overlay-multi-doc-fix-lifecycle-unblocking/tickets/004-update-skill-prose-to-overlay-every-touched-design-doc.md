---
id: '004'
title: Update skill prose to overlay every touched design doc
status: in-progress
use-cases:
- SUC-001
depends-on:
- '001'
- '002'
github-issue: ''
issue: design-overlay-cannot-seed-multiple-colocated-design-md-per-sprint.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update skill prose to overlay every touched design doc

## Description

**Scope note from architecture review**: verifying this touchpoint
against the actual plugin-source skill files during planning found
that `src/clasi/plugin/skills/architecture-authoring/SKILL.md` (Mode
2a, Step 2, ~L132-138) and `src/clasi/plugin/skills/plan-sprint/SKILL.md`
already describe the *aspirational* multi-doc behavior — e.g.
"`doc_names` ... note that `DESIGN.md` is not a unique name across
subsystems; the seed step records each seeded file's full canonical
source path in the ... manifest so `apply` can resolve it back to the
right subsystem later, even when multiple overlay files share the
`DESIGN.md` basename." No "can only overlay one" or "flat-overlay-slot"
workaround language was found in this repo's plugin-source skill files
— that framing (from the issue's evidence) belongs to a downstream
consumer project's sprint notes describing the tool's actual broken
behavior, not to this repo's own skill prose. So this ticket's real
work is narrower than the issue file implies: confirm each skill's
prose is accurate now that tickets 001-002 make the tool match what
was already documented, tighten any wording that undersells what's now
guaranteed (e.g. the docstring-matching claims), and add an explicit
instruction to seed *every* touched canonical doc in a single
`seed_sprint_design_overlay` call (not one call per doc) if that is not
already stated as clearly as it could be. Check `bootstrap-design`'s
`SKILL.md` too, even though no overlay-workaround language was found
there in an initial scan.

Depends on tickets 001-002: prose should describe behavior that
actually exists once those land, not aspirational behavior alone.

## Acceptance Criteria

- [x] `plan-sprint`, `architecture-authoring`, and `bootstrap-design`
      skill prose in `src/clasi/plugin/skills/` reviewed against the
      now-fixed tool behavior (tickets 001-002); any claim that no
      longer matches (e.g., a docstring quote or described accepted
      form) is corrected.
- [x] Prose explicitly instructs seeding every canonical doc the sprint
      touches in one `seed_sprint_design_overlay(sprint_id, doc_names)`
      call, not one doc at a time or one-doc-only.
- [x] No prose in any of the three skill files tells the reader a
      sprint "can only overlay one" doc or describes a "flat-overlay-slot"
      single-doc workaround as the expected path.
- [x] Confirm (do not just assume) whether the installed
      `.claude/skills/` copies of these three skills need the same
      correction, or whether they are generated/synced from
      `src/clasi/plugin/skills/` at install time — fix both locations
      if they are hand-maintained separately, or note the sync
      mechanism if not.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit tests/integration
  tests/system -k "skill or plugin"`
- **New tests to write**: none expected (prose-only change); if the
  repo has any test asserting skill-file content (e.g. a "no stale
  workaround language" grep-based test), extend it to cover the new
  wording instead of adding a new test file.
- **Verification command**: `uv run pytest tests/unit tests/integration
  tests/system`
