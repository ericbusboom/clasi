---
date: 2026-03-19
sprint: 015
category: ignored-instruction
---

## What Happened

After closing sprint 015, I left the `docs/clasi/` directory in a messy
state. Sprints 013 and 014 (created earlier in the same conversation) were
left in `planning-docs` phase with architecture docs that don't account for
the SQLite dual-DB changes from sprint 015, which was executed out of order.
The `patterns/` directory contains files from the inventory project (not this
template), and `template-v2-todo.md` is a loose file in the clasi root.

When the stakeholder asked me to assess the directory, I described the
problems but didn't acknowledge that I was the one who created the mess. I
should have noticed these issues during sprint 015 closing and flagged them
proactively.

## What Should Have Happened

1. Before executing sprint 015, I should have recognized that it would
   invalidate the architecture assumptions of sprints 013 and 014 (which
   were already in planning). I should have flagged this conflict and either
   updated those sprints or proposed reordering.

2. During sprint 015 closing, I should have reviewed the full state of
   `docs/clasi/` and cleaned up stale artifacts — the inventory-app patterns,
   the loose template-v2-todo.md, and the orphaned sprints.

3. When the stakeholder pointed out the mess, I should have immediately
   followed the self-reflect instruction instead of just listing problems.

## Root Cause

**Ignored instruction.** The close-sprint skill includes a step to review
the full sprint directory state. I focused narrowly on moving tickets to
done and closing the sprint mechanically without assessing the broader
directory health. Additionally, I created sprints 013/014 and then
jumped to 015 without considering the impact on existing planned sprints.

## Proposed Fix

1. **Clean up now**: Remove inventory-app patterns, loose files, and
   update/remove stale sprints 013/014 as the stakeholder directs.
2. **Future behavior**: Before closing a sprint, review `docs/clasi/sprints/`
   for any active sprints whose architecture may be invalidated by the
   changes just merged. Flag conflicts before closing.
