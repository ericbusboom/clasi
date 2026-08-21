---
status: in-progress
type: task
tags:
- clasr
- uninstall
- follow-up
sprint: '033'
tickets:
- 033-001
---

# Port clasr's manifest-based uninstall model into clasi.platforms

## Description

Sprint 032 ticket 002 froze the `clasr` fork and archived it out of the
repo onto a local-only branch, `archive/clasr` (not pushed to origin as
of this writing — that is a stakeholder call to make separately), and
deleted `src/clasr/`, `tests/clasr/`, and `tests/asr/` from `master`.
`src/clasi/platforms` is now the sole, authoritative implementation.
That was the right call — keeping both trees meant every platform fix
was a two-tree change — but it knowingly gives up one thing `clasr` did
better: its uninstall model.

## The problem being deferred

`src/clasi/platforms`'s uninstall (`claude.py:516-559`, and the same
pattern in `codex.py` / `copilot.py`) is **name-based**: it enumerates
the skill/agent/rule names used by the *currently installed* version of
the package and removes files matching those names. If a file was
installed by an older `clasi` whose names have since changed (a skill
renamed, an agent split, a rule file moved), uninstall never finds it
by its old name and it is silently orphaned — left behind forever,
invisible to any future uninstall. This is recorded as review finding
F14 in `docs/reviews/2026-08-reliability/04-cli-install-platforms.md:31`:

> **F14. minor / correctness — uninstall drift,
> `src/clasi/platforms/claude.py:516-559` (same pattern in
> codex/copilot)** — uninstall enumerates the *currently installed*
> package's plugin skills/agents/RULES; anything installed by an older
> clasi whose names have since changed is orphaned. clasr's manifest
> model already solves this. Fix: fold into F7 direction
> (manifest-based uninstall).

`clasr` avoided this entirely by tracking a **per-provider manifest** at
install time — an explicit record of exactly which files, marker
blocks, and merged-settings keys a given install actually wrote — and
uninstalling by replaying that manifest rather than by re-deriving
"what should be there now" from the currently-installed package. That
model doesn't drift: it doesn't matter whether names changed between
install and uninstall, because the manifest already says what to
remove.

## Proposed direction

Port the manifest-tracking approach from `clasr` into
`src/clasi/platforms`, replacing (or supplementing) the name-based
enumeration in `claude.py` / `codex.py` / `copilot.py`'s uninstall
paths. Reference implementation to study, on the `archive/clasr`
branch:

- `src/clasr/manifest.py` — the manifest read/write/schema logic.
- `src/clasr/integration.py` — how install-time writes populate the
  manifest and how uninstall reads it back to know exactly what to
  remove.

This is not scoped or estimated here — it needs its own planning pass
(sizing, whether it's a full replacement of the name-based path or an
additive safety net, migration story for installs that predate any
manifest). Flagging for a future roadmap pass to pick up.

## Priority

Not urgent. The name-based uninstall is a real but low-severity defect
(minor/correctness per F14) — it orphans files rather than corrupting
or crashing anything. No immediate user-facing pressure; this is a
"do it right when there's room" item.
