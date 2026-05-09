---
id: "B"
title: "Architecture as forcing-function delta spec at sprint planning"
status: planning
branch: sprint/B-architecture-as-delta-spec
use-cases: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint B: Architecture as forcing-function delta spec at sprint planning

## Goals

Make the per-sprint architecture artifact a **structured planning contract** authored at the front of sprint planning, in OpenSpec-style ADDED/MODIFIED/REMOVED/RENAMED format, validated by a parser, and merged into source-of-truth docs at sprint close.

This combines two TODOs:
- `delta-specs-for-brownfield-architecture-changes` — supplies the format, parser, merger.
- `sprint-process-changes` (architecture-positioning half only) — supplies the timing change. The exception-cord half of that TODO is split into Sprint C.

## Problem

CLASI today writes a free-prose `architecture-update.md` at sprint **end**, as a recording artifact. That position has no forcing function and produces drift:

1. The canonical `docs/design/specification.md` falls out of sync because nothing forces a merge.
2. "We changed X" prose is unverifiable — the architecture-reviewer agent reads narrative and guesses what "changed" means.
3. By the time the doc is written, the implementation has already happened, so the doc describes drift instead of committing to intent.

OpenSpec's delta format (ADDED / MODIFIED / REMOVED / RENAMED, four-hash item rule, MUST-include-full-content for MODIFIED) makes the artifact parseable and merge-friendly. Authoring at the **front** of sprint planning makes it the structural plan, with the diff between successive deltas serving as the sprint's contract.

## Solution

1. **Build the delta machinery** — `clasi/delta/parse.py`, `merge.py`, `model.py` (pydantic types). Pure, IO-free parsing; merging takes a parsed delta + path to source-of-truth doc and returns rewritten content.
2. **Move architecture-update.md to architecture-delta.md** — same per-sprint location (`<sprint>/architecture-delta.md`), new format. Replace the existing `architecture-update.md` template with a delta template.
3. **Reposition architecture-delta in the sprint flow** — new planning order:
   1. Sprint overview (`sprint.md`)
   2. Use cases (`usecases.md`)
   3. Architecture delta (`architecture-delta.md`) ← **new position**
   4. Tickets (derived from the above)
4. **Validate-on-write hook** — PostToolUse hook runs the parser when `architecture-delta.md` is saved; surfaces validation errors immediately, doesn't block.
5. **architecture-review skill becomes parser-first** — load the delta, validate it, then review the content. Deltas that fail to parse are rejected before semantic review begins.
6. **architecture-authoring skill** gains a delta mode — produces deltas conforming to the format spec.
7. **Merge into source-of-truth at close-sprint** — close-sprint additionally parses the delta, applies ADDED/MODIFIED/REMOVED/RENAMED to `docs/design/specification.md` and `docs/design/usecases.md`, commits the result. Behind a feature flag for one release.
8. **Remove the flag** once one release ships clean.

## Success Criteria

- `clasi/delta/` package exists with full unit-test coverage of every parser rejection branch (missing kind, wrong kind, items outside sections, MODIFIED with no body, malformed RENAMED, duplicate identities) and merger rejection branch (ADDED-already-exists, MODIFIED-doesn't-exist, REMOVED-doesn't-exist, RENAMED-collision).
- `clasi sprint validate-delta <id>` CLI subcommand exists and runs.
- New sprints created via `create_sprint` produce an `architecture-delta.md` (not `architecture-update.md`) at the planning stage.
- The phase machine recognizes architecture-delta as a planning artifact, not a ticketing artifact.
- `architecture-review` skill body documents the parser-first flow.
- `close-sprint` merges deltas into `docs/design/specification.md` and `docs/design/usecases.md`. Verified end-to-end on a synthetic sprint.
- The two-diff property holds: a sprint's delta at planning is the plan; the post-implementation `git diff` of source-of-truth docs is the verification.

## Scope

### In Scope

- Delta parser, validator, merger.
- Delta template at `clasi/templates/architecture-delta.md`.
- Phase-machine reordering (architecture-delta authored at planning).
- `architecture-authoring` and `architecture-review` skill updates.
- `close-sprint` merge step.
- Validate-on-write PostToolUse hook.
- One open question to resolve as part of planning: scenario identity (use scenario titles as identity vs per-scenario IDs). Default to titles unless a counter-argument surfaces during ticketing.
- One open question to resolve as part of planning: BDD Given/When/Then for new scenarios; existing scenarios stay until MODIFIED. Default: yes.

### Out of Scope

- Specification-doc deltas day 1 — start with architecture and use-cases. Specification deltas land in a follow-on sprint once format proves out.
- Skills/rules as delta categories — deltas cover architecture, use-cases, specification only. Skills/rules are out of the doc-of-record story.
- 3-way merge for parallel sprints — serial-only execution today; defer until parallelism is reintroduced.
- Diff viewer / GUI.
- Backfill of historical sprints into delta format — done sprints stay as `architecture-update.md`.
- The exception-cord protocol from `sprint-process-changes` — that is Sprint C.

## Test Strategy

- Pure-function unit tests for parser and merger; every rejection branch has a test.
- Integration test: synthetic sprint with deltas → close-sprint → verify source-of-truth docs reflect the delta exactly.
- Snapshot tests for the delta template rendering.
- The validate-on-write hook is exercised by a hook-handler test; verify it surfaces errors without blocking writes.

## Architecture impact

A new `clasi/delta/` package becomes the canonical location for architectural-document mutation logic. The phase machine's notion of "what artifact belongs at what phase" gains a single new entry. `close-sprint`'s contract grows by one step (merge deltas) but is otherwise unchanged.

## Dependencies / sequencing notes

- Sequence after Sprint A — Sprint A pins paths to `.clasi/`, so the delta file's location is stable when this work begins.
- Sequence before Sprint D — schema-driven workflow declares `architecture-delta` as one of its declared artifacts; landing the format first lets the schema slot it in cleanly without one-off integration.
- Independent of Sprints C, E, F.

## Source TODOs to be archived as superseded by this sprint

- `delta-specs-for-brownfield-architecture-changes.md` (entire)
- `sprint-process-changes.md` (architecture-positioning half only; exception-cord half goes to Sprint C)
