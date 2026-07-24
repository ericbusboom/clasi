---
status: pending
sprint: '025'
---

# Sprint design overlay cannot seed multiple co-located DESIGN.md files per sprint

## Summary

In a project using the co-located design-doc model (`design_docs:
enabled`, canonical docs at `<subsystem>/DESIGN.md`), the sprint design
overlay can only ever seed **one** `DESIGN.md` per sprint. A sprint that
touches several subsystem docs is forced to overlay just one and edit the
rest **directly on the canonical files during execution** — bypassing the
seed → edit → diff → `clasi design validate --overlay` → architecture-review
lifecycle that opting into design docs was supposed to provide for every
touched doc.

The overlay machinery was written for the pre-co-location world of flat
`docs/design/<slug>.md` docs, where every doc had a unique basename. It
was never updated for the co-located model (sprint 022) where every
subsystem doc is named `DESIGN.md`.

## Evidence (radio-robot-elite sprint 120)

`clasi/sprints/120-bench-tour-bring-up-with-fake-otos/sprint.md`'s
"Design Overlay" section explicitly states the sprint touches **three**
subsystem `DESIGN.md` files plus the system doc, then:

> "this sprint touches ... three subsystem `DESIGN.md` files plus the
> system doc **but can only overlay one**"

It cites a "flat-overlay-slot precedent established in sprints
116/117/118/119" — i.e. every sprint since 116 has hit this and the agent
has invented a coping convention: overlay one doc, edit the others
directly on canonical. The overlay dir confirms it — one `DESIGN.md`, one
`DESIGN.diff.md`, one `_sources.json` mapping that single file to
`src/firm/app/DESIGN.md`. The other two touched docs
(`src/firm/devices/DESIGN.md`, `src/host/robot_radio/DESIGN.md`) never
enter the overlay lifecycle.

The planner even had to smuggle a path escape —
`seed_sprint_design_overlay(sprint_id="120",
doc_names=["../../src/firm/app/DESIGN.md"])` — to reach a co-located doc
at all, because the tool resolves `doc_names` relative to `docs/design/`.

## Root cause (two coupled defects, both verified in source)

1. **Wrong base path.** `seed_sprint_design_overlay`
   (`src/clasi/tools/artifact_tools.py`, ~line 323) resolves
   `doc_names` as `project.design_dir / name` — hardcoded to
   `docs/design/`. Co-located subsystem docs live under the source roots
   (`src/firm/app/DESIGN.md`, ...), not under `docs/design/`, so they
   are only reachable via a `../../` path-escape hack, and the tool's
   own docstring still describes `doc_names` as "relative to
   `docs/design/`".

2. **Basename collision (the real blocker).** The overlay dir is flat
   and keyed by basename. `seed_and_commit` (`src/clasi/design/overlay.py`,
   ~lines 221-224) computes `dest = sprint_design_dir /
   canonical_path.name` and records `manifest_update[dest.name] =
   <canonical path>`. Seeding two co-located docs (both named
   `DESIGN.md`) would (a) overwrite each other's file on the
   `shutil.copyfile`, and (b) clobber each other's `_sources.json`
   manifest entry (last write wins). Hence "can only overlay one" is
   *literally true* today — the agent is not hallucinating a limitation;
   it is accurately describing a real one.

## Chosen approach: slugify overlay filenames

Keep the overlay directory flat, but encode each doc's canonical path
into a **unique overlay filename** (e.g. `firm-app-DESIGN.md`,
`host-robot-radio-DESIGN.md`) so multiple co-located `DESIGN.md` files
no longer collide. The `_sources.json` manifest continues to map each
(now-unique) overlay filename to its canonical path, and `apply()` /
`generate_diffs()` — which already key off the manifest and per-file
diffs — route each overlay back to its own canonical doc unchanged.

(Alternative considered: mirror the source tree inside the overlay dir,
`design/firm/app/DESIGN.md`. Rejected in favor of the flat-slug approach
per stakeholder decision; recorded here so the tradeoff is not
re-litigated. Slug transform must be reversible/unique and stable across
re-seeds.)

## Touchpoints the fix must cover

1. **`seed_sprint_design_overlay`** (`src/clasi/tools/artifact_tools.py`
   ~L323): stop hardcoding `project.design_dir / name`. Accept
   co-located canonical source paths (a subsystem's `DESIGN.md` under a
   source root, or the system `docs/design/design.md`), and derive a
   unique overlay slug per doc. Update the docstring, which currently
   claims `doc_names` are "relative to `docs/design/`".

2. **`seed_and_commit`** (`src/clasi/design/overlay.py` ~L221-224):
   `dest` must use the derived slug, not `canonical_path.name`; the
   manifest key must be the slug. Confirm `apply()`'s
   `_resolve_apply_plan` and `generate_diffs()`'s
   `<overlay_file.name>.diff.md` naming still work with slugged names
   (they read the manifest / per-file, so they should — verify with a
   multi-doc test).

3. **Validator overlay check** (`src/clasi/design/validator.py`
   `_canonical_doc_names` ~L222 and `_check_overlay` ~L231): today it
   validates an overlay file's *basename* against a set of canonical
   basenames — which collapses to `{design.md, DESIGN.md}` under the
   co-located model and cannot tell which subsystem a `DESIGN.md`
   overlay targets. Rework it to validate each overlay file against the
   `_sources.json` manifest's recorded canonical target instead of bare
   basename matching.

4. **Skill prose — "encourage the agent to do the right thing"**
   (`src/clasi/plugin/skills/plan-sprint/`,
   `architecture-authoring/`, `bootstrap-design/` as applicable): the
   planner learned a "flat-overlay-slot, only-one-doc" convention from
   the broken tool. Once the tool supports it, the prose must explicitly
   instruct: overlay **every** canonical design doc the sprint touches
   (all affected subsystem `DESIGN.md`s plus the system doc), each edited
   in the overlay and diffed/validated — not edited directly on canonical
   during execution. Kill the "can only overlay one" workaround language.

## Acceptance criteria

- `seed_sprint_design_overlay` can seed N co-located `DESIGN.md` files
  from different subsystems in one call without collision; each lands as
  a distinct overlay file with a distinct manifest entry.
- `doc_names` accepts co-located subsystem docs without a `../../` path
  escape; the docstring matches the real accepted form.
- `generate_diffs`, `clasi design validate --overlay`, and `apply` all
  operate correctly over a multi-`DESIGN.md` overlay: each diff is
  per-doc, validation matches each overlay to its true canonical target
  (not just basename), and apply writes each back to its own canonical
  path.
- A regression test seeds ≥2 co-located `DESIGN.md` files (e.g.
  `firm/app` and `host/robot_radio`), edits both, diffs, validates, and
  applies — asserting both canonical files receive their own edits.
- Skill prose no longer tells the planner it "can only overlay one" and
  instructs overlaying every touched doc.

## Notes

- Discovered while investigating radio-robot-elite sprint 120 on
  2026-07-23. Related to the co-located design model introduced in
  sprint 022 and the root-level-DESIGN.md requirement added
  2026-07-22/23.
- This affects every opted-in project, not just radio-robot-elite —
  radio-robot-elite is just where it was caught because its sprints
  routinely touch multiple firmware subsystems.
