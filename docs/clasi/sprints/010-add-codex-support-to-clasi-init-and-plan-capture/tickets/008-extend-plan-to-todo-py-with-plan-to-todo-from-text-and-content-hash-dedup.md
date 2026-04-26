---
id: "008"
title: "Extend plan_to_todo.py with plan_to_todo_from_text and content hash dedup"
status: done
use-cases:
  - SUC-010
  - SUC-011
depends-on: []
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Extend plan_to_todo.py with plan_to_todo_from_text and content hash dedup

## Description

Add two new items to `clasi/plan_to_todo.py`:

1. `_content_hash(text: str) -> str` — returns a hex SHA-256 digest of the input string.
2. `plan_to_todo_from_text(text: str, todo_dir: Path) -> Optional[Path]` — writes a
   pending TODO from raw plan text, including `source: codex-plan` and `source_hash` in
   frontmatter, with de-duplication by hash.

The existing `plan_to_todo()` function is not modified. This ticket is purely additive.

This ticket can run in parallel with tickets 002, 003, and 004 since it only modifies
`plan_to_todo.py`, which has no dependencies on the platforms package.

## Acceptance Criteria

- [x] `clasi/plan_to_todo.py` exports `plan_to_todo_from_text` and `_content_hash`.
- [x] `plan_to_todo_from_text(text, todo_dir)`:
  - Extracts title from first `# Heading` in `text` (or uses `"untitled-plan"` slug).
  - Computes `source_hash = _content_hash(text)`.
  - Scans `todo_dir` (and `todo_dir/in-progress/`) for any existing `.md` file whose
    frontmatter contains a matching `source_hash`. If found, returns `None` (no-op).
  - If not found, writes a new file with:
    ```
    ---
    status: pending
    source: codex-plan
    source_hash: <hex>
    ---

    <text>
    ```
  - Returns the path of the created file.
- [x] `_content_hash("")` returns the SHA-256 of an empty string (no error).
- [x] `plan_to_todo_from_text("", todo_dir)` returns `None` (empty text is a no-op).
- [x] Existing `plan_to_todo()` function and its tests are unchanged and still pass.
- [x] Tests in `tests/unit/test_plan_to_todo.py` (extended) cover:
  - `test_from_text_creates_todo`: plan text with a heading creates the expected file.
  - `test_from_text_empty_is_noop`: empty text returns `None`.
  - `test_from_text_dedup`: calling twice with the same text returns `None` on second call.
  - `test_from_text_different_content_not_deduped`: different text creates a second file.
  - `test_content_hash_stable`: same input always returns same hash.
  - `test_existing_plan_to_todo_unchanged`: original function tests still pass.

## Implementation Plan

### Files to modify

- `clasi/plan_to_todo.py` — add `_content_hash` and `plan_to_todo_from_text`
- `tests/unit/test_plan_to_todo.py` — extend with new tests

### Approach

```python
import hashlib

def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan_to_todo_from_text(text: str, todo_dir: Path) -> Optional[Path]:
    if not text or not text.strip():
        return None

    body = text.strip()
    h = _content_hash(body)

    # De-dupe: scan todo_dir for matching source_hash
    todo_dir.mkdir(parents=True, exist_ok=True)
    for search_dir in [todo_dir, todo_dir / "in-progress"]:
        if not search_dir.is_dir():
            continue
        for existing in search_dir.glob("*.md"):
            try:
                content = existing.read_text(encoding="utf-8")
                if f"source_hash: {h}" in content:
                    return None
            except OSError:
                continue

    # Extract title
    title = None
    for line in body.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    from clasi.templates import slugify
    slug = slugify(title) if title else "untitled-plan"
    if not slug:
        slug = "untitled-plan"

    out_path = _unique_path(todo_dir, slug)
    frontmatter = (
        f"---\nstatus: pending\nsource: codex-plan\nsource_hash: {h}\n---\n\n"
    )
    out_path.write_text(frontmatter + body + "\n", encoding="utf-8")
    return out_path
```

### Testing plan

```
uv run pytest tests/unit/test_plan_to_todo.py -v
uv run pytest -x
```

### Documentation updates

None — the function is exposed through the hook handler (ticket 009), not directly by
users.
