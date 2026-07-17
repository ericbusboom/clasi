---
id: '002'
title: 'Slugification: clasi.design.paths module'
status: open
use-cases: [SUC-002]
depends-on: ['001']
github-issue: ''
issue: persistent-per-subsystem-architecture-docs-with-sprint-update-overlays.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Slugification: clasi.design.paths module

## Description

Implement `clasi.design.paths`, the pure-function module that derives
canonical design-doc and README filenames from a subsystem's source-tree
path, per the two slugification rules in the issue:

- **Single source root**: slugify relative to the root (root name
  omitted), e.g. `src/clasi/tools/` -> `clasi-tools.md`.
- **Multiple source roots**: slugify relative to the repo root (root
  name included, disambiguating), e.g. `tests/e2e/` -> `tests-e2e.md`.

The top-level system document is always `design.md` regardless of root
count. This module has no file I/O and no git — it is pure path -> name
logic, consumed by store (003), validator (004), and overlay (005).

## Acceptance Criteria

- [ ] Given a single declared source root and a subsystem directory
      under it, returns the correct root-omitted slug (e.g.
      `src/clasi/tools/` with root `src` -> `clasi-tools.md`, matching
      the issue's own worked example).
- [ ] Given multiple declared source roots, returns the correct
      root-included slug (e.g. `tests/e2e/` -> `tests-e2e.md`).
- [ ] The system-level doc is always named `design.md`, independent of
      root count or path.
- [ ] Function(s) are pure: same input always produces same output, no
      filesystem or git calls.
- [ ] Two distinct subsystem paths never produce the same slug within a
      valid configuration (collision-freedom) — cover with a test that
      constructs a plausible multi-root case designed to almost collide
      and asserts it doesn't.
- [ ] Also derive the corresponding subsystem `README.md` path (the
      subsystem source directory itself, not `docs/design/`) from the
      same input, since SUC-001's bootstrap and SUC-003's validator both
      need this pairing.
- [ ] Raises a clear, typed error (not a bare exception) for a subsystem
      path that isn't under any declared source root.

## Implementation Plan

**Approach**: A small, dependency-free module. Core function signature
shape: `design_doc_slug(subsystem_path: Path, sources: list[Path]) ->
str` and `readme_path_for(subsystem_path: Path) -> Path`. Use Python's
standard slugification approach (lowercase, path separators to hyphens,
strip non-alphanumerics) — keep it simple and deterministic; do not add
a general-purpose slug library dependency for this.

**Files to create/modify**:
- `src/clasi/design/__init__.py` (new package)
- `src/clasi/design/paths.py` (new)

**Testing plan**:
- Unit tests covering: single-root omission, multi-root inclusion,
  `design.md` invariance, nested subsystem paths (e.g.
  `src/clasi/tools/` — two path segments), collision-avoidance case,
  out-of-root error case, README path derivation.
- Property-style test (or a small parametrized table) is appropriate
  here given the module is pure and small.

**Documentation updates**:
- None beyond docstrings — this module's contract is exercised entirely
  through the tickets that consume it (003, 004, 005).
