---
id: '004'
title: 'Validator core: clasi.design.validator + clasi design validate CLI + validate_design
  MCP tool'
status: open
use-cases: [SUC-003]
depends-on: ['002', '003']
github-issue: ''
issue: persistent-per-subsystem-architecture-docs-with-sprint-update-overlays.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Validator core: clasi.design.validator + clasi design validate CLI + validate_design MCP tool

## Description

Implement `clasi.design.validator`, modeled on the existing
`clasi.schemas`/`clasi.schemas.loader` pattern (`src/clasi/schemas/`,
`cli.py:245-266`): a `load`-like entry point that checks the doc set's
structure and bidirectional links, plus (when a sprint overlay directory
is given) the sprint-overlay-specific checks. Raises a `DesignError`
(parallel to `SchemaError`) with an actionable, specific message per
violation — not a single generic failure.

Expose it two ways, both thin wrappers around the same validation logic:
- CLI: `clasi design validate` (new `design` command group in `cli.py`,
  same shape as the existing `schema` group).
- MCP: `validate_design` tool in `src/clasi/tools/` (either
  `artifact_tools.py` alongside the other sprint/artifact tools, or a new
  `design_tools.py` — decide based on how large `artifact_tools.py` has
  become; it is already about 103KB per prior research, which leans
  toward a new sibling module for isolation).

## Acceptance Criteria

- [ ] Validates the canonical doc set: `design.md` present; one doc per
      declared subsystem (per `Project.sources` + `clasi.design.paths`);
      every design doc's frontmatter references a source path/README that
      resolves; every subsystem README's frontmatter references a design
      doc that resolves; no orphaned docs (doc with no matching source
      directory); no unmapped source roots (subsystem directory with no
      doc).
- [ ] Validates a sprint overlay directory (`clasi/sprints/NNN-slug/design/`)
      when given one: every overlay filename matches an existing
      canonical doc's filename; overlay frontmatter references resolve;
      every overlay `.md` file (excluding `.diff.md` files themselves)
      has a corresponding `<name>.diff.md` that is not stale (content
      hash or mtime comparison against the current overlay file content —
      pick one and document it).
- [ ] Each of the four failure modes named in the issue's Verification
      section is independently triggerable in tests and produces a
      distinct, actionable message: missing `design.md`; unmapped source
      root; design doc with no README backlink (and the reverse: README
      with no design-doc-side reference); sprint overlay file with a
      stale or missing `.diff.md`.
- [ ] `clasi design validate` exits 0 on a valid doc set, exit 1 with the
      failure messages on stderr otherwise — same contract as `clasi
      schema validate` (`cli.py:250-266`).
- [ ] `validate_design` MCP tool returns an equivalent pass/fail plus
      message list as structured output (not just a formatted string),
      so an agent caller can act on individual failures programmatically
      if needed.
- [ ] Both entry points call the same underlying validation function —
      no logic duplicated between CLI and MCP paths.

## Implementation Plan

**Approach**: Mirror `src/clasi/schemas/loader.py`'s shape: a `load(...)`
function that runs an ordered sequence of independent checks, collecting
all failures (not stopping at the first) before raising, so a caller sees
every problem in one pass rather than fixing errors one at a time. Model
`DesignError` on `SchemaError` (`src/clasi/schemas/models.py`).

**Files to create/modify**:
- `src/clasi/design/validator.py` (new) — core checks + `DesignError`.
- `src/clasi/cli.py` — new `design` command group (`clasi design
  validate <path-or-implicit-project-root>`), following the existing
  `schema` group's registration pattern (lines around 245-266).
- `src/clasi/tools/design_tools.py` (new, tentative — confirm sizing
  against `artifact_tools.py` before deciding) or an addition to
  `artifact_tools.py` — `validate_design` MCP tool wrapping the same
  validator call.

**Testing plan**:
- Unit tests: one test per named failure mode (see acceptance criteria),
  each using a temp-directory fixture doc set with exactly that one
  defect introduced, asserting the specific message.
- CLI test: `clasi design validate` exit codes, mirroring however
  `clasi schema validate` is tested today (check `tests/` for that
  existing test file and follow its shape).
- MCP tool test: structured output shape on pass and fail.
- Overlay staleness test: generate a `.diff.md`, then mutate the overlay
  file's content, assert the validator flags staleness.

**Documentation updates**:
- `clasi design validate --help` text (via click docstrings).
- Docstring on `DesignError` documenting the message format contract
  other tickets (007 bootstrap skill, 008 skill rework) can rely on when
  telling an agent how to interpret validator output.
