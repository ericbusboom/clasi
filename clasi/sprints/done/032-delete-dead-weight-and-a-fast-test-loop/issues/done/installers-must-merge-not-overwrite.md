---
status: done
type: bug
tags:
- reliability-campaign
- phase-4
- install
- data-loss
sprint: '032'
tickets:
- 032-004
---

# Installers overwrite instead of merging — four destructive behaviors, one root cause

## Description

From docs/reviews/2026-08-reliability/04-cli-install-platforms.md findings
F1-F4, F13. Four separate bugs share one cause: the installers write
wholesale where they should merge or compare. Each fix is under 20 lines;
together they are the mechanism behind "init breaks my own repo."

1. **`clasi init` reverts `.mcp.json`** (`init_command.py:37-52,84-111`).
   `_update_mcp_json` unconditionally rewrites `mcpServers.clasi` to the
   consumer default `{"command": "clasi", "args": ["mcp"]}`. In this repo
   — whose checked-in config points at the editable install via `uv run
   clasi mcp` — every `clasi init` (and every `clasi migrate`, which
   calls `run_init`) reverts it, so the next session silently connects to
   a different build. Tracked separately as
   [[clasi-init-reverts-this-repos-own-mcp-config-to-the-consumer-default]];
   fix them together.
2. **`clasi uninstall` deletes the whole CLAUDE.md**
   (`platforms/claude.py:503`). Install writes CLAUDE.md as a regular
   file holding a marker block, explicitly so other tools can manage
   their own blocks in the same file — but uninstall calls
   `unlink_alias` on the entire file. Any user or other-tool content is
   destroyed. AGENTS.md two lines later does the right thing
   (`strip_section`); CLAUDE.md should match.
3. **`clasi init` clobbers user hooks** (`platforms/claude.py:337-345`).
   `settings["hooks"] = new_hooks` replaces the whole hooks object, so
   any user-defined hook is silently deleted on every init.
4. **Multi-platform install stomps resolved skills**
   (`platforms/codex.py:209-234`, `copilot.py:56-86` vs
   `claude.py:253-271`). Three installers write the same canonical
   `.agents/skills/<n>/SKILL.md` with different content rules: Claude
   resolves `Load from:` directives, Codex and Copilot write the raw
   file. `clasi init --claude --codex` runs Codex second and overwrites
   the resolved canonical that Claude's symlinks point at, so Claude
   skills silently lose their prose.

Related, same family: `_create_rules`'s docstring
(`platforms/claude.py:386-407`) claims it "compares content before
writing and skips unchanged files"; the code always writes. Combined with
(1), local rule edits are silently reverted.

## Acceptance criteria

- [ ] `.mcp.json`: if a `clasi` server entry exists in any form, leave it
      untouched; only add the entry when absent.
- [ ] Uninstall strips CLASI's marker block from CLAUDE.md, preserving
      everything else. A test asserts other-tool content survives.
- [ ] Hooks are merged per event type; only entries identifiable as
      CLASI's (command starts with `clasi hook`) are replaced.
- [ ] One shared canonical-skill writer used by all three installers, so
      install order cannot change the result. A test installs two
      platforms in both orders and asserts identical output.
- [ ] `_create_rules` compares before writing, matching its docstring.
- [ ] `clasi migrate` refreshes only the platforms actually installed,
      rather than always force-installing Claude
      (`migrate_command.py:546`).
