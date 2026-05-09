---
status: pending
---

# Delta specs for brownfield architecture changes

Replace the free-prose `architecture-update.md` produced per sprint
with structured **delta specs** modeled on OpenSpec's ADDED /
MODIFIED / REMOVED / RENAMED format. Architecture and use-case docs
gain a machine-checkable contract about what each sprint changes,
and at sprint close the deltas merge into the source-of-truth
documents.

## Why we cared

CLASI's brownfield model today is:

- One canonical `docs/design/specification.md`,
  `docs/design/usecases.md`, etc., authored at project init and
  amended by hand thereafter.
- Per-sprint
  `docs/clasi/sprints/<id>/architecture-update.md` files written
  free-prose by the architect agent, narrating "in this sprint we
  changed X, added Y, removed Z."
- At sprint close, no formal merge step. The architecture-update
  becomes historical record; the canonical spec is updated by hand
  if at all.

Two failure modes recur:

1. **Drift.** Three sprints in, the canonical specification
   document doesn't reflect the current architecture, because
   nothing forces a merge of architecture-update content back into
   it. The sprints' update docs are the only accurate record, and
   they're scattered.
2. **Unverifiable changes.** An architecture-update can say "we
   removed the FooBar service" with no parseable assertion of what
   "remove" means. The architecture-reviewer agent reads prose and
   makes its best guess. Same for "we modified the auth flow" —
   modified how? Compared to what?

OpenSpec solved this with a delta format that's both human-readable
and parseable: requirements grouped under ADDED / MODIFIED / REMOVED
/ RENAMED headings, scenarios marked with a strict `#### Scenario:`
rule, and an "MUST include full updated content for MODIFIED" rule
so a diff is reconstructable. At archive time, deltas merge into
the source-of-truth specs.

This TODO ports that format to CLASI's architecture and use-case
artifacts.

## Format spec

Per-sprint delta lives at
`docs/clasi/sprints/<id>/architecture-delta.md`. Replaces
`architecture-update.md` going forward.

Three top-level sections: `## Architecture`, `## Use cases`,
`## Specification`. Each section contains delta-typed subsections.

```markdown
## Architecture

### ADDED Components

#### Component: ScheduleService
A new service responsible for cron-style scheduled task execution.

**Responsibilities:**
- Owns the scheduled-task table.
- Dispatches due tasks to the worker pool.

**Interfaces:** `create_task(spec)`, `list_due()`, `mark_complete(id)`.

### MODIFIED Components

#### Component: WorkerPool
**Full updated content** (MODIFIED entries replace, not patch):

The WorkerPool now accepts both interactive dispatches (existing)
and scheduled dispatches (new in this sprint). Dispatch source is
recorded in the dispatch_log.

**Interfaces:** `dispatch(brief, source: Literal["interactive",
"scheduled"])`.

### REMOVED Components

#### Component: LegacyCronShim
Replaced by ScheduleService. No callers remain after sprint 015
ticket 003.

### RENAMED Components

#### Component: TaskQueue → DispatchQueue
Naming alignment with the rest of the dispatch vocabulary. No
behavioural change.

## Use cases

### ADDED Scenarios

#### Scenario: User schedules a recurring report
- Given: a user with a saved report definition
- When: they invoke `/schedule weekly` on the report
- Then: a ScheduleService entry is created with cron `0 9 * * 1`

### MODIFIED Scenarios

#### Scenario: Worker dispatches a brief
**Full updated content:** [the entire revised scenario]

## Specification

### MODIFIED Requirements

#### Requirement: REQ-014 Dispatch logging
**Full updated content:** Every dispatch records source, brief
hash, target subagent, and start/end timestamps to dispatch_log.
```

Hard rules — these are what make it parseable:

- **Section heading is exactly `### <KIND> <Category>`** where KIND
  is one of `ADDED`, `MODIFIED`, `REMOVED`, `RENAMED` and Category
  is `Components`, `Scenarios`, `Requirements`. Other text breaks
  the parser.
- **Item heading is exactly four hashes** (`#### Component:`,
  `#### Scenario:`, `#### Requirement:`). This is OpenSpec's
  "4-hashtag scenario rule." Anything else is body text.
- **MODIFIED entries MUST include the full updated content** of
  the item, not a diff. The merger at archive time replaces the
  source-of-truth entry with this content verbatim.
- **REMOVED entries** state the item identity and a reason. No
  body required.
- **RENAMED entries** are `#### Component: OldName → NewName`
  with optional body.

A delta file is valid only if every `####` heading sits inside an
`### <KIND> <Category>` section. Validation is a
`clasi sprint validate-delta <id>` CLI subcommand.

## Merge at sprint close

Today `close-sprint` moves the sprint dir to `done/`. After this
TODO lands, `close-sprint` additionally:

1. Parses `architecture-delta.md`.
2. For each ADDED entry: appends to the matching source-of-truth
   doc.
3. For each MODIFIED entry: replaces the matching item in the
   source-of-truth doc with the delta's full content.
4. For each REMOVED entry: removes the matching item from the
   source-of-truth doc.
5. For each RENAMED entry: rewrites the heading and updates
   cross-references.
6. Writes the resulting source-of-truth doc back. Commits it as
   part of the sprint's close commit.

The delta file stays in `sprints/done/<id>/` as historical record.
The source-of-truth doc stays current.

## What gets stricter for the architect agent

`architecture-authoring` skill (existing) gains a new mode: when
producing a delta for an existing project (vs. greenfield
specification authoring), output must conform to the format above.
The skill body documents the format, names the four KINDs, and
forbids prose that isn't inside a delta section.

`architecture-review` skill (existing) gains a parser-first step:
load the delta, validate it, *then* review the content. A delta
that fails to parse is rejected before semantic review begins —
the reviewer doesn't have to chase free-prose ambiguity.

## Module layout

```
clasi/
  delta/
    __init__.py
    parse.py                  ← parser + validation errors
    merge.py                  ← apply deltas to source-of-truth docs
    model.py                  ← pydantic types: Delta, AddedItem,
                                ModifiedItem, RemovedItem, RenamedItem
  schemas/
    se-process/
      delta-template.md       ← skeleton with section headings filled
                                in but bodies empty
tests/delta/
  test_parse.py
  test_merge.py
  test_invalid_deltas.py      ← every rejection mode has a test
```

Parsing is pure (no IO, no state). Merging takes a parsed delta and
the path to a source-of-truth doc; returns the rewritten content.
Both layers tested independently.

## Migration sequence

1. **Parser + validator** with full test battery. No callers yet.
2. **Merger** with tests against synthetic source-of-truth docs.
3. **Delta template** in `clasi/schemas/se-process/delta-template.md`.
   `architecture-authoring` skill points new sprints at it.
4. **Validate-on-write hook.** A PostToolUse hook runs the parser
   when `architecture-delta.md` is saved; surfaces validation
   errors immediately, doesn't block the write.
5. **`architecture-review` agent uses the parser.** Reviewer rejects
   deltas that don't parse cleanly with a specific error message;
   author fixes and re-saves.
6. **Wire merge into close-sprint.** Behind a feature flag for one
   release. Verify on a real project that the merged source-of-
   truth docs read sensibly.
7. **Remove the flag.** Architecture-update.md is deprecated; delta
   format becomes the only path.

## Validation

- Parser rejects: missing section headings, wrong KIND, items not
  under a section, MODIFIED with no body, malformed RENAMED
  (missing `→`), duplicate item identities within one delta.
- Merger rejects: ADDED entry where item already exists, MODIFIED
  entry where item doesn't exist, REMOVED entry where item doesn't
  exist, RENAMED where new name collides.
- Tests cover every rejection branch.

## Open questions

- **Item identity.** Components have names; scenarios less so.
  OpenSpec uses scenario titles as identity, which means renaming
  a scenario forces a RENAMED entry. Acceptable? Suggest: yes,
  because the alternative is per-scenario IDs which the architect
  agent would have to manage.
- **Use-case scenarios with Given/When/Then formatting.** Today's
  use-cases doc isn't in BDD format. Either we adopt Given/When/
  Then for new scenarios (consistent with the OpenSpec example
  here) or we define a CLASI-specific scenario shape. Suggest:
  Given/When/Then for new sprints; existing scenarios stay as
  written until they're MODIFIED, at which point the delta brings
  them to the new shape.
- **Specification-doc deltas.** Do we want full delta support for
  `specification.md` from day one, or start with architecture-only
  and use-cases-only? Suggest: architecture and use-cases for v1;
  specification deltas added once the format proves out (it's the
  doc most likely to expose edge cases).
- **What about non-architectural sprint docs?** A sprint may
  introduce a new skill or rule. Those don't fit cleanly into
  ADDED Components. Either model "skills" and "rules" as their own
  delta categories or accept that this format covers architecture +
  use cases + spec, not the entire sprint. Suggest: the latter; the
  delta's job is doc-of-record updates, not an enumeration of every
  artefact the sprint touched.
- **Merge conflicts on overlapping deltas.** Two parallel sprints
  both MODIFY the same component. Today's serial-execution policy
  prevents this. If parallel sprints come back, we need a real
  3-way merge. Defer until parallelism does.

## Out of scope

- A diff viewer that visualises the delta against the source-of-
  truth doc. Useful eventually; a manual `git diff` of the
  rewritten doc covers the v1 review case.
- Automatic backfill of historical sprints into delta format.
  Existing `architecture-update.md` files stay as-is. New sprints
  use the new format.
- Cross-spec deltas (e.g. an architecture change implying a
  use-case change). Each delta section is independent; the
  architect-author chooses which sections to populate.

## Related work

The schema-driven-workflow TODO (suggestion #1) declares the
artifacts the SE process produces. `architecture-delta` becomes one
of those artifacts in the schema, with `requires: [sprint-plan]`
and a gate that runs the validator. The two TODOs compose; either
can land first, but landing schema-driven workflow first means the
delta artifact slots in cleanly without a one-off integration.

## Origin

Comparative analysis of CLASI vs github/spec-kit vs Fission-AI/
OpenSpec, 2026-05-07
(`clasi-spec-kit-openspec-analysis.md`). Suggestion #3, ranked
third: "if three changes: add delta specs — that gets CLASI
brownfield-honest in a way none of its current artifacts are." The
4-hashtag rule and "MUST include full updated content for MODIFIED"
are lifted directly from the OpenSpec format study in that
analysis.
