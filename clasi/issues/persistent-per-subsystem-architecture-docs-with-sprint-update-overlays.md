---
status: pending
---

# Persistent per-subsystem architecture docs with sprint update overlays

## Description

CLASI's architecture documents are not used well. Architecture lives as a `## Architecture` section inside each sprint's `sprint.md` (legacy sprints 001–020 carry a separate `architecture-update.md`), authored by the sprint-planner and never merged back — per-sprint sections accumulate as a chronological record, and code is treated as the source of truth. The `consolidate-architecture` skill can produce a single `docs/design/architecture.md` on demand, but that file does not exist in this repo. There is no persistent, subsystem-structured architecture description, no linkage between design docs and source directories, and no validation tooling.

Replace this with a **persistent, per-subsystem architecture document set** in `docs/design/`, maintained across sprints, with code-enforced bidirectional links between design docs and source-tree READMEs, tool-supported validation, and sprint-time updates expressed as full updated copies of the affected docs reviewed via generated human-readable diffs.

## Cause

The single-big-document and per-sprint-section models both fail the same way: no one document describes the current architecture of a specific part of the system, so agents neither read nor maintain them. Architecture written at sprint granularity has no stable home to converge into, and nothing enforces that docs correspond to the source tree, so drift is invisible.

## Proposed fix

### 1. Persistent design doc set in `docs/design/`

- One top-level `design.md` — the system design that links everything else together.
- One document per **logical subsystem**. The system is conceptualized as a collection of subsystems, not one big document; an agent can focus on and edit a single subsystem doc without touching the rest.
- Subsystems map to source-tree divisions (directories in Python/C++; other mechanisms in other languages). A project explicitly may have **multiple source roots** (e.g. `src/` and `tests/` each get designs) — declared in `.clasi/config.yaml` (extend `paths`, e.g. a `sources:` list).

### 2. Naming convention (slugified paths)

- Filenames derive from the subsystem's path by slugification.
- **Single source root:** slugify from *within* the root, so the root name does not appear (e.g. `src/clasi/tools/` → `clasi-tools.md`).
- **Multiple source roots:** slugify from the repo root so the root disambiguates (e.g. `src-clasi-tools.md`, `tests-e2e.md`).

### 3. Bidirectional README ↔ design-doc links

- Each subsystem directory (the top-level directory that holds the code; subdirectories belong to the subsystem) gets a `README.md` with frontmatter: subsystem name, one-line description, and a reference to its design document.
- Each design doc has frontmatter referencing its source path(s)/README.
- These links are **maintained and validated by code**, not by convention alone.

### 4. Creation and validation

- **The doc set is stakeholder-authorized, not mandatory.** When the team-lead finds no architecture doc set in `docs/design/`, it **encourages the stakeholder to authorize creating one** and, on approval, dispatches a sub-agent to read the system and write the docs. If the stakeholder declines — some will, because they want things to move faster and don't want to deal with the updates — the entire architecture-update process is **skipped**: no doc set, no sprint `design/` overlays, no architecture review gate. The decision should be recorded (e.g. in `.clasi/config.yaml`) so the team-lead doesn't re-ask every session, though the stakeholder can opt in later at any time.
- **Creation needs no tool support, but it does need skills:** dedicated skills that tell an agent how to do this work — one for **bootstrapping** the doc set (read the source roots, identify subsystems, write `design.md` + per-subsystem docs + frontmattered READMEs; repurposes/absorbs `consolidate-architecture`, whose single-doc output this design supersedes) and reworked **authoring** guidance for maintaining subsystem docs and writing sprint update overlays (evolves `architecture-authoring`). The team-lead dispatches sub-agents that follow these skills; it does not write the docs itself.
- **Validation needs tool support:** a validator that checks docs/design structure — top-level `design.md` present, one doc per subsystem, frontmatter present, links resolve both ways, no orphaned docs or unmapped source roots. Exposed as both a `clasi` CLI command (follow the `clasi schema validate` pattern at `src/clasi/cli.py:245-266`) and an MCP tool so the team-lead can call it; on failure, the team-lead dispatches an agent to fix and re-validates.
- Implementation pointers: `Artifact`/frontmatter machinery in `src/clasi/artifact.py` and `src/clasi/frontmatter.py`; `read_artifact_frontmatter`/`write_artifact_frontmatter` in `src/clasi/tools/artifact_tools.py:2383,2403`; `Project.design_dir` in `src/clasi/project.py:116`.

### 5. Sprint-time updates: full-copy overlay, diff derived

- Sprint planning no longer writes an Architecture section into `sprint.md`. Instead the sprint-planner writes **update files** in `clasi/sprints/NNN-slug/design/`, with the **same filename** as the canonical doc being updated (`design.md` for the top-level doc, `<subsystem-slug>.md` otherwise).
- Each update file is a **complete updated copy** of the design doc (chosen over hand-written unified diffs — agents write whole documents reliably; hand-built diffs drift). The diff is *derived*: comparing the sprint copy against the canonical doc reproduces the change, and copying the sprint file over the canonical one applies it — the round-trip property, without storing patch syntax.
- Update-file frontmatter references (a) the canonical doc it updates in `docs/design/` and (b) the subsystem README.
- **Derived diff files for review:** the final step in producing the sprint design set is to diff each canonical doc against its updated sprint copy and write a **human-readable diff** named `<same-name>.diff.md` in the same sprint `design/` directory (e.g. `design/mcp-server.md` full copy plus `design/mcp-server.diff.md`). These diff files are generated artifacts (tool-produced, regenerable), formatted for human reading rather than raw `patch(1)` input — e.g. fenced ```diff blocks or section-grouped before/after — and are what the architecture reviewer reads.
- The validator also covers sprint design dirs: filenames match canonical docs, frontmatter refs resolve, and each update file has a matching up-to-date `.diff.md`.

### 6. Sprint review and application

- The whole updates/review/apply cycle applies only when the stakeholder has opted into the architecture doc set (see 4); with no doc set, sprints carry no `design/` directory and the architecture review step is skipped.
- The architectural part of sprint review = reading the generated `.diff.md` files alongside the tickets, replacing today's `architecture-review` gate over `sprint.md` sections.
- On sprint close (after review passes), the sprint copies are applied to `docs/design/` — this is what makes the doc set persistent and maintained with the sprints. This deliberately reverses the current never-merge-back philosophy.

### Ripple effects (to be scoped when planned, not solved here)

- Skills needing rework or creation: a new **bootstrap skill** (or `consolidate-architecture` repurposed as it), `architecture-authoring` (subsystem docs + overlay authoring), `architecture-review` (reads `.diff.md` files), `plan-sprint` and `close-sprint` (overlay creation/application, plus the skip path when no doc set exists), the team-lead role definition (detect missing doc set, prompt the stakeholder, dispatch the bootstrap agent), and `execute-sprint` (programmer dispatch context currently pulls "relevant architecture sections" — it should pull the relevant subsystem doc plus sprint overlay instead).
- Bootstrap for this repo: `docs/design/` currently holds the frozen initiation docs (`overview.md`, `specification.md`, `usecases.md`, …) and no architecture docs; a one-time agent run creates the subsystem set. Open question: do initiation docs coexist in `docs/design/`, or do the subsystem docs get a subdirectory?
- Config: where multiple source roots are declared (`.clasi/config.yaml`).

## Verification

- With no doc set and no recorded opt-out, the team-lead prompts the stakeholder to authorize creating one; on decline, sprints proceed with no `design/` overlays and no architecture review; on approval, a dispatched sub-agent (following the bootstrap skill) produces the doc set.
- `clasi design validate` (CLI) and the matching MCP tool pass on a correctly linked doc set and fail with actionable errors on: missing `design.md`, an unmapped source root, a design doc with no README backlink (and vice versa), and a sprint update file with a stale or missing `.diff.md`.
- After a bootstrap agent run on this repo, `docs/design/` contains `design.md` plus one doc per subsystem, each subsystem directory has a frontmattered `README.md`, and validation passes.
- A trial sprint produces `design/` update files plus generated `.diff.md` files, architecture review reads the diffs, and sprint close applies the copies to `docs/design/` with validation passing afterward.

## Related

- `.agents/skills/architecture-authoring/SKILL.md`, `.agents/skills/architecture-review/SKILL.md`, `.agents/skills/consolidate-architecture/SKILL.md` — current architecture workflow this replaces.
- `.agents/skills/plan-sprint/SKILL.md`, `.agents/skills/execute-sprint/SKILL.md`, `.agents/skills/close-sprint/SKILL.md` — sprint lifecycle points that change.
