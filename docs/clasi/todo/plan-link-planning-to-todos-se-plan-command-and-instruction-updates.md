---
status: pending
---

# Plan: Link planning to TODOs — /se plan command and instruction updates

## Context

There are two paths for capturing future work in CLASI:

1. **Quick capture** (`/todo` or `/se todo`): User gives a one-liner,
   it becomes a TODO file immediately. No discussion.

2. **Discussed planning** (plan mode): User wants to explore an idea,
   discuss options, and arrive at a well-thought-out plan. The
   `plan-to-todo` hook already converts the plan to a TODO on exit.

The problem is that nothing tells the model when to use which path,
and there's no explicit `/se plan` command to enter plan mode. The
connection between plan mode and the TODO system is implicit.

## Changes

### 1. Add `/se plan` command — `clasi/plugin/skills/se/SKILL.md`

Add a new row to the command table:

```
| `/se plan` | Enter plan mode for a discussed TODO | Enter plan mode via `EnterPlanMode` |
```

And add a note:

```
## When to use /se todo vs /se plan

- `/se todo <text>`: Quick capture. The user has a clear idea and just
  wants it recorded. One statement → one TODO file.
- `/se plan`: The user wants to discuss, explore, and refine an idea
  before capturing it. Enters plan mode for a conversation. On exit,
  the plan-to-todo hook automatically creates the TODO.
```

### 2. Update team-lead agent — `clasi/plugin/agents/team-lead/agent.md`

In the **Process** section, add a new scenario before "Execute TODOs
Through a Sprint":

```
### Capture Ideas and Plans

**When:** The stakeholder has ideas or tasks they want to capture
for future work, but not execute now.

Two paths based on the stakeholder's intent:

1. **Quick capture** — The stakeholder gives a direct statement of
   what to do. Invoke the `todo` skill to create a TODO file.
   Example: "Add rate limiting to the API"

2. **Discussed planning** — The stakeholder wants to explore and
   discuss an idea. Enter plan mode (`EnterPlanMode`). Have the
   conversation, explore the codebase, ask clarifying questions,
   and write the plan. On `ExitPlanMode`, the plan-to-todo hook
   automatically creates the TODO. Do not implement after exit.
   Example: "Let's talk about how we should handle authentication"

**How to tell the difference:**
- Quick capture: imperative statement, single sentence, clear task
- Discussed planning: "let's talk about", "let's plan", "I want to
  discuss", exploratory language, questions about approach
```

### 3. Update todo skill — `clasi/plugin/skills/todo/SKILL.md`

Add a note at the bottom:

```
## When to use this skill vs plan mode

This skill is for **quick capture** — the user has a clear idea and
wants it recorded as a TODO. If the user wants to discuss, explore
options, or refine an idea before capturing it, use plan mode
(`EnterPlanMode`) instead. The plan-to-todo hook will create the
TODO automatically when plan mode exits.
```

### 4. Install updated copies to `.claude/`

Copy the three updated files to their `.claude/` counterparts so
the current session picks up the changes:
- `.claude/skills/se/SKILL.md`
- `.claude/skills/todo/SKILL.md`
- `.claude/agents/team-lead/agent.md`

## Files to modify

| File | Action |
|------|--------|
| `clasi/plugin/skills/se/SKILL.md` | Add `/se plan` command + guidance |
| `clasi/plugin/skills/todo/SKILL.md` | Add "when to use" note |
| `clasi/plugin/agents/team-lead/agent.md` | Add "Capture Ideas and Plans" scenario |
| `.claude/skills/se/SKILL.md` | Copy from plugin source |
| `.claude/skills/todo/SKILL.md` | Copy from plugin source |
| `.claude/agents/team-lead/agent.md` | Copy from plugin source |

No Python code changes. No tests needed (markdown only).

## Verification

1. Run `clasi init` to verify the updated files install correctly
2. Invoke `/se` with no args — verify `/se plan` appears in the table
3. Invoke `/se plan` — verify it enters plan mode
4. Exit plan mode — verify TODO is created and model stops
