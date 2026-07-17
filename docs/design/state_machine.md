---
source_paths:
- /Volumes/Proj/proj/ai-projects/clasi/src/clasi/state_machine
readme_path: /Volumes/Proj/proj/ai-projects/clasi/src/clasi/state_machine/README.md
---
# clasi.state_machine

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-16 · **Status:** stable

---

## 1. Purpose

`clasi.state_machine` is a small, generic state-machine evaluation engine: given a machine definition (states, invariants, transitions) and a context object, it determines which state the context is currently in and which transitions are fireable. It owns *evaluation* only — reading real project/sprint/ticket state and answering predicate questions is `clasi.status`'s job (via `ClasiStateReader`), and defining the YAML shape of a machine is `clasi.schemas`'s job. This subsystem is the seam between "declarative machine definition" and "is this artifact's declared status actually true right now" that `clasi.status.inconsistency` exists to check.

## 2. Orientation

Five modules plus a `predicates/` package:

- `models.py` — pure dataclasses (`Transition`, `State`, `Machine`, `TransitionResult`) and the full exception hierarchy (`StateMachineError` and its five subclasses). No I/O, no evaluation logic; every other module imports from here.
- `registry.py` — a module-level, write-once predicate registry. Predicates register themselves at import time via the `@predicate("name")` decorator (which does not wrap the function — it stores a reference and returns the original callable unchanged) and are looked up by name at evaluation time. `clear_registry` exists for test isolation only and must never be called in production code.
- `context.py` — the `StateReader` protocol (read-only interface predicates use to reach filesystem/git/DB state without doing I/O themselves) plus per-artifact-type context dataclasses, and `NullStateReader` for tests.
- `loader.py` — the only module that parses state-machine YAML; loads a named machine (`"project"`, `"sprint"`, or `"ticket"`) from `clasi/schemas/state-machines/<name>.yaml` via `importlib.resources`.
- `evaluator.py` — the computational core: `evaluate_state` (which state matches the current context, raising `NoMatchingStateError`/`AmbiguousStateError` if zero or more than one state's invariants hold), `inspect_transitions` (which outbound transitions from a state are fireable), and `evaluate_predicates` (evaluates a predicate list, capturing per-predicate exceptions rather than propagating them).
- `predicates/project.py`, `sprint.py`, `ticket.py` — the concrete predicate functions registered per artifact type.

## 3. Constraints and Invariants

- **Predicates must be pure and read-only:** the `StateReader` protocol has no write methods, by design, so predicates cannot have side effects on the state they're evaluating.
- **"Conditions + destination invariants" rule:** `inspect_transitions` automatically appends the destination state's invariants to a transition's own `conditions` as additional guards — a transition is fireable only when *both* hold. This is documented in `docs/design/state-machines.md` and enforced in `evaluator.py`; do not special-case a transition to skip destination-invariant checking without updating that doc too.
- **`clear_registry()` is test-only:** calling it in production code empties the write-once registry and breaks every subsequent predicate lookup for the life of the process.
- **Exactly one state must match a context, or evaluation fails loudly:** `NoMatchingStateError`/`AmbiguousStateError` exist so a machine definition bug (overlapping or gapped invariants) is caught at evaluation time rather than silently picking an arbitrary state.
- **`loader.py` is the only YAML parser for machine definitions:** mirrors `clasi.schemas.loader`'s same constraint for workflow schemas — one parsing entry point per data format.

## 4. Design

A `Machine` is a pure data object: a set of `State`s (each with invariant predicates) and `Transition`s (each with a source, destination, and guard predicates) for one artifact type. `evaluate_state` runs every state's invariants against the given context and requires exactly one match. `inspect_transitions` then unions each candidate transition's own `conditions` with its destination state's invariants before checking fireability, reporting per-transition which guard predicates are currently blocking it (not just true/false) — this is what lets `clasi.status.reporter` surface actionable "blocked_by" lists rather than a bare yes/no.

## 5. Interfaces

### Exposes
- **`loader.load_machine(name) -> Machine`:** load one of the three packaged machine definitions.
- **`evaluator.evaluate_state(machine, context) -> State`,** **`inspect_transitions(machine, state, context) -> list[TransitionResult]`,** **`evaluate_predicates(names, context) -> dict`:** the engine's full public API.
- **`registry.predicate(name)`** decorator and **`get_predicate(name)`** lookup: how predicate modules register themselves and how the evaluator resolves a predicate name.
- **`context.StateReader` protocol:** the contract any production or test state source must satisfy to be usable as a predicate's data source.

### Consumes
- **`clasi.schemas.state-machines/*.yaml`** (packaged data, not the `clasi.schemas` Python code) as the machine definitions `loader.py` parses.
- **`clasi.status.reader.ClasiStateReader`** (production `StateReader` implementation) supplies the real filesystem/git/DB-backed context this engine evaluates against — see the `status.md` doc for that side of the contract.

## 6. Open Questions / Known Limitations

- None known beyond what each module's own docstring already flags (e.g. `evaluator.py`'s destination-invariant rule is intentional but easy to overlook when adding a new transition).
