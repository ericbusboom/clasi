---
id: '001'
title: 'Harness scripts: bind-mount probe, guarded wipe, resume, local-wheel build,
  path corrections'
status: done
use-cases: []
depends-on: []
github-issue: ''
issue: clasi-e2e-harness-rework-fresh-bind-mounted-project-reactive-tester-script.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Harness scripts: bind-mount probe, guarded wipe, resume, local-wheel build, path corrections

## Description

Rewrite the mechanical layer of the `tests/e2e/` harness so it actually
provisions a fresh, host-visible project running the current working
tree's `clasi`, instead of silently reusing stale state from a
never-wiped named Docker volume. This is the foundation ticket — T2 and
T3 both depend on the paths, flags, and env contract this ticket
establishes.

Ground truth for the real clasi artifact layout: `ARTIFACT_PATH_DEFAULTS`
in `src/clasi/project.py` (`clasi/issues`, `clasi/sprints`,
`clasi/reflections`, `docs/design`) and `close_sprint`'s archival to
`clasi/sprints/done/` in `src/clasi/tools/artifact_tools.py`.

Full mechanism spec is in the issue's Proposed fix section (bind-mount
probe function, guarded-wipe semantics, env-file shape, entrypoint
fail-loud logic) — implement it as specified there; this ticket does not
re-derive those decisions.

### `start.sh` (rewrite)

Order of responsibilities: flags → prereq checks (`OPENROUTER_API_KEY`,
`docker`, `uv` when building local) → wheel build → `docker build` →
probe/choose dir → container down → wipe (unless resume) → env file →
`docker run` → readiness wait.

- Add `probe_bind()`: writes a token file inside a throwaway container,
  verifies the token appears on the **host** filesystem (never trust the
  docker exit code — this is the fix for the exact OrbStack failure mode
  that broke `start-container.py`).
- Canonical project dir: `tests/e2e/e2e-project/` (real dir, if the
  repo-local bind materializes per the probe). Fallback:
  `~/.clasi/e2e-project/` (real dir) + symlink
  `tests/e2e/e2e-project -> ~/.clasi/e2e-project` for discoverability.
  Reconcile symlink/dir transitions between runs; abort (do not
  auto-delete) if a non-empty real dir blocks a needed symlink.
- Always resolve to a physical path before passing to `docker -v`:
  `HOST_PROJECT_DIR="$(cd -P "$PROJECT_DIR" && pwd)"` — never pass a
  symlink path to Docker.
- Fresh-by-default: remove any existing container first, then guarded
  wipe of project-dir *contents* (never the dir/symlink itself), then
  run. Guard: refuse to wipe unless the resolved path ends in
  `/e2e-project`; refuse `/`, `$HOME`, and mount-point paths. Wipe via
  `find "$dir" -mindepth 1 -maxdepth 1 -exec rm -rf {} +`.
- `--resume` flag: skip the wipe; pass `E2E_RESUME=1` into the container
  env.
- Local-wheel build (default path): `rm -f tests/e2e/clasi-*.whl` →
  `uv build --wheel --out-dir tests/e2e` (run from repo root) → build the
  image → delete the wheel afterward. No stale wheel should ever remain
  on disk after a run.
- Env file (mktemp, deleted after the `docker run` call):
  ```
  ANTHROPIC_API_KEY=${OPENROUTER_API_KEY}
  ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1
  ANTHROPIC_MODEL=${E2E_MODEL}          # default anthropic/claude-opus-4.8
  ANTHROPIC_SMALL_FAST_MODEL=${E2E_SMALL_MODEL}   # optional
  E2E_RESUME=${RESUME}
  ```
  Baking `ANTHROPIC_MODEL` into the container env means `claude -p` calls
  need no `--model` flag downstream (relevant for T2/T3).

### `stop.sh` (minor rewrite)

- Keep existing stop/remove-container behavior.
- Add optional `--wipe` flag using the same guarded-wipe function/logic
  as `start.sh` (refuse unless path ends in `/e2e-project`).
- Add a legacy-volume sweep: `docker volume rm clasi-data 2>/dev/null ||
  true` (cleans up the old named-volume artifact from prior harness
  versions; safe no-op once nothing uses it).

### `entrypoint.sh` (rewrite of init section)

- Consistent `[1/5]..[5/5]` step numbering (current script has an
  inconsistent `[3.5/5]` step).
- Resume detection: if `E2E_RESUME=1` and both `.clasi` and `.git` exist
  in `/project`, skip re-initialization ("Resuming" in the log).
- Otherwise: **fail loudly if `/project` is non-empty** — exit non-zero
  with a clear message. Never silently re-run `clasi init` over existing
  state; that silent-masking behavior is the defect being fixed.
- Drop all `|| true` on `git init` / `git add` / `git commit` — failures
  there must surface, not be swallowed.
- `git init -b master` explicitly (not the default-branch-name-dependent
  form) — `close_sprint` merges to `master` by default, so the initial
  branch must be named `master` for later sprint closes to succeed.
- Keep: spec copy (guard it too — skip if resuming and the spec is
  already present), Claude Code trust pre-config, tmux launch, and the
  keep-alive loop.

### `Dockerfile`

- Change `ARG CLASI_SOURCE=v0.20260716.1` (or whatever the current pinned
  tag is) to `ARG CLASI_SOURCE=local`. Explicit pinning remains available
  via `--build-arg CLASI_SOURCE=<tag>` / `CLASI_SOURCE=<tag> ./start.sh`.
- No other Dockerfile changes needed — the local-wheel COPY/install logic
  already exists and is correct; only the default changes.

### `validate.sh` (rewrite path-dependent checks)

Real layout, globbing both live and archived sprint locations
(`/project/clasi/sprints/{done/,}NNN-*`):

- Overview: `docs/design/overview.md` (not `docs/clasi/overview.md`).
- Sprint planned: `sprint.md` present in the sprint dir (not
  `planning-docs/*.md`).
- Tickets: `tickets/*.md` present, plus completed tickets in
  `tickets/done/` with frontmatter `status: done`.
- Closure: sprint directory present under `clasi/sprints/done/`. **Drop**
  the four `close-report.md` existence checks entirely — clasi never
  produces that file, so those checks fail unconditionally today.
- Add exact-string checks against `guessing-game-spec.md`'s verbatim game
  text: `Correct! You got it!`, `Nope, try again.`, `Sorry! The answer
  was 7.`, `Please enter a number.`.
- Keep the existing code-quality, git-hygiene, and OOP-resilience checks
  as-is — their paths are already correct.
- Preserve the existing `check()` wrapper property: running `validate.sh`
  against an empty fresh project must print all FAILs, reach the summary
  footer, and `exit 1` — never crash mid-script under `set -e`.

### Ignores

- `.gitignore`: add `e2e-project/` (covers both the plain-dir and
  symlink cases); keep the existing `clasi-*.whl` entry.
- `.dockerignore`: add `e2e-project/` — critical, since `start.sh` now
  rebuilds the image on every run and a populated project directory
  would otherwise bloat the build context needlessly.

### Delete

- `tests/e2e/start-container.py` — the single remaining launcher is
  `start.sh`. This file bypassed the entrypoint (so `clasi init` never
  ran) and depended on a bind path that never worked reliably; it has no
  remaining purpose once `start.sh` has its own probed bind mount.

## Acceptance Criteria

- [x] `start.sh` implements `probe_bind()` asserting host-side file
      visibility (not just a docker exit code) before proceeding.
- [x] `start.sh` is fresh-by-default: removes the container, then wipes
      project-dir contents (guarded), then runs.
- [x] `start.sh --resume` skips the wipe and sets `E2E_RESUME=1`.
- [x] The wipe function refuses to run unless the resolved path ends in
      `/e2e-project`; refuses `/`, `$HOME`, and mount-point paths.
- [x] `start.sh` always passes a physically-resolved (non-symlink) path
      to `docker -v`.
- [x] Local-wheel build path deletes any stale `clasi-*.whl` before
      building, and deletes the built wheel after the image build
      completes.
- [x] Env file bakes in `ANTHROPIC_MODEL` (default
      `anthropic/claude-opus-4.8`) and `ANTHROPIC_SMALL_FAST_MODEL`
      (optional), and is deleted after `docker run`.
- [x] `Dockerfile`'s `CLASI_SOURCE` build-arg defaults to `local`.
- [x] `entrypoint.sh` fails loudly (non-zero exit, clear message) when
      `/project` is non-empty and `E2E_RESUME` is not set; skips init
      when resuming with `.clasi` + `.git` present; drops all `|| true`
      on git init/commit; runs `git init -b master` explicitly.
- [x] `validate.sh`'s path checks match the real layout
      (`clasi/sprints/`, `docs/design/overview.md`, `tickets/done/`,
      archived sprints under `clasi/sprints/done/`); the four
      `close-report.md` checks are removed; exact-string game-output
      checks are added.
- [x] `validate.sh` run against an empty fresh project prints only FAILs,
      reaches the footer, and exits 1 without a `set -e` crash.
- [x] `stop.sh` supports `--wipe` and sweeps the legacy `clasi-data`
      volume.
- [x] `.gitignore` and `.dockerignore` both list `e2e-project/`.
- [x] `tests/e2e/start-container.py` is deleted.

## Testing

- **Existing tests to run**: `uv run pytest` (repository suite; this
  ticket touches only `tests/e2e/` shell/Docker scripts, which are not
  exercised by the Python test suite, but the suite must still pass
  clean since it runs before every commit per repo rules).
- **New tests to write**: no new Python tests — this ticket's
  verification is manual/scripted smoke testing of the shell harness
  itself, covered by T3. Where practical, prefer `bash -n` syntax checks
  on each modified script as a cheap sanity gate during implementation.
- **Verification command**: `uv run pytest` (repo suite); manual smoke
  checks against the rewritten scripts are covered by ticket 003.
