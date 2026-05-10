---
sprint: 019
status: done
---

# Use Cases — Sprint 019: clasr settings.json multi-provider uninstall fix

## SUC-001: Two providers install overlapping top-level JSON keys

**Actor**: Operator running `clasr install` for two independent providers.

**Precondition**: A target project directory exists with no prior `clasr` installs. Both
`provider1` and `provider2` have `asr/` source directories that each include a
`claude/settings.json` file. Both files contain the same top-level keys (`model`,
`permissions`), with different nested values.

**Main flow**:
1. Operator installs provider1: `clasr install --source provider1 --provider provider1 --claude --target project`.
2. `settings.json` from provider1 is written as a plain copy into `.claude/settings.json`.
   provider1's manifest records this entry as `kind: "copy"`.
3. Operator installs provider2: `clasr install --source provider2 --provider provider2 --claude --target project`.
4. clasr detects that `.claude/settings.json` already exists.
5. clasr computes the deep-diff: the exact leaf paths and values that provider2's
   `settings.json` would contribute beyond the pre-merge state.
6. The merged result is written to `.claude/settings.json`.
7. provider2's manifest records the entry as `kind: "json-merged"` with a `"contributed"`
   field holding the deep-diff snapshot (not merely top-level key names).
8. A WARNING is emitted to stderr for each conflicting key, naming both providers.

**Postcondition**: `.claude/settings.json` contains values from both providers. provider2's
manifest records the precise leaf-level contribution, not just top-level key names.

---

## SUC-002: Uninstalling provider2 preserves provider1's data for overlapping keys

**Actor**: Operator running `clasr uninstall` for provider2.

**Precondition**: SUC-001 has completed. Both providers are installed; settings.json
contains merged data from both, with overlapping top-level keys (`model`, `permissions`).

**Main flow**:
1. Operator runs: `clasr uninstall --provider provider2 --claude --target project`.
2. clasr reads provider2's manifest entry for `.claude/settings.json` (`kind: "json-merged"`).
3. clasr reads the `"contributed"` deep-diff from provider2's manifest entry.
4. clasr reverses only provider2's contribution: walks the contributed leaf paths and
   removes only the specific nested values provider2 added.
5. For array values that provider2 appended to (e.g. `permissions.allow`), only the
   elements provider2 added are removed; provider1's elements are preserved.
6. For scalar values where provider2 overwrote provider1 (`model`), the scalar is
   removed; provider1's original value is NOT restored (it was captured in provider1's
   own manifest for its own uninstall to handle).
7. The resulting `.claude/settings.json` is written back (provider1's remaining
   contribution stays).
8. provider2's manifest file is deleted.

**Postcondition**: `.claude/settings.json` contains only provider1's contributed data.
provider1's `model` and `permissions.allow` entries are present and intact.

---

## SUC-003: Uninstalling provider1 after provider2 is gone leaves no orphaned data

**Actor**: Operator running `clasr uninstall` for provider1.

**Precondition**: SUC-002 has completed. Only provider1 is installed; `.claude/settings.json`
contains provider1's data only.

**Main flow**:
1. Operator runs: `clasr uninstall --provider provider1 --claude --target project`.
2. clasr reads provider1's manifest entry for `.claude/settings.json` (`kind: "copy"`).
3. For a `"copy"` entry, uninstall deletes the file outright (as before; no change to
   this path).
4. `.claude/settings.json` is deleted.
5. provider1's manifest file is deleted.

**Postcondition**: `.claude/settings.json` does not exist. No orphaned data from either
provider remains. Empty directories are cleaned up.

---

## SUC-004: Non-overlapping keys — uninstall removes only the contributing provider's keys

**Actor**: Operator running `clasr uninstall` for provider2 when providers use different
top-level keys.

**Precondition**: provider1 installed `settings.json` with `keyA`; provider2 merged in
`keyB` (no overlap). Both are present in `.claude/settings.json`.

**Main flow**:
1. Operator uninstalls provider2.
2. clasr reverses provider2's deep-diff: removes `keyB` only.
3. `.claude/settings.json` remains with `keyA` intact.

**Postcondition**: Existing behavior is preserved. The deep-diff approach produces the
same result for non-overlapping keys as the old top-level keys approach.

---

## SUC-005: Old-format manifest fallback during uninstall

**Actor**: Operator uninstalling a provider whose manifest was written by a pre-sprint-019
version of clasr (manifest entry has `"keys"` list but no `"contributed"` deep-diff).

**Precondition**: provider2's manifest entry for `.claude/settings.json` is in the old
format: `{"kind": "json-merged", "keys": ["model", "permissions"]}` with no `"contributed"`
field.

**Main flow**:
1. Operator runs `clasr uninstall --provider provider2 --claude --target project`.
2. clasr reads provider2's manifest and finds `kind: "json-merged"` with `"keys"` but
   no `"contributed"` field.
3. clasr falls back to old behavior: removes the top-level keys listed in `"keys"` from
   the JSON file.
4. A WARNING is printed to stderr noting that the old manifest format is in use and that
   re-installing this provider will use the new deep-diff format.
5. Uninstall completes.

**Postcondition**: Old installs are not broken by the sprint-019 upgrade. Operators who
reinstall will get the new deep-diff manifest format going forward.

---

## SUC-006: `tests/justfile` multi-tenant demo passes end-to-end

**Actor**: Developer running `just demo` in `tests/asr/`.

**Precondition**: provider1 and provider2 source directories exist. provider1 contributes
`model` and `permissions`; provider2 contributes `model` and `mcpServers` (overlapping on
`model`).

**Main flow**:
1. `just demo` installs provider1, installs provider2 (deep-merge), inspects, then
   uninstalls provider2.
2. After selective uninstall, provider1's `model` and `permissions` entries are present
   in `.claude/settings.json`.
3. provider2's contributed data is absent.
4. `just uninstall-all` leaves no `settings.json`.

**Postcondition**: The full demo completes without errors. Output confirms selective
uninstall correctness.
