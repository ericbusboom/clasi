# Spec-Driven Development for AI Agents: Spec Kit vs. Spec Kitty vs. Claude Code SDD

> Research compiled 2026-06-29. Cross-verified against primary sources (GitHub repos,
> GitHub REST API, PyPI, official Anthropic and GitHub docs/blogs) plus independent
> third-party reviews. Approximate figures and weakly-sourced claims are flagged inline.

## TL;DR

| | **GitHub Spec Kit** | **Spec Kitty** | **Claude Code SDD** (native + community) |
|---|---|---|---|
| **What** | Official GitHub SDD toolkit; the de-facto standard | Independent CLI "inspired by" SDD; adds orchestration + Kanban | A *pattern*, not one product: Claude Code's native plan/subagent primitives + community plugins |
| **Maintainer** | GitHub (Den Delimarsky; John Lam as research basis) | Priivacy-ai / Robert Douglass | Anthropic (primitives) + many independent authors (plugins) |
| **Maturity** | ~116k★, launched Sep 2025, very active | ~1.4k★, launched Oct 2025, very active but beta/churning | Native = production; plugins vary (Superpowers ~241k★, cc-sdd ~3.5k★, Pimzino MCP ~4.3k★) |
| **Workflow** | constitution → specify → clarify → plan → tasks → analyze → implement | spec → plan → tasks → **next → review → accept → merge** | Explore → Plan → Implement → Commit (native); plugins add requirements/design/tasks |
| **Orchestration** | None (single agent) | **Yes** — external orchestrator + git worktrees | Subagents (native); Superpowers/cc-sdd add multi-agent |
| **Kanban/gates** | No | **Yes** — live dashboard + review/accept/merge gates | No native; Pimzino MCP adds dashboard |
| **MCP** | No (only proposal, issue #99) | No (uses own `orchestrator-api`) | **Yes** — first-class MCP client; Pimzino is an MCP server |

---

## 1. GitHub Spec Kit

**What & who.** An [official GitHub open-source toolkit](https://github.com/github/spec-kit) for Spec-Driven
Development — "focus on product scenarios and predictable outcomes instead of vibe coding every piece
from scratch." Specs are treated as living, executable artifacts and the shared source of truth between
developers and AI agents. Announced [September 2, 2025 on the GitHub Blog](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
by **Den Delimarsky** (Principal PM at GitHub at launch; his bio now lists Anthropic — a post-launch
move). **John Lam** is credited as the research basis, *not* a verified active maintainer (no
MAINTAINERS file). MIT license, primarily Python.

**Workflow & artifacts.** Commands were renamed bare → `/speckit.` prefix (the Sept 2025 launch shipped
only `/specify`, `/plan`, `/tasks`). Strict left-to-right dependency ordering:

| Command | Produces |
|---|---|
| `/speckit.constitution` | `.specify/memory/constitution.md` — non-negotiable project principles |
| `/speckit.specify` | `specs/<feature>/spec.md` (+ auto-creates feature branch) |
| `/speckit.clarify` *(opt)* | refines `spec.md` |
| `/speckit.plan` | `plan.md` + `research.md` + `data-model.md` + `contracts/` + `quickstart.md` |
| `/speckit.checklist` *(opt)* | quality checklist ("unit tests for English") |
| `/speckit.tasks` | `tasks.md` (parallel tasks marked `[P]`) |
| `/speckit.analyze` *(opt)* | cross-artifact consistency report |
| `/speckit.implement` | source code |
| `/speckit.taskstoissues` | GitHub issues |
| `/speckit.converge` | appends remaining work to `tasks.md` |

**CLI & install.** The `specify` CLI requires **Python 3.11+, Git, and `uv`** (or pipx).
```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z
specify init my-project --integration claude   # was --ai before ~v0.10.0 (June 2026)
```
> **Flag:** the `--ai` → `--integration` rename (~v0.10.0) broke pre-mid-2026 tutorials.

**Agents:** README says "30+"; the live integrations table enumerates ~50 (Claude Code `claude`,
Copilot `copilot`, Cursor, Gemini CLI, Codex, Windsurf, Qwen, opencode, Kilo, Roo, Auggie, Zed, Kiro CLI,
and a Generic fallback). Selected via `--integration <key>`. The Claude Code integration is **file
generation, not a plugin** — `specify init` writes command/skill files into `.claude/` (historically
`.claude/commands/`; now `.claude/skills/` after Claude Code v2.1.88 stopped scanning `commands/`).

**The "constitution"** is a project-level governance document — "the architectural DNA of a system."
The shipped template is generic placeholders; its *example* principles (Library-First, CLI Interface,
**Test-First/TDD non-negotiable**, Integration Testing, Observability, Versioning, Simplicity/YAGNI) are
a useful menu. `/plan` reads it and fills a `## Constitution Check` gate.

**Strengths (user-reported):** antidote to vibe-coding chaos; agent-agnostic; forces upfront alignment;
"the most customizable" (Böckeler, martinfowler.com); strong constitution governance concept; good for
greenfield/enterprise.

**Weaknesses (user-reported):** ceremony-heavy and slow (Eberhardt/Scott Logic: ~10× slower than his
normal method, "not a viable process in its purest form"); markdown sprawl ("2,577 lines of markdown"
for one feature); overkill for small tasks; agent doesn't reliably follow the spec; spec drifts (no
verification loop); weaker for brownfield than greenfield; API churn breaks tutorials.

**Hard data point:** Spec Kit's slash commands consume **~18.6k tokens per session**
([issue #1401](https://github.com/github/spec-kit/issues/1401), no maintainer response as of fetch) —
nearly Cursor's entire ~20k default window, a third of Copilot's 64k. The empirical backbone of the
"native/lightweight = lower overhead" argument.

**Maturity:** ~**116k stars** (116,396 via GitHub API 2026-06-29), ~10.3k forks. Created 2025-08-21,
announced 2025-09-02. ~175 releases, latest v0.11.10 (2026-06-29). Among the highest-starred dev-tooling
repos of the era; the category standard.

---

## 2. Spec Kitty

**What & who.** An independent SDD CLI at [`Priivacy-ai/spec-kitty`](https://github.com/Priivacy-ai/spec-kitty),
maintained by **Robert Douglass**. *Provenance is the one genuine ambiguity:* third parties (a Hacker
News user, a LinkedIn post) call it "a fork of Spec Kit," but the README self-describes as
**"inspired by spec-driven development workflows"** and an expanded independent tool — *"adds repo-native
mission state, work-package lanes, git worktree isolation, a local dashboard, governance commands, and an
explicit `next → review → accept → merge` runtime loop."* PyPI-only (`spec-kitty-cli`); no npm.

**What it adds over Spec Kit** (the whole point of the project):
- **Git-worktree isolation** under `.worktrees/` for parallel agents "without branch chaos." A
  [comparison study](https://github.com/cameronsjo/spec-compare) credits Spec Kitty with *pioneering*
  built-in worktree support among SDD tools.
- **Multi-agent orchestration** via a deliberate **host/provider split**: the core CLI owns workflow
  state and git-safe mutations; a *separate* [`spec-kitty-orchestrator`](https://github.com/Priivacy-ai/spec-kitty-orchestrator)
  repo spawns agents in worktrees and drives work packages through the lanes by calling an
  `orchestrator-api`. Mutations carry `PolicyMetadata` (approval/sandbox/network mode); orchestration is
  opt-in and policy-gated. *"The core CLI does not provide spec-kitty orchestrate."*
- **Live Kanban dashboard** (`spec-kitty dashboard`) with lanes `planned → in_progress → for_review →
  in_review → approved → done` (+ `blocked`/`canceled`), plus **review/accept/merge/retrospective quality
  gates** and an audit trail.

**Workflow & artifacts.** Loop: `spec → plan → tasks → next → review → accept → merge`. Artifacts are
repo-native under `kitty-specs/` (specs, plans, work packages, acceptance criteria, review state, merge
decisions). In-editor commands: `/spec-kitty.charter`, `.specify`, `.plan`, `.tasks`, `.review`,
`.accept`, `.merge --push`.

**Install & agents.** Python 3.11+, Git (required, for worktrees).
```bash
pipx install spec-kitty-cli        # preferred
spec-kitty init my-project --ai claude,codex
```
Supports Claude Code, Codex, Cursor, Gemini, Copilot, Windsurf, OpenCode, Qwen, Kiro, Vibe, Pi, Letta.

**MCP:** **None.** Its machine interface is its own one-JSON-envelope-per-command `orchestrator-api`,
not MCP. (MCP appears only as a *proposal* on the unrelated GitHub Spec Kit, issue #99.)

**Maturity:** ~**1.4k stars** (1,369), 119 forks, ~63 contributors. Created 2025-10-09; **195 releases in
~8.5 months**, latest v3.2.3 (2026-06-29), daily commits. PyPI status **Beta** — changelogs openly
remediate regressions ("fix usability issues introduced in 3.2.0"), so it's powerful but still settling.
Independent validation thin (one favorable comparison, one positive HN anecdote; most write-ups by the
author). Two orders of magnitude below Spec Kit's adoption.

**Strengths:** the only one of the three with built-in orchestration, worktree parallelism, and a board +
governed human-in-the-loop lifecycle. **Weaknesses:** young, beta, rapid major-version churn, small
community, single-maintainer risk.

---

## 3. Claude Code SDD

A **category, not a single product** — SDD practiced with Anthropic's Claude Code, in two layers.

### (a) Native primitives → SDD phase mapping (verified against `code.claude.com/docs`)

Anthropic's official recommended loop is **Explore → Plan → Implement → Commit**; the docs explicitly
prescribe an interview-to-spec workflow for larger features:

> "Interview me in detail using the AskUserQuestion tool… **Keep interviewing until we've covered
> everything, then write a complete spec to SPEC.md.**" Then "start a fresh session to execute it… you
> have a written spec to reference." And: "The most useful specs are self-contained: they name the files
> and interfaces involved, state what is out of scope, and end with an end-to-end verification step."

Official "when NOT to spec" rule: **"If you could describe the diff in one sentence, skip the plan."**

| Primitive | SDD role | Enforcement |
|---|---|---|
| **Plan Mode** (Shift+Tab; `--permission-mode plan`) | Plan — read-only research + `ExitPlanMode` approval gate | **Hard** (read-only enforced) |
| **Subagents** (`.claude/agents/*.md`) | Role separation per phase; tool restrictions stop premature implementation | Medium (delegation model-driven) |
| **Slash commands → Skills** | Named, parameterized phase entry points | Soft |
| **CLAUDE.md** | Persistent spec/standards substrate | **Soft — "guidance, not enforced configuration"** |
| **Skills + Plugins** | Packaged phase procedures; a plugin bundles skills + agents + hooks + MCP into one shippable methodology | Soft→hard |
| **Hooks** (`PreToolUse`/`PostToolUse`) | The hard gate layer — can `deny` a tool call | **Hard** |

The load-bearing doc quote: *"[CLAUDE.md] Claude treats them as context, not enforced configuration. To
block an action regardless of what Claude decides, use a PreToolUse hook instead."*

> **Flags:** the `think`/`ultrathink` keyword ladder is no longer in current docs (was in the Apr 2025
> blog; Claude 4.6+ reportedly moved to adaptive thinking ~Jan 2026 — unconfirmed against a live primary
> source). There is no official `/spec` slash command — the official mechanism is interview → SPEC.md.

### (b) Community SDD tooling (verified against GitHub API 2026-06-29)

| Tool | Stars | Form | Why it matters |
|---|---|---|---|
| **[Superpowers](https://github.com/obra/superpowers)** (obra/Jesse Vincent) | ~241k | Plugin in **Anthropic's official marketplace** | Loop *is* SDD: brainstorm→spec→`writing-plans` (2–5 min tasks w/ file paths + verification)→`subagent-driven-development` (fresh subagent per task, two-stage review, **git worktrees**). `/plugin install superpowers@claude-plugins-official` |
| **[gotalab/cc-sdd](https://github.com/gotalab/cc-sdd)** | ~3.5k | npx installer | Highest install velocity (~12k/wk). Kiro-inspired `/kiro-*` commands; per-task TDD + reviewer + auto-debug across 8 agents. `npx cc-sdd@latest`. (Disambiguate from rhuss/cc-sdd.) |
| **[Pimzino/spec-workflow-mcp](https://github.com/Pimzino/spec-workflow-mcp)** | ~4.3k | **MCP server** | The most architecturally-relevant-to-CLASI tool: stateful MCP server, Requirements→Design→Tasks with approval gates + live web dashboard + VSCode sidebar. GPL-3.0 (copyleft). |

Superseded/stale (don't chase): Pimzino's older `claude-code-spec-workflow` (frozen Sep 2025);
`angelsen/claude-kiro`, `NeverGET/superclaude-spec-workflow`, `kingkongshot/specs-workflow-mcp`.

**Kiro lineage:** Amazon's Kiro (GA Nov 2025) originated the EARS-requirements → design → tasks gated flow
that cc-sdd literally clones. "Kiro-style SDD" is now a portable *pattern*, not a product.

**Strengths of native SDD:** zero install, deepest agent integration, native subagents + first-class MCP,
fully customizable, lowest token overhead. **Weaknesses:** no out-of-box artifact schema or enforced gates
without a plugin; no native drift detection; documented instruction-following failures (agent skips
CLAUDE.md constraints); weak multi-agent coordination (markdown has no locking → silent overwrites).

---

## 4. How they relate

Spec Kit set the template (constitution→specify→plan→tasks→implement) the whole category copies. **Spec
Kitty is the "Spec Kit + orchestration + governance + board" branch.** **Claude Code SDD** is the
substrate all of them run on — Spec Kit and Spec Kitty both *emit files into Claude Code*, while native +
community tooling does SDD inside it directly.

**The organizing axis is enforcement strength:**

1. **Advisory (convention/markdown):** Spec Kit, Spec Kitty, cc-sdd, CLAUDE.md, most plugins. The
   spec→plan→implement order is *suggested*; a confused agent can skip it.
2. **Per-action hard gate:** Claude Code `PreToolUse` hooks + Plan Mode's read-only boundary. Blocks *one*
   tool call.
3. **Stateful process gate:** **CLASI** and **Pimzino's MCP**. Block *transitions* based on accumulated
   process state — strictly more binding than a hook.

The **"reinvented waterfall" critique** (Böckeler, Eberhardt; ThoughtWorks Tech Radar v33 places SDD in
"Assess," warning of "bias toward heavy up-front specification and big-bang releases") applies to *any*
heavyweight SDD process, **including CLASI** — making a triviality escape hatch load-bearing, not optional.

---

## 5. Guidance for a team on a custom SE-process MCP workflow (CLASI)

**Don't adopt any of these as your engine — you already have the more capable one.** CLASI already does
what makes Spec Kitty interesting (governed work-package lifecycle, sprint/ticket state machine, review
gates, human-in-the-loop control) and adds the one thing none of these have: a **stateful MCP server
enforcing transitions**, rather than markdown an agent can ignore. Spec Kit and Spec Kitty are
file-and-convention systems; CLASI is an enforced process server.

The ecosystem **independently converged on CLASI's three core bets:**
(a) enforcement belongs in a stateful server, not convention files (Pimzino's MCP);
(b) you need a triviality escape hatch or ceremony kills you (every critic; CLASI's `/oop`);
(c) per-task subagents in isolated worktrees with separate review (Superpowers, Spec Kitty).
CLASI is the only tool combining all three with a *full-lifecycle* enforced state machine.

**Treat the others as a parts catalog:**
- **Spec Kit** — mine its *vocabulary* (constitution / clarify / analyze gate names; the Test-First,
  Observability, Simplicity constitution articles). Don't run its CLI beside CLASI — two state systems
  collide.
- **Spec Kitty / Superpowers** — borrow the **git-worktree-per-work-package** parallelism + two-stage
  review for the execute-sprint flow. Borrow the design, not the (beta, single-maintainer) dependency.
- **Pimzino's MCP** — CLASI's closest architectural sibling; validates the MCP-as-enforcement bet and
  shows the **dashboard direction** (three independent tools — Spec Kitty, Pimzino, Superpowers — all
  built a visual progress surface; CLASI's state is text-only YAML).

**Two cheap native upgrades worth adopting *alongside* the MCP server:**
1. **A `PreToolUse` hook on `Edit|Write`** that hard-blocks code edits when no ticket/sprint is in an
   executing state. Today CLASI enforces ordering at the MCP-tool layer (can't `advance_sprint_phase` out
   of order), but raw Edit/Write from a confused agent isn't gated. The docs prescribe exactly this hook.
2. **Package CLASI as a `.claude-plugin`** — it already has agents/skills/rules/`.mcp.json`; a plugin
   manifest bundles them + can set `agent:` (team-lead) as the default main thread, giving CLASI the
   one-command install story `specify init` has and CLASI lacks.

**A caution for CLASI itself:** Spec Kit's measured ~18.6k-token-per-session cost mirrors CLASI's own
per-turn `get_status` YAML dump (~28KB, emitted every turn). Watch context budget; the same
overhead critique applies.

---

## Sources

- https://github.com/github/spec-kit · https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/
- https://github.github.io/spec-kit/reference/integrations.html · https://github.com/github/spec-kit/issues/1401
- https://github.com/Priivacy-ai/spec-kitty · https://pypi.org/project/spec-kitty-cli/ · https://github.com/Priivacy-ai/spec-kitty-orchestrator
- https://github.com/cameronsjo/spec-compare · https://news.ycombinator.com/item?id=46966273
- https://code.claude.com/docs/en/best-practices · https://code.claude.com/docs/en/permission-modes · https://code.claude.com/docs/en/sub-agents · https://code.claude.com/docs/en/hooks · https://code.claude.com/docs/en/plugins
- https://github.com/obra/superpowers · https://github.com/gotalab/cc-sdd · https://github.com/Pimzino/spec-workflow-mcp
- https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html · https://blog.scottlogic.com/2025/11/26/putting-spec-kit-through-its-paces-radical-idea-or-reinvented-waterfall.html
