---
status: pending
---

# Project Knowledge Skill — Capture Hard-Won Technical Understanding

## Problem

When agents work through difficult problems — things that were broken,
behaving unexpectedly, or required multiple failed attempts before
finding a solution — that hard-won understanding evaporates at the end
of the conversation. The next time the same problem comes up (or a
related one), the agent starts from scratch. There is no mechanism to
capture and preserve the technical knowledge gained through struggle.

This is different from reflections. Reflections capture process failures
(agent didn't follow instructions). Project knowledge captures technical
victories — the problem was genuinely hard, the agent figured it out,
and that understanding should be preserved for future work.

## Stakeholder Input

> "What project knowledge is, is when you've worked hard to get
> something to work. It was broken. We didn't understand it. It was
> doing weird things, and then you got it to work. I want you to trigger
> on that. I want you to have some way to say, 'Oh wow, we need to
> record this.' In the end, one of the triggers is the user expresses
> excitement, 'Oh great, that worked,' or 'I can't believe that worked.'
> You notice that you've been through a bunch of trial and tribulations,
> and now you've figured out how to make it function. It's very similar
> to the reflection process, but it's not about you not following the
> process. It's about keeping track of, for that project, what you need
> to do in the future."

## Proposed Skill Design

### Name

`project-knowledge` (invoked as `/project-knowledge` or triggered
automatically)

### Triggers

The skill should activate when the agent detects any of:

1. **Stakeholder excitement** — The human expresses relief, surprise, or
   satisfaction that something finally works. Phrases like "it works!",
   "finally!", "I can't believe that worked", "oh great", "that fixed
   it", "awesome, it's working now".

2. **Resolution after struggle** — The agent has been through multiple
   failed attempts, debugging cycles, or trial-and-error iterations in
   the current conversation, and has now reached a working solution.

3. **Non-obvious fix** — The solution turned out to be something
   surprising, counterintuitive, or poorly documented. The kind of
   thing you'd never figure out from reading the docs alone.

4. **Agent self-recognition** — The agent itself recognizes that the
   path to the solution was unusually difficult and the knowledge is
   worth preserving.

When a trigger fires, the agent should say something like: "This was a
hard-won fix. I'd like to record this as project knowledge so we don't
have to rediscover it. OK to proceed?" (Or auto-record if the
stakeholder has enabled auto-approve.)

### What Gets Recorded

Each knowledge entry captures:

- **Title** — Short description of the problem or finding
- **Date** and **sprint** (if active)
- **Category** — e.g., `configuration`, `dependency`, `api-quirk`,
  `tooling`, `platform`, `integration`, `debugging-technique`
- **The Problem** — What was broken, what symptoms were observed, what
  was confusing
- **What Was Tried** — The failed approaches, in order, with brief notes
  on why each failed
- **What Worked** — The actual solution, with enough detail to reproduce
- **Why It Works** — The underlying explanation (if known) of why this
  fix is correct
- **Future Guidance** — What to do (or avoid) next time this comes up.
  This is the most important section — it's the actionable takeaway for
  future agents working on this project.

### Where It Lives

`docs/clasi/knowledge/YYYY-MM-DD-slug.md`

This is a new directory, parallel to `docs/clasi/reflections/` but
serving a different purpose:

| Directory       | Purpose                              | Trigger                     |
|-----------------|--------------------------------------|-----------------------------|
| `reflections/`  | Process failures — agent did it wrong | Stakeholder correction      |
| `knowledge/`    | Technical victories — hard problem solved | Stakeholder excitement / struggle resolved |

### File Format

```yaml
---
date: YYYY-MM-DD
sprint: NNN (if active)
category: configuration | dependency | api-quirk | tooling | platform | integration | debugging-technique | other
tags: [relevant, searchable, terms]
---
```

```markdown
## Problem

What was broken, confusing, or misbehaving.

## Symptoms

Observable behavior that led to investigation.

## What Was Tried

1. **Attempt 1** — Description. Why it failed.
2. **Attempt 2** — Description. Why it failed.
3. ...

## What Worked

The actual fix or solution, with specifics.

## Why It Works

The underlying explanation — what was actually going on.

## Future Guidance

What to do (or avoid) next time. Actionable rules for future agents.
```

### Process (Skill Steps)

1. **Detect trigger** — Recognize stakeholder excitement or resolution
   of a multi-attempt debugging session.
2. **Confirm with stakeholder** — "This was hard-won knowledge. Want me
   to record it?" (Skip if auto-approve is enabled.)
3. **Gather context** — Review the conversation for: the original
   problem, failed attempts, the working solution, and the explanation.
4. **Write knowledge file** — Create
   `docs/clasi/knowledge/YYYY-MM-DD-slug.md` with the template above.
5. **Commit** — `docs: record project knowledge — <title>`
6. **Confirm** — Show the stakeholder the file path and a one-line
   summary of what was captured.

### Integration Points

- **AGENTS.md** — Add a section under "Stakeholder Corrections" (or
  parallel to it) covering project knowledge triggers.
- **execute-ticket skill** — After a ticket is completed, if the
  execution involved significant debugging, prompt for knowledge capture.
- **systematic-debugging skill** — When debugging concludes
  successfully, trigger project knowledge capture.
- **Agent instructions** — All coding agents should watch for triggers
  and invoke this skill when appropriate.

## Open Questions

- Should knowledge entries be searchable by future agents automatically?
  (e.g., agent loads relevant knowledge files at the start of related
  work.) If so, how do we match "relevant" — by tags, by file paths
  touched, by category?
- Should the skill support updating an existing knowledge entry if the
  same problem recurs with new information?
- Should there be a `list_knowledge()` MCP tool parallel to
  `list_todos()`?
- Does the knowledge directory need a `done/` subdirectory, or are
  knowledge entries permanent (never "done")?

## Files to Create or Modify

```
skills/project-knowledge.md          (new skill definition)
docs/clasi/knowledge/                (new directory)
AGENTS.md                            (add knowledge trigger section)
skills/execute-ticket.md             (add knowledge capture prompt)
skills/systematic-debugging.md       (add knowledge capture on success)
```
