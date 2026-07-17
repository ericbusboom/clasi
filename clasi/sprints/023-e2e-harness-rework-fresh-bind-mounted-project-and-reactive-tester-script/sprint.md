---
id: '023'
title: 'E2E Harness Rework: Fresh Bind-Mounted Project and Reactive Tester Script'
status: planning-docs
branch: sprint/023-e2e-harness-rework-fresh-bind-mounted-project-and-reactive-tester-script
worktree: false
use-cases: []
issues:
- clasi-e2e-harness-rework-fresh-bind-mounted-project-reactive-tester-script.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 023: E2E Harness Rework: Fresh Bind-Mounted Project and Reactive Tester Script

## Goals

Make `tests/e2e/` actually test CLASI end-to-end on a fresh project running
current code, and make the tester (host-side driving agent) behave like a
human stakeholder instead of executing a scripted rubric of verbatim
prompts. Concretely: replace the never-wiped named Docker volume with a
guarded, probed bind mount; remove the second divergent launcher; default
to building and testing the local working tree instead of a stale pinned
tag; parameterize the model with a modern default; fix `validate.sh` to
check the artifact paths clasi actually produces; and rewrite `AGENTS.md`
as a reactive situation→action script backed by a stakeholder-persona
document.

## Problem

The harness silently drifted from what it claims to test:

- `start.sh` mounts a named volume (`clasi-data`) that is never deleted —
  every run reuses stale project state from prior runs, and `stop.sh`
  only removes the container, not the volume.
- A second launcher, `start-container.py`, bind-mounts a different
  directory, overrides the entrypoint so `clasi init` never runs, and
  produced a zombie container because OrbStack could not materialize a
  bind mount from `/Volumes/Proj` (docker reported success while writes
  landed VM-local, invisible on the host).
- `validate.sh` checks paths clasi has never produced
  (`docs/clasi/overview.md`, `docs/clasi/sprints/NNN/planning-docs/`,
  `close-report.md`) — the real layout is `clasi/sprints/{NNN}-{slug}/`
  with `sprint.md`, `tickets/`, `tickets/done/`, closed sprints archived
  to `clasi/sprints/done/`, and overview at `docs/design/overview.md`.
  Every validation check in the current script fails against real clasi
  output, by construction.
- `Dockerfile` defaults `CLASI_SOURCE` to a pinned, already-stale git tag
  — unflagged runs test old code, not the working tree.
- The model is hardcoded to Sonnet via OpenRouter with no way to bump the
  default without editing the script.
- `AGENTS.md` hands the driving agent a fixed list of verbatim sprint
  prompts and a rigid ten-step script — nothing like how the stakeholder
  actually drives CLASI (conversational, reactive, no slash commands).

## Solution

Rework the harness around one storage strategy (bind mount, probed for
real host-side visibility — never trust a docker exit code on OrbStack)
with a guarded wipe for fresh-by-default and an explicit `--resume`
opt-out. Rebuild the image's `clasi` install from the working tree by
default (`CLASI_SOURCE=local`, wheel built fresh each run) rather than a
pinned tag. Parameterize the model via `E2E_MODEL` (default
`anthropic/claude-opus-4.8`) baked into the container's env so `claude -p`
calls need no `--model` flag. Rewrite `validate.sh`'s path checks against
the real artifact layout (ground truth: `src/clasi/project.py`'s
`ARTIFACT_PATH_DEFAULTS`, and `close_sprint`'s archival to
`clasi/sprints/done/` in `src/clasi/tools/artifact_tools.py`) and drop
checks for artifacts clasi never produces. Delete the divergent
`start-container.py` launcher entirely. Replace `AGENTS.md`'s verbatim
prompt script with a reactive situation→action playbook, backed by a new
`stakeholder-persona.md` capturing how the stakeholder actually talks to
CLASI (mined from real session transcripts, preserved verbatim per the
issue's Appendix A).

The issue's Proposed fix section is decision-complete on every mechanism
(probe design, wipe guard, env-file shape, entrypoint fail-loud
semantics, path corrections, file inventory) — this sprint structures
that material into tickets, it does not re-derive it.

## Success Criteria

- Bind mount is proven host-visible by an explicit probe before any run
  proceeds — the exact failure mode that broke `start-container.py`
  (VM-local writes, docker reporting success) cannot recur silently.
- `./start.sh` wipes prior project state by default; `./start.sh --resume`
  preserves it; a stale non-empty project dir without `--resume` fails
  loudly instead of silently re-initializing.
- The container under test runs the current working tree's `clasi` by
  default, not a pinned tag.
- `validate.sh` checks paths that match what `clasi init` / sprint
  planning / `close_sprint` actually produce, and completes to its footer
  with exit 1 (not a crash) against an empty fresh project.
- `AGENTS.md` contains no verbatim subject prompts — it is a
  situation→action script that points at `stakeholder-persona.md` for
  phrasing.
- `start-container.py` is deleted; `start.sh` is the only launcher.
- The smoke-test table in the issue's Verification section passes (or,
  for the one check requiring `OPENROUTER_API_KEY`, is explicitly marked
  blocked rather than failed if the key is unset).
- The repository's own `pytest` suite passes.

## Scope

### In Scope

- `tests/e2e/start.sh` — bind-mount probe, guarded wipe, `--resume`,
  local-wheel build, env-file model parameterization.
- `tests/e2e/stop.sh` — `--wipe` flag, legacy volume sweep.
- `tests/e2e/entrypoint.sh` — loud-fail init guard, resume detection,
  consistent step numbering, explicit `git init -b master`.
- `tests/e2e/Dockerfile` — `CLASI_SOURCE=local` default.
- `tests/e2e/validate.sh` — path corrections to the real clasi artifact
  layout; drop checks for artifacts clasi never produces; add exact-string
  checks from the guessing-game spec.
- `tests/e2e/.gitignore`, `tests/e2e/.dockerignore` — `e2e-project/`
  entries.
- Delete `tests/e2e/start-container.py`.
- Rewrite `tests/e2e/AGENTS.md` as a reactive situation→action script.
- New `tests/e2e/stakeholder-persona.md`, sourced from the issue's
  Appendix A (verbatim quotes preserved).
- Smoke verification of the above per the issue's Verification table,
  plus the repository's pytest suite.

### Out of Scope

- Full 4-sprint end-to-end harness runs — the stakeholder triggers those
  personally; this sprint's own verification is smoke-test only.
- `clasi/issues/role-guard-blocks-plan-mode-plans-dir.md` — a separate,
  unrelated issue; stays in the pool.
- Sprints 020-022 declared-closed/computed-pre-flight state drift —
  pre-existing, unrelated, not touched.
- Any change to `src/clasi` itself. This sprint touches only the test
  harness; clasi's own source, MCP tools, and process gates are unchanged.
- One-time host docker cleanup (zombie containers, stale volume/image) —
  already performed by the team-lead outside sprint process.

## Test Strategy

This sprint's own verification is a smoke test, per the issue's explicit
scope decision (the stakeholder runs full 4-sprint validation personally,
separately). Smoke verification exercises the mechanisms most likely to
regress silently — bind-mount host-visibility, fresh-vs-resume state
handling, the stale-state loud-fail guard, local-code freshness, model
env propagation, and `validate.sh`'s own mechanical soundness against an
empty project — using the exact checks in the issue's Verification table.
Where a check depends on `OPENROUTER_API_KEY` (the one live model
round-trip), it is marked blocked rather than failed if the key is unset
in the sprint executor's environment, per the issue's guidance. The
repository's own `pytest` suite is also run, per standing repo rules for
any commit.

## Architecture

**Compact** — this sprint reworks one cohesive unit, the `tests/e2e/`
test harness, treated as a single module for sizing purposes: it
introduces no new cross-module dependency into `src/clasi` (the harness
already depended on `clasi` as the system under test; that relationship
is unchanged), no dependency-direction change, and no data-model change.
It touches many files, but they are all facets of one component (the
harness) coordinating around a single new contract (bind-mount-with-probe
+ guarded wipe), not several independently-changing modules. `src/clasi`
itself — clasi's own architecture, MCP tools, and process gates — is not
touched by this sprint; `docs/design/` is not updated because
`tests/e2e/` is test harness, not one of the documented `sources:
[src/clasi]` subsystems the design-doc opt-in (`design_docs: enabled` in
this repo's `.clasi/config.yaml`) covers. No diagram is included per the
compact variant of the methodology — a single-module rework with no new
cross-module dependency has nothing a component diagram would clarify
beyond the plain-language description below.

### What Changed

**Module: `tests/e2e/` harness.** Purpose: drive a real, disposable clasi
project through Docker so the tester (host-side driving agent) can verify
CLASI's SE process end-to-end. Boundary: everything inside
`tests/e2e/` — the launcher, entrypoint, image definition, validator, and
the tester's own operating instructions. Outside the boundary: `src/clasi`
itself (consumed only as installable package + CLI, never modified) and
the host's Docker daemon (treated as an external dependency whose bind
semantics must be verified, not assumed).

Within that one module, five previously-inconsistent pieces are brought
into agreement on a single storage and freshness contract:

- **Storage**: named Docker volume (`clasi-data`, never wiped) replaced
  by a bind mount at `tests/e2e/e2e-project/` (or, if the repo-local bind
  doesn't materialize, `~/.clasi/e2e-project/` with a discoverable
  symlink), always passed to `docker -v` as a resolved physical path.
  Host-side visibility is asserted by an explicit probe
  (write-in-container, read-on-host) rather than inferred from a docker
  exit code — this is the direct fix for the exact failure mode that
  produced the zombie `start-container.py` container (OrbStack silently
  failing to materialize a bind from `/Volumes/Proj`).
- **Freshness**: fresh-by-default (remove container, then guarded
  contents-only wipe of the project dir, then run) with `--resume` as an
  explicit opt-out that skips the wipe and signals the container via
  `E2E_RESUME=1`.
- **Launcher**: `start-container.py`, a second launcher that bypassed the
  entrypoint and drifted from `start.sh`, is deleted. `start.sh` is the
  only entry point.
- **Code freshness**: `Dockerfile`'s `CLASI_SOURCE` build-arg defaults to
  `local` (working-tree wheel, built fresh by `start.sh` via `uv` each
  run) instead of a pinned tag that rots by construction. Pinning remains
  available as an explicit override.
- **Validation ground truth**: `validate.sh`'s path checks are rewritten
  against the real artifact layout (`ARTIFACT_PATH_DEFAULTS` in
  `src/clasi/project.py`: `clasi/sprints/`, `docs/design/`; archival to
  `clasi/sprints/done/` in `close_sprint`, per
  `src/clasi/tools/artifact_tools.py`) rather than an imagined one
  (`docs/clasi/...`, `close-report.md`, `planning-docs/` — none of which
  clasi produces).

Separately, the tester-facing documentation changes register: `AGENTS.md`
moves from a fixed script of verbatim subject prompts to a reactive
situation→action playbook, and a new `stakeholder-persona.md` supplies
the phrasing register that playbook points at instead of embedding it
inline.

### Why

Every one of these was silently defeating the harness's purpose: stale
state meant later runs weren't testing a fresh project; the second
launcher meant some runs never initialized clasi at all; wrong validate.sh
paths meant the rubric could never pass against real output; a pinned
Dockerfile tag meant "testing CLASI" quietly became "testing whatever
commit was tagged last"; and a verbatim prompt script tested the harness's
authors' phrasing, not whether a stakeholder driving CLASI conversationally
gets a working system. Fixing the mechanism (bind-mount + probe + guard)
without also fixing the validator and the tester script would leave the
harness able to run correctly but still report success/failure against
the wrong criteria.

### Impact on Existing Components

None outside `tests/e2e/` — additive and corrective within the harness
only. `src/clasi` is unmodified; no MCP tool, CLI command, or process gate
changes behavior. The harness's contract with clasi (installed as a
package, driven via the `claude` CLI and CLASI MCP tools inside the
container) is unchanged; only how the harness sets up and validates that
environment changes.

### Design Rationale

**Decision: probe host-visibility explicitly rather than trust docker's
bind-mount exit code.**
Context: `start-container.py`'s bind mount from `/Volumes/Proj` produced
a container where `docker run` succeeded but `/project` was dead —
OrbStack could not materialize the bind, and nothing surfaced that until
manual inspection.
Alternatives considered: (a) trust the exit code, as before — rejected,
it's precisely what failed silently; (b) require a named volume always —
rejected, that's the freshness bug this sprint fixes; (c) explicit
write-in-container/read-on-host probe before every run — chosen.
Consequences: adds one throwaway container run to every `start.sh`
invocation, but converts a silent, discovered-hours-later failure into an
immediate, loud one.

**Decision: guarded contents-only wipe, gated on the path ending in
`/e2e-project`.**
Context: fresh-by-default requires deleting prior state, but a wipe
routine is exactly the kind of code where a path-computation bug becomes
catastrophic (deleting `/`, `$HOME`, or a mount point).
Alternatives considered: (a) delete-and-recreate the directory itself —
rejected, breaks the symlink-to-`~/.clasi` fallback case, where the
symlink itself must survive; (b) no guard, trust the caller — rejected,
too dangerous for a script anyone can invoke; (c) refuse unless the
resolved path ends in `/e2e-project`, delete contents only via
`find ... -mindepth 1 -maxdepth 1 -exec rm -rf {} +`, never the dir/symlink
— chosen.
Consequences: the guard string is a hardcoded convention (`e2e-project`)
that both the canonical and fallback paths must honor; if that naming
ever changes, the guard must change with it or the wipe silently refuses
to run (safe failure mode, not a silent wrong one).

### Migration Concerns

None in the data-migration sense — this is a test harness, not a
production data path. Operational notes carried into `AGENTS.md` per the
issue: `uv` becomes a host prerequisite for the default local-wheel path
(pinning `CLASI_SOURCE` to a tag is the escape hatch if `uv` is
unavailable); on Linux hosts, container-uid-1000 file ownership could
make the host-side wipe hit permission errors (acceptable, documented,
not fixed by this sprint).

## Use Cases

Compact sprint — use cases below are brief (the harness has no formal
parent UC in `docs/design/usecases.md`, since `tests/e2e/` is test
infrastructure rather than a documented product subsystem; each SUC
stands alone).

### SUC-001: Tester starts a fresh e2e run
- **Actor**: Tester (host-side driving agent / stakeholder)
- **Preconditions**: Docker running; `OPENROUTER_API_KEY` set; no
  `--resume` flag passed.
- **Main Flow**:
  1. Tester runs `./start.sh`.
  2. Harness builds the image (local wheel by default), removes any
     existing container, probes bind-mount host-visibility, wipes prior
     project-dir contents (guarded), and starts the container.
  3. Harness waits for readiness and reports the project directory.
- **Postconditions**: Container is running against an empty project dir
  backed by a proven-host-visible bind mount; current working-tree
  `clasi` is installed inside.
- **Acceptance Criteria**:
  - [ ] A file written by the container appears on the host at the
        resolved project path.
  - [ ] A marker left by a prior run is gone after a fresh (non-resume)
        start.
  - [ ] `docker exec clasi-e2e clasi --version` reflects the current dev
        version, not a stale pinned tag.

### SUC-002: Tester resumes an interrupted run
- **Actor**: Tester
- **Preconditions**: A previous run's project state exists on the host
  bind-mounted path.
- **Main Flow**:
  1. Tester runs `./start.sh --resume`.
  2. Harness skips the wipe, passes `E2E_RESUME=1` into the container.
  3. Entrypoint detects `.clasi` + `.git` already present and skips
     re-initialization.
- **Postconditions**: Prior project state (sprints, tickets, git history)
  is intact; entrypoint logs show "Resuming," not a fresh init.
- **Acceptance Criteria**:
  - [ ] A marker file present before `--resume` is still present after.
  - [ ] Entrypoint does not run `clasi init` again.

### SUC-003: Entrypoint refuses to silently re-initialize stale state
- **Actor**: Entrypoint (inside container, no tester interaction)
- **Preconditions**: `/project` is non-empty and `E2E_RESUME` is not set
  (e.g., the wipe was somehow skipped or bypassed).
- **Main Flow**:
  1. Entrypoint checks whether `/project` is non-empty.
  2. Since resume was not requested, entrypoint fails loudly and exits
     non-zero rather than running `clasi init` over existing state.
- **Postconditions**: Container fails to come up cleanly; the failure is
  visible in `docker logs`, not masked as a successful fresh run.
- **Acceptance Criteria**:
  - [ ] Given a pre-populated, non-empty project dir and no resume flag,
        the entrypoint exits 1 with a clear message.

### SUC-004: Tester validates a completed run
- **Actor**: Tester
- **Preconditions**: Sprints/tickets have been driven to completion inside
  the container (out of scope for this sprint's own verification, but the
  mechanism being validated).
- **Main Flow**:
  1. Tester runs `./validate.sh`.
  2. Script checks real clasi artifact paths (`clasi/sprints/`,
     `docs/design/overview.md`, `tickets/done/` with `status: done`,
     archived sprint dirs under `clasi/sprints/done/`) plus code-quality,
     git-hygiene, and exact-string game-behavior checks.
  3. Script prints PASS/FAIL per check, reaches its footer, and exits
     with the correct status.
- **Postconditions**: Tester has an accurate PASS/FAIL rubric reflecting
  what clasi actually produced — not a rubric that fails by construction
  against invented paths.
- **Acceptance Criteria**:
  - [ ] Run against an empty fresh project, `validate.sh` prints only
        FAILs, reaches the footer, and exits 1 without crashing
        (`set -e` does not abort mid-script).
  - [ ] No check references `close-report.md`, `docs/clasi/...`, or
        `planning-docs/`.

### SUC-005: Tester drives CLASI conversationally, in persona
- **Actor**: Tester
- **Preconditions**: Container is running (SUC-001 or SUC-002 complete).
- **Main Flow**:
  1. Tester consults `AGENTS.md` for the situation it's currently in
     (fresh environment, sprint finished, subject stalled, between
     sprints, hit max-turns, artifacts look wrong).
  2. `AGENTS.md` describes what the prompt to the subject must *convey*
     for that situation and points at `stakeholder-persona.md` for how a
     real stakeholder would phrase it — never a verbatim prompt to copy.
  3. Tester composes a prompt in that register and sends it via
     `docker exec clasi-e2e claude -p ...`.
- **Postconditions**: The subject receives conversational, in-persona
  direction indistinguishable in style from the stakeholder's real usage
  patterns, not a fixed script.
- **Acceptance Criteria**:
  - [ ] `AGENTS.md` contains no verbatim subject prompt text for any
        sprint or OOP step.
  - [ ] `stakeholder-persona.md` exists and preserves the issue's
        Appendix A quotes verbatim.
  - [ ] Every situation in `AGENTS.md`'s playbook names what to convey and
        references the persona doc for phrasing.

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [ ] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Harness scripts: bind-mount probe, guarded wipe, resume, local-wheel build, path corrections | — |
| 002 | Tester docs: reactive AGENTS.md and stakeholder-persona.md | 001 |
| 003 | Smoke verification: harness mechanics and repo test suite | 001, 002 |

Tickets execute serially in the order listed.
