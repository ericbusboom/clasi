---
source_file: status-DESIGN.md
source_hash: 0cc05abec7696f15dc81cb5dc02c9f400722f6f346a06723ce0c8a60a88dea31
---
# Diff: status-DESIGN.md

Comparison of the sprint overlay copy of `status-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- status-DESIGN.md (pristine)
+++ status-DESIGN.md (current)
@@ -12,15 +12,16 @@
 
 Five modules, roughly a pipeline from raw state to scoped output:
 
-- `reader.py` — `ClasiStateReader`, the production implementation of `clasi.state_machine.context.StateReader`. Reads real data from three sources (filesystem path/markdown checks, `git` via subprocess, and `StateDB`/SQLite) and returns safe defaults on any failure rather than raising.
+- `reader.py` — `ClasiStateReader`, the production implementation of `clasi.state_machine.context.StateReader`. Reads real data from three sources (filesystem path/markdown checks, `git` via subprocess, and `StateDB`/SQLite) and returns safe defaults on any failure rather than raising. As of sprint 026, its git-subprocess-backed methods (`git_branch`, `default_branch`, `branch_merged`, etc.) memoize their result per `ClasiStateReader` instance — a single status-inject hook invocation, which evaluates the same git query many times across the project/sprint/ticket machines, now shells out once per distinct query instead of once per predicate (about 28 calls collapsed to about 3 for a typical invocation). The cache is instance-scoped and lives only as long as the hook process; there is no cross-invocation cache to invalidate.
 - `reporter.py` — `StatusReporter` evaluates the project/sprint/ticket machines against a `StateReader` and assembles the full nested status dict (project state, per-sprint state and tickets, available transitions with `blocked_by` lists, issue counts).
-- `inconsistency.py` — detects state drift: cases where an artifact's frontmatter `status:` field disagrees with what the state machine computes, reporting each as a `state_drift` entry naming which invariant predicates evaluated false (or raised) and why.
+- `inconsistency.py` — detects state drift: cases where an artifact's frontmatter `status:` field disagrees with what the state machine computes, reporting each as a `state_drift` entry naming which invariant predicates evaluated false (or raised) and why. As of sprint 026, the `status-inject` hook path (`UserPromptSubmit`, fired on every prompt) no longer calls this module — running the full drift-detection pass on every prompt cost about 400ms for no per-prompt benefit. `clasi status` (the CLI command) and the `project-status` skill still call it unchanged; drift detection remains a deliberate, on-demand action, not something the hot hook path pays for by default.
 - `narrowing.py` — `narrow_status(full_dict, agent, ...)` filters the full team-lead-scoped dict down to what a `sprint-planner` or `programmer` agent is allowed to see (team-lead: unchanged; sprint-planner: one sprint, no per-ticket detail; programmer: one ticket, summarized parent sprint), with an explicit `notes.fallback` when the narrowing agent didn't supply the ID needed to narrow precisely.
 - `formatting.py` — pure `to_yaml`/`to_json` serializers for the final dict, no logic beyond serialization.
 
 ## 3. Constraints and Invariants
 
 - **`ClasiStateReader` methods never raise; they return safe defaults (`False`/`""`/`None`/`0`) on failure:** a broken git repo or missing file must degrade the status report, not crash it — status reporting has to work even when the project itself is in a partially-broken state, which is exactly when an agent most needs to see status.
+- **Per-invocation memoization must not become cross-invocation state:** the sprint-026 git-call cache lives on the `ClasiStateReader` instance and is never persisted or shared across hook processes — each hook invocation constructs its own reader and starts with an empty cache, so a stale git result can never survive past the process that produced it.
 - **`narrow_status` scoping is a security/context-discipline boundary, not just a convenience filter:** a `programmer` agent must not see other tickets' or sprints' detail through the status tool — this is deliberate agent-scope isolation, not an arbitrary truncation, and must not be "helpfully" loosened.
 - **`inconsistency.py` only detects drift; it never corrects it:** fixing a drifted artifact is a separate, deliberate action elsewhere (e.g. `update_ticket_status`), never an automatic side effect of computing status.
 - **`formatting.py` is pure serialization:** no status-computation logic belongs here; adding any would blur the reporter/formatter boundary the module split was meant to keep clean.
```
