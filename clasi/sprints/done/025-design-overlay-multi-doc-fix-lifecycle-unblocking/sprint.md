---
id: '025'
title: Design-overlay multi-doc fix + lifecycle unblocking
status: closed
branch: sprint/025-design-overlay-multi-doc-fix-lifecycle-unblocking
worktree: false
use-cases: []
issues:
- design-overlay-cannot-seed-multiple-colocated-design-md-per-sprint.md
- norecursedirs-stale-e2e-project-breaks-bare-pytest-and-close-sprint.md
- team-lead-agent-doc-contradicts-mcp-guard-on-create-sprint.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 025: Design-overlay multi-doc fix + lifecycle unblocking

## Goal

Fix the design-overlay machinery so a sprint can seed and run the full
overlay lifecycle (seed → edit → diff → validate → apply) for **every**
co-located `DESIGN.md` it touches, not just one; plus two small
non-`hook_handlers.py` correctness/staleness fixes.

## Scope

This is a roadmap-phase sprint. The three issues below are linked and
summarized here; full detail lives in the issue files themselves and is
not duplicated.

**1. Design overlay cannot seed multiple co-located DESIGN.md files per
sprint** (`design-overlay-cannot-seed-multiple-colocated-design-md-per-sprint.md`)
— PRIMARY issue, substantial. In the co-located design-doc model, every
subsystem's canonical doc is named `DESIGN.md`, but the sprint overlay
directory is flat and keys entries by basename — so a sprint touching
more than one subsystem doc can only ever overlay one of them; the rest
get edited directly on the canonical files, bypassing the seed → edit →
diff → validate → apply lifecycle entirely. `seed_sprint_design_overlay`
also hardcodes `docs/design/` as the base path, which predates
co-location. Stakeholder-decided fix: slugify overlay filenames
(hyphenated, e.g. `firm-app-DESIGN.md`) so multiple docs can coexist in
the flat overlay dir; the existing `_sources.json` manifest already
disambiguates `apply()` and `generate_diffs()` and does not need to
change. Four touchpoints identified: `seed_sprint_design_overlay`
(`artifact_tools.py`), `seed_and_commit` (`overlay.py`), the validator's
overlay check (`validator.py` — must match via the manifest rather than
basename), and skill prose (plan-sprint / architecture-authoring /
bootstrap-design — instruct overlaying every touched doc, not just one).

**2. Stale `norecursedirs` breaks bare pytest and close-sprint**
(`norecursedirs-stale-e2e-project-breaks-bare-pytest-and-close-sprint.md`)
— trivial, one-line `pyproject.toml` fix. `norecursedirs` lists the older
e2e fixture project paths but not `tests/e2e/e2e-project` (introduced by
the sprint-023 e2e-harness rework), so a bare `uv run pytest` from the
repo root tries to collect that nested standalone project's test modules
and fails with import collisions, breaking both ad-hoc test runs and
`close_sprint`'s test-suite gate.

**3. team-lead agent doc contradicts mcp-guard on create_sprint**
(`team-lead-agent-doc-contradicts-mcp-guard-on-create-sprint.md`) —
trivial, plugin-source docs sync. `.claude/agents/team-lead/agent.md`
still instructs the team-lead to call `create_sprint` directly in two
places, but the `mcp-guard` PreToolUse hook blocks tier-0 (team-lead)
calls to `mcp__clasi__create_sprint`, requiring dispatch to
sprint-planner instead. Every team-lead session that follows the
documented flow verbatim gets denied. Fix is a docs correction to match
the enforced (and correct) behavior.

### Out of scope

All `hook_handlers.py` issues — `db-backed-oop-flag`,
`get-project-upward-discovery`, `role-guard-plans-dir`,
`sprint-planner-tier-1` — are explicitly excluded from this sprint.
There is uncommitted, concurrent work in `src/clasi/hook_handlers.py` and
`tests/unit/test_hook_handlers.py` from another session; this sprint must
not touch either file to avoid colliding with that in-flight work.

Also out of scope, as unrelated to this sprint's theme:
`clasi-init-reverts-mcp-config` and `claude-cli-openrouter`.

## Sizing Decision

**Substantial** — driven by the primary issue (design-overlay multi-doc
fix), which touches 3+ modules (`artifact_tools.py`,
`design/overlay.py`, `design/validator.py`, plus three skill-prose
files) and changes a cross-module contract: the shape of the
`_sources.json` manifest key changes from "canonical basename" to
"derived slug," which every consumer of that manifest (`apply`,
`generate_diffs`, the validator) must agree on. That is a
dependency-direction-relevant contract change even though it does not
touch a persisted data model. The two trivial issues (`norecursedirs`
one-liner; team-lead doc sync) ride along in the same sprint without
raising its tier — each gets a single ticket sized and reviewed as
trivial in its own right (no architecture entry, no separate use case),
but the sprint as a whole is sized by its heaviest issue, per the
sizing-decision guidance to prefer the heavier tier on a mixed sprint
rather than average across issues.

## Use Cases

### SUC-001: Sprint planner seeds every touched co-located design doc
without collision

**Actor**: sprint-planner agent, during Phase 2 detail-planning of an
opted-in project.

**Trigger**: the sprint's planned changes touch two or more canonical
design docs that share the co-located `DESIGN.md` basename (e.g. a
system doc plus two subsystem docs, or two subsystem docs in different
source roots).

**Flow**:
1. The sprint-planner identifies every canonical doc the sprint's
   changes affect (per `architecture-authoring` Mode 2a Step 1) and
   calls `seed_sprint_design_overlay(sprint_id, doc_names)` with all of
   them in one call, passing co-located source paths directly (no
   `../../` escape).
2. The tool derives a unique, reversible, stable slug for each doc from
   its canonical path (e.g. `src/firm/app/DESIGN.md` to
   `firm-app-DESIGN.md`) and seeds each as a distinct file in the flat
   `design/` overlay dir, recording each slug to its full canonical path
   in `_sources.json`.
3. The sprint-planner edits each seeded copy independently.
4. `generate_diffs` produces one `<slug>.diff.md` per edited file.
5. `clasi design validate --overlay` matches each overlay file against
   its manifest-recorded canonical target (not bare basename) and
   passes when every overlay file resolves to a real, distinct
   canonical doc.
6. `apply` copies each overlay file back to its own recorded canonical
   path.

**Postcondition**: N co-located `DESIGN.md` docs went through the full
seed → edit → diff → validate → apply lifecycle in one sprint, with no
file collision and no manifest-entry clobber at any step.

**Failure mode addressed**: today, step 1's second and later
`seed_sprint_design_overlay` calls for a same-basename doc overwrite the
first doc's file and manifest entry (`{last write wins}`), silently
dropping the earlier doc from the overlay lifecycle entirely — it gets
edited directly on the canonical file during execution instead, with no
diff and no validation.

### SUC-002: Validator distinguishes same-basename overlay files by
their true canonical target

**Actor**: `clasi design validate` (CLI and MCP `validate_design` tool).

**Trigger**: an overlay directory contains two or more files whose
basenames collapse to the same canonical name under the co-located
model (`DESIGN.md`, `DESIGN.md`, ...).

**Flow**: the validator's overlay check reads each overlay file's
recorded canonical target from `_sources.json` and confirms it against
the doc set's known canonical doc paths — not against a set of bare
canonical basenames, which cannot disambiguate `firm/app/DESIGN.md`
from `host/robot_radio/DESIGN.md`.

**Postcondition**: validation correctly reports pass/fail per overlay
file based on its real target, and a genuinely unmatched overlay file
(one with no manifest entry, or a manifest entry pointing outside the
doc set) is still caught as an error — the fix must not weaken the
check to "any file present is fine."

## Architecture

**Substantial** — see Sizing Decision above. Full 7-step methodology
applied below.

### 1. Understand the Problem

The co-located design-doc model (sprint 022) names every subsystem's
canonical doc `DESIGN.md`. The sprint `design/` overlay directory is
flat and, today, keys every step of its lifecycle
(`seed_and_commit`'s `dest`/manifest write, the validator's overlay
check) by bare filename. Seeding a second same-basename doc overwrites
the first doc's overlay file and its `_sources.json` manifest entry.
`seed_sprint_design_overlay` additionally hardcodes
`project.design_dir / name` as the resolution base, unreachable for
co-located docs without a `../../` path escape. Net effect: a sprint
touching more than one subsystem doc can only carry one through the
seed → edit → diff → validate → apply lifecycle; the rest get edited
directly on canonical files during execution, bypassing diff generation
and validation entirely. Full evidence and root-cause trace:
`clasi/issues/design-overlay-cannot-seed-multiple-colocated-design-md-per-sprint.md`.
Two independent trivial issues ride along: a stale `pyproject.toml`
`norecursedirs` entry, and a plugin-source doc (team-lead agent.md)
still instructing a guard-blocked `create_sprint` call.

### 2. Identify Responsibilities

1. **Overlay seeding path resolution and slug derivation**
   (`seed_sprint_design_overlay`, `artifact_tools.py`) — accepting
   co-located canonical source paths and deriving a unique, stable,
   reversible overlay filename per doc. Changes because today's base
   path is wrong and its output filenames collide.
2. **Overlay seed/commit mechanics** (`seed_and_commit`, `overlay.py`)
   — writing the seeded file under its derived slug and recording that
   slug (not the canonical basename) as the manifest key. Changes for
   the same reason as (1) but is a distinct module.
3. **Overlay-to-canonical validation** (`_canonical_doc_names`,
   `_check_overlay`, `validator.py`) — confirming each overlay file
   resolves to a real, distinct canonical doc via the manifest, not via
   basename set membership. Changes independently of (1)/(2): it reads
   the manifest `seed_and_commit` writes but has its own bug (basename
   matching) that must be fixed on its own terms.
4. **Planning-time skill guidance** (`plan-sprint`, `architecture-authoring`,
   `bootstrap-design` skill prose) — instructing the sprint-planner to
   seed every touched canonical doc once the tool supports it. This is
   documentation, not code, but it gates whether the fixed tool actually
   gets used correctly.
5. **Test collection scope** (`pyproject.toml` `norecursedirs`) —
   unrelated to 1-4; a stale ignore-list entry. Independent responsibility,
   trivial tier.
6. **Plugin-source/installed doc parity** (`team-lead/agent.md` in
   `src/clasi/plugin/agents/`) — unrelated to 1-5; a docs-only
   correction to match already-fixed installed behavior. Independent
   responsibility, trivial tier.

Responsibilities 1-3 are the primary issue's fix; 5 and 6 are
independent trivial issues bundled into this sprint for scheduling
convenience, not because they share a root cause with 1-4.

### 3. Define Subsystems and Modules

- **`clasi.tools.artifact_tools.seed_sprint_design_overlay`** — purpose:
  translate a sprint-planner's list of canonical design-doc paths into
  the overlay's on-disk seed operation. Boundary: owns path resolution
  and slug derivation; delegates the actual copy/commit/manifest-write
  to `clasi.design.overlay.seed_and_commit`. Serves SUC-001.
- **`clasi.design.overlay`** (`seed_and_commit`, `generate_diffs`,
  `apply`) — purpose: maintain the overlay directory's git-anchored
  seed/diff/apply lifecycle. Boundary: owns the `_sources.json`
  manifest's schema and read/write; `generate_diffs` and `apply` already
  consume the manifest per-file and require no change — only
  `seed_and_commit`'s write side changes (dest path, manifest key).
  Serves SUC-001.
- **`clasi.design.validator`** (`_canonical_doc_names`, `_check_overlay`)
  — purpose: confirm an overlay directory is well-formed before
  architecture-review consumes it. Boundary: reads the manifest and the
  doc set; does not write to either. Serves SUC-002.
- **Skill prose** (`plan-sprint`, `architecture-authoring`,
  `bootstrap-design`) — purpose: instruct the sprint-planner to invoke
  the fixed tool correctly (every touched doc, not one). No code
  boundary; a documentation-only "module" for tracking purposes.

No new module is introduced; all three code modules already exist and
keep their existing boundaries. The fix corrects a naming/resolution
defect inside each, plus a bug in the validator's match logic.

### 4. Diagrams

A component diagram is omitted by reasoned exception, matching sprint
020's precedent for stating this rather than skipping the check
silently: `seed_sprint_design_overlay`, `overlay.py`, and `validator.py`
already depend on each other in exactly the shape a diagram would show
(`artifact_tools` to `overlay.seed_and_commit`; `validator` reads
`overlay`'s manifest format) — this sprint does not add, remove, or
redirect any of those edges, it corrects what flows over the existing
ones (a slug instead of a basename). No new cross-module dependency and
no dependency-direction change is introduced. An ERD is not applicable
— `_sources.json` is a flat filename-to-path mapping today and remains
one; only the key's derivation changes, not its shape.

### 5. What Changed / Why / Impact / Migration Concerns

**What Changed**:
- `seed_sprint_design_overlay` accepts co-located canonical source paths
  directly (no `../../` escape) and derives a unique overlay slug per
  doc instead of resolving `project.design_dir / name`.
- `seed_and_commit` writes each seeded file under its derived slug and
  records the slug (not `canonical_path.name`) as the `_sources.json`
  key.
- The validator's overlay check matches each overlay file against its
  manifest-recorded canonical target instead of a bare canonical-basename
  set.
- Skill prose (`plan-sprint`, `architecture-authoring`, `bootstrap-design`)
  is updated to instruct seeding every touched canonical doc in one
  `seed_sprint_design_overlay` call.
- `pyproject.toml`'s `norecursedirs` gains `tests/e2e/e2e-project`.
- `src/clasi/plugin/agents/team-lead/agent.md` is corrected to dispatch
  sprint-planner for sprint creation instead of calling `create_sprint`
  directly, matching the already-fixed installed
  `.claude/agents/team-lead/agent.md`.

**Why**: see Understand the Problem above; each trivial fix addresses
its own issue file's evidence.

**Impact on Existing Components**: `generate_diffs` and `apply` are
**not modified** — both already resolve targets per-file via the
`_sources.json` manifest (confirmed by source read: `apply`'s docstring
states it "never" derives a target from the overlay file's name or a
flat target directory; `generate_diffs` iterates per-file). This is
verified by a new multi-doc regression test (ticket 4) rather than by
editing either function — the sizing note in the issue file
("apply()/generate_diffs() already key off the manifest... should NOT
need changes") is confirmed correct by this reading, not merely assumed.
Any existing single-doc overlay (from a sprint already in flight) is
unaffected: a single doc's derived slug and its old basename coincide
whenever the doc's canonical path has no co-located sibling of the same
name (the common single-subsystem case), and even where they differ,
existing overlays are read fresh each time by `generate_diffs`/`apply`
rather than cached, so there is no stored state to migrate.

**Migration Concerns**: none for existing overlays (see above — nothing
persists across the schema change that needs converting). No data
migration; no breaking change to any external interface (`doc_names` is
still a list of filenames — only what shapes of filenames it accepts
grows, it does not shrink).

### 6. Design Rationale

**Decision**: slugify overlay filenames (flat directory, unique derived
name) rather than mirror the source tree inside the overlay directory.

**Context**: the overlay directory must hold N co-located `DESIGN.md`
files without collision. Two shapes were available: keep the directory
flat and rename files uniquely, or reproduce each doc's source-tree
path inside `design/` (e.g. `design/firm/app/DESIGN.md`).

**Alternatives considered**: mirroring the source tree preserves the
canonical basename and needs no slug-derivation logic, but it makes the
overlay directory's own depth and shape track the source tree's shape,
which the flat overlay convention (one directory holding all of a
sprint's design-doc edits, regardless of source location) was
deliberately designed to avoid — and it does not change the manifest's
necessity, since `apply` still needs to know each overlay file's
canonical target regardless of directory shape.

**Why this choice**: stakeholder-decided (recorded in the issue file);
keeps the overlay directory flat and shallow regardless of how deep the
sprint's touched docs live in the source tree, and the manifest already
does the target-resolution work that mirroring would otherwise be
relied on to provide implicitly via path shape — so mirroring would add
directory-shape complexity without removing the manifest dependency.

**Consequences**: overlay filenames are no longer human-obvious at a
glance (`firm-app-DESIGN.md` instead of a path); the manifest becomes
load-bearing for every consumer (already true today for the has-one-doc
case, now equally true for the N-doc case) — validator and `apply` must
both be manifest-driven, which is exactly what responsibility 3's fix
delivers.

### 7. Open Questions

- **Slug transform exact form**: the issue file gives examples
  (`firm-app-DESIGN.md`, `host-robot-radio-DESIGN.md`) implying
  path-separator-to-hyphen substitution relative to some root, but does
  not fully specify the transform for edge cases (a source path
  containing a literal hyphen already; the system-level `design.md` at
  `docs/design/design.md`, which has no source-root prefix to slugify).
  Ticket 1 must pick a concrete, documented transform and the transform
  must be stable and reversible (round-trips are not required — the
  manifest carries the true canonical path — but re-seeding the same
  doc must reliably reproduce the same slug so re-seeds overwrite
  in place rather than accumulating duplicates).
- None of the three issues require stakeholder input beyond the
  slug-transform judgment call above, which ticket 1 resolves and
  records inline (Design Rationale, if a real choice, or a one-line note
  otherwise) rather than deferring further.

### Design-Overlay Dogfooding Decision (this sprint's own doc updates)

This sprint edits `src/clasi/design/` and `src/clasi/tools/`, both of
which have canonical `DESIGN.md` docs, plus the `src/clasi` root
`DESIGN.md` (`design_docs: enabled`, `sources: [src/clasi]`). Normally
Phase 2 detail-planning would seed a `design/` overlay for these three
docs now, per `architecture-authoring` Mode 2a. Doing so today would
require seeding three co-located canonical docs
(`src/clasi/DESIGN.md`, `src/clasi/design/DESIGN.md`,
`src/clasi/tools/DESIGN.md`) in one call — exactly the multi-doc seed
this sprint exists to fix. Bootstrapping the overlay before ticket 1
lands would hit the very collision being repaired.

**Decision**: defer overlay seeding for this sprint's own three affected
design docs until after ticket 1 (the `seed_sprint_design_overlay` /
`seed_and_commit` fix) is implemented and passing its regression test.
At that point, ticket 5 seeds the overlay for
`src/clasi/DESIGN.md`, `src/clasi/design/DESIGN.md`, and
`src/clasi/tools/DESIGN.md` using the now-fixed multi-doc call, edits
each to reflect this sprint's actual changes, diffs, and validates —
so this sprint dogfoods its own fix rather than working around it.
Tickets 2 and 3 (the validator fix and skill-prose update) land before
ticket 5 seeds, so the seed step also exercises the fixed validator.
This ordering is encoded directly in ticket dependency order (ticket 5
depends on tickets 1-3) rather than left as a footnote — see Tickets
below.

**Rejected alternative**: editing the three canonical `DESIGN.md` files
directly during this sprint's execution, bypassing the overlay entirely.
Rejected because it is exactly the workaround pattern issue 1 is about
eliminating, and because this sprint is uniquely positioned to prove the
fix works on its own affected docs before any other project relies on
it.

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [x] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [x] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Slugify design-overlay seed paths and manifest keys | — |
| 002 | Validator: match overlay files via manifest, not basename | 001 |
| 003 | Multi-doc overlay regression test (seed/edit/diff/validate/apply) | 001, 002 |
| 004 | Update skill prose to overlay every touched design doc | 001, 002 |
| 005 | Dogfood: seed and update this sprint's own affected DESIGN.md docs via overlay | 001, 002, 003, 004 |
| 006 | Add tests/e2e/e2e-project to pytest norecursedirs | — |
| 007 | Sync plugin-source team-lead agent doc off create_sprint | — |

Tickets execute serially in the order listed. Tickets 006 and 007 have
no dependency on 001-005 (independent trivial issues) and could run in
any position relative to them; they are listed last because they are
unrelated riders, not because anything blocks them earlier.
