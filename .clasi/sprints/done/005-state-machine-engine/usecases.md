---
status: approved
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 005 Use Cases

---

## SUC-001: Load a State Machine from YAML

- **Actor**: Python code (any caller — MCP tool, CLI command, test)
- **Preconditions**: A valid YAML file for one of the three machines (project, sprint, ticket) exists at `clasi/schemas/state-machines/<name>.yaml`.
- **Main Flow**:
  1. Caller invokes `load_machine("sprint")` (or equivalent).
  2. The loader reads the YAML file.
  3. The loader constructs and returns an in-memory `Machine` object containing typed `State` and `Transition` records.
- **Postconditions**: Caller holds a `Machine` object; all states, invariants, transitions, conditions, and action names are accessible as Python attributes.
- **Acceptance Criteria**:
  - [ ] Loading `project.yaml`, `sprint.yaml`, and `ticket.yaml` each produces a `Machine` without error.
  - [ ] Missing or malformed YAML raises a descriptive `MachineSyntaxError`.
  - [ ] Referencing an unknown predicate name in a state or transition raises at load time (or on first evaluation — acceptable either way, documented clearly).

---

## SUC-002: Register a Predicate Function

- **Actor**: Python module (predicate implementation file)
- **Preconditions**: The predicate registry is initialized (imported).
- **Main Flow**:
  1. A module-level function decorated with `@predicate("is_architecture_present")` is imported.
  2. The decorator registers the function under that name in the global predicate registry.
  3. Any subsequent lookup by name returns the function.
- **Postconditions**: The predicate is callable by name from any engine component.
- **Acceptance Criteria**:
  - [ ] `@predicate("is_architecture_present")` registers the function so `get_predicate("is_architecture_present")` returns it.
  - [ ] Registering the same name twice raises `DuplicatePredicateError`.
  - [ ] `list_predicates()` returns all registered names.

---

## SUC-003: Evaluate Current State

- **Actor**: Python code consuming the engine (e.g., sprint 006's status command)
- **Preconditions**: A `Machine` object is loaded; a matching context object (`ProjectContext`, `SprintContext`, or `TicketContext`) is constructed with the relevant filesystem/DB data; all invariant predicates referenced by the machine are registered.
- **Main Flow**:
  1. Caller invokes `evaluate_state(machine, context)`.
  2. The evaluator iterates over the machine's states.
  3. For each state, it calls each invariant predicate with the context.
  4. The evaluator returns the single state whose invariants all pass.
- **Postconditions**: Caller knows the current state name.
- **Acceptance Criteria**:
  - [ ] Returns the correct state when exactly one state's invariants hold.
  - [ ] Raises `NoMatchingStateError` when no state matches (drift detected).
  - [ ] Raises `AmbiguousStateError` when more than one state matches.
  - [ ] Predicate exceptions propagate without silent swallowing.

---

## SUC-004: Inspect Available Transitions

- **Actor**: Python code consuming the engine (e.g., sprint 006's status command)
- **Preconditions**: Current state is known (from SUC-003 or explicit); `Machine` object is loaded; context is available.
- **Main Flow**:
  1. Caller invokes `inspect_transitions(machine, state_name, context)`.
  2. For each outbound transition from the named state, the inspector evaluates each condition predicate.
  3. The inspector returns a list of `TransitionResult` objects, each carrying `name`, `to`, `fireable` (bool), and `blocked_by` (list of predicate names whose evaluation returned False).
- **Postconditions**: Caller has a complete picture of which transitions can fire and which cannot, and why.
- **Acceptance Criteria**:
  - [ ] A fireable transition has `fireable=True` and `blocked_by=[]`.
  - [ ] A non-fireable transition has `fireable=False` and `blocked_by` listing every failing predicate name.
  - [ ] Destination-state invariants are also evaluated and included in `blocked_by` when they fail (engine adds them automatically per design doc rule).
  - [ ] A state with no outbound transitions returns an empty list without error.

---

## SUC-005: Query Predicate Status for a Context

- **Actor**: Python code (diagnostic / status display)
- **Preconditions**: Predicates are registered; a context object is available.
- **Main Flow**:
  1. Caller invokes `evaluate_predicates(names, context)` with a list of predicate names.
  2. The engine calls each named predicate with the context.
  3. Returns a dict mapping name → bool (or name → exception if a predicate errored).
- **Postconditions**: Caller can show a human which predicates pass and which fail without running full state evaluation.
- **Acceptance Criteria**:
  - [ ] Returns correct True/False for each named predicate.
  - [ ] An unknown predicate name raises `UnknownPredicateError`.
  - [ ] Predicate exceptions are captured per-predicate and reported rather than propagating (diagnostic use case tolerates partial results).

---

## SUC-006: Implement the is_* Predicates for All Three Machines

- **Actor**: Engine internals (called by SUC-003 and SUC-004)
- **Preconditions**: Context objects carry access to the filesystem, state DB, and git state via a `StateReader` interface.
- **Main Flow**:
  1. A predicate such as `is_overview_present` is called with a `ProjectContext`.
  2. It queries the `StateReader` for the relevant fact (file exists, lock held, branch name, etc.).
  3. Returns True or False.
- **Postconditions**: All `is_*` names referenced in `project.yaml`, `sprint.yaml`, and `ticket.yaml` are implemented and registered.
- **Acceptance Criteria**:
  - [ ] Every predicate name appearing in the three YAML files has a corresponding registered Python function.
  - [ ] Predicates are pure: no writes, no side effects.
  - [ ] Each predicate is independently unit-testable by injecting a mock `StateReader`.
