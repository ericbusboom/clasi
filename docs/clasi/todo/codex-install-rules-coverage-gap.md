---
status: pending
---

# Codex install rules coverage gap — only partial mirror of Claude RULES dict

Sprint 011 ticket 005 produced two nested `AGENTS.md` files for the
Codex platform but only mirrored a subset of the rules the Claude
installer ships. Three of the five Claude rules are partially covered
or completely missing on the Codex side.

## Coverage today

The Claude installer writes 5 path-scoped rule files via the hardcoded
`RULES` dict in `clasi/platforms/claude.py`:

| Rule (file in `.claude/rules/`) | Path scope | Currently mirrored to Codex? |
|---|---|---|
| `mcp-required.md` | `**` (everywhere) | Partial — content is in `docs/clasi/AGENTS.md` only, but the scope is global |
| `clasi-artifacts.md` | `docs/clasi/**` | Partial — active-sprint check and phase check are missing from `_DOCS_CLASI_RULES` |
| `source-code.md` | `clasi/**` | ✓ Covered by `_CLASI_SRC_RULES` in `clasi/AGENTS.md` |
| `todo-dir.md` | `docs/clasi/todo/**` | **Missing** — no nested AGENTS.md exists at `docs/clasi/todo/` |
| `git-commits.md` | `**` (everywhere) | **Missing** — no global home, content is nowhere on the Codex side |

Sprint 011 ticket 005 produced two nested AGENTS.md files
(`docs/clasi/AGENTS.md`, `clasi/AGENTS.md`) but never:

- placed root-scope rules at the project root,
- created a `docs/clasi/todo/AGENTS.md` for the todo-dir rule, or
- handled `git-commits.md` at all.

## Why this matters

Codex resolves "closest AGENTS.md upward in the tree" for each tool
call. To match Claude's path-scoped rule injection:

- Rules with `paths: ["**"]` must live in the ROOT `AGENTS.md`.
- Rules scoped to a subtree must live in the closest `AGENTS.md` at
  that subtree root.

Right now, a Codex agent doing git operations has no idea about the
git-commits rule (run tests before commit, version bump after, sprint
branch lock check). A Codex agent touching `docs/clasi/todo/` doesn't
know to use the `todo` skill or `move_todo_to_done` MCP tool instead
of generic todo machinery.

## Proposed fix (sprint-sized)

1. **Restructure the codex installer's rules section** to mirror the
   full RULES dict:
   - Add a SECOND marker block to the root `AGENTS.md` (e.g.
     `<!-- CLASI:RULES:START --> ... <!-- CLASI:RULES:END -->`)
     holding the rules with `paths: ["**"]` — `mcp-required` and
     `git-commits`. The existing `<!-- CLASI:START --> ... <!-- CLASI:END -->`
     marker stays for the team-lead entry point. Use the
     `_markers.write_section` helper or extend it to support multiple
     named blocks.
   - Update `docs/clasi/AGENTS.md` to include the FULL
     `clasi-artifacts` content (active-sprint check, phase check,
     MCP-tools-only).
   - Add `docs/clasi/todo/AGENTS.md` for the `todo-dir` rule.
   - Keep `clasi/AGENTS.md` (source-code rule) as-is.

2. **Single source of truth**: Move the rule content out of the
   hardcoded `RULES` dict in `claude.py` and the duplicate constants
   in `codex.py` into a shared module — e.g.
   `clasi/platforms/_rules.py` — so both installers consume the same
   canonical rule text. Each installer renders to its own native
   target (Claude → `.claude/rules/<name>.md` with `paths:`
   frontmatter; Codex → nested AGENTS.md at the right subtree root).

3. **Update uninstall** for both platforms to remove the
   corresponding files cleanly.

4. **Tests**:
   - End-to-end Codex install test (extend
     `test_codex_install_end_to_end`) asserting all 4-5 nested
     AGENTS.md files exist with the right rule content.
   - Round-trip test: install → assert content → uninstall → assert
     removal.

## Out of scope for this TODO

- The `clasi/plugin/rules/*.md` files (`auto-approve`,
  `clasi-se-process`, `scold-detection`,
  `use-mcp-for-sprint-queries`) appear to be dead content — they're
  not consumed by either installer's RULES dict. Worth a separate
  cleanup decision: either wire them into the install path or delete
  them. Track separately.

## Origin

Stakeholder flagged the gap after sprint 011 closed:

> ".claude has a rules/ directory with a bunch of other content in it
> which does not exist in either .agents or .codex"

Investigation confirmed the partial-mirror state above. The
team-lead identity fix that triggered this discovery has already
landed OOP in commits `ad75175` / `043d734`.
