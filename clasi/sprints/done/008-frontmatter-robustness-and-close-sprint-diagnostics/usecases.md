---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 008 Use Cases

## SUC-001: Detect and report corrupted frontmatter fence

- **Actor**: CLASI MCP server (automated); CLASI operator (observing output)
- **Preconditions**: A CLASI artifact file (`sprint.md`, `ticket.md`, issue
  file, etc.) exists on disk with non-empty content whose first line is not a
  valid `---` opening fence (e.g. `pwd---`, `---x`, `xyz---`).
- **Main Flow**:
  1. Any CLASI operation calls `read_frontmatter` or `read_document` on the
     file.
  2. `read_frontmatter` detects that the file has content but the opening fence
     is not the string `---` (possibly followed immediately by a newline).
  3. `read_frontmatter` raises `MalformedFrontmatterError`, naming the file path
     and describing the invalid fence text.
  4. The exception propagates to the caller with a clear stack trace that
     identifies the file.
- **Postconditions**:
  - The caller receives a `MalformedFrontmatterError` (a subclass of
    `ValueError`) rather than an empty dict.
  - No silent empty-field behavior occurs for files with content.
- **Acceptance Criteria**:
  - [ ] `read_frontmatter` raises `MalformedFrontmatterError` when the file has
        content but no recognizable `---` opening fence.
  - [ ] The exception message names the file path.
  - [ ] `read_frontmatter` continues to return `{}` for files that genuinely
        have no frontmatter at all (first character is not `-`).
  - [ ] `MalformedFrontmatterError` is a subclass of `ValueError` so existing
        `except ValueError` callers remain compatible.

---

## SUC-002: close_sprint provides actionable diagnostics when sprint.md is corrupted

- **Actor**: CLASI operator calling `close_sprint` (via MCP or CLI)
- **Preconditions**: A sprint directory exists at the expected path, `sprint.md`
  is present but has a corrupted frontmatter fence.
- **Main Flow**:
  1. Operator calls `close_sprint(sprint_id="NNN", ...)`.
  2. `_close_sprint_full` attempts to locate the sprint via `project.get_sprint`.
  3. `get_sprint` encounters the malformed `sprint.md` and raises a typed
     exception that identifies the file and the parse failure.
  4. `_close_sprint_full` catches the exception and returns a structured error
     response naming the file and the specific fault.
  5. The `recovery.instruction` tells the operator to fix the frontmatter in the
     named file — not to "create or restore the directory."
- **Postconditions**:
  - Operator can immediately identify the corrupt file and correct it.
  - No misleading "create or restore the directory" guidance is emitted.
- **Acceptance Criteria**:
  - [ ] When `sprint.md` is present but malformed, `close_sprint` returns an
        error naming the specific file and describing the parse failure.
  - [ ] The `recovery.instruction` is actionable for the actual fault (fix the
        frontmatter, not recreate the directory).
  - [ ] When a sprint directory is genuinely absent, the existing "not found,
        create or restore" message continues to be correct.
  - [ ] When frontmatter parses but the `id:` field is absent or mismatched,
        the error names the file and the mismatch.
