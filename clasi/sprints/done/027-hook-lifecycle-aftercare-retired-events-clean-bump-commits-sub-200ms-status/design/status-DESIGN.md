# clasi.status

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-16 · **Status:** stable

---

## 1. Purpose

`clasi.status` assembles the answer to "what is the current state of this project, its sprints, and their tickets, and what should the requesting agent do next" by evaluating `clasi.state_machine` machines against real project state and formatting the result for a specific agent's scope. It owns turning declarative state-machine evaluation into a concrete, agent-consumable status report — the engine itself (`clasi.state_machine`) has no idea what a sprint or a ticket actually is; this subsystem is where that real-world grounding happens.

## 2. Orientation

Five modules, roughly a pipeline from raw state to scoped output:

- `reader.py` — `ClasiStateReader`, the production implementation of `clasi.state_machine.context.StateReader`. Reads real data from three sources (filesystem path/markdown checks, `git` via subprocess, and `StateDB`/SQLite) and returns safe defaults on any failure rather than raising. As of sprint 026, its git-subprocess-backed methods (`git_branch`, `default_branch`, `branch_merged`, etc.) memoize their result per `ClasiStateReader` instance — a single status-inject hook invocation, which evaluates the same git query many times across the project/sprint/ticket machines, now shells out once per distinct query instead of once per predicate (about 28 calls collapsed to about 3 for a typical invocation). The cache is instance-scoped and lives only as long as the hook process; there is no cross-invocation cache to invalidate. As of sprint 027, the 2-3 real `subprocess.run` calls that survive that memoization (`git branch --show-current`, `git symbolic-ref refs/remotes/origin/HEAD`, `git branch --merged <default>`) are further collapsed — each spawn costs about 20-30ms of OS process-creation overhead that no amount of in-process caching removes, identified by ticket 007 (sprint 026) as the dominant remaining cost once sprint-count-scaling was fixed. The exact technique (direct `.git/HEAD`/ref reads, a single batched plumbing call, or both) is a ticket-time, measurement-driven decision rather than a locked-in mechanism — see sprint 027's Design Rationale. `StateReader`'s public method signatures are unchanged; this is an internal implementation change only.
- `reporter.py` — `StatusReporter` evaluates the project/sprint/ticket machines against a `StateReader` and assembles the full nested status dict (project state, per-sprint state and tickets, available transitions with `blocked_by` lists, issue counts). Its `exclude_done`-gated sprint sweep (`_build_sprints_block`, used only by the status-inject hook path) skips a sprint's own machine evaluation and its tickets' entirely for any sprint `_is_terminal_sprint` classifies as archived — as of sprint 026 ticket 007, that check matches declared `status: done` **or** `status: closed` (the sprint machine's own terminal state name, distinct from the ticket machine's `done`) and, independently, physical location under the project's `sprints/done/` archive directory regardless of what `status:` says. Before this widening, sprints archived with `status: closed` (the majority of this project's own archive) leaked past the `exclude_done` filter and were fully re-evaluated on every status-inject invocation — 7 sprints instead of 1, about 137 `get_sprint()` / 1,816 `read_frontmatter()` calls per prompt in this repo.
- `inconsistency.py` — detects state drift: cases where an artifact's frontmatter `status:` field disagrees with what the state machine computes, reporting each as a `state_drift` entry naming which invariant predicates evaluated false (or raised) and why. As of sprint 026, the `status-inject` hook path (`UserPromptSubmit`, fired on every prompt) no longer calls this module — running the full drift-detection pass on every prompt cost about 400ms for no per-prompt benefit. `clasi status` (the CLI command) and the `project-status` skill still call it unchanged; drift detection remains a deliberate, on-demand action, not something the hot hook path pays for by default.
- `narrowing.py` — `narrow_status(full_dict, agent, ...)` filters the full team-lead-scoped dict down to what a `sprint-planner` or `programmer` agent is allowed to see (team-lead: unchanged; sprint-planner: one sprint, no per-ticket detail; programmer: one ticket, summarized parent sprint), with an explicit `notes.fallback` when the narrowing agent didn't supply the ID needed to narrow precisely.
- `formatting.py` — pure `to_yaml`/`to_json` serializers for the final dict, no logic beyond serialization.

## 3. Constraints and Invariants

- **`ClasiStateReader` methods never raise; they return safe defaults (`False`/`""`/`None`/`0`) on failure:** a broken git repo or missing file must degrade the status report, not crash it — status reporting has to work even when the project itself is in a partially-broken state, which is exactly when an agent most needs to see status.
- **Per-invocation memoization must not become cross-invocation state:** the sprint-026 git-call cache lives on the `ClasiStateReader` instance and is never persisted or shared across hook processes — each hook invocation constructs its own reader and starts with an empty cache, so a stale git result can never survive past the process that produced it.
- **`narrow_status` scoping is a security/context-discipline boundary, not just a convenience filter:** a `programmer` agent must not see other tickets' or sprints' detail through the status tool — this is deliberate agent-scope isolation, not an arbitrary truncation, and must not be "helpfully" loosened.
- **`inconsistency.py` only detects drift; it never corrects it:** fixing a drifted artifact is a separate, deliberate action elsewhere (e.g. `update_ticket_status`), never an automatic side effect of computing status.
- **`formatting.py` is pure serialization:** no status-computation logic belongs here; adding any would blur the reporter/formatter boundary the module split was meant to keep clean.

## 4. Design

`StatusReporter` is the orchestration point: for the project and for each sprint and ticket, it loads the corresponding `clasi.state_machine` machine, evaluates the current state via a `ClasiStateReader`-backed context, and calls `inspect_transitions` to compute `available_transitions` with per-transition `blocked_by` predicate names — this is what gives the output dict its "next step" usefulness rather than being a bare status label. `inconsistency.py` runs independently over the same evaluated states, comparing each artifact's declared frontmatter status against the computed one. `narrow_status` is the last step before formatting, applied by the MCP `get_status` tool according to the calling agent's declared role.

## 5. Interfaces

### Exposes
- **`reader.ClasiStateReader`:** production `StateReader`; the concrete class most other status-consuming code instantiates directly.
- **`reporter.StatusReporter`:** `.report()` (or equivalent) returning the full nested status dict — see `reporter.py`'s docstring for the exact output shape.
- **`inconsistency` module functions:** drift detection, returning a list of `state_drift` dicts.
- **`narrowing.narrow_status(status_dict, agent, sprint_id=None, ticket_id=None)`:** agent-scoped filtering of a full status dict.
- **`formatting.to_yaml(d)` / `to_json(d)`:** final serialization, used by the CLI (`clasi status`, YAML default) and MCP `get_status` tool (JSON default) respectively.

### Consumes
- **`clasi.state_machine`** for machine loading and evaluation — this subsystem supplies the `StateReader` implementation and the real artifacts; the engine supplies the evaluation logic.
- **`clasi.state_db_class.StateDB`** (execution lock, sprint phase, sprint gate state) and **git** (branch name, default branch) as two of `ClasiStateReader`'s three data sources, alongside direct filesystem reads.

## 6. Open Questions / Known Limitations

- None recorded beyond what individual module docstrings already note.
