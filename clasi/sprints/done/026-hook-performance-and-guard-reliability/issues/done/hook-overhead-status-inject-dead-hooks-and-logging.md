---
status: done
sprint: '026'
tickets:
- 026-001
- 026-003
- 026-004
---

# Hook overhead: 1s status-inject per prompt, dead hooks taxing every Bash call, unusable hook log

## Description

Measured on this repo (external volume; 2,447 events in
`.clasi/log/hooks.log`):

- **status-inject costs ~1.05-1.15 s of blocking latency on EVERY user
  prompt.** `build_status` alone measures 990 ms. 315 logged invocations ≈
  5.5 minutes of accumulated pure wait. It also injects ~3.6 KB ≈ 900
  tokens of YAML per prompt, 61% of which is
  `available_transitions`/`blocked_by` noise for empty pre-flight sprints.
- **Every hook invocation pays a ~90-130 ms process-startup floor** before
  any logic runs; guard logic itself is only ~15-20 ms.
- **commit-check is dead code taxing every Bash call ~90 ms.** It reads
  `os.environ["TOOL_INPUT"]` (`src/clasi/hook_handlers.py:1615`), which
  Claude Code never sets (payload arrives on stdin); it has produced 0 of
  the 2,447 log lines. `TaskCreated`/`TaskCompleted` registrations have
  also never fired once.
- **The hook log cannot answer "what was blocked":** `_log_hook_event`
  reads `file_path` from the payload top level (`hook_handlers.py:295`) but
  Claude Code nests it under `tool_input`, so no blocked path is ever
  recorded (exactly 1 of 2,447 lines has one, from a synthetic test).
  Timestamps are `%H:%M:%SZ` with no date (:290), so events can't be
  separated across days.
- Not the problem: staleness checking is 0.6-1.1 ms with no subprocesses —
  don't spend effort there.

## Cause

`build_status` profile (990 ms): 28 uncached git subprocesses per call
(`src/clasi/status/reader.py:129,153,182`; `is_on_sprint_branch` alone
shells git 14×), ~2,174 frontmatter YAML parses sweeping every
sprint/ticket file, `load_machine` re-parsing the same 3 state-machine
YAMLs 20× with no cache (`src/clasi/state_machine/loader.py:22`), and
`detect_inconsistencies` (~400 ms of diagnostics,
`src/clasi/status/inconsistency.py`) run inline in the hook path.

Startup floor: `uv run` wrapper 30-50 ms (only in this repo's drifted
`.claude/settings.json`; the plugin's `hooks.json` uses bare `clasi` — the
installer would overwrite the prefix on re-init), Python + imports 60-80 ms
of which 33 ms is an eager `importlib.metadata.version("clasi")` at
`src/clasi/__init__.py:7`. Per role-guard invocation the logic layer also
calls `get_project()` 5×, parses `config.yaml` 3× (`Project._load_config`
has no cache), and opens 4 sqlite connections (each running WAL/foreign-key
PRAGMAs).

No hook registration sets a `timeout`, so the ~1.1 s status hook runs with
no explicit budget.

## Proposed fix

1. status-inject (target 990 ms → ~150 ms): memoize git calls per process
   (28 → about 3); `lru_cache` on `load_machine` (20 → 3); remove
   `detect_inconsistencies` from the hook path (keep it in the
   `clasi status` CLI and the project-status skill); trim the injected YAML
   (drop transition/blocked_by detail for empty pre-flight sprints).
2. Delete the dead registrations from `plugin/hooks/hooks.json` and the
   installer: commit-check (or fix it to read stdin — but it has never
   worked and was never missed), TaskCreated, TaskCompleted.
3. Lazy `__version__` via module `__getattr__` in `src/clasi/__init__.py`
   (−33 ms per hook process; only the staleness check needs it).
4. One cached `Project` and one sqlite connection per hook invocation.
5. Align this repo's `.claude/settings.json` with the plugin `hooks.json`
   (drop the `uv run` prefix drift) and set explicit `timeout` values on
   all hook registrations.
6. Fix `_log_hook_event`: read `file_path` from `tool_input`, add the date
   to timestamps. This is the prerequisite for re-measuring friction after
   any guard change.

## Verification

- `time clasi hook status-inject < captured-payload.json` before/after:
  expect under 200 ms after.
- `time clasi hook role-guard < captured-payload.json`: expect the
  startup-floor savings (no eager metadata scan; single config parse —
  observable via strace/dtruss open counts or a debug counter).
- Confirm commit-check / TaskCreated / TaskCompleted absent from the
  installed settings of a fresh `clasi init` fixture.
- After a working session, `.clasi/log/hooks.log` lines carry dated
  timestamps and a real `file_path` on block events.
- Existing test suite passes; status YAML for a project with active
  ticketed sprints is unchanged apart from the trimmed noise.

## Related

- `report-guard-friction-slowness-relax-tier-0-restrictions.md` —
  companion policy issue from the same investigation.
- `guard-dead-ends-no-ticket-gate-scope-and-close-sprint-recovery.md` —
  companion dead-end fixes.
- `mcp-stale-runtime-same-version-drift` (memory/prior finding): staleness
  machinery is cheap at 0.6-1.1 ms — perf work should leave it alone.
