---
status: pending
sprint: '014'
---

# close_sprint: auto-detect sprint_id from current git branch when not provided

When the VS Code extension or model sends `arguments: {}` to `close_sprint`, the call fails at Pydantic validation because `sprint_id` is required. The sprint being closed is always deterministic from the current git branch name (e.g., `sprint/002-readme-tagline` → sprint `002`). Making `sprint_id` optional with git-branch auto-detection would make the empty-args case work automatically.

## Observed Pattern

The inventory MCP log shows that sometimes the model generates correct args and sometimes it generates `{}`. Making the tool tolerant of missing sprint_id eliminates the failure mode entirely.

## Fix

Change `close_sprint` and `finalize_sprint` signature from:
```python
def close_sprint(sprint_id: str, ...)
```
to:
```python
def close_sprint(sprint_id: Optional[str] = None, ...)
```

If `sprint_id` is None or empty, detect it from the current git branch:
1. Run `git branch --show-current` to get the branch name.
2. Parse the sprint ID from branch names matching `sprint/NNN-*` → `NNN`.
3. Raise a clear error if not on a sprint branch and no sprint_id provided.

Apply the same change to `finalize_sprint`.
