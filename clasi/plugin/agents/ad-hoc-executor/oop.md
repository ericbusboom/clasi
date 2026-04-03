---
name: oop
description: Out-of-process mode — skip SE ceremony for small, targeted changes
---

# /oop — Out of Process

Skip all SE process ceremony and make a quick, targeted change directly
on master. This is for changes where the full process would be overkill.

## When to use

- Typo fixes
- Small bug fixes (one or two files)
- Config tweaks
- One-line changes
- Documentation corrections

## When NOT to use

- New features (use the SE process)
- Changes touching more than 3 files
- Anything requiring design decisions
- Anything the stakeholder hasn't seen yet

## Process

1. Read the relevant code.
2. Make the change.
3. Run the full test suite: `uv run pytest`.
4. If tests pass, commit directly to master with a descriptive message.
5. If tests fail, fix the issue and re-run.

That's it. No sprint, no tickets, no review gates, no architecture review.

## Rules

- Do NOT create sprints, tickets, or planning documents.
- Do NOT use `create_sprint`, `create_ticket`, or other artifact tools.
- Do NOT ask for stakeholder approval at process gates — there are no gates.
- DO run tests before committing. Tests are never optional.
- DO write a clear commit message explaining the change.
- After committing, run `clasi version bump`. It checks the trigger
  setting internally and skips if not applicable.
