---
status: done
sprint: '023'
tickets:
- 023-001
- 023-002
- 023-003
---

# CLASI E2E Harness Rework — Fresh Bind-Mounted Project + Reactive Tester Script

## Description

The e2e harness at `tests/e2e/` no longer does what it exists to do — test CLASI end-to-end on a **fresh** project with the **current** code:

- `start.sh` mounts a named Docker volume `clasi-data` that is never deleted, so every run silently reuses stale project state from prior runs. `stop.sh` removes only the container.
- A second, divergent launcher (`start-container.py`) bind-mounts `tests/e2e/e2e-bind`, overrides the entrypoint (so `clasi init` never runs), and produced a zombie container whose `/project` mount was dead (OrbStack bind from `/Volumes/Proj` never materialized).
- `validate.sh` checks paths clasi never produces (`docs/clasi/sprints/...`, `close-report.md`, `planning-docs/`). The real layout is `clasi/sprints/{NNN}-{slug}/` with `sprint.md`, `tickets/`, `tickets/done/`; closed sprints archive to `clasi/sprints/done/`.
- `Dockerfile` defaults `CLASI_SOURCE` to a pinned, already-stale tag, so un-flagged runs test old code.
- The model is hardcoded to Sonnet via OpenRouter; the stakeholder wants it parameterized, defaulting to at least Opus 4.8.
- `AGENTS.md` hands the test-driver agent verbatim prompts and a rigid step list — not how a human drives CLASI. It should become a **reactive** script (situation → action) backed by a **stakeholder persona** document (Appendix A below, mined from 12 real session transcripts).

Terminology: **tester** = Claude Code on the host driving the test; **subject** = Claude Code inside the container executing CLASI.

Stakeholder decisions already made: bind mount preferred over named volume; fresh-by-default; model ≥ Opus 4.8; verification of this rework is a smoke test only (the stakeholder triggers full 4-sprint runs personally).

## Cause

- `docker volume create || true` is an idempotent no-op — freshness was never enforced, and cross-run persistence was even documented as a feature.
- Two launchers drifted apart; the bind-mount one bypassed the entrypoint entirely and OrbStack could not materialize a bind from `/Volumes/Proj` (writes land VM-local while docker reports success).
- `validate.sh` and the AGENTS.md rubric were written against an imagined artifact layout (`close-report.md`, `planning-docs/`) rather than what `clasi init`/`close_sprint` actually produce.
- A pinned-tag Dockerfile default rots by design; nothing rebuilt the wheel from the working tree.

## Proposed fix

### Storage: bind mount with probe + fallback (replaces named volume)

Embed a probe in `start.sh` that asserts **host-side visibility**: write a token file inside a throwaway container, then verify it appears on the host. Never trust docker exit codes for OrbStack binds.

- Canonical path: `tests/e2e/e2e-project/` (real dir if the repo-local bind works).
- Fallback: real dir `~/.clasi/e2e-project/` (clasi does not use `~/.clasi`; verified) + symlink `tests/e2e/e2e-project -> ~/.clasi/e2e-project` for discoverability.
- Always pass the physical path to `docker -v`: `HOST_PROJECT_DIR="$(cd -P "$PROJECT_DIR" && pwd)"` — never a symlink.
- Reconcile symlink/dir transitions between runs; abort (don't auto-delete) if a non-empty real dir blocks a needed symlink.

```bash
probe_bind() {   # $1 = host dir; 0 iff container writes are host-visible
    local dir="$1" token="probe-$$-$RANDOM"
    mkdir -p "$dir"
    docker run --rm -v "$dir:/probe" --entrypoint sh "$IMAGE_NAME" \
        -c "echo $token > /probe/.bind-probe" >/dev/null 2>&1 || return 1
    grep -qs "$token" "$dir/.bind-probe" || return 1
    rm -f "$dir/.bind-probe"
}
```

### Fresh by default, `--resume` to keep state

- `./start.sh`: remove container **first**, then guarded wipe of project-dir contents, then run.
- `./start.sh --resume`: skip the wipe; pass `E2E_RESUME=1` into the container.
- Guarded wipe: refuse unless path ends in `/e2e-project`; refuse `/`, `$HOME`, mount points; delete contents only (`find "$dir" -mindepth 1 -maxdepth 1 -exec rm -rf {} +`), never the dir/symlink itself.

### `start.sh` (rewrite) — responsibilities in order

flags → prereq checks (`OPENROUTER_API_KEY`, docker, `uv` when building local) → wheel build → `docker build` → probe/choose dir → container down → wipe (unless resume) → env file → `docker run` → readiness wait. Env file (mktemp, deleted after run):

```
ANTHROPIC_API_KEY=${OPENROUTER_API_KEY}
ANTHROPIC_BASE_URL=https://openrouter.ai/api/v1
ANTHROPIC_MODEL=${E2E_MODEL}          # default anthropic/claude-opus-4.8 (verified in OpenRouter catalog 2026-07-17)
ANTHROPIC_SMALL_FAST_MODEL=${E2E_SMALL_MODEL}   # optional, e.g. anthropic/claude-haiku-4.5
E2E_RESUME=${RESUME}
```

Baking `ANTHROPIC_MODEL` into the container means `claude -p` calls need no `--model` flag.

### clasi-under-test freshness

- `Dockerfile`: `ARG CLASI_SOURCE=local` (was pinned stale tag). Pin explicitly via `CLASI_SOURCE=<tag> ./start.sh` when wanted.
- `start.sh` local path: `rm -f tests/e2e/clasi-*.whl` → `uv build --wheel --out-dir tests/e2e` (from repo root) → build image → delete the wheel. Stale wheels become impossible.

### `entrypoint.sh` (rewrite of init section)

- Consistent `[1/5]..[5/5]` numbering.
- Resume detection: if `E2E_RESUME=1` and `.clasi` + `.git` exist → skip init. Otherwise **fail loudly if `/project` is non-empty** (never silently re-init — that was the masking defect). Drop all `|| true` on git init/commit.
- `git init -b master` explicitly (`close_sprint` merges to master by default).
- Keep: spec copy (guarded for resume), trust pre-config, tmux launch, keep-alive loop.

### `validate.sh` (rewrite path-dependent checks)

Real layout, globbing both live and archived locations (`/project/clasi/sprints/{done/,}NNN-*`):
- overview: `docs/design/overview.md`
- sprint planned: `sprint.md` in the sprint dir
- tickets: `tickets/*.md` + completed in `tickets/done/` with `status: done`
- closure: sprint dir present under `clasi/sprints/done/` (drop the 4 `close-report.md` checks — clasi never produces that file)
- add exact-string checks from the spec (`Correct! You got it!`, `Nope, try again.`, `Sorry! The answer was 7.`, `Please enter a number.` — all verbatim in guessing-game-spec.md)
- keep code-quality/git/OOP checks (paths already correct)
- must run to completion on an empty fresh project: all FAILs, exit 1, no `set -e` crash (preserve the existing `check` wrapper property).

### `stop.sh` (minor)

Keep stop/remove; add optional `--wipe` (same guarded wipe); add legacy sweep `docker volume rm clasi-data 2>/dev/null || true`.

### Ignores

- `.gitignore`: add `e2e-project/` (covers dir or symlink); keep `clasi-*.whl`.
- `.dockerignore`: add `e2e-project/` — critical, since start.sh rebuilds each run and a populated project would bloat the build context.

### Delete

- `start-container.py` (single launcher = start.sh).

### `tests/e2e/AGENTS.md` — rewrite as reactive tester script

1. **Roles**: tester (host) vs subject (container). Mission: drive the guessing-game project through 4 sprints + 3 OOP changes *the way a human stakeholder would*, then validate mechanically.
2. **Harness usage**: `./start.sh` (fresh) / `--resume` / `./stop.sh [--wipe]` / env knobs `E2E_MODEL` (default `anthropic/claude-opus-4.8`), `E2E_SMALL_MODEL`, `CLASI_SOURCE`. Project dir location + symlink caveat.
3. **Launching subject sessions**: `docker exec clasi-e2e claude -p --dangerously-skip-permissions --output-format text --max-turns <N> "<prompt>"` (runs in `/project` via WORKDIR; env carries key/base-url/model — no `--model` flag). Max-turns guidance: sprint ~40-50, OOP ~5-10, catch-up/close ~20.
4. **NO verbatim prompts.** A situation → action playbook; each entry says what the prompt must *convey* and points at `stakeholder-persona.md` for phrasing. Situations:
   - *Fresh environment* → start harness; introduce the project as a stakeholder would (point at `docs/guessing-game-spec.md`, name the first sprint's goal, authorize autonomy in the stakeholder's idiom: "all the way through, auto-approve").
   - *Sprint finished cleanly* → review artifacts like the stakeholder (inspect sprint dir, tickets in `done/`), then kick off the next sprint conversationally.
   - *Subject stalls / asks confirmation* → respond in-persona ("run it all the way through", "carry on").
   - *Between sprints* → make the scripted OOP change (content from `oop.sh`), phrased in the stakeholder's OOP register.
   - *Sprint hit max-turns* → continuation in the stakeholder's resume idiom ("Hey, we were interrupted, let's get back to work"), catch-up turn budget.
   - *Artifacts look wrong* → interrogate before fixing ("why is sprint X still open?").
5. **Rubric**: `validate.sh` is the mechanical rubric (real paths above); drop invented artifacts (close-report.md, planning-docs, "37+ tests" counts).
6. **Environment noise notes**: `close_sprint` tag-push fails (no git remote in container) — expected, not a clasi bug; OrbStack slowness.
7. Corrected file inventory table.

### `tests/e2e/stakeholder-persona.md` — new

Written from Appendix A below.

### Suggested ticket split

- **T1 — Harness scripts**: start.sh, stop.sh, entrypoint.sh, Dockerfile, validate.sh, `.gitignore`/`.dockerignore`; delete `start-container.py`.
- **T2 — Tester docs**: rewrite AGENTS.md (reactive), create `stakeholder-persona.md` from Appendix A.
- **T3 — Smoke verification** (see Verification).

## Verification

Smoke test only — the stakeholder triggers full 4-sprint runs personally.

| Property | Proof |
|---|---|
| Bind visible from host | `docker exec clasi-e2e touch /project/MARKER` → marker appears under `$(cd -P tests/e2e/e2e-project && pwd)` (the exact check the old e2e-bind failed) |
| Fresh start | after plain `./start.sh`, previous MARKER gone; logs show init ran, not "Resuming" |
| Resume | `touch MARKER; ./start.sh --resume` → MARKER survives; logs say "Resuming" |
| Stale-state guard | non-empty dir + no resume → entrypoint exits 1 loudly |
| Local code under test | `docker exec clasi-e2e clasi --version` shows current dev version, not a stale tag |
| Model default | `docker exec clasi-e2e printenv ANTHROPIC_MODEL` → `anthropic/claude-opus-4.8`; one cheap round-trip `claude -p --max-turns 1 "Reply READY"` returns without model error |
| validate.sh mechanically sound | on fresh empty project: prints FAILs, reaches footer, exits 1, no crash |
| No stale wheel | `ls tests/e2e/clasi-*.whl` empty after start; `git status` clean |
| Wipe guard | refuses paths not ending in `e2e-project` |

Plus the project test suite (`pytest`) before commits, per repo rules.

Risks: the host-visibility assertion in `probe_bind` is the single most load-bearing line; `uv` becomes a host prereq for the default local-wheel path (pinning a tag is the escape hatch); on Linux hosts container-uid-1000 ownership could make the host-side wipe hit permission errors (acceptable; note in AGENTS.md).

## Related

- One-time host cleanup (zombie containers `clasi-e2e` + `clasi-discovery-trial`, volume `clasi-data`, trial image, stale wheel) was performed by the team-lead when this issue was filed — not part of the sprint.
- Separate issue: role-guard blocks tier-0 Writes to `~/.claude/plans/`, which `ExitPlanMode` + the `plan-to-issue` hook require (see `role-guard-blocks-plan-mode-plans-dir` issue).
- Sprints 020–022 declared-closed/computed-pre-flight state drift is pre-existing and out of scope.
- Ground truth for artifact layout: `src/clasi/project.py` (`ARTIFACT_PATH_DEFAULTS`); `close_sprint` archival in `src/clasi/tools/artifact_tools.py`.

---

# Appendix A — Stakeholder Persona: How Eric Actually Uses CLASI

Mined from 12 real Claude Code session transcripts (~79MB, ~99+ substantive human messages). This appendix is the source content for `tests/e2e/stakeholder-persona.md`.

## Key structural finding

**Eric almost never types slash commands** — zero standalone slash-command turns found. He drives CLASI in natural language and lets the agent route to skills. He uses the system vocabulary (issue, sprint, ticket, OOP, close, reflection, auto-approve) as ordinary conversational words.

## 1. Creating issues

Plain English ("file it", "make an issue", "write this up as an issue"); often points at a file/reflection and delegates formalization; batches with next action.
- "alright, let's make an issue. It looks like when we do clazy init and it asks you to move things, it moves stuff out of the .clazy directory... but it doesn't get rid of the directory."
- "Please study this and turn it into an issue: [path to reflection]"
- "go ahead and file it, and then let's get on with the sprint."
- "So file this as an issue." (appended to a long feature description)

## 2. Starting/planning sprints

Batch-plans but gates execution. Signature move: plan first sprint completely, rest first-pass, stop for review. References sprints by number.
- "ok, let's work on all these open issues. We're going to plan out all the sprints: The first sprint completely, The rest of them, first pass, and then stop and let me look at the sprints, and then I'll kick you off on them."
- "Run this clasi/issues/co-locate-design-docs... in a new sprint, all the way through auto approve, back to master."
- "let's do it. Let's load up all the tickets and get to work. You're gonna write all this up into a sprint. I'm gonna review it, and then I'll approve it to be run."
- "alright, let's run sprint 20."

## 3. Making changes

Two modes: (a) review-first symptom description — opens a file, says what he suspects, asks the agent to verify before touching anything; (b) long dictated design dump ending "write it up / file this as an issue". Prescribes solutions but invites pushback.
- "let's review [path]. I want to make sure that this is going to create a new directory or the bind mount... I don't want it to reuse a volume."
- "I'd like to make a change. This will be applied immediately after you're done with the tickets..."
- "Okay, so what causes that? What would you do differently to not cause this?"

## 4. Out-of-process (OOP)

Explicit and casual; triggered by tooling breakage blocking normal process (especially MCP failures) or small targeted fixes. Not for feature work.
- "hey, so OOP the fix"
- "your MCP server is failing, so you're going to have to fix it out of process."
- "yeah, correct that right now, and then go on with sprint... You can dispatch someone to fix it, and then carry on with ticket three."

## 5. Corrections/feedback

Sharp interrupt ("wait!", "hold on", "no, no, no") then explains the correct mental model. Teaches rather than just rejects; tone spikes when the agent does something clearly wrong, but explanation always follows.
- "wait! It doesn't have to stay dirty across the whole sprint. The moment you start to sprint, you can check those files in..."
- "no, but that's crazy. No, no, no, look. The DocsClazzy thing in dotconfig has nothing to do with this, OK?"
- "you created it in .clasi! why is it in .clasi?"
- "wait, why do I have to edit? Look, if the sprint is done, it's done. I don't care what the front matter says."

## 6. Review/validation habits

Personally gates expensive/irreversible steps; approves sprints before execution; tests merged work himself; interrogates artifact state.
- "and then stop and let me look at the sprints, and then I'll kick you off on them."
- "okay, run the sprint all the way through. I will test it on Master."
- "I want to make sure that you don't try to automate the pruning... I'm going to drive the whole thing here. I'm going to tell you when I want the e2e test to run."
- "Why is sprint 12 still open? Why are we working in sprint 13 if sprint 12 is still open? What exactly is going on here?"

## 7. Style/voice

Dictated speech-to-text: "clasi" garbles to clazy/clausi/quasi/classy/clazzy; dropped letters ("Please ontinue", "chect out"). Long run-on sentences with embedded numbered lists; casual openers ("How you doin'"); signature "let's" and "I want you to"; ends design dumps with a meta-question ("Solve the problem?", "Is there any reason not to?"); occasional exasperated profanity.
- "let me back up a bit, and let's talk about what I'm actually trying to solve. 1. What I want to do is..."
- "He fixed a Homebrew Python 3.14, so why don't you chect out."

## 8. Session arc

Open casually or by interrogating an artifact → discuss/diagnose → decide (often prescriptive) → act. Uses plan mode deliberately for analysis ("I'm going to put you in plan mode because we're just doing analysis here"; "right now we're just talking. But don't make any changes."). Resumes with "continue / carry on / Continue from where you left off". Authorizes long autonomy explicitly ("power through until morning... get this thing finished by tomorrow").

## Role-play summary for the tester

Speak entirely in dictated natural language — never slash commands — using CLASI vocabulary as ordinary words. Open casually or by asking "what's going on here / why is X like this." Think out loud in run-on sentences with occasional speech-to-text garbling ("clazy", "classy"). Either describe a symptom and let the subject diagnose, or dictate a detailed design and end with "write it up as an issue / file this." Batch-plan roadmaps but hard-gate execution: "plan the first sprint completely, the rest first-pass, then stop and let me look"; approve, then "run it all the way through, auto-approve, I'll test on master." Interrupt wrong turns with "wait / hold on / no, no, no" and explain the correct model. Reach for "OOP the fix" when tooling breaks. Close with "continue," "carry on," or "power through."
