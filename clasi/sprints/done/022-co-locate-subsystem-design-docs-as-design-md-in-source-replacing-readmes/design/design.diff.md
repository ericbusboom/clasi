---
source_file: design.md
source_hash: b73d95cf74c843a40e5053edb5a3ca17bb83aaa1655f188f03ed37167260fdfa
---
# Diff: design.md

Comparison of the sprint overlay copy of `design.md` against its pristine (seed-commit) canonical version.

```diff
--- design.md (pristine)
+++ design.md (current)
@@ -1,46 +1,48 @@
----
-source_paths:
-- /Volumes/Proj/proj/ai-projects/clasi/src/clasi
-readme_path: null
----
 # CLASI: System Design
 
-**Owner:** clasi maintainers · **Last reviewed:** 2026-07-16 · **Status:** in-flux
+**Owner:** clasi maintainers · **Last reviewed:** 2026-07-17 · **Status:** in-flux
 
 CLASI is a Software Engineering process tool: an MCP server plus CLI plus
 installable platform integration (Claude Code / Codex / Copilot) that
 drives a structured issue -> sprint -> ticket -> execution -> close
 lifecycle for AI-agent-assisted software development. This document is the
-entry point into the persistent per-subsystem design-doc set introduced in
-sprint 021 (see `clasi.design`'s own doc for the mechanics of this doc set
-itself).
+entry point into the persistent per-subsystem design-doc set. As of sprint
+022, each subsystem's design doc is **co-located with its code** as
+`DESIGN.md` inside the subsystem's own source directory — see
+`src/clasi/design/DESIGN.md` for the mechanics (sprint 021 introduced the
+doc set as a central `docs/design/` + paired-README model; sprint 022
+inverted that into this co-located model).
 
 ## Subsystem Map
 
 All subsystems below live under `src/clasi/` (this project's sole
 configured source root — see `.clasi/config.yaml`'s `sources: [src/clasi]`).
-Each row links to that subsystem's own design doc for full detail; this
-document stays at the "what exists and how does it fit together" level.
+Each row links to that subsystem's own `DESIGN.md`, co-located in its
+source directory; this document stays at the "what exists and how does it
+fit together" level.
 
 | Subsystem | One-line purpose |
 |---|---|
-| [`clasi.design`](clasi-design.md) (`design/`) | Persistent per-subsystem architecture doc set: naming, storage, validation, sprint overlay lifecycle. |
-| [`clasi.platforms`](platforms.md) (`platforms/`) | Install/uninstall CLASI's file-based integration for a host AI coding tool. |
-| [`clasi.plugin`](plugin.md) (`plugin/`) | Packaged content root: canonical agents, skills, instructions, rules, hooks. |
-| [`clasi.schemas`](schemas.md) (`schemas/`) | Declarative workflow-schema and state-machine YAML definitions and their loaders. |
-| [`clasi.state_machine`](state_machine.md) (`state_machine/`) | Generic state-machine evaluation engine (state + fireable-transition computation). |
-| [`clasi.status`](status.md) (`status/`) | Assembles agent-scoped project/sprint/ticket status from real state. |
-| [`clasi.templates`](templates.md) (`templates/`) | Raw markdown template files for new artifacts and the CLASI host-file section. |
-| [`clasi.tools`](tools.md) (`tools/`) | MCP tool functions: the agent-facing surface over artifact and process operations. |
+| [`clasi.design`](../design/DESIGN.md) (`design/`) | Per-subsystem architecture doc co-location: path resolution, storage, validation, sprint overlay lifecycle. |
+| [`clasi.platforms`](../platforms/DESIGN.md) (`platforms/`) | Install/uninstall CLASI's file-based integration for a host AI coding tool. |
+| [`clasi.plugin`](../plugin/DESIGN.md) (`plugin/`) | Packaged content root: canonical agents, skills, instructions, rules, hooks. |
+| [`clasi.schemas`](../schemas/DESIGN.md) (`schemas/`) | Declarative workflow-schema and state-machine YAML definitions and their loaders. |
+| [`clasi.state_machine`](../state_machine/DESIGN.md) (`state_machine/`) | Generic state-machine evaluation engine (state + fireable-transition computation). |
+| [`clasi.status`](../status/DESIGN.md) (`status/`) | Assembles agent-scoped project/sprint/ticket status from real state. |
+| [`clasi.templates`](../templates/DESIGN.md) (`templates/`) | Raw markdown template files for new artifacts and the CLASI host-file section. |
+| [`clasi.tools`](../tools/DESIGN.md) (`tools/`) | MCP tool functions: the agent-facing surface over artifact and process operations. |
 
-Note on `design/`'s doc filename: its mechanically-derived single-root slug would
-otherwise be `design.md`, colliding with this document's own reserved filename
-(`clasi.design.paths.SYSTEM_DOC_NAME`). Ticket 010 (`clasi.design.paths`) added a
-collision fallback: when a subsystem's slug would equal the system-doc name, the
-root-qualified form is used instead, so `design/` resolves to `clasi-design.md`.
-This is the only subsystem in this doc set whose slug includes the source-root
-name — every other subsystem here uses the plain single-root form (root name
-omitted) since none of the others collide.
+Note on naming: each subsystem's doc is simply `DESIGN.md` inside its own
+directory — there is no filename derivation, slugification, or
+collision handling anymore. A subsystem's identity is its path, and its
+doc's identity is that same path plus `/DESIGN.md`; two subsystems can
+never collide on a doc name the way two `docs/design/<slug>.md` files
+could under the old central-directory model. (The old model's
+`clasi-design.md` collision-fallback naming rule — needed only because
+`design/`'s mechanical slug would otherwise equal the reserved
+`design.md` system-doc name — no longer applies to anything: the system
+doc and every subsystem doc now live in structurally different places by
+construction.)
 
 ## `clasi-core`: Loose Top-Level Modules
 
@@ -48,10 +50,10 @@
 also has a substantial set of top-level `.py` files with no enclosing
 subdirectory — these are not picked up by the mechanical subsystem
 enumeration (`clasi.design.store._subsystem_dirs` only walks directories
-one level under a source root), so they have no dedicated per-file design
-doc or README in this doc set (see `clasi-design.md`'s Open Questions for
-the gap this leaves). They are described here narratively instead, grouped
-by rough responsibility:
+one level under a source root), so they have no dedicated per-file
+`DESIGN.md` in this doc set (see `design/DESIGN.md`'s Open Questions for
+the gap this leaves — unchanged by sprint 022). They are described here
+narratively instead, grouped by rough responsibility:
 
 **Artifact object model** — `sprint.py` (`Sprint`, OO wrapper around a
 sprint directory; `MergeConflictError`), `ticket.py` (`Ticket`, OO wrapper
@@ -101,10 +103,14 @@
 
 Every subsystem doc in this set is allowed to assume, without repeating:
 
-- **Artifacts are markdown files with YAML frontmatter**, read/written
-  through `Artifact` (`artifact.py`) and its per-type wrappers (`Sprint`,
-  `Ticket`, `Issue`). No subsystem should hand-parse frontmatter with its
-  own YAML calls.
+- **A subsystem's design doc is co-located with its code**, as
+  `<subsystem_path>/DESIGN.md` — no separate `README.md`, no frontmatter
+  required. Written/read through `clasi.design.store`
+  (`write_design_doc`/`read_design_doc`); never hand-constructed.
+- **Artifacts other than `DESIGN.md`** (sprints, tickets, issues) are
+  markdown files with YAML frontmatter, read/written through `Artifact`
+  (`artifact.py`) and its per-type wrappers (`Sprint`, `Ticket`, `Issue`).
+  No subsystem should hand-parse frontmatter with its own YAML calls.
 - **All git operations use the inline `subprocess.run(["git", ...],
   cwd=..., capture_output=True, text=True)` idiom** already established in
   `clasi.sprint`/`tools/artifact_tools.py` — no subsystem introduces a new
@@ -115,24 +121,41 @@
   installs and built wheels (`clasi.design.store.subsystem_template`,
   `clasi.schemas.loader`, `clasi.state_machine.loader` all follow this).
 - **MCP tools are thin wrappers, not where business logic lives** — see
-  `tools.md`'s Constraints. The artifact object model and the
+  `tools/DESIGN.md`'s Constraints. The artifact object model and the
   `clasi.design`/`clasi.state_machine`/`clasi.status` subsystems own the
   actual logic; `clasi.tools` exposes it.
-- **This doc set coexists with the frozen initiation docs** already in
+- **This doc set coexists with the frozen project-level docs** in
   `docs/design/` (`overview.md`, `specification.md`, `state-machines.md`,
-  `usecases.md`, `worktree-process.md`) at the same top level, per sprint
-  021's Open Question 2 — no filename collision occurs between the two
-  sets (confirmed by this bootstrap run; the eight subsystem docs above
-  are all named `clasi-<subsystem>.md`).
+  `usecases.md`, `worktree-process.md`) — these describe the whole
+  project or the SE process itself, not any one subsystem, so they have
+  no source directory to co-locate into and stay where they are. This
+  document (`design.md`) also stays in `docs/design/`, as the one
+  system-level design document with no single owning subsystem directory
+  of its own.
+
+## Sprint-Change Linkage
+
+A sprint that changes a subsystem's `DESIGN.md` records which doc(s) it
+touched via a `design_docs:` list (repo-relative `DESIGN.md` paths) in
+the sprint's own frontmatter — the default, lightweight linkage
+mechanism. For a doc whose location is stable for the sprint's duration,
+the sprint may additionally run it through the `design/` overlay
+lifecycle (seed / edit / generate-diffs / commit / apply) for
+diff-reviewable tracking, exactly as this document itself was updated by
+sprint 022. The overlay lifecycle's `apply` step resolves each overlay
+file's canonical target from the subsystem path it was seeded from, not
+from a flat shared directory — necessary once canonical docs live at N
+different per-subsystem locations instead of one shared `docs/design/`
+directory.
 
 ## Open Questions
 
 See each subsystem doc's own "Open Questions" section for subsystem-local
 gaps. The one system-level gap worth flagging here: the `clasi-core`
-loose-top-level-module grouping above is this bootstrap run's judgment
-call, not a mechanically-enforced subsystem — nothing in `clasi.design`
-validates that grouping stays accurate as top-level modules are added,
-removed, or renamed. A future sprint could resolve this by extending
+loose-top-level-module grouping above is a judgment call, not a
+mechanically-enforced subsystem — nothing in `clasi.design` validates
+that grouping stays accurate as top-level modules are added, removed, or
+renamed. A future sprint could resolve this by extending
 `clasi.design.store`'s subsystem enumeration to (optionally) name a
 synthetic "core" pseudo-subsystem for loose top-level files, with the
 validator treating it the same as a real directory-backed subsystem.
```
