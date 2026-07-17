---
id: '001'
title: 'Config: sources list and doc-set opt-in flag'
status: done
use-cases:
- SUC-002
- SUC-006
depends-on: []
github-issue: ''
issue: persistent-per-subsystem-architecture-docs-with-sprint-update-overlays.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Config: sources list and doc-set opt-in flag

## Description

Extend `.clasi/config.yaml` and `Project` (`src/clasi/project.py`) to
support a `sources:` list (one or more source-tree roots, e.g. `src`,
`tests`) and a stakeholder opt-in/opt-out flag for the persistent
architecture doc set. This is foundation work — every other ticket in
this sprint (slugification, store, validator, overlay, lifecycle
integration) reads this config.

This repo currently has no `sources:` concept at all (confirmed absent
from both code and `.clasi/config.yaml`); it is genuinely new
configuration, not a rename of something existing.

## Acceptance Criteria

- [x] `.clasi/config.yaml` schema documented/supports a `sources:` key:
      a list of one or more repo-relative directory paths (e.g.
      `[src]` or `[src, tests]`).
- [x] `.clasi/config.yaml` schema supports a doc-set opt-in field (e.g.
      `design_docs: enabled` / `disabled` / absent-means-unset) distinct
      from `sources:` — absence of a decision must be distinguishable
      from an explicit opt-out, so the team-lead knows whether to prompt.
- [x] `Project` gains a way to resolve the configured `sources:` list
      (list of `Path`, absolute, resolved against project root),
      following the existing `_resolve_dir`/`_path_config` pattern used
      for `design_dir` etc. (`project.py:90-117`).
- [x] `Project` gains a way to read the opt-in/opt-out/unset tri-state
      decision.
- [x] Missing `sources:` key defaults to no source roots declared (not an
      error) — callers (validator, bootstrap) are responsible for
      treating "no sources declared" as "doc-set not usable yet."
- [x] Single vs. multiple source roots is derivable from the resolved
      list's length — this is what later tickets (002 slugification, 004
      validator) branch on.
- [x] Config round-trips: writing the opt-in decision via the same
      mechanism the team-lead will use (see ticket 008) and reading it
      back in a fresh `Project` instance returns the same value.

## Implementation Plan

**Approach**: Follow the existing `_path_config()`/`_resolve_dir()`
pattern in `project.py` (lines 90-117) rather than inventing a new
config-access mechanism. Add a `sources` property and an
`design_docs_opt_in` (or similarly named) property to `Project`, each
reading from the parsed `.clasi/config.yaml` dict.

**Files to create/modify**:
- `src/clasi/project.py` — add `sources` and opt-in properties to
  `Project`.
- `.clasi/config.yaml` (this repo's own config) — left unset here; the
  opt-in decision itself is recorded by ticket 009's bootstrap run, not
  this ticket. This ticket only adds the *capability* to declare
  `sources:` and the opt-in flag.
- Any config-loading/validation helper that currently enumerates known
  `paths:` keys should be checked for whether it needs to tolerate the
  new top-level `sources:` key (likely yes, since YAML parsing is
  generic, but confirm no strict-schema check rejects unknown keys).

**Testing plan**:
- Unit tests: `Project.sources` returns `[]` when `sources:` is absent;
  returns resolved absolute paths for one or more declared roots; opt-in
  property returns a clear "unset" sentinel when absent, and correctly
  reads `enabled`/`disabled` when set.
- Regression: existing `Project` tests (path resolution for
  issues/sprints/design/etc.) continue to pass — this ticket is
  additive only.

**Documentation updates**:
- Note the new `sources:` and opt-in keys in whatever document already
  describes `.clasi/config.yaml`'s shape (if any exists; otherwise this
  ticket's tests serve as the specification for now — later tickets'
  skill rewrites (008) will document the stakeholder-facing behavior).
