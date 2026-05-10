---
sprint: "020"
---

# Use Cases — Sprint 020: Schema-driven workflow: YAML DAG of artifacts

## SUC-001: SE process schema declares the workflow as a DAG

**Actor**: CLASI developer (modifying workflow)

**Goal**: Change or extend the SE process workflow by editing a single YAML
file instead of three separate locations.

**Precondition**: The CLASI server starts and loads `se-process/schema.yaml`
at startup.

**Main flow**:

1. Developer opens `clasi/schemas/se-process/schema.yaml`.
2. Developer adds, removes, or rewires an artifact node (changing `id`,
   `requires`, or `gate` fields).
3. Developer restarts the server.
4. The loader parses and topo-sorts the updated schema; the derived `PHASES`
   list reflects the change.
5. All downstream enforcement (phase machine, skill instructions, dispatch
   routing) reflects the single edit with no other files touched.

**Outcome**: The workflow change propagates from schema to runtime with one
edit. No desyncs between `state_db_class.py`, skill bodies, and dispatch
logic.

**Use case covered by tickets**: 001, 002, 003, 005, 008

---

## SUC-002: Loader rejects malformed schemas at startup

**Actor**: CLASI developer or CI pipeline

**Goal**: Catch structural errors in a schema (cycles, missing deps, unknown
gate kinds, duplicate IDs) before the server serves any requests.

**Precondition**: A schema file with one or more structural errors exists at
the configured path.

**Main flow**:

1. Server startup calls `loader.load(path)`.
2. Loader parses the YAML and runs Pydantic validation (catches unknown
   fields, wrong types, missing required fields).
3. Loader checks for duplicate artifact IDs — raises `SchemaError` if found.
4. Loader resolves `requires` references — raises `SchemaError` for any
   reference to an unknown artifact ID.
5. Loader runs topological sort — raises `SchemaError` if a cycle is
   detected.
6. Loader validates each `gate.kind` against the known gate-kind registry —
   raises `SchemaError` for unknown kinds.
7. Server surfaces the error and refuses to start.

**Alternate flow (CI)**: `clasi schema validate <path>` runs the same loader
and exits non-zero, printing the `SchemaError` message.

**Outcome**: Malformed schemas are caught at load time, not at runtime when a
phase transition fails silently.

**Use case covered by tickets**: 002, 004, 010

---

## SUC-003: PHASES becomes derived from schema

**Actor**: CLASI server runtime

**Goal**: The phase sequence enforced by `state_db_class.py` matches the
artifact DAG without requiring manual synchronization.

**Precondition**: A valid schema is loaded at server startup. The feature flag
`CLASI_SCHEMA_PHASES` is set (or the flag is removed after migration).

**Main flow**:

1. Server startup loads the active schema via `loader.load(...)`.
2. `state_db_class.py` calls `schema.phases()` to obtain the ordered list of
   phase names (topological sort of artifact IDs plus gate ordering).
3. The returned list replaces the hardcoded `PHASES` constant for all phase
   transition logic.
4. Existing phase-machine behavior (gate requirements, lock checks, done
   detection) is unchanged — only the source of the phase list changes.

**Feature flag behavior**: When the flag is absent or disabled, the fallback
hardcoded `PHASES` list is used. This retains one release of backward
compatibility.

**Outcome**: Adding a phase to the schema adds it to enforcement automatically.
Removing a phase removes it from enforcement.

**Use case covered by tickets**: 008, 009

---

## SUC-004: Skill bodies load instruction prose from schema-referenced files

**Actor**: Team-lead agent invoking a skill

**Goal**: Skill bodies become thin stubs; all instructional prose lives in
`instructions/*.md` files referenced by the schema.

**Precondition**: The active schema has each artifact's `instruction:` field
pointing to an existing markdown file under `schemas/<process>/instructions/`.

**Main flow**:

1. Team-lead invokes a skill (e.g., `plan-sprint`).
2. Skill stub reads the active schema to find its artifact node.
3. Skill stub loads the instruction file from `artifact.instruction`.
4. The loaded prose is presented as the skill body — behavior is identical to
   the previous inline version.
5. If the instruction file is missing, the skill raises a clear error rather
   than silently presenting empty instructions.

**Outcome**: Updating a skill's instructional prose is a markdown file edit,
not a skill-file edit. All five affected skills (`plan-sprint`,
`execute-sprint`, `architecture-review`, `sprint-review`, `close-sprint`)
follow this pattern.

**Use case covered by tickets**: 006, 007

---

## SUC-005: `clasi schema validate` CLI subcommand

**Actor**: CLASI developer or CI pipeline

**Goal**: Validate an arbitrary schema file against the loader without starting
the full MCP server.

**Precondition**: `clasi` is installed and accessible on PATH.

**Main flow**:

1. Developer runs `clasi schema validate path/to/schema.yaml`.
2. CLI invokes `loader.load(path)`.
3. If the schema is valid, CLI prints "Schema valid." and exits 0.
4. If the schema is invalid, CLI prints the `SchemaError` message to stderr
   and exits non-zero.

**Outcome**: Schema validation is a lightweight one-liner usable in CI pre-commit
hooks and local iteration without a running server.

**Use case covered by tickets**: 010

---

## SUC-006: `clasi init --process` flag selects the workflow schema

**Actor**: Developer initializing a new CLASI project

**Goal**: Choose between the full SE process (`se`) and the leaner solo process
(`solo`) at project initialization.

**Precondition**: Both `se-process/schema.yaml` and `solo-process/schema.yaml`
exist as package data.

**Main flow**:

1. Developer runs `clasi init --process solo` (or `--process se`, the default).
2. `init_command.py` writes the selected process name to the project's CLASI
   config (`.clasi/config.yaml`).
3. Server startup reads the config and loads the corresponding schema.
4. The solo-process schema produces a leaner phase list: overview,
   sprint-plan, tickets, execution, close — no architecture-review or
   stakeholder gates.

**Alternate flow**: `clasi init` with no `--process` flag defaults to `se`.

**Outcome**: A solo developer can adopt CLASI without the full SE ceremony.
The abstraction is validated by producing a real second working workflow.

**Use case covered by tickets**: 011, 012, 013
