---
source_file: DESIGN.md
source_hash: 8948984d888950a91cfae5e2db89f6747c522bffad653f2f0047d5389a798e59
---
# Diff: DESIGN.md

Comparison of the sprint overlay copy of `DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- DESIGN.md (pristine)
+++ DESIGN.md (current)
@@ -1,6 +1,6 @@
 # clasi (source root)
 
-**Owner:** clasi maintainers · **Last reviewed:** 2026-07-22 · **Status:** stable
+**Owner:** clasi maintainers · **Last reviewed:** 2026-07-24 · **Status:** stable
 
 ---
 
@@ -64,7 +64,15 @@
   resolves artifact locations through `Project` properties, never by
   hardcoding `docs/`, `clasi/`, or `.clasi/` paths. This is what lets a
   project remap any artifact directory via `.clasi/config.yaml`'s `paths:`
-  map without touching code.
+  map without touching code. Sprint 025's design-overlay seed-path fix is
+  an instance of this invariant being repaired rather than newly
+  introduced: `tools/artifact_tools.py`'s `seed_sprint_design_overlay`
+  previously resolved every `doc_names` entry relative to
+  `project.design_dir`, which silently mis-resolved a co-located
+  subsystem's canonical source path (e.g. `src/clasi/tools/DESIGN.md`);
+  it now resolves a path-separator-bearing entry relative to
+  `project.root` instead, matching how every other co-located path in the
+  package is resolved.
 - **The MCP server and CLI must stay behavior-equivalent:** both surfaces
   dispatch to the same operation functions (see `tools/` and the command
   modules). A fix applied on one path but not the other is a defect —
```
