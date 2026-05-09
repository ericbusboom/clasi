---
id: "F"
title: "clasr settings.json multi-provider uninstall — preserve other provider's data"
status: planning
branch: sprint/F-clasr-settings-multi-provider-uninstall
use-cases: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint F: clasr settings.json multi-provider uninstall — preserve other provider's data

## Goals

Fix the bug where `clasr` uninstall removes another provider's data when both providers contributed to the same top-level JSON key in `settings.json`. Implement a deep-diff manifest so uninstall reverses exactly what each provider added, no more.

## Problem

When two providers both contribute to the same top-level JSON key in `settings.json` (e.g. both add entries to `permissions.allow`, both set `model`), the current `merge_json_files` records only "this provider contributed top-level key X." On uninstall, popping key X removes the **other** provider's data along with this one's. The file becomes `{}` and gets deleted by the empty-file rule.

This is the realistic case for AI-agent settings. Surfaced 2026-05-02 by `tests/justfile`'s multi-tenant demo: provider1 installs `settings.json` with `model` and `permissions`; provider2 installs `settings.json` with different `model` and `permissions`; merge succeeds (deep-merge, last-write-wins on conflicts); provider2 uninstall pops `model` and `permissions` — provider1's settings are gone.

Sprint 014's keys-list manifest only tracks top-level keys contributed; it doesn't track which **nested** keys this specific provider added. Hence the regression.

## Solution

Implement **option 2** from the source TODO: deep-diff manifest.

1. **At install time**, record the deep-diff between pre-merge and post-merge state. The manifest entry for each merged JSON file lists exactly which nested key paths this provider added (or the leaf-value contributed). Schema:
   ```json
   {
     "path": ".claude/settings.json",
     "kind": "json-merged",
     "diff": {
       "added_paths": [["permissions", "allow", 2], ["permissions", "allow", 3], ["model"]],
       "values": { "model": "claude-opus-4-7", "permissions.allow[2]": "Bash(*)", ... }
     }
   }
   ```
2. **At uninstall time**, walk the diff and reverse it precisely:
   - Scalar leaves recorded by this provider → remove the leaf.
   - Array entries recorded by this provider → remove by **value match** (not by index — indices are fragile after later modifications).
   - Empty objects/arrays after removal → recursively prune.
   - File becomes `{}` → delete.
3. **Existing manifest format compatibility** — older manifests written before this sprint use the keys-list format. Detect and fall back: if `diff` is absent, behave as today (knowing it's lossy). Document this in changelog.
4. **Test the multi-provider case end-to-end** — `tests/clasr/test_multi_tenant.py` gets a settings.json scenario: install provider1, install provider2 with overlapping keys, uninstall provider2, verify provider1's data intact.
5. **Add a documentation note** to `clasr/SCHEMA.md`: "JSON-merged settings can be safely uninstalled when each provider's contributions are recoverable from the manifest. Avoid manual edits to merged settings.json that overlap with provider-managed entries — those manual edits will not be tracked."

## Success Criteria

- `tests/clasr/test_multi_tenant.py` covers: install→install→uninstall sequence with overlapping `model` and `permissions.allow` entries; verify residual file matches provider1's original contributions exactly.
- `clasr` manifest schema gains a `diff:` field for `kind: json-merged` entries.
- Old-format manifests still uninstall (back-compat fallback path with a one-line warning logged).
- Array-entry removal is value-based, not index-based — proven by a test that mutates the array between install and uninstall and verifies correct removal.
- `clasr/SCHEMA.md` documents the deep-diff manifest entry shape.
- Empty-file deletion still works after deep-diff uninstall.

## Scope

### In Scope

- Deep-diff manifest computation and storage.
- Reversal logic in uninstall.
- Multi-tenant settings.json test coverage.
- Back-compat fallback for old-format manifests.
- SCHEMA.md update.

### Out of Scope

- The other three options from the source TODO (top-level-key paths, snapshot-based, documentation-only) — picking option 2 as the right long-term answer.
- Per-provider sub-keys convention (`permissions.byProvider.example`) — that was the workaround, not the fix.
- Migrating existing manifests to the new format — they'll auto-migrate on next install via the back-compat path.
- TOML or YAML merge support — settings.json is the case. Other formats use the existing copy/symlink path.

## Test Strategy

- Unit: deep-diff computation against pre/post snapshots; rejection cases (malformed JSON, conflicting types).
- Unit: uninstall reversal — scalar leaves, array entries, nested objects, recursive pruning.
- Integration: `test_multi_tenant.py` install→install→uninstall sequence; diff-based provider isolation verified.
- Regression: existing single-provider install/uninstall sequences pass unchanged.
- Edge case: array entry mutated between install and uninstall (e.g. permission re-ordered) — value-match removal still finds it.

## Architecture impact

Localized to `clasr/manifest.py` and `clasr/platforms/copilot.py` (and any other platform that uses `merge_json_files`). No architectural change to the larger system.

## Dependencies / sequencing notes

- Independent of Sprints A, B, C, D, E. Can run in parallel with any of them.
- Best landed soon — the bug exists in shipped code (sprint 014).

## Source TODO

- `clasr-settings-json-multi-provider-uninstall-overlapping-top-level-keys.md` (as-is)
