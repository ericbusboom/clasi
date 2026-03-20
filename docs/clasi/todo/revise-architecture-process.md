---
status: pending
---

# Revise Architecture Process: Updates Instead of Full Copies

## Problem

The current process copies the full architecture document into every sprint and updates it. The architecture is long and getting longer. Updating it is a job in itself. Every sprint carries the full weight of the architecture even when only a small piece changes.

## New Process

### Architecture Directory

Keep the consolidated architecture in `docs/clasi/architecture/`, named after the sprint at which it was last consolidated. Example: `architecture-024.md` means it was consolidated at sprint 024.

### Sprint Architecture Updates (not full copies)

Sprints no longer get a full copy of the architecture. Instead, each sprint gets an **architecture update** document — a description of how the architecture is changing in that sprint. This is much smaller and focused.

When the sprint closes, the architecture update is copied to the architecture directory with the sprint number: `architecture-update-025.md`.

### Consolidation (manual, on demand)

Architecture consolidation is a manual process triggered by the stakeholder telling the team lead "consolidate the architecture now."

Example timeline:
- `architecture-024.md` — last consolidated architecture
- `architecture-update-025.md` — changes from sprint 025
- `architecture-update-026.md` — changes from sprint 026
- `architecture-update-027.md` — changes from sprint 027
- Stakeholder says "consolidate" → team lead reads the base (024) plus all updates (025-027), rewrites the architecture, verifies against actual code, produces `architecture-027.md`

Consolidation involves:
1. Reading the current consolidated architecture
2. Reading all subsequent update documents
3. Rewriting the architecture to incorporate all changes
4. Verifying the result against the actual codebase (not just the updates — check that the architecture still matches reality)
5. Naming the result after the latest sprint included

### What Changes

- `create_sprint` no longer copies the full architecture into the sprint directory
- Sprint template gets a lightweight "architecture update" template instead
- `close_sprint` copies the update to the architecture directory
- The architect agent writes updates, not full rewrites
- New consolidation skill/process for when the stakeholder requests it
