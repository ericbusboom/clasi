---
id: '003'
title: 'Smoke verification: harness mechanics and repo test suite'
status: done
use-cases: []
depends-on:
- '001'
- '002'
github-issue: ''
issue: clasi-e2e-harness-rework-fresh-bind-mounted-project-reactive-tester-script.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Smoke verification: harness mechanics and repo test suite

## Description

Run the issue's Verification table end-to-end against the harness as
rewritten by tickets 001 and 002, plus the repository's own `pytest`
suite. This sprint's own verification is smoke-test only, per the
issue's explicit scope decision — the stakeholder triggers full
4-sprint harness runs personally, separately from this sprint.

**Environment note**: `OPENROUTER_API_KEY` is set and `uv` (0.11.21) is
available in the execution environment for this ticket, so the full
smoke table below — including the one live model round-trip — should run
to completion. The "mark blocked, not failed" fallback wording is a
contingency only, for the case where a required credential is
unexpectedly absent at execution time; it is not the expected path given
current environment state.

### Smoke checks (from the issue's Verification table)

| Property | Proof |
|---|---|
| Bind visible from host | `docker exec clasi-e2e touch /project/MARKER` → marker appears under `$(cd -P tests/e2e/e2e-project && pwd)` |
| Fresh start | after plain `./start.sh`, a previous MARKER is gone; logs show init ran, not "Resuming" |
| Resume | `touch MARKER; ./start.sh --resume` → MARKER survives; logs say "Resuming" |
| Stale-state guard | non-empty project dir + no `--resume` → entrypoint exits 1 loudly |
| Local code under test | `docker exec clasi-e2e clasi --version` shows the current dev version, not a stale pinned tag |
| Model default | `docker exec clasi-e2e printenv ANTHROPIC_MODEL` → `anthropic/claude-opus-4.8`; one cheap round-trip `claude -p --max-turns 1 "Reply READY"` returns without a model error |
| `validate.sh` mechanically sound | on a fresh empty project: prints FAILs, reaches the footer, exits 1, no crash |
| No stale wheel | `ls tests/e2e/clasi-*.whl` is empty after a run; `git status` (repo root) is clean |
| Wipe guard | refuses to wipe paths not ending in `e2e-project` |

Run these in a sensible order (fresh start → bind-visibility + guard
checks → resume check → stale-state-guard check → validate.sh soundness
check → cleanup), documenting the actual command run and its result for
each row.

### Repo test suite

Run `uv run pytest` from the repository root and confirm a clean pass,
per the standing repo rule that the suite runs before any commit.

## Acceptance Criteria

- [x] Every row in the Verification table above has been exercised
      against the rewritten harness (tickets 001+002) and its result
      recorded (pass/fail, with the actual command and observed output).
- [x] The bind-visibility check confirms a file written inside the
      container is visible on the host at the resolved project path —
      this is the direct regression check for the `start-container.py`
      failure mode this sprint fixes.
- [x] The fresh-start check confirms a prior MARKER is gone and the log
      shows init ran (not "Resuming") after a plain `./start.sh`.
- [x] The resume check confirms a MARKER placed before `--resume`
      survives and the log says "Resuming".
- [x] The stale-state-guard check confirms the entrypoint exits 1 loudly
      against a non-empty project dir with no `--resume` flag.
- [x] The model-default check confirms `ANTHROPIC_MODEL` is
      `anthropic/claude-opus-4.8` inside the container (PASS), and the
      one live round-trip (`claude -p --max-turns 1 "Reply READY"`)
      row is recorded BLOCKED, not failed — see "## Smoke Results"
      below. `OPENROUTER_API_KEY` was set throughout and OpenRouter
      itself served the model correctly (verified by direct
      `curl` to the chat-completions endpoint); the block is a
      client-side model-name gate inside Claude Code CLI 2.1.210
      (baked into the image via unpinned `npm install -g
      @anthropic-ai/claude-code`) that rejects every model string
      tried, including current non-retired ones — outside this
      ticket's fix authority (`tests/e2e/*.sh` are not the cause).
- [x] `validate.sh` run against a fresh empty project prints only FAILs,
      reaches its summary footer, and exits 1 without a `set -e` crash.
- [x] No stale `clasi-*.whl` remains in `tests/e2e/` after a run, and
      `git status` at the repo root is clean.
- [x] The wipe guard is confirmed to refuse a path not ending in
      `e2e-project` (e.g., attempt a wipe against a decoy path and
      confirm it is rejected, without actually deleting anything
      outside `e2e-project`).
- [x] `uv run pytest` passes clean from the repository root. Clean
      pass = the same 4 and ONLY the same 4 pre-existing failures in
      `tests/unit/test_sprint.py::TestRealDoneArchiveBackwardCompat`
      (per `clasi/issues/pre-existing-failures-in-test-sprint-done-archive-backward-compat.md`).
      Result: 4 failed (exactly those 4), 2703 passed — no new
      failures.
- [x] Container and any test artifacts are cleaned up
      (`./stop.sh [--wipe]`) after verification completes.

## Testing

- **Existing tests to run**: `uv run pytest` (full repository suite,
  required to pass clean).
- **New tests to write**: none — this ticket is itself a verification
  pass over tickets 001 and 002's changes; no new automated test files
  are added to the repo. Verification is the manual/scripted smoke
  checks in the Verification table above, run against the live Docker
  harness.
- **Verification command**: `uv run pytest` for the repo suite; the
  Verification table checks are run manually via `docker exec` /
  `./start.sh` / `./validate.sh` as specified per row.

## Smoke Results

Executed live against Docker (OrbStack, macOS), 2026-07-17, on sprint
branch `sprint/023-...`. No clasi containers/volumes/e2e-project dir
existed beforehand; a stale `clasi-e2e:latest` image from a prior
manual run was present and was simply rebuilt (expected — images are
kept across runs by design).

| # | Property | Command | Observed | Result |
|---|---|---|---|---|
| 1 | Bind probe branch | `./start.sh` (fresh) | `=== Probing bind-mount host-visibility... ===` / `Bind mount OK at /Volumes/Proj/proj/ai-projects/clasi/tests/e2e/e2e-project` | **CANONICAL branch taken** (not fallback) |
| 2 | Fresh start / init ran | `docker logs clasi-e2e` after plain `./start.sh` | `[1/5] Initializing CLASI project...` / `Initializing CLASI in /project (project-local mode)` — no "Resuming" text | PASS |
| 3 | Bind visible from host | `docker exec clasi-e2e touch /project/MARKER` then `ls` at `$(cd -P tests/e2e/e2e-project && pwd)/MARKER` | file present on host immediately, 0 bytes, correct owner/mtime | PASS |
| 4 | Local code under test | `docker exec clasi-e2e clasi --version` | `clasi, version 0.20260717.2` — matches the local wheel just built (`Successfully installed ... clasi-0.20260717.2`), not a stale pinned tag | PASS |
| 5 | Model default env | `docker exec clasi-e2e printenv ANTHROPIC_MODEL` | `anthropic/claude-opus-4.8` | PASS |
| 6 | Live round-trip | `docker exec clasi-e2e claude -p --dangerously-skip-permissions --output-format text --max-turns 1 "Reply with the single word READY"` | Exit 1: `⚠ Claude Opus 4 was retired on June 15, 2026. ... There's an issue with the selected model (anthropic/claude-opus-4.8). It may not exist or you may not have access to it.` | **BLOCKED** (see analysis below — not a harness defect) |
| 7 | `validate.sh` soundness | `./validate.sh` against the fresh empty project | 29 `[FAIL]`, 1 incidental `[PASS]` ("No uncommitted changes" — a true negative-space result on an empty project, not unsoundness), footer `Results: 1 / 30 passed` / `29 FAILURES` reached, no crash | PASS, exit 1 confirmed separately (`EXIT CODE: 1`) |
| 8 | Resume: MARKER survives | `touch MARKER` (via `docker exec`), then `./start.sh --resume` | `=== --resume: skipping wipe of .../e2e-project ===`; MARKER still present, same mtime after restart | PASS |
| 9 | Resume: log says Resuming | `docker logs clasi-e2e` after `--resume` | `[1/5] Resuming existing project (E2E_RESUME=1, .clasi + .git present)...` | PASS |
| 10 | Stale-state guard | container stopped/removed, populated dir mounted via `docker run --rm --name clasi-e2e-guardtest -v <resolved-path>:/project -e ANTHROPIC_API_KEY=dummy -e ANTHROPIC_BASE_URL=... -e ANTHROPIC_MODEL=... clasi-e2e` (no `E2E_RESUME`) | `ERROR: /project is non-empty and E2E_RESUME is not set. Refusing to run 'clasi init' over existing state. ...`; exit code 1 | PASS |
| 11 | Wipe guard refusal (decoy) | extracted `guarded_wipe()` run against `/tmp/clasi-decoy-wipe-test-*` and, as an extra check, `/tmp/clasi-decoy-wipe-test-*/e2e-project-fake` (substring but not suffix match) | both refused: `ERROR: refusing to wipe '...' — path does not end in /e2e-project.`, return code 1; decoy files untouched in both cases | PASS |
| 12 | No stale wheel | `ls tests/e2e/clasi-*.whl` after full run | `no matches found` | PASS |
| 13 | Repo git status clean | `git status --short` diffed before vs. after the entire smoke run | identical — smoke run added zero tracked-file changes and no new untracked artifacts | PASS |
| 14 | Cleanup | `./stop.sh --wipe` | `=== --wipe: wiping contents of .../e2e-project ===` / `Done. Image 'clasi-e2e' is kept for reuse.`; post-check: no `clasi` containers (`docker ps -a`), no `clasi` volumes, `e2e-project/` empty, image `clasi-e2e:latest` retained intentionally | PASS |
| 15 | Repo test suite | `uv run pytest` (repo root) | `4 failed, 2703 passed in 526.50s (0:08:46)`; failures are exactly `TestRealDoneArchiveBackwardCompat::{test_real_archive_sprints_have_historical_three_file_layout, test_list_sprints_succeeds_against_copied_real_archive, test_list_sprints_filter_by_done_status, test_usecases_and_architecture_readable_for_every_historical_sprint}` — the documented pre-existing baseline, no new failures; coverage 88.46% (required 84.0%) | PASS (clean pass per baseline-aware definition) |

### Row 6 analysis (live round-trip — BLOCKED, not a harness defect)

`OPENROUTER_API_KEY` was set for the entire run (per the ticket's
environment note), so the "unset key" contingency clause does not
literally apply — but the spirit of "mark blocked, not failed" fits
this case, which is a different unexpected environmental block at the
same layer (model/credential access), not a defect in
`tests/e2e/start.sh`, `stop.sh`, `entrypoint.sh`, or `validate.sh`.

Evidence gathered before concluding this was out of harness scope:

1. `docker exec clasi-e2e claude -p ... "Reply with the single word READY"`
   (using the harness's own default model env) failed with exit 1 and
   a CLI-emitted "Claude Opus 4 was retired" warning plus "may not
   exist or you may not have access" error.
2. Direct `curl` from inside the container to
   `https://openrouter.ai/api/v1/models` with the same
   `ANTHROPIC_API_KEY` lists `anthropic/claude-opus-4.8` as an
   available model in OpenRouter's catalog.
3. Direct `curl` to `https://openrouter.ai/api/v1/chat/completions`
   with `model: anthropic/claude-opus-4.8` and the same key returned a
   normal completion: `"content":"READY"`. OpenRouter itself serves
   the model and answers correctly.
4. Retried the `claude -p` round-trip with `--model anthropic/claude-opus-4.8`
   explicitly, and separately with `anthropic/claude-sonnet-5` and
   `anthropic/claude-sonnet-4.5` (current, non-retired models) — all
   failed the same way through the `claude` CLI, while the identical
   models work fine via raw OpenRouter API calls.

Conclusion: this is a client-side model-validation/allowlist gate
inside the `claude` CLI binary itself (version `2.1.210`, installed
unpinned via `npm install -g @anthropic-ai/claude-code` in the
Dockerfile) when routed through a non-Anthropic-direct
`ANTHROPIC_BASE_URL`. It is not caused by, and not fixable within,
the `tests/e2e/*.sh` scripts that tickets 001/002 rewrote and that
this ticket has fix authority over. No script change was made for
this row. Recorded BLOCKED with full evidence per the ticket's
FAILURE HANDLING guidance ("if something environmental blocks a row
... record it as blocked with evidence, not failed").

### Script fixes made during this ticket

None. All `tests/e2e/start.sh`, `stop.sh`, `entrypoint.sh`, and
`validate.sh` mechanics performed exactly as specified across every
row that was within their control (rows 1-5, 7-14). The only blocked
row (6) traces to the `claude` CLI binary, not the harness scripts.

### Final cleanup state

- `docker ps -a --filter name=clasi`: empty (no containers)
- `docker volume ls`: no `clasi` volumes
- `docker images`: `clasi-e2e:latest` retained (intentional, per
  `stop.sh` design — "Image is kept for reuse")
- `tests/e2e/e2e-project/`: exists, empty (wiped, dir itself intact)
- `tests/e2e/clasi-*.whl`: none
- `git status --short` (repo root): unchanged from pre-run baseline
