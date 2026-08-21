---
source_file: schemas-DESIGN.md
source_hash: 5342f39aa981cc73e68bb8ad573ab80f480f7c7325d108d5b517576356ab4cd7
---
# Diff: schemas-DESIGN.md

Comparison of the sprint overlay copy of `schemas-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- schemas-DESIGN.md (pristine)
+++ schemas-DESIGN.md (current)
@@ -26,6 +26,8 @@
 
 `loader.load()`/`load_from_dict()` validate in three passes after Pydantic's own structural validation: duplicate artifact `id`s, `requires` references pointing at unknown artifact IDs, and gate kinds outside the registered `_VALID_GATE_KINDS` set (`stakeholder-review`, `review`, `per-ticket`). All failures are collected into one `SchemaError` rather than raising on the first. `se-process/schema.yaml` and `solo-process/schema.yaml` are the two packaged workflow definitions this project ships (full SE ceremony vs. a lighter solo mode), each with its own `instructions/` subdirectory of artifact-specific guidance documents referenced by the schema's `instruction` fields.
 
+**As of sprint 031**: `se-process/schema.yaml`'s `stakeholder-review` artifact entry is deleted; `ticketing`'s `requires:` becomes `[architecture-review]` (was `[stakeholder-review]`). `ArtifactGraph.phases()` (and therefore `state_db_class.py`'s `_compute_phases()`, which is the sole consumer that turns this list into the DB's phase sequence) derives the new 7-value phase list with no code change beyond the YAML edit, since `graph.py` reads the artifact list positionally — this is the concrete instance of `graph.py`'s own "read-only, assumes valid and topologically sorted input" contract (see `## 3` below) doing real work: the phase-order fix is a pure data change in the schema this module owns, not a change to any evaluation logic. `stakeholder_approval` is no longer the gate that blocks reaching `ticketing`; it now gates `acquire_execution_lock` instead (a `tools/artifact_tools.py`-level check against the recorded gate, not a schema-level `gate:` field on any artifact — this schema's `gate:` mechanism only ever expressed "gate the *next artifact's* creation," which was exactly the contradiction sprint 031 fixes; relocating the check to the lock rather than inventing a new schema-level construct for "gate an action that isn't artifact creation" keeps this module's own scope — declarative artifact/gate structure — unchanged).
+
 ## 5. Interfaces
 
 ### Exposes
```
