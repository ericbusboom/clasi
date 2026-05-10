---
id: "003"
title: "Update platform installers to store contributed deep-diff in json-merged manifest entries"
status: done
use-cases: [SUC-001, SUC-004]
depends-on: ["002"]
github-issue: ""
todo: ""
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update platform installers to store contributed deep-diff in json-merged manifest entries

## Description

Update the `json-merged` install branch in all three platform installers
(`claude.py`, `codex.py`, `copilot.py`) to use the new `dict` return type from
`merge_json_files` and store both `"keys"` (derived summary) and `"contributed"` (the
authoritative deep-diff) in the manifest entry.

Current manifest entry written by the install branch:
```python
entries.append({
    "path": rel_str,
    "kind": "json-merged",
    "keys": keys,          # keys is list[str]
})
```

New manifest entry:
```python
diff = merge_json_files(...)[1]   # now a dict
entries.append({
    "path": rel_str,
    "kind": "json-merged",
    "keys": list(diff.keys()),    # top-level summary for backward compat
    "contributed": diff,          # authoritative deep-diff for precise uninstall
})
```

The same change applies identically to `claude.py`, `codex.py`, and `copilot.py` since
all three implement the same `json-merged` install pattern.

## Acceptance Criteria

- [x] `claude.py` install: `json-merged` manifest entry includes `"contributed"` dict field.
- [x] `claude.py` install: `"keys"` field is `list(diff.keys())` (top-level summary).
- [x] `codex.py` install: same change applied.
- [x] `copilot.py` install: same change applied.
- [x] Installing provider2 over provider1 with overlapping `model` key: provider2's manifest
      entry `"contributed"` equals `{"model": <provider2_value>}` (not `["model"]`).
- [x] The merged `settings.json` content is unchanged (merge logic not affected).
- [x] `uv run pytest tests/clasr/` passes (full suite).

## Implementation Plan

### Approach

In each platform module, locate the `json-merged` install branch — the block that calls
`merge.merge_json_files` when the destination exists and is a JSON file. Update the
variable receiving the second return value from the function from a list variable to a
dict variable named `diff` (or similar), then update the `entries.append(...)` call.

The change is mechanical and identical in all three files. Read each file, locate the
branch, make the edit.

### Files to modify

- `clasr/platforms/claude.py`: update `json-merged` install branch (~3 lines changed).
- `clasr/platforms/codex.py`: same.
- `clasr/platforms/copilot.py`: same.

### Testing plan

- Run `uv run pytest tests/clasr/` after all three files are updated.
- The existing `test_provider_b_manifest_records_json_merged` test in `test_multi_tenant.py`
  already checks that `"mcpServers"` is in `settings_entry["keys"]`; update it to also
  assert `"contributed"` is present and is a dict.
- Run the full test suite to confirm no regressions in other entry kinds.

### Documentation updates

None beyond the code changes.
