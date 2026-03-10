---
status: done
sprint: '017'
---

# Add SE process reminder line to all document templates

Add a one-line reminder to every document template that CLASI generates in
`docs/plans/`. The line should read something like:

> If you are an automated coding agent, before changing any code or engaging
> in any pre-coding plans, review the software engineering process in AGENTS.md.

This provides redundant reinforcement — agents encounter the reminder in
every planning artifact they read, not just in CLAUDE.md/AGENTS.md.

## Templates to update

- Sprint document (`sprint.md` template)
- Architecture document template
- TODO files (created by the `todo` skill)
- Ticket files (created by `create_ticket`)

## Notes

- Keep it to one line (or a short HTML comment) so it doesn't clutter
  the document for human readers.
- Some teams put similar reminders in every source file; here we limit
  it to `docs/plans/` artifacts since that's where the process engages.
- Once the first TODO (inline CLASI into CLAUDE.md) lands, the reminder
  text should reference CLAUDE.md instead of AGENTS.md.
