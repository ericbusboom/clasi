---
id: '010'
title: Transcript renderer should format Write tool content readably
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: transcript-render-write-tool-content.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Transcript renderer should format Write tool content readably

## Description

In `_render_transcript_lines` in `clasi/hook_handlers.py`, `Write` and `Edit`
tool_use blocks are currently rendered by JSON-dumping the entire `input` dict.
This produces escaped newlines and JSON noise, making file content — especially
markdown ticket and skill files — completely unreadable in the transcript log.

This ticket updates the `tool_use` rendering branch to detect `Write` and `Edit`
tool names and apply structured formatting:

- **Write**: show `file_path` as a bold heading; render `content` as inline
  markdown (no fence) for `.md` files, or as a fenced code block with a language
  tag derived from the extension for all other file types.
- **Edit**: show `file_path` as a bold heading; show `old_string` and
  `new_string` each in a fenced block labeled **Before** / **After** (or as a
  simple diff-style presentation).

All other tool_use blocks continue to use the existing JSON-dump rendering.

## Acceptance Criteria

- [x] `_render_transcript_lines` in `clasi/hook_handlers.py` detects `Write`
      tool_use by name and renders `file_path` as a bold heading and `content`
      separately (not as a JSON blob)
- [x] For `Write`: `.md` file content is rendered as inline markdown (no code
      fence)
- [x] For `Write`: non-`.md` file content is rendered in a fenced code block
      with an appropriate language tag (e.g., ` ```python ` for `.py` files,
      ` `````` ` for unknown extensions)
- [x] `Edit` tool_use renders `file_path` as a bold heading, `old_string` in a
      labeled fenced block, and `new_string` in a labeled fenced block
- [x] All other tool_use blocks are unaffected by the change
- [x] Existing transcript tests still pass
- [x] `uv run pytest` passes

## Implementation Plan

### Approach

Extend the `elif block_type == "tool_use":` branch in `_render_transcript_lines`
with a name-dispatch pattern. Extract a helper (or inline logic) that handles
`Write` and `Edit` specially. Keep the fallback JSON-dump path for all other
tools.

For language tag derivation, use `pathlib.Path(file_path).suffix` to get the
extension and map common extensions to language names (`.py` -> `python`,
`.js` -> `javascript`, `.ts` -> `typescript`, `.sh` -> `bash`, `.yaml`/`.yml`
-> `yaml`, `.json` -> `json`, `.toml` -> `toml`). Default to empty string for
unknown extensions.

The existing 15-line truncation logic for JSON inputs should be preserved for
the fallback path. For `Write`/`Edit`, content may be long — apply a character
limit (e.g., 3000 chars) with a truncation notice rather than a line-count
limit, since markdown content benefits from more context.

### Files to Modify

- `clasi/hook_handlers.py`
  - In `_render_transcript_lines`, extend the `tool_use` rendering branch:
    - If `name == "Write"`: extract `file_path` and `content`; render as
      described above.
    - If `name == "Edit"`: extract `file_path`, `old_string`, `new_string`;
      render as before/after blocks.
    - Otherwise: existing JSON-dump path (unchanged).
  - Add a small helper function `_ext_to_language(path: str) -> str` mapping
    file extensions to fenced-code-block language tags. Place it just above
    `_render_transcript_lines`.

### Testing Plan

- Locate existing transcript rendering tests (search for `_render_transcript_lines`
  in `tests/`).
- Add new test cases covering:
  1. `Write` with a `.md` file — content appears as inline markdown, no fence.
  2. `Write` with a `.py` file — content appears in a ` ```python ` fence.
  3. `Write` with an unknown extension — content appears in a plain ` ``` ` fence.
  4. `Edit` — `file_path` heading, `old_string` and `new_string` each in their
     own labeled fence.
  5. A non-Write/Edit tool_use (e.g., `Bash`) — rendered as before (JSON dump).
- Run `uv run pytest` to verify all existing and new tests pass.

### Documentation Updates

No external documentation changes required. The behavior change is internal to
the transcript rendering pipeline.
