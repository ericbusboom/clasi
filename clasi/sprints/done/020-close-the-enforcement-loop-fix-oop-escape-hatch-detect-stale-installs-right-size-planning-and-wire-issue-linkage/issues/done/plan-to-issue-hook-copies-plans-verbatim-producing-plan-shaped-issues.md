---
status: done
sprint: '020'
tickets:
- 020-007
---

# plan-to-issue hook copies plans verbatim, producing plan-shaped issues

## Description

The `plan-to-issue` PostToolUse hook fires on `ExitPlanMode` and writes the plan
file into `clasi/issues/` unchanged apart from frontmatter. The result is an
issue file that is not an issue — it is a plan *about* doing work, carrying
plan-mode framing that makes no sense once it is sitting in the issue queue.

Observed 2026-07-14 while capturing the "re-enable the MCP process-content
tools" issue. The hook produced
`clasi/issues/issue-re-enable-the-mcp-process-content-tools.md` containing:

- A `## Scope of this plan` section saying **"Write the issue file. Do not
  implement."** — an instruction to the planning session, meaningless in an issue.
- A `## Deliverable` section instructing the reader to *create the issue file*
  that the document already was, at a different filename
  (`re-enable-mcp-process-content-tools.md`).
- A `## Files to touch (this plan)` section listing that same phantom file.
- `## Recommendation to record in the issue` — recommendations *about* what the
  issue should say, rather than the issue saying it.
- Plan-shaped headings (Context / Scope / What the research established /
  Deliverable) instead of the established issue format.

The file had to be rewritten by hand into the house format. Every plan that
exits plan mode lands in `clasi/issues/` in this shape.

Compare the convention the rest of the queue follows, e.g.
`clasi/issues/create-ticket-auto-links-all-sprint-issues-to-every-ticket.md`:
`# Title`, then `## Description`, `## Cause`, `## Proposed fix`,
`## Verification`, `## Related`.

Two smaller defects visible in the same artifact:

- **Filename.** The title heading was `# Issue: re-enable the MCP process-content
  tools`, so `slugify` produced `issue-re-enable-...` — the word "issue"
  redundantly baked into a filename already living in `issues/`.
- **Silent overwrite risk is absent but adjacent.** `_unique_path` correctly
  suffixes `-2`, `-3` on collision, so nothing is clobbered; but a re-exited plan
  on the same topic silently produces a near-duplicate issue rather than
  updating the first.

## Cause

`src/clasi/plan_to_issue.py:52-77` — `plan_to_issue()` is a verbatim copier by
design:

```python
content = plan_file.read_text(encoding="utf-8").strip()
# Strip existing frontmatter if present
body = content
if content.startswith("---"):
    parts = content.split("---", 2)
    if len(parts) >= 3:
        body = parts[2].strip()
# Extract title from first # heading
...
out_path.write_text(f"---\nstatus: pending\n---\n\n{body}\n", encoding="utf-8")
```

The body passes through untouched. Nothing reshapes plan sections into issue
sections, and nothing strips plan-mode scaffolding. Wired at
`src/clasi/hook_handlers.py:1006-1019` (`handle_plan_to_issue`), reading
`tool_input.planFilePath`.

`plan_to_issue_from_text()` (`:80-120`, the Codex path) has the same
pass-through behavior, so a fix should cover both.

This is arguably working as originally specified — "save the plan as an issue" —
and the gap is that a plan and an issue are different documents with different
audiences. A plan addresses the session about to act. An issue addresses a future
sprint-planner with no context.

## Proposed fix

Pick one:

1. **Have the hook block and hand off to the model** (preferred). The hook
   already returns `{"decision": "block", "reason": ...}` and the model reads it.
   Change the reason to instruct the model to rewrite the just-written file into
   the issue format rather than merely "confirm the issue was created and stop."
   The model has the plan's full context in-session and is the only party that
   can reshape prose. Cheap, no parsing.
2. **Template-map the sections** in `plan_to_issue()` — drop known plan-only
   headings (`Scope of this plan`, `Deliverable`, `Files to touch`,
   `Recommendation to record in the issue`), map `Context` → `Description`.
   Brittle: heading names are model-chosen, not fixed.
3. **Accept plan-shaped issues** and change the issue convention to tolerate
   them. Rejected — the queue's readers are sprint-planners, and "Do not
   implement. Write the issue file." actively misleads them.

Option 1 also fixes the filename: instruct the model to name the file without an
`issue-` prefix.

## Verification

- Enter plan mode, write a plan containing a `## Scope of this plan` section that
  says "do not implement", exit plan mode.
- Assert the resulting `clasi/issues/*.md` contains no plan-mode framing: no
  "Scope of this plan", no "Deliverable", no "Files to touch", no instruction to
  create the file that already exists.
- Assert it carries `## Description` and `## Proposed fix`.
- Assert the filename has no redundant `issue-` prefix.
- Regression: `_unique_path` still suffixes on collision; `status: pending`
  frontmatter still present; the source plan file is still unlinked.
- Cover the Codex path (`plan_to_issue_from_text`) with the same shape check.

## Related

- Found 2026-07-14 while filing
  `clasi/issues/issue-re-enable-the-mcp-process-content-tools.md`, which is
  itself the corrupted artifact (since hand-corrected). That file's name is the
  filename defect; its git history is the before/after.
- Independent of sprint 019 — this is a capture-path bug, not an
  enforcement-guard bug.
