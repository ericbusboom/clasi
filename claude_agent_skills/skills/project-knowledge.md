---
name: project-knowledge
description: Captures hard-won technical understanding from difficult debugging sessions and non-obvious fixes
---

# Project Knowledge Skill

This skill captures hard-won technical understanding when agents work
through genuinely difficult problems. The knowledge is preserved so
future agents and sessions can benefit from the struggle instead of
repeating it.

**This is different from reflections.** Reflections capture process
failures -- the agent did something wrong. Project knowledge captures
technical victories -- the problem was genuinely hard, the agent (and
stakeholder) figured it out, and that understanding should be preserved
for future work.

| Directory       | Purpose                              | Trigger                     |
|-----------------|--------------------------------------|-----------------------------|
| `reflections/`  | Process failures -- agent did it wrong | Stakeholder correction      |
| `knowledge/`    | Technical victories -- hard problem solved | Stakeholder excitement / struggle resolved |

## Agent Used

**project-manager** (or whichever agent is active when the trigger fires)

## Triggers

Invoke this skill when any of the following occur:

1. **Stakeholder excitement** -- The human expresses relief, surprise, or
   satisfaction that something finally works. Phrases like "it works!",
   "finally!", "I can't believe that worked", "oh great", "that fixed
   it", "awesome, it's working now".

2. **Resolution after struggle** -- The agent has been through multiple
   failed attempts, debugging cycles, or trial-and-error iterations in
   the current conversation, and has now reached a working solution.

3. **Non-obvious fix** -- The solution turned out to be something
   surprising, counterintuitive, or poorly documented. The kind of
   thing you would never figure out from reading the docs alone.

4. **Agent self-recognition** -- The agent itself recognizes that the
   path to the solution was unusually difficult and the knowledge is
   worth preserving.

When a trigger fires, say something like: "This was a hard-won fix.
I'd like to record this as project knowledge so we don't have to
rediscover it. OK to proceed?"

## Process

1. **Detect trigger** -- Recognize stakeholder excitement or resolution
   of a multi-attempt debugging session.

2. **Confirm with stakeholder** -- "This was hard-won knowledge. Want me
   to record it?" Skip if the stakeholder has enabled auto-approve.

3. **Gather context** -- Review the conversation for: the original
   problem, symptoms observed, failed attempts (and why each failed),
   the working solution, and the underlying explanation.

4. **Write knowledge file** -- Create a file at
   `docs/clasi/knowledge/YYYY-MM-DD-slug.md` with the format below.

5. **Commit** -- `docs: record project knowledge -- <title>`

6. **Confirm** -- Show the stakeholder the file path and a one-line
   summary of what was captured.

## File Format

YAML frontmatter:

```yaml
---
date: YYYY-MM-DD
tags: [relevant, searchable, terms]
related-tickets: [NNN] (if applicable)
---
```

Followed by these markdown sections:

```markdown
## Problem

What was broken, confusing, or misbehaving.

## Symptoms

Observable behavior that led to investigation.

## What Was Tried

1. **Attempt 1** -- Description. Why it failed.
2. **Attempt 2** -- Description. Why it failed.
3. ...

## What Worked

The actual fix or solution, with enough detail to reproduce.

## Why It Works

The underlying explanation -- what was actually going on.

## Future Guidance

What to do (or avoid) next time. Actionable rules for future agents.
This is the most important section -- it is the actionable takeaway.
```

## Output

- Knowledge file in `docs/clasi/knowledge/`
- Commit with message `docs: record project knowledge -- <title>`
- Confirmation to the stakeholder with the file path and summary
