---
id: "005"
title: "Revise architecture process"
status: done
use-cases: [SUC-005]
depends-on: []
todo: "revise-architecture-process.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Revise architecture process

## Description

Replace the current full-architecture-copy-per-sprint approach with a
lightweight architecture-update model. The full architecture lives in
`docs/clasi/architecture/` and is consolidated on demand. Each sprint
produces only an architecture update document describing what changed.

### Changes

1. **`create_sprint`** -- Stop copying the full architecture into the
   sprint directory. Instead, generate a lightweight architecture-update
   template (`architecture-update.md`) with sections for "What changed",
   "Why", and "Impact on existing components".

2. **`close_sprint`** -- When closing a sprint, copy the sprint's
   `architecture-update.md` to the architecture directory as
   `architecture-update-NNN.md` (where NNN is the sprint number).

3. **Architect agent** -- Update the architect agent definition so it
   writes architecture updates (focused diffs) instead of full
   architecture rewrites.

4. **Consolidation skill** -- Create a new skill for on-demand
   architecture consolidation. When triggered, it reads the last
   consolidated architecture plus all subsequent update documents,
   rewrites the architecture, verifies against actual code, and
   produces a new consolidated document named after the latest sprint.

### Architecture directory structure

```
docs/clasi/architecture/
  architecture-024.md              # last consolidated
  architecture-update-025.md       # changes from sprint 025
  architecture-update-026.md       # changes from sprint 026
```

## Acceptance Criteria

- [x] `create_sprint` produces a lightweight architecture-update template instead of copying full architecture
- [x] Sprint directories contain `architecture-update.md` instead of `architecture.md`
- [x] `close_sprint` copies the update to `docs/clasi/architecture/architecture-update-NNN.md`
- [x] Architect agent definition instructs writing updates, not full rewrites
- [x] Consolidation skill exists and can merge base architecture + updates into a new consolidated doc
- [x] `uv run pytest` passes with no regressions

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**: Unit tests for the modified `create_sprint` and `close_sprint` behavior; test that the architecture-update template is generated correctly
- **Manual verification**: Run a sprint lifecycle and confirm the architecture directory receives the update document on close
