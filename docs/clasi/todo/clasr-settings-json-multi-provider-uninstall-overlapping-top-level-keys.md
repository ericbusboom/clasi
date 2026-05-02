---
status: pending
---

# clasr settings.json multi-provider uninstall loses other provider's data when top-level keys overlap

When two providers both contribute to the same top-level JSON key (e.g. both write `permissions: {allow: [...]}` or both write `mcpServers: {...}`), the `merge_json_files` function records "this provider contributed top-level key X" in its manifest. On uninstall, that provider's manifest entry pops key X, which removes the OTHER provider's data along with this provider's data.

Surfaced by: `tests/justfile` multi-tenant demo. provider1 installs `settings.json` with `model` and `permissions`. provider2 installs `settings.json` with `model` and `permissions` (different inner values). Merge succeeds (deep-merge, last-write-wins on conflicts). provider2 uninstall pops `model` and `permissions` — provider1's settings are gone too. File becomes `{}` and gets deleted by the empty-file rule.

This is the realistic case for AI-agent settings (both providers want to add to `permissions.allow`, both want to set `model`, etc.). The keys-list manifest design from ticket 013 only tracks TOP-LEVEL keys contributed; it doesn't track which nested keys this specific provider added.

## Possible fixes (architect to choose)

1. Record nested-key paths instead of top-level keys: e.g. `["permissions.allow[2]", "permissions.allow[3]", "model"]`. Uninstall walks each path and removes only the leaf value. Complex for arrays — index-based paths are fragile after later modifications.

2. Record the deep-diff: at install time, record exactly which nested key paths this provider added (or the value of each leaf this provider contributed). Uninstall reverses the deep-diff. Most precise; non-trivial implementation.

3. Snapshot-based: each provider's manifest entry records the FULL pre-merge state of the file. Uninstall reverts to that snapshot. Simple but doesn't compose well with three+ providers.

4. Document the limitation clearly: "JSON-merged uninstall is per-top-level-key. If multiple providers contribute to the same top-level key, uninstalling either may remove the other's contribution. For settings.json, prefer scoping each provider's contributions under a unique top-level key (e.g. `permissions.byProvider.example`)." This shifts the burden to consumers.

Recommend option 2 (deep-diff) as the right long-term answer. Option 4 is acceptable as a short-term documentation fix.

## Workaround for now

In `tests/justfile` and in any consumer, structure `settings.json` so different providers use DIFFERENT top-level keys.

## Blocking?

Not blocking — sprint 014 ships as designed. This is a refinement for a future sprint.

## Origin

`tests/justfile` demo on 2026-05-02 surfaced the problem. The behavior matches the design from sprint 014 ticket 013 (keys-list manifest), but the design's implications for realistic `settings.json` overlap weren't fully appreciated at the time.
