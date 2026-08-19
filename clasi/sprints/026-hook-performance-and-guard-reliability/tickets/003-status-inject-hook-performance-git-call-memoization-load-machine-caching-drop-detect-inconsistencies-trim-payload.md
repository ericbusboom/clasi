---
id: '003'
title: 'status-inject hook performance: git-call memoization, load_machine caching,
  drop detect_inconsistencies, trim payload'
status: open
use-cases: [SUC-001]
depends-on: []
github-issue: ''
issue: hook-overhead-status-inject-dead-hooks-and-logging.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# status-inject hook performance: git-call memoization, load_machine caching, drop detect_inconsistencies, trim payload

## Description

`status-inject` (the `UserPromptSubmit` hook, `clasi hook status-inject`)
costs about 1.05-1.15s of blocking latency on every user prompt.
Profiling attributes this to: 28 uncached git subprocess calls per
`build_status` call (`ClasiStateReader`'s git-backed methods, e.g.
`is_on_sprint_branch` alone shells out 14x), `load_machine` re-parsing
the same three state-machine YAMLs about 20x with no cache, and
`detect_inconsistencies` (about 400ms of diagnostics) running inline in
the hot hook path. The injected YAML is also about 3.6KB (about 900
tokens), 61% of which is `available_transitions`/`blocked_by` noise for
empty pre-flight sprints. This ticket caches the redundant work and
trims the noise without changing status semantics for the common case
(a project with active ticketed sprints).

## Acceptance Criteria

- [ ] `ClasiStateReader`'s git-subprocess-backed methods memoize their
      result per instance (per hook invocation) — repeated calls to the
      same git query within one `build_status` call shell out once, not
      once per predicate.
- [ ] `state_machine.loader.load_machine` is wrapped with
      `functools.lru_cache` (or equivalent process-lifetime cache) —
      the three packaged machine definitions (`project`, `sprint`,
      `ticket`) are parsed once per process, not once per call.
- [ ] The `status-inject` hook path no longer calls
      `detect_inconsistencies`; `clasi status` (CLI) and the
      project-status skill still call it, unchanged.
- [ ] Injected YAML drops `available_transitions`/`blocked_by` detail
      for empty pre-flight sprints (no active or ticketed sprint);
      status YAML for a project with active ticketed sprints is
      unchanged apart from this trim.
- [ ] `time clasi hook status-inject < captured-payload.json`: before
      about 990ms-1.1s, after under 200ms.
- [ ] Git-subprocess call count per invocation drops from about 28 to
      about 3 (verified via a debug counter or mock call-count
      assertion, not just wall-clock variance).
- [ ] `load_machine` parse count per invocation drops from about 20 to 3
      (one per machine name).
- [ ] Full existing test suite passes, including any existing
      status-shape regression tests.

## Implementation Plan

**Approach**: Add an instance-scoped cache to `ClasiStateReader`
(`src/clasi/status/reader.py`) for its git-subprocess methods — a dict
keyed by the git command/args, populated lazily on first call within
that reader instance's lifetime, never persisted across instances. Wrap
`state_machine.loader.load_machine` with `functools.lru_cache(maxsize=None)`
(the three machine names are the entire keyspace, and the packaged YAML
never changes within a process's lifetime — see this sprint's `design/`
overlay note in `state_machine-DESIGN.md`). Remove the
`detect_inconsistencies` call from the status-inject hook handler in
`hook_handlers.py` specifically (leave the CLI and project-status skill
callers untouched). Trim the YAML-building step (likely in
`status/reporter.py` or the hook handler's serialization step) to omit
`available_transitions`/`blocked_by` when a sprint's pre-flight state is
empty.

**Files to modify**:
- `src/clasi/status/reader.py` (`ClasiStateReader` git methods).
- `src/clasi/state_machine/loader.py` (`load_machine`).
- `src/clasi/hook_handlers.py` (status-inject handler: drop
  `detect_inconsistencies` call, trim payload).
- Possibly `src/clasi/status/reporter.py` if the trim belongs there
  instead of in the hook handler.
- Test modules covering `ClasiStateReader`, `load_machine`, and the
  status-inject hook handler.

**Testing plan**: Mock/count git subprocess invocations and
`load_machine` calls across a realistic `build_status` call (a fixture
project with multiple sprints/tickets) to verify the call-count
reductions structurally, not just via timing. Add a `time`-based
before/after measurement using a captured real payload. Add a
regression test comparing full status YAML output (project with active
ticketed sprints) before and after the trim, asserting only the
intended fields are dropped and only for the empty-pre-flight case.

**Documentation updates**: This sprint's `design/` overlay
(`status-DESIGN.md`, `state_machine-DESIGN.md`) already documents these
caching changes at the module level.
