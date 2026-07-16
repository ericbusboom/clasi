---
name: consolidate-architecture
description: Merge architecture documentation scattered across sprint history and current source code into a single, up-to-date consolidated architecture document
---

# Consolidate Architecture Skill

Reads architecture documentation scattered across sprint history —
`sprint.md` Architecture sections and legacy `architecture-update.md`
files alike — plus the current source code, and produces a single
up-to-date consolidated architecture document.

## When to Use

Run on demand when:
- Sprint history makes it hard to understand current architecture from
  any one document
- A new team member needs to onboard
- You want a clean baseline before a major refactoring sprint

This is NOT run automatically on every sprint close.

## Process

1. **Collect sprint architecture history**: Walk `clasi/sprints/**`,
   including `clasi/sprints/done/**`, and read architecture content from
   every sprint, in order:
   - For sprints using the single-doc model, read the `## Architecture`
     section of `sprint.md`.
   - For historical sprints (001-017 and any other sprint that predates
     the single-doc model), read the legacy `architecture-update.md`
     file instead.

   Both forms describe the same thing — architectural decisions and
   changes made during that sprint — just in different files. Treat them
   as one continuous history ordered by sprint number.

2. **Read actual code**: Verify current system structure against source
   code. The consolidated document must reflect reality, not just what
   sprint docs claim — where they disagree, the code wins.

3. **Write the new consolidated document**: Incorporate the full sprint
   history and the verified current-code state into one narrative,
   including updated Mermaid diagrams.

4. **Save**: Write as `docs/design/architecture.md`, overwriting
   whatever was there before. There is no versioning and no archive —
   each run reads all available sprint history fresh and produces one
   current snapshot.

## Output

- `docs/design/architecture.md` (single file, overwritten each run)
