---
name: consolidate-architecture
description: Merge the base architecture document with subsequent sprint update documents into a new consolidated architecture
---

# Consolidate Architecture Skill

Merges the last consolidated architecture document with all subsequent
architecture-update documents to produce a new, up-to-date consolidated
architecture.

## When to Use

Run this skill on demand when:
- The number of outstanding update documents makes it hard to understand
  the current architecture at a glance.
- A new team member needs to onboard and understand the system.
- You want a clean baseline before a major refactoring sprint.

This is NOT run automatically on every sprint close. Sprint close only
copies the update document; consolidation is a deliberate act.

## Process

1. **Identify the base**: Find the latest consolidated architecture in
   `docs/clasi/architecture/architecture-NNN.md` (highest NNN).

2. **Collect updates**: Find all `architecture-update-MMM.md` files in
   `docs/clasi/architecture/` where MMM > NNN (i.e., updates since the
   last consolidation). Read them in order.

3. **Read actual code**: Verify the current system structure against the
   source code. The consolidated document must reflect reality, not just
   the sum of planned changes.

4. **Write the new consolidated document**: Produce a new architecture
   document that:
   - Incorporates all changes from the update documents
   - Reflects the actual current state of the codebase
   - Follows the architecture document structure (see
     `instructions/architectural-quality.md`)
   - Includes updated Mermaid diagrams

5. **Save**: Write the new document as
   `docs/clasi/architecture/architecture-MMM.md` (where MMM is the
   sprint number of the latest update incorporated).

6. **Archive old files**: Move the previous consolidated document and
   all incorporated update documents to `docs/clasi/architecture/done/`.

## Output

- New `docs/clasi/architecture/architecture-MMM.md` reflecting the
  current system state
- Old base and update files moved to `docs/clasi/architecture/done/`
