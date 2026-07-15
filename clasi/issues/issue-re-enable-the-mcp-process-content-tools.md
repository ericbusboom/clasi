---
status: pending
---

# Re-enable the MCP process-content tools

## Description

Nine content-serving MCP tools in `src/clasi/tools/process_tools.py` are
disabled, but are still advertised as available in files shipped to every CLASI
project. Agents are being told to call tools that do not exist.

- `src/clasi/plugin/rules/clasi-se-process.md:26-34` — an "SE Process Access"
  table listing `get_activity_guide`, `list_agents`, `list_skills`,
  `list_instructions`, `get_agent_definition`, `get_skill_definition`, and
  `get_instruction` as live MCP tools. All seven are disabled.
- `.claude/rules/source-code.md:15`, `src/clasi/AGENTS.md:8`, and
  `.github/instructions/source-code.instructions.md` — all instruct agents to
  call `get_skill_definition("execute-ticket")` "if unsure of the steps." That
  call cannot succeed.
- `src/clasi/se-overview-template.md:110-112` — same list, same problem.

Meanwhile `tests/unit/test_mcp_server.py:62` pins `EXPECTED_PROCESS_TOOLS` to the
three live tools (`get_use_case_coverage`, `get_version`, `get_status`) and
`test_no_unexpected_tools` fails if any of the nine are re-enabled. The docs and
the tests actively contradict each other, and no artifact records which way is
right.

This is a live bug on its own. It is also the first step toward a larger goal:

1. **Fewer files in the consumer repo.** `clasi init` copies about 47 files into
   every project (26 skills under `.agents/skills/`, 9 agent files under
   `.claude/agents/`, 5 Codex TOMLs, plus rules and settings); 37 are
   git-tracked. That content is *already* shipped inside the pip/pipx install —
   `pyproject.toml:73` declares `plugin/**/*` as package data, and it is verified
   present in the live pipx install. There is no reason to vendor a second copy
   into each repo.
2. **Work on more than Claude.** Codex and Copilot must keep working. This rules
   out the Claude-plugin route, which is Claude-only. MCP is the only mechanism
   all three clients speak, and all three already point at the CLASI server
   (`.mcp.json`, `.codex/config.toml` `[mcp_servers.clasi]`).

The disabled tools are exactly the mechanism both goals need. They read from
`content_path("plugin", ...)`, which resolves `__file__`-relative into the
**installed package**, not the repo (`src/clasi/mcp_server.py:52,74-81`).

## Cause

Nine `#@server.tool()` decorators are commented out in `process_tools.py`:
`list_agents` (188), `list_skills` (198), `list_instructions` (212),
`get_agent_definition` (221), `get_skill_definition` (307), `get_instruction`
(339), `list_language_instructions` (349), `get_language_instruction` (358),
`get_activity_guide` (414).

Registration is an import-triggered decorator side-effect, so commenting the
decorator removes the tool from the MCP surface while leaving the function
importable and directly callable — which is why the test suite still passes.

They were disabled during an earlier period when agents broadly weren't following
instructions, on the theory that MCP-served skills were the cause. The
stakeholder now believes that diagnosis was probably wrong; it was never
confirmed. Git history records nothing — the history is squashed, and
`git log -S'#@server.tool()' -- src/clasi/tools/process_tools.py` returns a
single unrelated commit (`e6e5e0f`, the `src/` layout move). No issue, sprint, or
architecture doc discusses the decision.

## Proposed fix

Staged. The three steps are separable and must not be bundled.

**1. Re-enable the nine decorators.** Update `EXPECTED_PROCESS_TOOLS`
(`tests/unit/test_mcp_server.py:62`) and the hard-coded `== 36` tool count
(`:144`). Low risk: the functions are already well covered by
`tests/system/test_process_tools.py`, `tests/system/test_content_smoke.py`, and
`tests/unit/test_skill_stub_loader.py`, all of which import the undecorated
functions directly and pass today. This resolves the doc/implementation
contradiction on its own merits, regardless of what follows.

**2. Measure discovery reliability. This gates everything else.** Filesystem
skills are auto-discovered — the model sees them without asking. MCP-served
skills are not: the model must decide to call `list_skills()`. No published
Anthropic guidance or reliability data exists on whether models reliably make
that call when instructed via a rule; the documentation is silent. This is
precisely the failure mode that prompted the original disabling, so it must be
measured, not assumed. Trial: a team-lead in a scratch repo with the rule in
place but the SKILL.md absent — does it find and invoke the skill?

**3. Only if (2) holds: shrink `clasi init`** toward the floor, keeping
`Load from:` expansion working (`platforms/claude.py:168,265`).

Note the floor is about 6-8 files, not zero. Plugins cannot ship instructions or
path-scoped rules, and neither can MCP. `CLAUDE.md`, `AGENTS.md`,
`.github/copilot-instructions.md`, and `.claude/rules/*.md` must remain real
files in the repo. Realistic target: 47 → about 6.

Do step 1 regardless. Treat step 3 as conditional on step 2's measurement.
Bundling re-enablement with the file-count reduction would repeat the original
mistake — changing several things at once and not knowing which one mattered.

## Verification

- `clasi mcp` exposes 45 tools (36 + 9); `test_no_unexpected_tools` and
  `test_tool_count` pass with the updated expectations.
- `get_skill_definition` resolves a `Load from:` skill **against an installed
  wheel, not the working tree**. Sprint 013 flagged this exact coupling — the
  triple-`parent` `_PACKAGE_ROOT` at `process_tools.py:259` — and asked for it to
  be proven against a wheel; that proof is still owed. Five skills use the
  directive: `plan-sprint`, `close-sprint`, `execute-sprint`, `sprint-review`,
  `architecture-review`.
- Scratch-repo discovery trial for step 2, before any file removal.
- Regression: `clasi init` still expands `Load from:` at install time
  (`tests/unit/test_skill_stub_loader.py::TestInstallExpandsStubs`).

## Related

- **Sprint 013** (`clasi/sprints/done/013-reorganize-clasi-files-.../`) flagged
  the `_PACKAGE_ROOT` / wheel-resolution risk and asked for a clean-venv
  `pip install` → `clasi mcp` smoke + `Load from:` resolution check.
- The file-count goal (47 → ~6) depends entirely on step 2's outcome. If
  MCP-served discovery proves unreliable, step 1 still stands and step 3 dies.
- `.codex/config.toml` and `.mcp.json` already point at the CLASI server, so
  Codex and Copilot inherit any tool re-enabled here at no extra cost. Copilot
  supports MCP *tools* only (not resources), which is why tools — not resources
  or prompts — are the cross-platform vehicle.
- MCP server instructions are a proven adjunct channel: the protocol's
  `instructions` field is set at `src/clasi/mcp_server.py:46-50` and is
  observably injected into Claude Code context (2KB truncation).
