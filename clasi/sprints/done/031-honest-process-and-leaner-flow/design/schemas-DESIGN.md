# clasi.schemas

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-16 · **Status:** stable

---

## 1. Purpose

`clasi.schemas` defines and validates the two declarative data formats that drive CLASI's process: workflow schemas (which artifacts a process requires, their dependency DAG, and their approval gates) and state-machine definitions (which states a sprint/ticket/project can be in and what predicates gate each transition). It owns "is this declarative config internally valid and self-consistent" — a problem distinct from *evaluating* a state machine against live project state (that's `clasi.state_machine`'s job) or storing workflow progress (that's `state_db_class.py`'s job).

## 2. Orientation

Two independent halves sharing this directory only because both are "schema validation for a YAML-defined structure":

- **Workflow schemas** (`loader.py`, `models.py`, `graph.py`, plus the packaged `se-process/schema.yaml` and `solo-process/schema.yaml` data files with their own `instructions/` subdirectories): `models.py` defines the Pydantic shape (`WorkflowSchema`, `ArtifactSpec`, `GateSpec`); `loader.py` is the *only* module permitted to parse schema YAML, running Pydantic validation plus structural checks (duplicate artifact IDs, dangling `requires` references, unknown gate kinds, topological ordering) and raising `SchemaError` with every collected failure; `graph.py`'s `ArtifactGraph` is a read-only query wrapper over an already-loaded, already-sorted `WorkflowSchema` for callers (state DB, skill stubs) that need to ask "what are this artifact's dependents" without re-parsing YAML.
- **State-machine definitions** (`state-machines/project.yaml`, `sprint.yaml`, `ticket.yaml`): pure YAML data files (no Python here) defining states, invariants, and transitions per artifact type. Parsed by `clasi.state_machine.loader`, not by anything in this directory.

## 3. Constraints and Invariants

- **`loader.py` is the only module allowed to parse schema YAML:** the module's own docstring states this. Adding a second YAML-parsing entry point for workflow schemas anywhere else in the codebase creates two sources of truth for what makes a schema valid.
- **`load_from_dict` and `load` must run the identical validation/structural-check sequence:** `load_from_dict` exists specifically so tests can construct schema dicts in-memory without file I/O; letting it drift from `load`'s checks would make tests pass against rules the file-loading path doesn't actually enforce.
- **`ArtifactGraph` is read-only and assumes its input is already valid and topologically sorted:** it performs no validation of its own — passing it an unvalidated or unsorted `WorkflowSchema` produces undefined query results, not an error.
- **The `state-machines/` YAML files here are data only, consumed elsewhere:** this directory does not evaluate state machines; do not add evaluation logic here — that belongs in `clasi.state_machine`.

## 4. Design

`loader.load()`/`load_from_dict()` validate in three passes after Pydantic's own structural validation: duplicate artifact `id`s, `requires` references pointing at unknown artifact IDs, and gate kinds outside the registered `_VALID_GATE_KINDS` set (`stakeholder-review`, `review`, `per-ticket`). All failures are collected into one `SchemaError` rather than raising on the first. `se-process/schema.yaml` and `solo-process/schema.yaml` are the two packaged workflow definitions this project ships (full SE ceremony vs. a lighter solo mode), each with its own `instructions/` subdirectory of artifact-specific guidance documents referenced by the schema's `instruction` fields.

**As of sprint 031**: `se-process/schema.yaml`'s `stakeholder-review` artifact entry is deleted; `ticketing`'s `requires:` becomes `[architecture-review]` (was `[stakeholder-review]`). `ArtifactGraph.phases()` (and therefore `state_db_class.py`'s `_compute_phases()`, which is the sole consumer that turns this list into the DB's phase sequence) derives the new 7-value phase list with no code change beyond the YAML edit, since `graph.py` reads the artifact list positionally — this is the concrete instance of `graph.py`'s own "read-only, assumes valid and topologically sorted input" contract (see `## 3` below) doing real work: the phase-order fix is a pure data change in the schema this module owns, not a change to any evaluation logic. `stakeholder_approval` is no longer the gate that blocks reaching `ticketing`; it now gates `acquire_execution_lock` instead (a `tools/artifact_tools.py`-level check against the recorded gate, not a schema-level `gate:` field on any artifact — this schema's `gate:` mechanism only ever expressed "gate the *next artifact's* creation," which was exactly the contradiction sprint 031 fixes; relocating the check to the lock rather than inventing a new schema-level construct for "gate an action that isn't artifact creation" keeps this module's own scope — declarative artifact/gate structure — unchanged).

## 5. Interfaces

### Exposes
- **`loader.load(path) -> WorkflowSchema`** / **`load_from_dict(data) -> WorkflowSchema`:** validated, structurally-checked schema; raises `SchemaError` with all failures on any problem.
- **`models.WorkflowSchema`, `ArtifactSpec`, `GateSpec`, `SchemaError`:** the Pydantic shape and exception type every other schema consumer imports.
- **`graph.ArtifactGraph(schema)`:** read-only DAG query interface (phases, dependents, dependencies) over a loaded schema.
- **Packaged YAML data** (`se-process/`, `solo-process/`, `state-machines/`): read via `importlib.resources`, not relative file paths, so they resolve correctly under both editable installs and wheels.

### Consumes
- **Pydantic** for schema model validation — no CLASI-internal dependency.
- Nothing else in `clasi` — this is a low-level, near-leaf subsystem; `clasi.state_machine` and `state_db_class.py` depend on it, not the reverse.

## 6. Open Questions / Known Limitations

- Whether `se-process` and `solo-process` will diverge further (more artifact types, different gate kinds) or eventually merge into a single configurable schema is not resolved here.
