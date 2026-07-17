# clasi.templates (directory)

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-16 · **Status:** stable

---

## 1. Purpose

`src/clasi/templates/` holds the raw `.md` template files (`sprint.md`, `sprint-brief.md`, `ticket.md`, `review-checklist.md`, `clasi-section.md`) that `src/clasi/templates.py` (the loose top-level module, described in the `clasi-core` section of `design.md`) loads at import time and exposes as string constants. This directory is a subsystem in the narrow sense the bootstrap enumeration mechanically applies (a top-level directory under the source root) even though its "design" is almost entirely content, not logic — the logic (loading, slugification) lives in the sibling `templates.py` module, not here.

## 2. Orientation

Five flat markdown files, each the literal starting content for a new artifact of that kind: `sprint.md` (new sprint's `sprint.md`, with `{id}`/`{title}`/`{slug}` `str.format()` placeholders and starter frontmatter), `sprint-brief.md`, `ticket.md`, `review-checklist.md`, and `clasi-section.md` (the CLASI-managed marker-block content `clasi.platforms._markers` writes into a host CLAUDE.md/AGENTS.md). No subdirectories, no code.

## 3. Constraints and Invariants

- **These files are loaded via `str.format()` with named placeholders, not a templating engine:** any literal `{` or `}` in a template's prose body must be escaped (`{{`/`}}`) or it will be misinterpreted as a placeholder by `templates.py`'s `_load`/format call sites — this is an easy trap for anyone editing template prose without checking `templates.py`'s usage.
- **Template content here is the literal thing users and agents first see for a new artifact:** changes here are user-facing in a way most other content changes are not; treat wording changes with the same care as changing a public message, not as an internal refactor.

## 4. Design

No control flow lives in this directory — it is pure content, read by `clasi.templates._load(name)` via a fixed `_TEMPLATES_DIR = Path(__file__).parent / "templates"` relative to the sibling module.

## 5. Interfaces

### Exposes
- The five `.md` files themselves, consumed exclusively through `clasi.templates`'s module-level constants (`SPRINT_TEMPLATE`, `SPRINT_BRIEF_TEMPLATE`, `TICKET_TEMPLATE`, `REVIEW_CHECKLIST_TEMPLATE`, `CLASI_SECTION_TEMPLATE`) — nothing should read these files directly by path outside that module.

### Consumes
- Nothing; this is pure static content with no dependency on any other subsystem.

## 6. Open Questions / Known Limitations

- Whether this directory should instead be treated as part of the `clasi-core` narrative (since its only consumer is the single loose top-level `templates.py` module) rather than getting its own subsystem doc is a reasonable question the mechanical "every top-level directory is a candidate" rule doesn't resolve on its own; this bootstrap run kept it as its own doc per the rule stated in the `bootstrap-design` skill ("when in doubt, err toward giving the directory its own doc").
