---
status: done
---

# Remove the `create_overview` MCP tool

## Problem

The `create_overview` MCP tool's contract conflicts with the
`project-initiation` skill, making the documented process always fail.

- The skill instructs the dispatched agent to write
  `docs/clasi/design/overview.md` (along with `specification.md` and
  `usecases.md`) and then call `create_overview` ("required — do not
  skip it").
- The tool writes a skeleton template and raises `ValueError` if the
  file already exists.

So the tool always errors when the skill is followed correctly. The tool
also tracks no state — its only side effect is writing a template — so
calling it after the real file exists adds no value even if it didn't
error. The agent already writes `specification.md` and `usecases.md`
directly with no analogous "create" tool, so the asymmetry has no
functional reason.

Discovered when an agent ran `project-initiation` in
`/Users/eric/proj/league/scratch/mediacms`. It wrote three correct
documents but got "Overview already exists" from the trailing tool call.

## Fix

Delete the tool and the documented call to it.

### Code

- `clasi/tools/artifact_tools.py` — remove the `create_overview`
  function and its `OVERVIEW_TEMPLATE` import if unused elsewhere.
- `tests/unit/test_mcp_server.py` — remove `"create_overview"` from
  the registered-tools list.
- `tests/system/test_artifact_tools.py` — remove the `TestCreateOverview`
  class.

### Documentation / prompts

- `clasi/plugin/skills/project-initiation/SKILL.md` — drop the
  instruction to call `create_overview`; the skill should simply tell
  the dispatched agent to write all three documents to
  `docs/clasi/design/`.
- `clasi/plugin/instructions/software-engineering.md` (~line 105) —
  remove the sentence recommending `create_overview` for new projects.
- `clasi/plugin/rules/clasi-se-process.md` (~line 39 of the tools
  table) — remove the `create_overview()` row.
- `clasi/plugin/agents/old/project-manager/agent.md` and
  `clasi/plugin/agents/old/project-manager/dispatch-template.md.j2` —
  remove the "After writing `overview.md`, call the `create_overview`
  MCP tool" lines. (These are in `agents/old/`, but the strings still
  ship in the plugin package.)

## Test Plan

- Unit + system test suite passes after the tool and its tests are
  removed.
- `grep -rn create_overview clasi/ tests/` returns no matches under
  active source paths after the change (matches under `docs/old/` and
  archived sprint dirs are fine — those are historical).

## Out of Scope

- Re-evaluating whether `specification.md` / `usecases.md` should have
  any kind of registration tool. They currently don't, and this TODO
  doesn't propose adding any.
