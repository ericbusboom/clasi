---
status: pending
---

# Co-locate design docs as DESIGN.md in each source directory, replacing README

## Description

Move each subsystem's design document out of the central `docs/design/` set and
into the subsystem's own source directory, as a file named `DESIGN.md`. A
subsystem's design then lives beside its code, one `DESIGN.md` per source
directory, and the separate source-tree `README.md` goes away — `DESIGN.md`
subsumes it.

Stakeholder intent (2026-07-16), as stated:

- Design documents move **into the source code**, in files named `DESIGN.md`.
- This **eliminates the need for a `README.md`** in the source tree — one
  co-located design doc per directory, not two files.
- **Front matter may not be needed.** Today's `docs/design/*.md` carry little
  or no frontmatter (`overview.md`, `state-machines.md` open straight into
  prose). If the linkage a doc needs can be expressed without frontmatter,
  drop it; keep only what a real link requires.
- **Sprint-change linkage is preserved.** A sprint must still be able to record
  which design docs it touched. That linkage stays; only the docs' home
  changes.

**This supersedes the direction sprint 021 is currently executing.** 021
("Persistent per-subsystem architecture docs with sprint update overlays") is
mid-flight and building the opposite arrangement: a *central* `docs/design/`
doc set (`src/clasi/design/store.py`), sprint-scoped overlay copies of those
central docs (`src/clasi/design/overlay.py`, `Sprint.design_dir`), and a
validator that checks a **bidirectional link between a `docs/design/` doc and a
co-located subsystem `README.md`** (`src/clasi/design/paths.py:readme_path_for`,
"SUC-001's bootstrap and SUC-003's validator both need this pairing"). This
change collapses that doc/README pairing into a single co-located `DESIGN.md`
and inverts the storage location from central to co-located.

**Do not start this until sprint 021 is closed** (its tickets 008/009 are still
open/in-progress). Reconciling the two directions mid-021 would thrash the same
files twice. This is explicitly a "immediately after the current tickets" item
per the stakeholder.

## Cause

Not a bug — a deliberate model change. The current `docs/design/` +
source-`README.md` split (021's model) puts a subsystem's design one directory
away from its code and requires maintaining two paired files with a validated
cross-link. Co-locating as a single `DESIGN.md` removes the split and the
pairing.

## Proposed fix

Sequencing and open questions, for the planner to resolve — this is a design
change with real decisions, not a mechanical move.

### Sequencing

1. Land and close sprint 021 first (do not touch its files mid-flight).
2. Then plan this as its own sprint. Much of 021's machinery is reusable with
   its target path changed:
   - `src/clasi/design/paths.py` — `readme_path_for` and the doc-path
     resolution: retarget to `<subsystem_path>/DESIGN.md`; the README pairing
     goes away.
   - `src/clasi/design/store.py` — read/write moves from `docs/design/<slug>.md`
     to per-source `DESIGN.md`.
   - `src/clasi/design/validator.py` — the bidirectional doc↔README check
     becomes a single-file existence/quality check on `DESIGN.md`.
   - `src/clasi/design/overlay.py` / `Sprint.design_dir` — the sprint-change
     linkage the stakeholder wants kept. Decide whether overlays still make
     sense when docs are co-located (see open questions).

### Open questions (planner to decide, with stakeholder if needed)

- **What is "a subsystem"?** One `DESIGN.md` per source directory, or per
  logical subsystem (which may span directories)? `paths.py` currently keys off
  a `subsystem_path`; the granularity of that mapping drives everything.
- **Frontmatter: none, or minimal?** The stakeholder says "may not be needed."
  The only hard requirement stated is sprint-change linkage. Determine whether
  that linkage can live entirely in the sprint artifact (sprint records which
  `DESIGN.md` files it touched) with the doc itself frontmatter-free, or whether
  the doc needs a stable id/slug of its own. Prefer no frontmatter if the sprint
  side can carry the link.
- **How does sprint-change linkage work post-move?** Today 021 uses
  sprint-scoped overlay copies under `Sprint.design_dir`. With docs co-located
  in source, does the overlay model still apply, or does the sprint simply list
  the `DESIGN.md` paths it changed? The latter is simpler and matches "we can
  still have a linkage from the changes in Sprint."
- **Migration of existing `docs/design/*.md`.** Five docs exist today
  (`overview`, `specification`, `state-machines`, `usecases`,
  `worktree-process`). Some are project-level (overview, specification) and have
  no single "source directory" to co-locate into. Decide which become co-located
  `DESIGN.md` files and which stay as genuinely project-level docs — not
  everything in `docs/design/` is a subsystem design.
- **Does `docs/design/` survive at all?** Project-level docs (overview,
  specification) may still want a home there even after subsystem designs move
  into the source tree.

## Verification

- Each targeted subsystem has a `DESIGN.md` in its source directory; the paired
  source `README.md` is gone (or explicitly retained where justified).
- A sprint that changes a subsystem's design records the touched `DESIGN.md`
  path(s), and that linkage is queryable — the mechanism 021 built, retargeted.
- The design validator passes against `DESIGN.md` files (no dangling
  doc↔README link check remains).
- Project-level docs that are not subsystem designs are handled deliberately,
  not accidentally dropped.
- Full suite green; `docs/design/` references updated across code and docs
  (generator sources, not just generated files — `.claude/` is gitignored).

## Related

- **Supersedes / reworks sprint 021** ("Persistent per-subsystem architecture
  docs with sprint update overlays"), which builds the central-`docs/design/`
  + source-`README.md` model this change inverts. Must land after 021 closes.
- `src/clasi/design/{paths,store,overlay,validator}.py` and `Sprint.design_dir`
  (`src/clasi/sprint.py`) are 021's implementation surface and this change's
  primary edit targets.
- `src/clasi/design/paths.py:readme_path_for` is the specific doc↔README pairing
  being collapsed into a single co-located `DESIGN.md`.
