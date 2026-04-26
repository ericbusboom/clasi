---
status: in-progress
sprint: '011'
tickets:
- 011-002
- 011-003
- 011-004
- 011-005
- 011-006
- 011-007
---

# Codex installer correctness pass — fix hooks schema, add sub-agents, drop misleading `/se` pointer

Cohesive cleanup sprint for the Codex install path shipped in sprint
010. Web research (sources cited inline) found:

- The `.agents/skills/` path is correct (confirmed cross-tool standard).
- The MCP servers TOML is correct.
- **The `.codex/hooks.json` schema we ship is wrong** — Codex never
  fires our Stop hook, so plan-to-todo capture is dead end-to-end.
- Sub-agents on Codex live in `.codex/agents/<name>.toml`, not the
  `.agents/agents/` path I'd guessed; format is TOML with
  `developer_instructions`.
- No native equivalent of Claude's path-scoped rules exists on Codex.
  Closest is nested `AGENTS.md` files or embedding rule content in a
  Skill.
- The "Available skills: run `/se` for a list" line in the CLASI
  section is misleading because `/se` is a user-facing dispatcher,
  not a skill enumerator. Both platforms auto-discover skills.

This is not OOP material — there's a schema bug, a missing install
category, and several documentation/template touch-ups. Better to do
it as a single sprint with proper planning so the codex install path
ends in a known-correct state.

## Issue 1 (BUG, P0): `.codex/hooks.json` schema is wrong — codex-plan-to-todo never fires

Our installer writes:

```json
{ "hooks": { "Stop": [ {"command": "clasi", "args": ["hook", "codex-plan-to-todo"]} ] } }
```

Codex's actual schema is wrapper-objects-around-handler-arrays, with
`type: "command"` and a single shell-style command string (no `args`):

```json
{ "hooks": { "Stop": [
  { "hooks": [
    { "type": "command",
      "command": "clasi hook codex-plan-to-todo",
      "timeout": 30 }
  ] }
] } }
```

Source: <https://developers.openai.com/codex/hooks>

**Effect**: every codex install ships a hooks.json Codex won't honor.
Plan-to-todo capture (the entire point of the codex Stop hook
plumbing in sprint 010) is dead end-to-end.

**Additional caveat**: GitHub issue
<https://github.com/openai/codex/issues/17532> reports that repo-local
`.codex/hooks.json` doesn't fire in interactive sessions; only
`~/.codex/hooks.json` does. Verify after fixing the schema.

**Fix**: rewrite `_CLASI_STOP_HOOK` in
[clasi/platforms/codex.py](../../../clasi/platforms/codex.py) to
emit the wrapper structure with `type`, joined `command` string, and
`timeout`. Update tests in `tests/unit/test_platform_codex.py`. This
is small enough to OOP if scoped tightly.

## Issue 2 (DESIGN): codex install is missing agents and rules — but the right home is `.codex/agents/*.toml`, not `.agents/agents/`

Codex CLI has a native subagents feature. Definitions live in TOML
files (one per agent) at `.codex/agents/<name>.toml` (project-scoped)
or `~/.codex/agents/` (user-scoped). Required fields: `name`,
`description`, `developer_instructions`. Optional: `model`,
`sandbox_mode`, `mcp_servers`.

Source: <https://developers.openai.com/codex/subagents>

**Implication**: our Markdown agent definitions in
`clasi/plugin/agents/<name>/agent.md` need to be either (a)
re-emitted as TOML at `.codex/agents/<name>.toml` during install, or
(b) referenced from a single TOML wrapper that points back at the
Markdown content. (a) is cleaner; the Markdown body becomes the
`developer_instructions` value.

**Path-scoped rules**: no Codex equivalent exists.
- Confirmed via <https://developers.openai.com/codex/config-reference>
  and <https://github.com/openai/codex/issues/17401>.
- The `[rules]` table in `~/.codex/config.toml` is for admin-enforced
  prefix patterns, not path-scoped instruction injection.
- Closest equivalents: nested `AGENTS.md` at subdirectory roots
  (Codex's "closest file wins" resolution), or embedding rule content
  into a Skill so progressive loading triggers it.
- **Recommendation**: drop the rules concept on the Codex side. Move
  the rule *content* (mcp-required, source-code-needs-ticket,
  git-commits, etc.) into either nested `AGENTS.md` files or fold it
  into the SE skill body. Don't ship a `.agents/rules/` or
  `.codex/rules/` directory — no tool reads it.

## Issue 3: `/se` line in CLASI section is misleading for agents

[clasi/templates/clasi-section.md](../../../clasi/templates/clasi-section.md)
ends with "Available skills: run `/se` for a list." `/se` is a
user-facing dispatcher — its 8-row table is the high-traffic
stakeholder commands, not the 30+ skill files. Both Claude Code
(`.claude/skills/`) and Codex (`.agents/skills/`) auto-discover skill
files at session start, so the line is unnecessary and steers the
agent at the wrong target.

**Fix**: drop the line. Entry-point sentence is sufficient.

## Confirmed-correct from research (no change needed)

- **`.agents/skills/<name>/SKILL.md`** is the cross-tool standard
  (Codex, Cursor, Gemini CLI, VS Code Copilot, Antigravity, Windsurf
  via the open Agent Skills spec). Sprint 010's path is correct.
  - <https://developers.openai.com/codex/skills>
  - <https://agentskills.io/specification>
- **MCP servers TOML** — `[mcp_servers.clasi]` with `command` and
  `args` matches the official Codex spec. The OOP "always use bare
  `clasi mcp`" fix produces compliant output.
  - <https://developers.openai.com/codex/mcp>
- **AGENTS.md spec** — root + nested subdirectory files, instructions
  only, doesn't standardize sub-agents/skills/hooks/rules. Our marker
  block at the project root is fine.
  - <https://agents.md/>

## Adoption breadth (for context)

Tools that natively read AGENTS.md: Codex, Aider, Cursor, Windsurf,
GitHub Copilot Coding Agent, Gemini CLI, Jules, Devin, Amp, opencode,
RooCode, Kilo Code, Zed, Warp, VS Code, JetBrains Junie, Factory,
goose, UiPath, Ona, Augment Code, Phoenix, Semgrep. So the codex
install path is the right base for any future `--platform=other`
flag — most other tools already understand the same files.

## Suggested ticket decomposition for the sprint planner

(Final shape is the planner's call, but this is a reasonable starting
breakdown.)

1. **Fix `.codex/hooks.json` schema** — rewrite `_CLASI_STOP_HOOK` to
   the wrapper structure with `type: "command"`, joined command
   string, and `timeout`. Update merge logic for backward
   compatibility (existing wrong-shape entries should be replaced,
   not duplicated). Update `tests/unit/test_platform_codex.py`. AC
   includes: a real codex hooks.json round-trip test that asserts the
   exact spec shape.
2. **Verify hook actually fires from repo-local config** — manual or
   integration test against issue
   <https://github.com/openai/codex/issues/17532>. If repo-local
   doesn't work, decide: install to `~/.codex/hooks.json` instead, or
   document the limitation, or both.
3. **Drop the misleading `/se` line** from
   `clasi/templates/clasi-section.md`. One-line template edit + test
   update.
4. **Add Codex sub-agent install** at `.codex/agents/<name>.toml`.
   Generate one TOML per active agent (`team-lead`, `sprint-planner`,
   `programmer`) by reading the Markdown agent definition and
   converting body → `developer_instructions`. Required TOML fields:
   `name`, `description`, `developer_instructions`. Update uninstall
   to remove these too.
5. **Decide and implement rule placement on Codex side** — fold rule
   content into the SE skill body (so progressive loading triggers
   it) OR emit nested `AGENTS.md` files at the relevant subdirectory
   roots. Architecture review should pick one; both work, neither is
   a Claude-style enforcer. Update install + uninstall accordingly.
6. **Tests for end-to-end Codex install correctness** — install into
   tmp dir, validate every emitted file against its spec
   (config.toml, hooks.json, sub-agent TOML). Round-trip parse with
   `tomllib`/`json` and assert exact structures.
7. **Update README** to describe the codex install footprint
   accurately once the above lands.

## Open questions for the planner

- Should the codex hook handler register to `~/.codex/hooks.json` if
  the repo-local one doesn't fire? That changes the install scope
  (writes outside the project). Present the trade-off to the
  stakeholder during planning.
- The Codex `developer_instructions` for sub-agent TOMLs — should
  they be the agent.md body verbatim, or stripped of frontmatter? The
  Markdown contains role descriptions that are useful but also some
  Claude-Code-specific phrasing ("dispatch via Agent tool") that
  doesn't apply on Codex. Consider whether a translation layer is
  needed or if Codex agents should get their own agent.md per
  platform.
- Should there be a `--platform=other` or `--platform=AGENTS.md`
  install mode that produces only the lowest-common-denominator
  AGENTS.md + .agents/skills/ output, suitable for the 20+ tools that
  read that spec? Maybe in a follow-on sprint.

## Related

- Codex installer source: [clasi/platforms/codex.py](../../../clasi/platforms/codex.py)
- Sprint 010 (where the broken hook schema landed):
  `docs/clasi/sprints/done/010-add-codex-support-to-clasi-init-and-plan-capture/`
- "Install all skills" OOP: commit `27c6797`
