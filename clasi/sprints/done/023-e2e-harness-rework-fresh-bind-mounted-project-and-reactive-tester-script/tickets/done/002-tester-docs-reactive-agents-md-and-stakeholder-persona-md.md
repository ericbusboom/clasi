---
id: '002'
title: 'Tester docs: reactive AGENTS.md and stakeholder-persona.md'
status: done
use-cases: []
depends-on:
- '001'
github-issue: ''
issue: clasi-e2e-harness-rework-fresh-bind-mounted-project-reactive-tester-script.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Tester docs: reactive AGENTS.md and stakeholder-persona.md

## Description

Replace `AGENTS.md`'s fixed script of verbatim subject prompts with a
reactive situation→action playbook, and add a new
`stakeholder-persona.md` that supplies the phrasing register the
playbook points at. Depends on ticket 001 because the playbook must
reference the corrected flags (`--resume`, `--wipe`), env knobs
(`E2E_MODEL`, `E2E_SMALL_MODEL`, `CLASI_SOURCE`), and paths
(`docs/design/overview.md`, `clasi/sprints/...`) that ticket 001
establishes — writing this ticket first would either invent stale
references or require rework once T1 lands.

Terminology carried throughout both documents: **tester** = Claude Code
on the host driving the test; **subject** = Claude Code inside the
container executing CLASI.

### `tests/e2e/stakeholder-persona.md` (new)

Create verbatim from the issue's Appendix A ("Stakeholder Persona: How
Eric Actually Uses CLASI"). Preserve all quoted material exactly as
written in the issue — these are mined from real session transcripts and
their specific phrasing (including the described speech-to-text
garbling: "clazy", "classy", "clausi", "quasi", dropped letters) is the
point of the document, not incidental color. Sections to carry over:

1. Key structural finding (natural language, not slash commands)
2. Creating issues
3. Starting/planning sprints
4. Making changes
5. Out-of-process (OOP)
6. Corrections/feedback
7. Review/validation habits
8. Style/voice
9. Session arc
10. Role-play summary for the tester

### `tests/e2e/AGENTS.md` (full rewrite)

Restructure per the issue's Proposed fix section into:

1. **Roles**: tester (host) vs. subject (container). Mission: drive the
   guessing-game project through 4 sprints + 3 OOP changes *the way a
   human stakeholder would*, then validate mechanically.
2. **Harness usage**: `./start.sh` (fresh) / `--resume` / `./stop.sh
   [--wipe]`; env knobs `E2E_MODEL` (default `anthropic/claude-opus-4.8`),
   `E2E_SMALL_MODEL`, `CLASI_SOURCE`; project directory location and the
   symlink fallback caveat from ticket 001.
3. **Launching subject sessions**: `docker exec clasi-e2e claude -p
   --dangerously-skip-permissions --output-format text --max-turns <N>
   "<prompt>"` — runs in `/project` via the image's `WORKDIR`; env
   carries the API key, base URL, and model, so no `--model` flag is
   needed. Max-turns guidance: sprint about 40-50, OOP about 5-10,
   catch-up/close about 20.
4. **No verbatim prompts.** A situation→action playbook; each entry
   states what the prompt must *convey*, not what to type, and points at
   `stakeholder-persona.md` for phrasing. Situations to cover (content
   per the issue's Proposed fix section):
   - Fresh environment → start the harness; introduce the project as a
     stakeholder would (point at `docs/guessing-game-spec.md`, name the
     first sprint's goal, authorize autonomy in the stakeholder's idiom).
   - Sprint finished cleanly → review artifacts like the stakeholder
     would (inspect the sprint dir, tickets in `done/`), then kick off
     the next sprint conversationally.
   - Subject stalls / asks for confirmation → respond in-persona ("run it
     all the way through", "carry on").
   - Between sprints → make the scripted OOP change (content sourced from
     `oop.sh`), phrased in the stakeholder's OOP register.
   - Sprint hits max-turns → continuation in the stakeholder's resume
     idiom, with catch-up turn budget guidance.
   - Artifacts look wrong → interrogate before fixing (e.g., "why is
     sprint X still open?").
5. **Rubric**: `validate.sh` is the mechanical rubric (real paths per
   ticket 001); explicitly drop references to invented artifacts
   (`close-report.md`, `planning-docs/`, "37+ tests" counts) that no
   longer apply.
6. **Environment noise notes**: `close_sprint`'s tag-push failure (no git
   remote inside the container) is expected, not a clasi bug; note
   OrbStack slowness as another expected-noise item.
7. **Corrected file inventory table** reflecting ticket 001's changes:
   drop `start-container.py`, add `stakeholder-persona.md`, keep the
   rest with corrected one-line descriptions.

## Acceptance Criteria

- [x] `tests/e2e/stakeholder-persona.md` exists and reproduces the
      issue's Appendix A content, preserving all quoted material
      verbatim.
- [x] `tests/e2e/AGENTS.md` contains **no verbatim subject prompt text**
      for any sprint step or OOP step — grep for the old exact prompts
      (e.g. "Sprint 001: Project structure and menu...") returns nothing.
- [x] `AGENTS.md`'s playbook is organized by situation (fresh
      environment, sprint finished, subject stalls, between sprints,
      max-turns hit, artifacts look wrong), not by a fixed step sequence.
- [x] Every situation entry states what the prompt must convey and
      references `stakeholder-persona.md` for phrasing.
- [x] `AGENTS.md`'s harness-usage section documents `--resume`,
      `--wipe`, `E2E_MODEL`, `E2E_SMALL_MODEL`, and `CLASI_SOURCE` as
      established by ticket 001.
- [x] `AGENTS.md`'s rubric section references `validate.sh`'s real
      checks and does not mention `close-report.md`, `planning-docs/`,
      or a fixed test count.
- [x] `AGENTS.md`'s file inventory table matches the actual post-ticket-001
      contents of `tests/e2e/` (no `start-container.py`; includes
      `stakeholder-persona.md`).

## Testing

- **Existing tests to run**: `uv run pytest` (repo suite; unaffected by
  this documentation-only ticket, but must still pass clean).
- **New tests to write**: none — these are Markdown documentation files
  with no executable surface. Verification is manual review against the
  acceptance criteria above (grep checks for absent verbatim prompts,
  presence of required sections).
- **Verification command**: `uv run pytest`.
