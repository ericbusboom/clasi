---
status: done
github-issue: ericbusboom/clasi#16
sprint: '012'
---

# State-machine predicates read artifact paths that don't match where writers create them (blocks all transitions)

> Imported from [ericbusboom/clasi#16](https://github.com/ericbusboom/clasi/issues/16)
**clasi version:** 0.20260603.2

CLASI state-machine predicates read artifacts from paths/filenames that do not match where the project model (`clasi/project.py`, `clasi/sprint.py`) and the MCP artifact tools actually **write** them. The writers succeed, but the predicates report the files absent, so the project/sprint/ticket machines compute state `unknown` and no transition can fire after artifact creation.

## Two layers disagree on every artifact path

**WRITE side** (`clasi/project.py` — internally consistent, uses `.clasi/`):
- `clasi_dir = <root>/.clasi`
- `sprints_dir = .clasi/sprints`
- sprint dir name = `<id>-<slug>` (e.g. `.clasi/sprints/001-concurrent-start-.../`)
- sprint use-cases file = `usecases.md` (`clasi/sprint.py` ~line 104/126)
- ticket filename = `<ticket_id>-<ticket_slug>.md` (`clasi/sprint.py` `create_ticket` ~line 225: `path = self.tickets_dir / f"{ticket_id}-{ticket_slug}.md"`)
- overview written by the project-initiation skill to `.clasi/design/overview.md`

**READ side** (`clasi/state_machine/predicates/*.py` — hardcodes `docs/clasi/` + different names):
- `project.py`: `is_overview_present` checks `docs/clasi/overview.md`
- `sprint.py`: checks `docs/clasi/sprints/{sprint_id}/sprint.md`, `.../architecture-update.md`, `.../use-cases.md` (**hyphen**), `.../close-report.md`
- `ticket.py`: `is_ticket_file_present` checks `docs/clasi/sprints/{sprint_id}/tickets/{ticket_id}.md` and `.../tickets/done/{ticket_id}.md`

## Three concrete mismatches
1. **Directory root:** writers use `.clasi/...`; predicates read `docs/clasi/...`.
2. **Sprint dir name:** writers create `<id>-<slug>` (e.g. `001-concurrent-start-...`); predicates read bare `{sprint_id}` (e.g. `001`).
3. **Filenames:** writers produce `usecases.md` and `<id>-<slug>.md` tickets; predicates read `use-cases.md` and `{ticket_id}.md` (id only).

## Reproduction
1. Fresh project; run project-initiation skill → writes `.clasi/design/overview.md`.
2. `clasi status` still shows project `uninitialized`; `initialize` blocked by `is_overview_present` (predicate reads `docs/clasi/overview.md`, which doesn't exist).
3. Manually copy overview to `docs/clasi/overview.md` → project advances to `planning` (confirms the path-drift diagnosis).
4. Dispatch sprint-planner → `create_sprint` + `create_ticket` write to `.clasi/sprints/001-<slug>/tickets/001-<slug>.md`.
5. `clasi status` reports `state_drift` for the sprint ("declared 'planning-docs' is not a recognised sprint machine state") and for every ticket ("declares status='open' but is_ticket_file_present is False"). All tickets compute `unknown`; no transition fireable.

## Impact
End-to-end CLASI process is unusable on a real project: initiation, sprint planning, and ticket execution all create artifacts the state machine cannot see. We had to hand-mirror files into `docs/clasi/` with renamed files just to advance a single transition.

## Suggested fix
Make the predicates' reader resolve artifact paths through the same project model used by the writers (`clasi/project.py`: `clasi_dir` / `sprints_dir` / sprint dir slug / ticket filename scheme) instead of hardcoding `docs/clasi/...` + bare ids + hyphenated names. Single source of truth for paths.

**Secondary:** the sprint state machine doesn't recognise the `planning-docs` status the planner sets (known states: `open, planned, pre-flight, ticketed, executing, review, closed`) — reconcile the planner's status vocabulary with the sprint machine.
