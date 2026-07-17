# Guessing Game — CLASI E2E Test (Tester Instructions)

**This file is instructions for an AI agent.** You are the agent, and
you are the **tester**. You will read this document and execute the
full test autonomously — no human is involved, you drive everything.

## Roles

- **tester** — Claude Code running on the host (you). You read this
  file, run the harness scripts, and launch `claude -p` sessions inside
  the container. You do not write any CLASI code or artifacts yourself
  — you drive by prompting the subject.
- **subject** — Claude Code running inside the container, executing
  CLASI (`clasi`) against the guessing-game project at `/project`. The
  subject is the thing under test.

## Mission

Drive the guessing-game project (spec baked into the container at
`/project/docs/guessing-game-spec.md`) through 4 sprints and 3
out-of-process changes **the way a human stakeholder would drive
CLASI** — not by feeding the subject a rigid script of pre-written
prompts. Read `stakeholder-persona.md` before you start; it is the
source for how a real stakeholder phrases things and it is what makes
this a meaningful test of CLASI's natural-language front end rather
than a test of your own prompt templates. Once all 4 sprints and all 3
OOP changes are done, validate mechanically with `./validate.sh`.

## What You're Testing

CLASI is a spec-driven development system for AI coding agents. It
defines a structured process: overview → sprint plan → tickets →
execute → close. This test validates that the full pipeline works
correctly end-to-end: artifacts are produced in the right places,
tickets progress through their lifecycle, sprints close cleanly, and
out-of-process changes are handled gracefully — all while being *told*
what to do the way an actual stakeholder tells it, not the way a test
script would.

The target project is a trivial Python CLI with 3 guessing games,
split across 4 sprints, with 3 OOP changes interleaved. The spec is
baked into the image and copied to `/project/docs/guessing-game-spec.md`
by `entrypoint.sh`.

## Harness usage

### Starting and stopping

```bash
./start.sh              # fresh: wipes the project dir, runs clasi init
./start.sh --resume      # keep existing project state, skip the wipe
./stop.sh                 # stop and remove the container
./stop.sh --wipe          # stop, remove the container, and wipe the project dir
```

`./start.sh` always removes any existing container first. Unless
`--resume` is given, it then wipes the project directory's contents
(not the directory/symlink itself) before starting a fresh container,
so every plain `./start.sh` run is a clean slate. `--resume` skips the
wipe and passes `E2E_RESUME=1` into the container, which tells
`entrypoint.sh` to skip `clasi init` and git init and continue from
whatever is already there.

### Env knobs

- `E2E_MODEL` — model baked into the container as `ANTHROPIC_MODEL`.
  Defaults to `anthropic/claude-opus-4.8`. Because this is set at
  container-start time, `claude -p` calls inside the container need no
  `--model` flag.
- `E2E_SMALL_MODEL` — optional, sets `ANTHROPIC_SMALL_FAST_MODEL`
  (e.g. `anthropic/claude-haiku-4.5`). Unset by default.
- `CLASI_SOURCE` — which build of clasi to install in the image.
  Default (unset) builds the **local wheel** from the current working
  tree via `uv build --wheel` — this is what makes the test exercise
  the code you're actually working on, not a stale pinned release. Set
  it to a tag (`CLASI_SOURCE=<tag> ./start.sh`) to pin a released
  version instead.

### Host prerequisites

- Docker (OrbStack or Docker Desktop).
- `OPENROUTER_API_KEY` set in your environment — this becomes
  `ANTHROPIC_API_KEY` inside the container, redirected to OpenRouter
  via `ANTHROPIC_BASE_URL`.
- `uv` installed **when using the default local-wheel path**
  (`CLASI_SOURCE` unset). `start.sh` checks for `uv` up front and
  fails with a clear message if it's missing; the escape hatch is
  pinning a released tag instead (`CLASI_SOURCE=<tag>`), which does
  not need `uv`.

### Project directory location

The canonical project directory is `tests/e2e/e2e-project/`. `start.sh`
probes whether a bind mount there is actually host-visible (writes
made inside a throwaway container must appear on the host — this is
the exact failure mode that broke the old `start-container.py` under
OrbStack, where the mount reported success but was VM-local and
invisible from the host). If the probe succeeds, that's your project
directory, plain and simple.

**Symlink-fallback caveat**: if the probe fails at the canonical path,
`start.sh` falls back to a real directory at `~/.clasi/e2e-project/`
and replaces `tests/e2e/e2e-project` with a symlink pointing there, so
you can still `ls`/`cat` project files from the same familiar path. If
you ever see `tests/e2e/e2e-project` as a symlink rather than a real
directory, that's expected — it means the fallback is active on this
host. Don't be alarmed and don't "fix" it by deleting the symlink.

**Linux uid-1000 caveat**: the container runs as uid 1000. On Linux
hosts, files it writes into a bind-mounted directory may be owned by
uid 1000 on the host side too, which can make the host-side wipe
(`guarded_wipe` in `start.sh`/`stop.sh --wipe`) hit permission errors
if your host user isn't uid 1000. This is a known, acceptable rough
edge on Linux, not a harness bug — if you hit it, `sudo rm -rf` the
project dir contents manually and retry.

## Launching subject sessions

Every subject session is a `docker exec` into the running container,
using Claude Code's print mode:

```bash
docker exec clasi-e2e claude -p \
  --dangerously-skip-permissions --output-format text --max-turns <N> \
  "<prompt>"
```

- No `--model` flag — `ANTHROPIC_MODEL` is already set in the
  container's environment (see `E2E_MODEL` above), and print mode
  picks it up automatically.
- Print mode runs in `/project` (the image's `WORKDIR`) and needs no
  OAuth — the API key, base URL, and model all come from the
  container's environment.
- Choose `--max-turns` for the kind of work you're asking for:
  - **Sprint** (plan → ticket → execute → close): about 40-50.
  - **OOP change**: about 5-10.
  - **Catch-up / close-out** after a sprint got interrupted by
    max-turns: about 20.

## The Playbook

This is a situation → action playbook, not a fixed step sequence.
**No entry below contains a verbatim prompt.** Each entry describes
the situation you'll recognize and what your prompt to the subject
must *convey* — the goals, constraints, and authorization it needs to
carry. For how to phrase it, read `stakeholder-persona.md` and write
in that register: natural language, no slash commands, casual but
specific, ending with clear authorization to proceed autonomously.

### Situation: fresh environment

You've just run `./start.sh` and the container is up with a bare
project (only the copied spec and an initial git commit). Introduce
the project the way a stakeholder would on day one: point the subject
at `docs/guessing-game-spec.md` as the source of truth, name the goal
of the *first* sprint specifically (project structure + menu + the
first game, per the spec — read the spec yourself before composing
this so you know what "first sprint" should scope to), and authorize
it to run autonomously through planning and execution without pausing
for confirmation. This is the highest-stakes prompt of the run — get
the framing right, then let go.

### Situation: sprint finished cleanly

The subject's print-mode call returned control to you (not cut off by
max-turns) and claims a sprint is done. Before moving on, review the
artifacts the way a stakeholder would — don't take the subject's word
for it. Look at the sprint directory under
`/project/clasi/sprints/` (it may have archived to
`/project/clasi/sprints/done/` if the sprint closed), check that its
tickets ended up in `tickets/done/` with `status: done`, and skim for
anything that looks off. If it looks right, kick off the next sprint
conversationally — reference it by number the way the persona doc
shows, name what this next sprint should cover per the spec, and
authorize the same autonomous run-through.

### Situation: subject stalls or asks for confirmation

The subject's output pauses on a question, asks whether to proceed, or
otherwise waits instead of finishing the work. Respond in persona:
short, impatient, and re-authorizing — the stakeholder's habitual move
here is not to answer the question in detail but to wave it through
and tell the subject to keep moving. Convey "don't stop for
confirmation, run it all the way through" without turning it into a
procedural instruction.

### Situation: between sprints (OOP change)

After a sprint closes and before you kick off the next one, make the
scripted out-of-process change for that slot. The content of the
change comes from `oop.sh` — run `./oop.sh <N>` to see what change N
actually is (menu title case after sprint 1, `__version__` after
sprint 2, a TODO comment after sprint 3; see the table below). Don't
send the raw `oop.sh` output as your prompt — rephrase it in the
stakeholder's OOP register (see persona doc section 4): casual,
explicit that this bypasses the sprint process, and clear that it
should run now, directly, with tests and a commit.

### Situation: sprint hits max-turns

The `claude -p` call for a sprint returns because it hit `--max-turns`,
not because the subject said it finished. Resume in the stakeholder's
continuation idiom — "we got interrupted, keep going from where you
left off" — rather than restating the whole sprint goal from scratch.
Give it a catch-up turn budget (about 20) sufficient to wrap up
whatever's unfinished: closing tickets, closing the sprint, merging.
If it was mid-implementation rather than mid-close, say so and give it
more room; use your judgment on the artifacts, the same way a
stakeholder checking in would.

### Situation: artifacts look wrong

Something in the sprint/ticket state doesn't match what you'd expect —
a sprint directory still open when it should be closed, a ticket
that's not in `done/` after the subject claimed the sprint finished, a
missing overview doc, etc. Don't just tell the subject to fix it.
Interrogate first, the way the persona doc's corrections/review
sections show: ask why it's in that state, make the subject explain
itself, and only then direct the fix (or let the subject propose one).
This mirrors real stakeholder behavior — "why is sprint X still open?"
— and it's a better test of the subject's diagnostic path than a blind
"fix it" would be.

## OOP Change Table

`oop.sh` is unchanged from ticket 001 — these are still the 3 scripted
changes, in order:

| After sprint | Script | What it changes | What it tests |
|-------------|--------|-----------------|---------------|
| 001 | `./oop.sh 1` | Fix menu title capitalization (title case for all 3 game names) | Next sprint doesn't revert the fix |
| 002 | `./oop.sh 2` | Add `__version__` to package `__init__.py` | Next sprint preserves the version |
| 003 | `./oop.sh 3` | Add a TODO comment to `number_game.py` | Next sprint doesn't strip the comment |

## The Rubric

`./validate.sh` **is** the rubric — it's a mechanical check script,
not a description to reproduce by hand. Run it after all 4 sprints and
3 OOP changes:

```bash
./validate.sh
```

It checks, against the real clasi artifact layout (globbing both live
and archived sprint locations under `/project/clasi/sprints/`):
process artifacts (`docs/design/overview.md`, each sprint's
`sprint.md`), ticket lifecycle (tickets present, completed ones in
`tickets/done/` with `status: done`, acceptance criteria present),
sprint closure (each sprint archived under `clasi/sprints/done/`),
code quality (the package runs, the menu displays, `q` quits, tests
pass), exact spec strings from the guessing-game behavior, git hygiene
(commit count, clean tree), and OOP change resilience (all 3 scripted
edits survived into the final state).

Do not invent or expect artifacts `validate.sh` doesn't check for —
there is no `close-report.md` (clasi never produces one), no
`planning-docs/` directory, and no fixed test-count target ("37+
tests" or similar). If you're ever unsure whether something should
exist, `validate.sh`'s own checks are the ground truth, not this
document's prose.

`validate.sh` is designed to run to completion even on a fresh, empty
project (all checks FAIL, exit 1, no crash) — if you want a sanity
check that the rubric itself is wired correctly before or between
sprints, it's safe to run early.

## Environment Noise Notes

A few things you'll see that are expected noise, not signs of a clasi
bug:

- **`close_sprint`'s tag-push step fails inside the container.** The
  container's git repo has no remote configured, so any push attempted
  as part of sprint closure will error. This is a harness limitation
  (no remote inside the throwaway container), not a defect in clasi's
  close-sprint logic. Don't treat it as a failed test.
- **OrbStack can be slow.** `docker exec`/`docker run` calls
  occasionally hang or take longer than expected. If a docker command
  seems stuck, give it 30 seconds before concluding something is
  actually wrong.

## Files In This Directory

| File | Purpose |
|------|---------|
| `AGENTS.md` | **This file** — tester instructions |
| `stakeholder-persona.md` | Phrasing register for prompts to the subject — read before composing any prompt |
| `Dockerfile` | Container image with Python, Node, Claude Code, clasi |
| `entrypoint.sh` | Runs inside container: clasi init → git → spec → tmux keep-alive |
| `start.sh` | Build image (local wheel by default) + probe bind mount + wipe (unless `--resume`) + start container |
| `stop.sh` | Stop and remove container; `--wipe` also clears the project dir |
| `connect.sh` | Attach to the container's tmux session for interactive/manual poking |
| `validate.sh` | Mechanical rubric checker — run after all sprints and OOP changes |
| `oop.sh` | Source content for the 3 out-of-process change prompts (rephrase, don't paste verbatim) |
| `guessing-game-spec.md` | The 4-sprint spec baked into the container image |
| `e2e-project/` | Project directory — real dir, or a symlink to `~/.clasi/e2e-project/` on the fallback path (see Harness usage above); gitignored, transient |
| `.gitignore` | Excludes `e2e-project/` and built wheels (`clasi-*.whl`) from the repo |
| `.dockerignore` | Excludes `e2e-project/` from the Docker build context (critical — `start.sh` rebuilds the image every run) |

Note: `clasi-*.whl` in this directory is transient — `start.sh` builds
it fresh at the start of each run and deletes it after the image is
built. If you see one sitting around after a run, something aborted
mid-build; it's safe to delete.
