---
id: "004"
title: "Update programmer agent prompt with exception protocol section"
status: todo
use-cases:
  - SUC-001
depends-on:
  - "018-003"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update programmer agent prompt with exception protocol section

## Description

Add an "Exception Protocol" section to `clasi/plugin/agents/programmer/agent.md`.
Without this section, programmer agents have no defined threshold for when to
stop and signal a structural wall vs. improvise a workaround. The section
establishes the threshold rule, the throw mechanism, the surface classification
guidance, and the exit behavior.

This ticket depends on ticket 003 (`throw_ticket_exception` tool) being done
first, because the prompt instructs programmers to call that tool by name.

## Acceptance Criteria

- [ ] `clasi/plugin/agents/programmer/agent.md` contains a clearly delimited
  "Exception Protocol" section (e.g., `## Exception Protocol`).
- [ ] The section states the threshold: throw when unable to proceed without
  overriding an upstream architecture or use-case decision; hard work is not
  a threshold.
- [ ] The section instructs the programmer to call `throw_ticket_exception`
  with `thrown_by="programmer"` and describes each required argument.
- [ ] The section defines `surface` classification: `"user-visible"` if the
  conflict touches behavior in `usecases.md`; `"internal"` otherwise.
- [ ] The section instructs the programmer to exit cleanly after throwing —
  no partial code, no partial ticket completion.
- [ ] The section states that the ticket is the sole carrier — no
  out-of-band exception text in the final return message.
- [ ] No existing content in `agent.md` is removed or materially altered.
- [ ] No tests to write for this ticket (documentation change only).
  Spot-check by reading the file; the tests in ticket 008 do not cover
  agent prompt content directly.

## Implementation Plan

**File to modify**: `clasi/plugin/agents/programmer/agent.md`

**Approach**: Append a new top-level section at the end of the document.
Read the current file first to verify no existing exception-related section
exists. Add:

```markdown
## Exception Protocol

**Threshold**: Throw an exception when you cannot proceed without overriding
an upstream architecture decision or a use-case boundary. Hard implementation
work — even very hard work — is not a threshold. The wall must be structural.

**How to throw**: Call `throw_ticket_exception(path, thrown_by="programmer",
attempted=..., conflict=..., surface=...)`. Do this before exiting.

- `attempted`: One paragraph describing what you tried before hitting the wall.
- `conflict`: The specific architecture section, use-case, or decision
  that blocks you. Be precise — cite the section heading or use-case ID.
- `surface`: Your first-pass classification:
  - `"user-visible"` — the conflict affects behavior described in usecases.md.
  - `"internal"` — the conflict is purely structural (module boundary,
    dependency direction, internal data model). When in doubt, prefer
    `"internal"` and let the team-lead override.

**Exit cleanly**: After calling `throw_ticket_exception`, stop. Do not write
partial code. Do not mark the ticket in-progress beyond the exception call.
The thrown exception is your deliverable.

**No out-of-band signaling**: The ticket is the carrier. Do not return the
exception payload in your final message text as a substitute for writing
it to the ticket frontmatter via the tool.
```

**Verification**: Read the updated file; confirm the section is present
and the existing content is intact.
