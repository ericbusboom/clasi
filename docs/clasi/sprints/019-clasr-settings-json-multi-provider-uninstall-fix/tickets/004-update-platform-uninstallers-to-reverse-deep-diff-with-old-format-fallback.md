---
id: "004"
title: "Update platform uninstallers to reverse deep-diff with old-format fallback"
status: todo
use-cases: [SUC-002, SUC-003, SUC-004, SUC-005]
depends-on: ["003"]
github-issue: ""
todo: ""
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update platform uninstallers to reverse deep-diff with old-format fallback

## Description

Update the `json-merged` uninstall branch in all three platform installers to reverse the
deep-diff contribution rather than popping entire top-level keys. Add a fallback code path
for manifests written by pre-sprint-019 clasr (missing `"contributed"` field) that
preserves the old top-level-key-removal behavior with a deprecation warning.

Current uninstall branch (excerpt from `claude.py`):
```python
elif kind == "json-merged":
    keys_to_remove: list[str] = entry.get("keys", [])
    ...
    for k in keys_to_remove:
        data.pop(k, None)
```

New uninstall branch:
```python
elif kind == "json-merged":
    if full_path.exists():
        data = json.loads(full_path.read_text(encoding="utf-8"))
        contributed = entry.get("contributed")
        if contributed is not None:
            # New format: reverse the deep-diff precisely.
            data = merge.reverse_diff(data, contributed)
        else:
            # Old format fallback: top-level key removal.
            print(
                f"WARNING: clasr: manifest entry for '{path_rel}' uses old format "
                f"(no 'contributed' field); falling back to top-level key removal. "
                f"Reinstall '{provider}' to upgrade the manifest.",
                file=sys.stderr,
            )
            for k in entry.get("keys", []):
                data.pop(k, None)
        if data:
            full_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        else:
            full_path.unlink(missing_ok=True)
```

This change is the core fix for the bug: provider2 uninstall no longer removes provider1's
data for keys they both contributed to.

## Acceptance Criteria

- [ ] `claude.py` uninstall: new-format manifest (`"contributed"` present) uses `merge.reverse_diff`.
- [ ] `claude.py` uninstall: old-format manifest (no `"contributed"`) falls back to top-level key pop + WARNING.
- [ ] `codex.py` uninstall: same symmetric change.
- [ ] `copilot.py` uninstall: same symmetric change.
- [ ] Uninstalling provider2 (contributed `model` + `permissions`) leaves provider1's `model` and
      `permissions` values intact in `settings.json`.
- [ ] Uninstalling provider1 after provider2 is gone deletes `settings.json` (file becomes empty).
- [ ] Old-format uninstall emits WARNING containing the path and provider name.
- [ ] Old-format uninstall still completes successfully (not an error).
- [ ] `uv run pytest tests/clasr/` passes.

## Implementation Plan

### Approach

In each platform module, update the `elif kind == "json-merged":` block inside the
`uninstall` function. The block is structurally identical in all three files.

The `merge.reverse_diff` call requires adding `import sys` if not already present (needed
for `sys.stderr` in the warning). `merge` is already imported.

### Files to modify

- `clasr/platforms/claude.py`: update `json-merged` uninstall branch in `uninstall()`.
- `clasr/platforms/codex.py`: same.
- `clasr/platforms/copilot.py`: same.

### Testing plan

- Run `uv run pytest tests/clasr/` after all three files are updated.
- The integration tests in ticket 006 specifically verify the overlapping-key uninstall
  behavior introduced by this ticket — execute ticket 006 in this same session to confirm
  the fix works end-to-end.
- The existing `test_c1_uninstall_b_leaves_a_key` test covers non-overlapping key
  uninstall and must still pass.
- Confirm `test_c2_file_deleted_when_both_uninstalled` still passes.

### Documentation updates

None beyond the code changes.
