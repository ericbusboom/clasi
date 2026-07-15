# Guessing Game — CLASI E2E Test (Agent Instructions)

**This file is instructions for an AI agent.** You are the agent. You will read
this document, follow the steps, and execute the full test autonomously. No
human is involved — you drive everything.

## What You're Testing

CLASI (`clasi`) is a spec-driven development system for AI coding agents. It
defines a structured process: overview → sprint plan → tickets → execute →
close. This test validates that the full pipeline works correctly end-to-end:
artifacts are produced in the right places, tickets progress through their
lifecycle, sprints close cleanly, and out-of-process changes are handled
gracefully.

The target project is a trivial Python CLI with 3 guessing games, split across
4 sprints. The spec is at `guessing-game-spec.md`.

## Architecture

```
┌──────────┐     claude -p      ┌──────────────────┐     docker exec      ┌──────────────┐
│  Agent   │ ────────────────── │  Docker container │ ──────────────────── │  clasi MCP   │
│  (you)   │                    │  (clasi-e2e)      │                      │  server      │
│          │                    │  /project/        │                      │  + Claude    │
│  reads   │                    │  claude + clasi   │                      │  sub-agents  │
│  this    │                    └──────────────────┘                      └──────────────┘
│  file    │
└──────────┘
```

The agent (you) runs on the host. Claude Code runs inside a Docker container
with a named volume at `/project`. You send sprint prompts via
`docker exec clasi-e2e claude -p "..."` (print mode). Print mode uses the
API key from the environment (routed through OpenRouter), needs no OAuth,
and produces no interactive dialogs.

Data persists in a named Docker volume (`clasi-data`). You can access it via
`docker exec` or `docker cp`.

## Prerequisites

- Docker running (OrbStack or Docker Desktop)
- `OPENROUTER_API_KEY` set in your environment
- The Docker image built: `docker build -t clasi-e2e .`
- `start.sh` redirects Claude Code to OpenRouter via `ANTHROPIC_BASE_URL`

## Agent Workflow (the step-by-step script you follow)

### Step 1: Build and launch the environment

```bash
./start.sh
```

This builds the Docker image (if needed), creates the `project/` bind mount,
runs `clasi init` inside the container, and launches Claude Code's MCP server.
Wait for the container to be running (`docker ps` shows `clasi-e2e`).

### Step 2: Sprint 001 — Project structure and menu

Send the sprint prompt to Claude Code inside the container:

```bash
docker exec clasi-e2e claude -p \
  --dangerously-skip-permissions --model anthropic/claude-sonnet-4.5 --output-format text --max-turns 50 \
  "Sprint 001: Project structure and menu. Read docs/guessing-game-spec.md.
   ... [full sprint prompt below] ..."
```

**EXACT prompt to use:**

> Sprint 001: Project structure and menu. Read docs/guessing-game-spec.md.
> 1. Write docs/design/overview.md with a high-level project description.
> 2. Write a sprint plan in clasi/sprints/001-*/planning-docs/.
> 3. Create implementation tickets in clasi/sprints/001-*/tickets/.
> 4. Execute each ticket: in-progress → implement → test → done.
> 5. Write a close-report.md in the sprint directory.
> 6. Create branch sprint/001, commit all work.
> The menu shows: 1=Number, 2=Color, 3=City, q=Quit. Games 1-3 print
> 'Coming soon!' and return to menu. Install pytest if needed.
> Do NOT ask for confirmation. Say SPRINT_001_COMPLETE when done.

**Wait for completion.** Print mode will return when Claude finishes (can
take 10–20 minutes). Look for `SPRINT_001_COMPLETE` in the output.

### Step 3: Out-of-Process change 1

The driving agent sends an OOP prompt to Claude (print mode). Claude makes the
edit directly — no sprint, no tickets. The prompt is in `oop.sh`:

```bash
docker exec clasi-e2e claude -p \
  --dangerously-skip-permissions --model anthropic/claude-sonnet-4.5 --output-format text --max-turns 5 \
  "$(./oop.sh 1)"
```

This tells Claude to fix menu.py title capitalization as a direct edit.

### Step 4: Sprint 002 — Number guessing game

```bash
docker exec clasi-e2e claude -p \
  --dangerously-skip-permissions --model anthropic/claude-sonnet-4.5 --output-format text --max-turns 40 \
  "Sprint 002: Number Guessing Game. Secret is 7 (hardcoded). 3 guesses.
   Non-numeric shows 'Please enter a number' (does not count as guess).
   Correct: Correct! You got it!. Wrong: Nope, try again. 3 wrong:
   Sorry! The answer was 7. Wire to menu choice 1. Sprint plan, tickets,
   execute, close, commit on sprint/002. Do NOT ask for confirmation.
   Say SPRINT_002_COMPLETE."
```

### Step 5: Out-of-Process change 2

```bash
docker exec clasi-e2e claude -p \
  --dangerously-skip-permissions --model anthropic/claude-sonnet-4.5 --output-format text --max-turns 5 \
  "$(./oop.sh 2)"
```

Tells Claude to add `__version__` to `__init__.py` as a bypassed edit.

### Step 6: Sprint 003 — Color guessing game

```bash
docker exec clasi-e2e claude -p \
  --dangerously-skip-permissions --model anthropic/claude-sonnet-4.5 --output-format text --max-turns 35 \
  "Sprint 003: Color Guessing Game. Secret: blue (case-insensitive, strip
   whitespace). 3 guesses. Correct: Correct! You got it!. Wrong: Nope,
   try again. 3 wrong: Sorry! The answer was blue. Wire to menu choice 2.
   Plan, ticket, execute, close, merge. No confirmation.
   Say SPRINT_003_COMPLETE."
```

### Step 7: Out-of-Process change 3

```bash
docker exec clasi-e2e claude -p \
  --dangerously-skip-permissions --model anthropic/claude-sonnet-4.5 --output-format text --max-turns 5 \
  "$(./oop.sh 3)"
```

Tells Claude to add a TODO comment to number_game.py as a quick bypass.

### Step 8: Sprint 004 — City guessing game

```bash
docker exec clasi-e2e claude -p \
  --dangerously-skip-permissions --model anthropic/claude-sonnet-4.5 --output-format text --max-turns 30 \
  "Sprint 004 (FINAL): City Guessing Game. Secret: Paris (case-insensitive,
   strip whitespace). 3 guesses. Correct: Correct! You got it!. Wrong:
   Nope, try again. 3 wrong: Sorry! The answer was Paris. Wire to menu
   choice 3. Plan, ticket, execute, close, merge. No confirmation.
   Say SPRINT_004_COMPLETE."
```

### Step 9: Validate

```bash
./validate.sh
```

All checks must pass. If the close was interrupted by `max-turns`, run a
short catch-up command:

```bash
docker exec clasi-e2e claude -p \
  --dangerously-skip-permissions --model anthropic/claude-sonnet-4.5 --output-format text --max-turns 20 \
  "Close sprint 004: write close-report, merge to master, tag. Code + tests
   are DONE. Do NOT re-implement anything. SPRINT_004_COMPLETE."
```

### Step 10: Clean up

```bash
./stop.sh
```

## OOP Change Details

| After sprint | Script | What it changes | What it tests |
|-------------|--------|-----------------|---------------|
| 001 | `./oop.sh 1` | Fix menu title capitalization | Next sprint doesn't revert the fix |
| 002 | `./oop.sh 2` | Add `__version__` to package init | Next sprint preserves the version |
| 003 | `./oop.sh 3` | Add TODO comment to number_game.py | Next sprint doesn't strip comments |

## What To Do If Things Go Wrong

| Symptom | Action |
|---------|--------|
| Container not running | `./stop.sh && ./start.sh` (data persists in named volume) |
| Sprint hits max-turns without `COMPLETE` | Re-run with higher `--max-turns` or a catch-up prompt |
| `claude -p` returns error about API key | Verify `OPENROUTER_API_KEY` is set and valid |
| Docker commands hang | OrbStack may be slow — wait 30s and retry |
| Tests fail after OOP change | The change may have broken something — inspect `project/` dir |

## The Rubric

After all 4 sprints and 3 OOP changes, `./validate.sh` checks:

### Process Artifacts
- [ ] `docs/design/overview.md` exists and describes the project
- [ ] Each sprint has a plan, tickets, and close report

### Ticket Lifecycle
- [ ] 3 tickets per sprint, all `status: done`
- [ ] Tickets show state transitions (in-progress → done)
- [ ] Tickets have acceptance criteria with checkboxes

### Sprint Closure
- [ ] All 4 close reports exist
- [ ] All 4 sprints are `phase: done` in the state DB

### Code Quality
- [ ] `python -m guessing_game` runs and displays the menu
- [ ] All 3 games: accept guesses, limit 3, return to menu
- [ ] `q` quits, invalid input shows error
- [ ] `python -m pytest` — 37+ tests, 0 failures

### Git Hygiene
- [ ] ≥10 commits (1 per sprint + tickets + OOPs)
- [ ] Branches per sprint
- [ ] No uncommitted changes

### OOP Change Resilience
- [ ] All 3 OOP commits are in git history (not squashed or reverted)
- [ ] OOP change 1: menu title case survived
- [ ] OOP change 2: `__version__` survived in `__init__.py`
- [ ] OOP change 3: TODO comment survived in `number_game.py`

## Files In This Directory

| File | Purpose |
|------|---------|
| `AGENTS.md` | **This file** — agent instructions |
| `Dockerfile` | Container image with Python, Node, Claude Code, clasi |
| `entrypoint.sh` | Runs inside container: clasi init → git → spec → tmux |
| `start.sh` | Build image + start container + bind mount |
| `stop.sh` | Stop and remove container |
| `validate.sh` | Rubric checker — run after all sprints |
| `oop.sh` | Out-of-process change script (run between sprints) |
| `guessing-game-spec.md` | The 4-sprint spec baked into the container |
| `.dockerignore` | Excludes `project/` from build context |