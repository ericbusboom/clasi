---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 016 Use Cases

These use cases cover the user-visible surface of the delta-spec sprint.
Each describes a concrete developer scenario. New scenarios use Given/When/Then.

The delta is a historical record and planning forcing-function. It does NOT
merge into source-of-truth docs. Canonical design docs are project-init
artifacts, frozen after initiation.

---

## SUC-001: Sprint planner authors a structured architecture delta at planning time

**Actor**: Sprint-planner agent (and the team-lead reviewing its output)

**Context**: The team-lead dispatches the sprint-planner for sprint 017.
The sprint has a `sprint.md` and `usecases.md` already written. The planner
must produce the architectural plan before writing tickets.

- **Given**: A sprint directory exists with `sprint.md` (status: planning)
  and `usecases.md`. The `architecture-delta.md` file does not yet exist.
  The sprint is in `planning-docs` phase.

- **When**: The sprint-planner agent invokes the `architecture-authoring`
  skill in brownfield/delta mode. The agent writes the structural changes
  for the sprint into `architecture-delta.md` using the required ADDED /
  MODIFIED / REMOVED / RENAMED section headings. MODIFIED entries describe
  the change in prose.

- **Then**: `architecture-delta.md` exists in the sprint directory. Every
  `####` item heading sits inside a `### <KIND> <Category>` section.
  The file can be parsed by `clasi sprint validate-delta` with zero errors.
  The sprint planner then writes tickets derived from the delta — not before it.

**Acceptance Criteria**:
- [ ] `architecture-authoring` skill documents the delta mode explicitly and
  forbids free prose outside delta sections for brownfield sprints.
- [ ] MODIFIED entries in the skill instructions say "describe the change in
  prose" — no requirement for full replacement content.
- [ ] The sprint-planner agent prompt references `architecture-delta.md` as
  the expected output artifact; `architecture-update.md` is not mentioned.
- [ ] A valid `architecture-delta.md` passes `validate-delta` with exit code 0.

---

## SUC-002: Architecture reviewer validates parse before semantic review

**Actor**: Sprint-planner agent running the architecture self-review step

**Context**: The sprint-planner has written `architecture-delta.md` and is
now running the architecture review inline (as required by the sprint-planner
agent instructions). The reviewer must catch format violations before wasting
time on semantic analysis.

- **Given**: `architecture-delta.md` exists in the sprint directory.

- **When**: The `architecture-review` skill is invoked for the sprint.

- **Then (happy path)**: The reviewer calls `clasi sprint validate-delta <id>`
  first. The parser returns zero errors. The reviewer then proceeds to
  semantic review (consistency, codebase alignment, design quality,
  anti-pattern detection, risks). The verdict is issued based on content.

- **Then (parse failure)**: The delta has a malformed section heading (e.g.,
  `### CHANGED Components` instead of `### MODIFIED Components`). The parser
  returns a specific error naming the line and the violation. The reviewer
  returns a REVISE verdict with the parse error text verbatim. No semantic
  review is performed. The sprint-planner fixes the delta and re-validates.

**Acceptance Criteria**:
- [ ] `architecture-review` skill documents the parser-first step as the first
  action in its process.
- [ ] A parse failure produces a REVISE verdict with the parser error message
  quoted in the verdict body.
- [ ] A parse-passing delta proceeds to full semantic review.
- [ ] The skill's process section says "validate-delta first; only proceed to
  semantic review if exit code is 0."

---

## SUC-003: Developer validates a delta file from the command line

**Actor**: Developer (or agent) working on sprint architecture

**Context**: A developer is editing `architecture-delta.md` for sprint 017
and wants to check format conformance before committing.

- **Given**: Sprint 017 exists. The developer has written (or partially
  written) `architecture-delta.md`.

- **When**: The developer runs `clasi sprint validate-delta 017` from any
  directory inside the project.

- **Then (valid delta)**: Exit code 0. Stdout reports the count of items
  found per KIND per Category (e.g., "ADDED Components: 2, MODIFIED
  Scenarios: 1"). No errors.

- **Then (invalid delta — item outside section)**: Exit code 1. Stderr (or
  stdout) reports the specific violation: line number, the offending heading,
  and a plain-English description of the rule it breaks (e.g., "Line 42:
  `#### Component: Foo` appears outside any `### <KIND> <Category>` section").

- **Then (invalid delta — MODIFIED with no body)**: Exit code 1. Error names
  the item and the rule: "Line 58: MODIFIED `Component: WorkerPool` has empty
  body. MODIFIED entries must describe the change in prose."

- **Then (delta file does not exist)**: Exit code 1. Error: "No
  architecture-delta.md found for sprint 017. If the sprint uses the old
  format, use architecture-update.md; validate-delta only applies to delta
  format files."

**Acceptance Criteria**:
- [ ] `clasi sprint validate-delta <id>` exists as a CLI subcommand.
- [ ] Exit code 0 on valid delta, 1 on any validation failure.
- [ ] Every documented rejection mode produces a specific error message with
  line number and rule name.
- [ ] Missing delta file is handled gracefully (not a Python traceback).

---

## SUC-004: PostToolUse hook surfaces parse errors immediately on save

**Actor**: Sprint-planner agent (or developer) editing `architecture-delta.md`
in a Claude Code session

**Context**: The agent is iteratively writing the delta. Each time the file
is saved (via the Write or Edit tool), the agent needs immediate feedback if
the format is broken — not discovery at review time.

- **Given**: A Claude Code session is active. The PostToolUse hook for
  `architecture-delta.md` saves is configured.

- **When**: The agent writes a partial delta that has an item heading outside
  a valid section (e.g., the agent forgot to write the `### ADDED Components`
  section header before writing `#### Component: ScheduleService`).

- **Then**: Within the same tool-use turn, the hook output reports the parse
  error: "architecture-delta.md validation: ERROR — Line 14: `#### Component:
  ScheduleService` appears outside any `### <KIND> <Category>` section."
  The file is NOT blocked (the write succeeds); the error is surfaced as a
  hook notification. The agent sees the error in the next turn and corrects
  it.

- **When (valid delta saved)**: The hook output reports: "architecture-delta.md
  validation: OK — 3 items parsed."

**Acceptance Criteria**:
- [ ] PostToolUse hook fires when `architecture-delta.md` is written or edited.
- [ ] Parse errors are surfaced in the hook output (visible to the agent in
  the next turn).
- [ ] The hook does not block the write on parse errors (validate-and-report,
  not validate-and-reject).
- [ ] Valid deltas produce a brief confirmation in the hook output.

---

## SUC-005: Accumulated deltas are the architecture history; code is the source of truth

**Actor**: Developer or team-lead asking "what is the current architecture?"

**Context**: Several sprints have closed. Each sprint produced an
`architecture-delta.md` that now lives under `docs/clasi/sprints/done/<id>/`.
The canonical design docs (`docs/design/specification.md`,
`docs/design/usecases.md`) were authored at project initiation and have not
been modified since. The developer wants to understand the current architecture.

- **Given**: Multiple closed sprints exist in `docs/clasi/sprints/done/`.
  Each has an `architecture-delta.md` describing the structural changes made
  during that sprint. The project-init docs are frozen.

- **When**: The developer wants to know the current architecture.

- **Then**: The developer reads the code (the authoritative source of truth)
  and supplements with the accumulated delta files — reading them in sprint
  order to understand the intended structural decisions at each point.
  The project-init docs provide the original baseline. No single snapshot doc
  exists; the history is the deltas.

- **When**: A sprint closes.

- **Then**: `Sprint.archive()` moves the sprint directory (including
  `architecture-delta.md`) intact to `done/<id>/`. No merge step executes.
  No source-of-truth docs are written. The delta is now part of the
  historical record.

**Acceptance Criteria**:
- [ ] `Sprint.archive()` does NOT include a merge step. Source-of-truth docs
  are not modified at sprint close.
- [ ] `architecture-delta.md` survives into `done/<id>/architecture-delta.md`
  after sprint close (as part of the moved directory).
- [ ] The SE overview, README, and sprint-planner documentation explicitly
  state: "canonical design docs are project-init artifacts — frozen after
  initiation. Deltas accumulate as historical record."
- [ ] No `clasi/delta/merge.py` is created in this sprint.
- [ ] The close-sprint skill and `Sprint.archive()` code contain no new merge
  logic.
