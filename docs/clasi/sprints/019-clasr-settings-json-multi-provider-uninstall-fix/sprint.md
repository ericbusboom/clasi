---
id: "019"
title: "clasr settings.json multi-provider uninstall fix"
status: roadmap
branch: sprint/019-clasr-settings-json-multi-provider-uninstall-fix
use-cases: []
source-todos:
  - clasr-settings-json-multi-provider-uninstall-overlapping-top-level-keys.md
---

# Sprint 019: clasr settings.json multi-provider uninstall fix

## Goals

Fix clasr's `merge_json_files` function so that uninstalling one provider
reverses exactly what that provider contributed — no more, no less — even when
multiple providers write to the same top-level JSON keys (e.g. both providers
contribute to `permissions.allow` or both set `model`). Multi-tenant
`settings.json` round-trips must be safe.

## Problem

When two providers both contribute to the same top-level JSON key, the current
manifest design records "this provider contributed top-level key X." On
uninstall, that manifest entry pops the entire top-level key, which removes
the other provider's data along with this provider's data.

This was surfaced by the `tests/justfile` multi-tenant demo: provider1
installs `settings.json` with `model` and `permissions`; provider2 does the
same with different inner values. Deep-merge succeeds. Provider2 uninstall
pops `model` and `permissions` entirely — provider1's settings are gone. The
file becomes `{}` and gets deleted by the empty-file rule.

This is the realistic AI-agent settings scenario (multiple providers adding to
`permissions.allow`, both setting `model`). The keys-list manifest design from
sprint 014 ticket 013 only tracks top-level keys; it does not track which
nested keys this specific provider added.

## Solution outline

The preferred fix (option 2 from the source TODO) is a deep-diff approach:

- At install time, compute and record the exact nested key paths and leaf
  values that this provider contributed (the deep-diff between pre-merge and
  post-merge state).
- Store this diff in the provider's manifest entry rather than a list of
  top-level key names.
- On uninstall, reverse the recorded deep-diff: remove only the leaves this
  provider added, leaving other providers' contributions intact.

The alternative (option 4 — document the limitation and ask providers to use
unique top-level keys) is acceptable as a short-term documentation fix but
should not be the endpoint for a multi-tenant tool. This sprint implements the
deep-diff solution.

## Success criteria

- Installing provider1 and provider2 both contributing to `permissions.allow`
  and `model` produces a correctly deep-merged `settings.json`.
- Uninstalling provider2 leaves provider1's `permissions.allow` entries and
  `model` value intact.
- Uninstalling provider1 after that leaves an empty or absent `settings.json`
  (no orphaned provider2 data remains).
- The manifest stored for each provider records leaf-level paths, not
  top-level key names.
- The existing `tests/justfile` multi-tenant demo passes end-to-end.
- Existing unit tests for `merge_json_files` and uninstall are updated to
  cover overlapping top-level key scenarios.

## In Scope

- `clasr/merge.py` (or wherever `merge_json_files` lives): change manifest
  recording to store deep-diff (nested key paths + contributed leaf values).
- Uninstall logic: reverse deep-diff rather than pop top-level keys.
- `tests/justfile` multi-tenant demo: update to verify the fix.
- Unit tests for the new deep-diff manifest shape and uninstall reversal.

## Out of Scope

- Option 4 (documentation-only fix). This sprint implements the code fix.
- Any changes to how clasr handles non-JSON file types (markers, symlinks, etc.).
- New provider formats or new merge strategies beyond deep-diff for JSON.
- Integration registry or platform abstraction changes (see sprint 021).

## Dependencies and sequencing

- Depends on sprint 014 (clasr core) being landed. The multi-tenant merge
  machinery from 014 is the thing being fixed here.
- Independent of sprints 017, 018, 020, 021, 022. Can be scheduled any time
  after 014 closes.
- Small, self-contained bug-fix sprint. Good candidate to run early if there
  is developer bandwidth between larger sprints.

## Source TODOs

- `docs/clasi/todo/clasr-settings-json-multi-provider-uninstall-overlapping-top-level-keys.md`

## Tickets

| # | Title | Depends On |
|---|-------|------------|
