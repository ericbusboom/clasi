# Guessing Game — CLASI E2E Test

Drive a **Claude Code** agent through the full CLASI software engineering process
to build the Guessing Game CLI from spec.

## What You're Testing

CLASI (`clasi`) is a spec-driven development system for AI coding agents. It
defines a structured process: overview → sprint plan → tickets → execute →
close. This test validates that an AI agent (Claude Code) follows that process
correctly when driven by a human-like conductor (you).

The target project is a trivial Python CLI with 3 guessing games, split across
4 sprints. The spec is at `guessing-game-spec.md`.

## Quick Start

```bash
# 1. Build and launch the Docker environment
./start.sh

# 2. In a separate terminal, connect to Claude Code
./connect.sh

# 3. Drive the process (see "Driving the Process" below)

# 4. When all 4 sprints are done, validate
./validate.sh

# 5. Clean up
./stop.sh
```

## The CLASI Solo Process

Claude Code has been initialized with `clasi init` and the guessing-game spec
is at `docs/guessing-game-spec.md`. The expected artifact tree after a complete
run:

```
docs/
├── clasi/
│   ├── overview.md                    # High-level project description
│   └── sprints/
│       ├── 001/
│       │   ├── planning-docs/         # Sprint plan documents
│       │   ├── tickets/               # Implementation tickets
│       │   │   ├── 001-001-*.md       # Ticket files
│       │   │   └── ...
│       │   └── close-report.md        # Sprint close summary
│       ├── 002/
│       │   ├── planning-docs/
│       │   ├── tickets/
│       │   └── close-report.md
│       ├── 003/
│       │   ├── planning-docs/
│       │   ├── tickets/
│       │   └── close-report.md
│       └── 004/
│           ├── planning-docs/
│           ├── tickets/
│           └── close-report.md
```

## Driving the Process

### Connection

After running `./connect.sh`, you're attached to a tmux session with Claude
Code running inside the container. The working directory is `/project`.

### Dialog Handling

On first connection, Claude Code may show a **workspace trust dialog**:

```
❯ 1. Yes, I trust this folder
  2. No, exit
```

Press **Enter** to accept (the default). If you see a permissions dialog that
defaults to "No, exit", press **Down** then **Enter** to accept.

If Claude ever asks you a question (shows `❯` and waits), answer naturally as
the project owner. When in doubt, choose the path that keeps the process moving.

### The 4 Sprints

For each sprint, send Claude Code a prompt like this (adapt sprint number
and goal):

---

> **Sprint 001**
>
> Read `docs/guessing-game-spec.md`. Follow the CLASI solo-process for
> Sprint 001 (Project structure and menu):
>
> 1. Write or update `docs/clasi/overview.md` with a high-level description.
> 2. Write a sprint plan in `docs/clasi/sprints/001/planning-docs/`.
> 3. Create implementation tickets in `docs/clasi/sprints/001/tickets/`.
> 4. Execute each ticket one at a time: set status to `in-progress`,
>    implement, write tests, mark acceptance criteria checked, set to `done`.
> 5. Verify all tests pass, then write `docs/clasi/sprints/001/close-report.md`.
>
> Commit your work at the end of the sprint. Create a branch `sprint/001`.

---

Repeat for sprints 002 (Number game), 003 (Color game), and 004 (City game).
Adapt the sprint goal in each prompt.

### Monitoring Progress

While Claude is working, it shows tool calls with `●` indicators. Wait for the
`❯` prompt before sending the next sprint prompt — that means Claude is done
and waiting for input.

If Claude gets stuck or goes off-track, you can send corrective guidance like:
- "You're overcomplicating this. The spec is simple — just follow it."
- "Remember to write tests before marking tickets done."
- "Don't create more tickets than the sprint needs."

### Important: Let Claude Drive

**Don't write code yourself.** Your job is to give Claude the sprint prompt and
corrective guidance. Claude does all the coding, ticket management, and
testing. You are the project manager, not the developer.

If Claude asks you to make a decision (e.g. "should I use argparse or a
hand-written menu?"), answer briefly and let it continue.

## The Rubric

After all 4 sprints, validate against this checklist. Every item must pass.

### Process Artifacts

- [ ] `docs/clasi/overview.md` exists and describes the project
- [ ] `docs/clasi/sprints/001/planning-docs/` has sprint plan content
- [ ] `docs/clasi/sprints/002/planning-docs/` has sprint plan content
- [ ] `docs/clasi/sprints/003/planning-docs/` has sprint plan content
- [ ] `docs/clasi/sprints/004/planning-docs/` has sprint plan content

### Ticket Lifecycle

- [ ] Each sprint has at least one ticket file in `tickets/`
- [ ] Ticket files show state transitions (in-progress → done)
- [ ] Ticket files have acceptance criteria
- [ ] All tickets across all sprints are marked `done`

### Sprint Closure

- [ ] `docs/clasi/sprints/001/close-report.md` exists
- [ ] `docs/clasi/sprints/002/close-report.md` exists
- [ ] `docs/clasi/sprints/003/close-report.md` exists
- [ ] `docs/clasi/sprints/004/close-report.md` exists

### Code Quality

- [ ] `python -m guessing_game` runs and displays the menu
- [ ] Game 1 (number) accepts guesses and returns to menu
- [ ] Game 2 (color) accepts guesses (case-insensitive) and returns to menu
- [ ] Game 3 (city) accepts guesses (case-insensitive) and returns to menu
- [ ] `q` quits the program
- [ ] Each game limits to exactly 3 guesses
- [ ] `python -m pytest` passes with no failures
- [ ] Test files exist for each game

### Git Hygiene

- [ ] At least 4 commits (one per sprint minimum)
- [ ] Branches exist for each sprint (`sprint/001`, `sprint/002`, etc.)
- [ ] No uncommitted changes at the end

### Non-Goals (things we DON'T check)

- Sprint artifacts don't need to be in a specific format — we're testing that
  the *process* produces them, not that they're perfectly formatted.
- Claude might go "out of process" on trivial changes — that's fine as long as
  the major artifacts (plans, tickets, close reports) are produced.
- The code quality only needs to be functional, not beautiful.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Can't connect to tmux | Run `docker exec -it clasi-e2e tmux attach -t claude` directly |
| Claude is unresponsive | Press Ctrl+C in tmux to cancel current operation |
| Container won't start | Check `docker ps -a` for the container status, check `docker logs clasi-e2e` |
| API key errors | Ensure `ANTHROPIC_API_KEY` is set before running `start.sh` |
| Permission denied (Linux) | `chmod +x *.sh` |