# tests/asr/provider1/

A "general engineering" provider's `asr/` source directory. Ships
everything `clasr` knows how to install:

- `skills/code-review/`, `skills/security-audit/`
- `agents/reviewer.md`, `agents/scribe.md` (union frontmatter so each
  tool — Claude, Codex, Copilot — gets its own projected version)
- `rules/no-secrets.md`, `rules/python-style.md` (with `applyTo:` and
  `paths:` metadata for tools that scope rules by file glob)
- `claude/settings.json` (top-level keys `model` and `permissions`)
- `claude/commands/changelog.md`
- `codex/notes.md`
- `copilot/.vscode/mcp.json`

This provider exercises every clasr feature in isolation. For
multi-tenant demos, see `tests/asr/provider2/` and `tests/justfile`.
