---
status: done
sprint: 008
tickets:
- 008-002
---

# `close_sprint` "not found in active or done" error misdirects diagnosis

## Context

Discovered in the same debugging session as `frontmatter-silent-on-malformed-fence.md`. After fixing the frontmatter corruption, `close_sprint` worked. But the error message it produced beforehand sent diagnosis down the wrong path.

The error returned by `_close_sprint_full` at [clasi/tools/artifact_tools.py:1146-1155](clasi/tools/artifact_tools.py):

```json
{
  "step": "precondition",
  "message": "Sprint '007' not found in active or done",
  "recovery": {
    "instruction": "Create or restore the sprint directory."
  }
}
```

In reality, the sprint directory **was** present. The `sprint.md` file **was** present. The failure was caused by the frontmatter parser silently returning empty fields, so the id-match in `project.get_sprint` failed. The recovery instruction tells the operator to "create or restore the sprint directory" — but no recreation is needed; the directory is already there.

## The bug

`_close_sprint_full` catches `ValueError` from `project.get_sprint(sprint_id)` and reports "not found in active or done." That catch-all assumes the only reason `get_sprint` raises is that the directory is genuinely absent. It is not — any condition that causes the id-match to fail produces the same exception, including:

- Corrupt or missing frontmatter (the case observed).
- Frontmatter present but `id:` field missing or empty.
- Frontmatter present with `id: 7` (integer) when the lookup passes `"007"` (string).
- Directory present without a `sprint.md` (the iteration skips it, no warning).

Each of these would surface as "not found, create or restore the directory" — which is wrong guidance in every case except a genuinely-missing directory.

## Proposed behavior

`project.get_sprint(sprint_id)` should distinguish between:

1. **No matching directory** — current message is correct.
2. **Directory present, frontmatter missing or unparseable** — report which file and why.
3. **Directory present, frontmatter parsed, id mismatch or absent** — report the mismatch.

Either change `get_sprint` to raise typed exceptions (`SprintDirectoryNotFoundError`, `SprintFrontmatterError`, `SprintIdMismatchError`) and have `close_sprint` translate them into specific recovery instructions, or do the discrimination inside `close_sprint`'s precondition by scanning the sprints dir before catching.

Pairs naturally with `frontmatter-silent-on-malformed-fence.md` — the upstream fix (a warning/exception on malformed frontmatter) would let `close_sprint` produce a precise error message instead of the generic "not found" one.

## Acceptance

- When `sprint.md` is malformed, `close_sprint`'s error names the file and the parse failure, not "create the sprint directory."
- The recovery `instruction` is actionable for the actual fault.
