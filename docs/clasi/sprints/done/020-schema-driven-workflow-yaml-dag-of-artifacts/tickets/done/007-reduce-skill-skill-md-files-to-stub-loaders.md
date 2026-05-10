---
id: "007"
title: "Reduce skill SKILL.md files to stub loaders"
status: done
use-cases: [SUC-004]
depends-on: ["006"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Reduce skill SKILL.md files to stub loaders

## Description

Replace the inline prose in each of the five affected skill `SKILL.md` files
with a stub that references the instruction file. After ticket 006 moved the
prose to `se-process/instructions/*.md`, this ticket trims the `SKILL.md`
files down to: YAML frontmatter, a one-sentence purpose description, and a
load directive.

The load directive is a markdown block that instructs the skill loader
(existing `clasi/plugin/` machinery) to read the referenced instruction file
at invocation time:

```markdown
## Instructions

Load from: `clasi/schemas/se-process/instructions/<artifact-id>.md`
```

The externally visible behavior of each skill is unchanged — the same prose
reaches the agent, just via a file load instead of inline embedding.

## Acceptance Criteria

- [x] `plan-sprint/SKILL.md` is reduced to frontmatter + purpose sentence + load directive pointing to `sprint-plan.md`.
- [x] `execute-sprint/SKILL.md` is reduced similarly, pointing to `execution.md`.
- [x] `architecture-review/SKILL.md` is reduced similarly, pointing to `architecture-update.md`.
- [x] `sprint-review/SKILL.md` is reduced similarly, pointing to `sprint-review.md`.
- [x] `close-sprint/SKILL.md` is reduced similarly, pointing to `close.md`.
- [x] The five stub files retain their YAML `name:` and `description:` frontmatter fields unchanged.
- [x] The skill loader machinery (`clasi/plugin/`) is updated to resolve and include the referenced instruction file when a `Load from:` directive is present (if the machinery does not already support this, add the support).
- [x] A manual invocation test: invoke one of the stubs and confirm the instruction prose from the file appears in the agent context.
- [x] `uv run pytest` passes.

## Implementation Plan

**Approach**: First check whether the existing skill-loader machinery in
`clasi/plugin/` already supports a file-reference directive. If yes, use the
existing convention. If no, add minimal support: when `SKILL.md` contains a
`Load from:` line with a path, read that file and include its contents as the
skill body.

**Files to modify**:
- `clasi/plugin/skills/plan-sprint/SKILL.md`
- `clasi/plugin/skills/execute-sprint/SKILL.md`
- `clasi/plugin/skills/architecture-review/SKILL.md`
- `clasi/plugin/skills/sprint-review/SKILL.md`
- `clasi/plugin/skills/close-sprint/SKILL.md`
- (potentially) `clasi/plugin/` loader code if `Load from:` directive is not yet supported

**Testing plan**: After stubbing, verify that running the `plan-sprint` skill
delivers the full prose from `instructions/sprint-plan.md`. No automated test
for prose delivery (it's agent-runtime behavior), but add a unit test for the
`Load from:` directive resolution in the plugin loader if that code is changed.

**Documentation updates**: None.
