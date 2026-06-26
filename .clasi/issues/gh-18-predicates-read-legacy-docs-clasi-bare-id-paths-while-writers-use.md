---
status: pending
github-issue: ericbusboom/clasi#18
sprint: '012'
---

# Predicates read legacy docs/clasi/ bare-ID paths while writers use .clasi/ slugged paths → permanent gate blocks + state_drift

> Imported from [ericbusboom/clasi#18](https://github.com/ericbusboom/clasi/issues/18)
## Summary

The `docs/clasi/` → `.clasi/` storage migration is only half-applied. **Write/storage code stores artifacts under `.clasi/` with slugged directory and file names, but the state-machine predicates still hardcode the legacy `docs/clasi/` root with bare-ID names.** As a result the predicates can never see the artifacts the tools actually wrote, gates that depend on those predicates stay permanently blocked, and `get_status` reports persistent `state_drift`.

There are really **two layered mismatches**:

1. **Root mismatch** — predicates read `docs/clasi/…`; writers write `.clasi/…`.
2. **Name mismatch** (even after the root is fixed):
   - sprint/ticket dirs are **slugged** on write (`.clasi/sprints/001-foundations-…/`, `tickets/001-no-hw-….md`) but predicates expect **bare IDs** (`…/sprints/001/`, `…/tickets/001.md`);
   - sprint use-cases predicate expects **`use-cases.md`** (hyphenated) while the writer emits **`usecases.md`**;
   - overview predicate checks top-level **`docs/clasi/overview.md`** while the writer stores **`.clasi/design/overview.md`**.

## Environment

- CLASI version: `0.20260603.3` (`get_version` → metadata_version `0.20260603.3`)
- Install: pipx venv, Python 3.14.5
- Source path: `…/site-packages/clasi/__init__.py`

## Root cause (exact locations in installed source)

Predicates still pointing at `docs/clasi/` with bare IDs:

- `clasi/state_machine/predicates/project.py:30,36` — `ctx.reader.file_exists("docs/clasi/overview.md")` (`is_overview_present` / `_absent`)
- `clasi/state_machine/predicates/ticket.py:30-31` — `is_ticket_file_present`:
  ```python
  active = f"docs/clasi/sprints/{ctx.sprint_id}/tickets/{ctx.ticket_id}.md"
  done   = f"docs/clasi/sprints/{ctx.sprint_id}/tickets/done/{ctx.ticket_id}.md"
  ```
- `clasi/state_machine/predicates/sprint.py:33,41,49,123`:
  ```python
  f"docs/clasi/sprints/{ctx.sprint_id}/sprint.md"
  f"docs/clasi/sprints/{ctx.sprint_id}/architecture-update.md"
  f"docs/clasi/sprints/{ctx.sprint_id}/use-cases.md"     # note: hyphenated
  f"docs/clasi/sprints/{ctx.sprint_id}/close-report.md"
  ```

Writers/storage that actually create the artifacts (under `.clasi/`, slugged, `usecases.md`):

- `clasi/sprint.py:99,104,121,126` — `sprint.md`, `usecases.md` resolved under the slugged sprint dir
- `clasi/project.py:110,167,204,219-220` — sprint dirs created/scanned under `.clasi/sprints/<id>-<slug>/`
- `clasi/migrate_command.py` / `cli.py:144` — the migration that moved storage `docs/clasi/ → .clasi/` (predicates were not moved with it)

So `sprint.py:49`'s `use-cases.md` vs `sprint.py:104`'s `usecases.md` is an internal contradiction inside the same release.

## Symptoms (observed in a real project)

`get_status` on a project where all 7 tickets of sprint 001 are `done` and the sprint is closed:

```yaml
- name: confirm-pre-flight        # blocked even though tickets exist on disk
  blocked_by: [is_at_least_one_ticket]
inconsistencies:
- kind: state_drift
  machine: sprint
  id: '001'
  declared: closed
  computed: pre-flight
  explanation: sprint.md declares status='closed' but is_close_report_present,
    is_branch_merged, is_review_satisfied are False.
```

The artifacts all exist under `.clasi/`; the predicates just look in `docs/clasi/` with the wrong names, so they report "missing."

## Reproduction

1. Use the MCP write tools (`create_sprint`, `create_ticket`, etc.) — they write to `.clasi/sprints/<id>-<slug>/…` with slugged names.
2. Call `get_status` / try to fire a gate gated on `is_at_least_one_ticket`, `is_sprint_doc_present`, `is_usecases_present`, `is_ticket_file_present`, or `is_overview_present`.
3. The predicate returns False (looks under `docs/clasi/<bare-id>/…`), so the gate is permanently blocked and status shows `state_drift`.

## Expected vs actual

- **Expected:** predicates resolve against the same root/names the write tools use, so artifacts created by the tools satisfy their own gates.
- **Actual:** predicates check `docs/clasi/<bare-id>/{sprint.md,use-cases.md,tickets/<id>.md,…}` and never match the slugged `.clasi/` artifacts.

## Suggested fix

Move the predicates onto the same path resolution the writers use, rather than hardcoded string paths:

1. Change the `docs/clasi/` literals in `predicates/{project,ticket,sprint}.py` to `.clasi/` (or, better, resolve via the same Sprint/Project path helpers in `sprint.py`/`project.py` so slug↔id lookup is centralized).
2. Resolve sprint/ticket directories by **ID prefix match** (`<id>-*`) instead of an exact bare-ID directory name, to handle slugs.
3. Reconcile `use-cases.md` vs `usecases.md` — pick one and use it in both the predicate (`sprint.py:49`) and the writer (`sprint.py:104`).
4. Reconcile `overview.md` location — predicate checks `docs/clasi/overview.md`; writer stores `.clasi/design/overview.md`.
5. Add a regression test that creates a sprint+ticket via the write tools and asserts the corresponding predicates return True.

## Current workaround

We maintain a `scripts/clasi_compat_sync.py` that rebuilds a `docs/clasi/` tree of **relative symlinks** mirroring `.clasi/` into the exact legacy bare-ID paths/names (incl. aliasing `usecases.md` → `use-cases.md`), since `file_exists` follows symlinks. It satisfies the path/name predicates but **not** the close-gate predicates (`is_close_report_present`, `is_branch_merged`, `is_review_satisfied`), so `state_drift` on closed sprints persists. It must be re-run after every create/close. This is a brittle stopgap, not a fix.
