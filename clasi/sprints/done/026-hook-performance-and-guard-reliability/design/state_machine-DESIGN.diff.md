---
source_file: state_machine-DESIGN.md
source_hash: b6e12b17b876a8b410b7400fe47db243dd898ab91d5f1b97a1ee58dd3c843c36
---
# Diff: state_machine-DESIGN.md

Comparison of the sprint overlay copy of `state_machine-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- state_machine-DESIGN.md (pristine)
+++ state_machine-DESIGN.md (current)
@@ -15,7 +15,7 @@
 - `models.py` — pure dataclasses (`Transition`, `State`, `Machine`, `TransitionResult`) and the full exception hierarchy (`StateMachineError` and its five subclasses). No I/O, no evaluation logic; every other module imports from here.
 - `registry.py` — a module-level, write-once predicate registry. Predicates register themselves at import time via the `@predicate("name")` decorator (which does not wrap the function — it stores a reference and returns the original callable unchanged) and are looked up by name at evaluation time. `clear_registry` exists for test isolation only and must never be called in production code.
 - `context.py` — the `StateReader` protocol (read-only interface predicates use to reach filesystem/git/DB state without doing I/O themselves) plus per-artifact-type context dataclasses, and `NullStateReader` for tests.
-- `loader.py` — the only module that parses state-machine YAML; loads a named machine (`"project"`, `"sprint"`, or `"ticket"`) from `clasi/schemas/state-machines/<name>.yaml` via `importlib.resources`.
+- `loader.py` — the only module that parses state-machine YAML; loads a named machine (`"project"`, `"sprint"`, or `"ticket"`) from `clasi/schemas/state-machines/<name>.yaml` via `importlib.resources`. As of sprint 026, `load_machine` is wrapped with `functools.lru_cache`: the three packaged machine definitions never change within a process's lifetime, so a single status-inject invocation that evaluates all three machines (project, sprint, ticket) — and, across a sprint with several tickets, re-evaluates the sprint/ticket machines per artifact — now parses each YAML file once per process instead of once per `load_machine` call (about 20 re-parses collapse to 3, one per machine name).
 - `evaluator.py` — the computational core: `evaluate_state` (which state matches the current context, raising `NoMatchingStateError`/`AmbiguousStateError` if zero or more than one state's invariants hold), `inspect_transitions` (which outbound transitions from a state are fireable), and `evaluate_predicates` (evaluates a predicate list, capturing per-predicate exceptions rather than propagating them).
 - `predicates/project.py`, `sprint.py`, `ticket.py` — the concrete predicate functions registered per artifact type.
 
@@ -26,6 +26,7 @@
 - **`clear_registry()` is test-only:** calling it in production code empties the write-once registry and breaks every subsequent predicate lookup for the life of the process.
 - **Exactly one state must match a context, or evaluation fails loudly:** `NoMatchingStateError`/`AmbiguousStateError` exist so a machine definition bug (overlapping or gapped invariants) is caught at evaluation time rather than silently picking an arbitrary state.
 - **`loader.py` is the only YAML parser for machine definitions:** mirrors `clasi.schemas.loader`'s same constraint for workflow schemas — one parsing entry point per data format.
+- **`load_machine`'s cache is process-lifetime and keyed only on `name`:** safe because the packaged YAML a given installed `clasi` build reads never changes underneath a running process — there is no live-editing path for `clasi/schemas/state-machines/*.yaml` inside a single process's lifetime. Test code that needs a fresh parse across cases should not rely on this caching being disabled; it is a production-path optimization, not a testing concern to design around.
 
 ## 4. Design
 
```
