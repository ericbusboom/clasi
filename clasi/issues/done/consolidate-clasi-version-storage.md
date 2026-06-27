---
status: done
---

# Consolidate clasi-version storage

Move `.agents/.clasi-version` into `.clasi/config.yaml`, or eliminate
it entirely in favor of the version already stored by dotconfig.

## Description

We currently track the CLASI version in a dedicated `.agents/.clasi-version`
file. This is a separate location from other CLASI configuration and
duplicates information that dotconfig already maintains.

Two options to consider:

1. **Move into `.clasi/config.yaml`** — keep version info under CLASI's
   own control, but consolidate with other CLASI config rather than
   sitting alone in `.agents/`. Cleaner layout, single source of truth
   within the project.

2. **Eliminate entirely** — rely on the version stored by dotconfig
   as the canonical source. Removes duplication and avoids drift
   between the two locations, but couples CLASI version tracking to
   dotconfig being present/used.

DECISION: Options 2, eliminate the separate `.agents/.clasi-version` file and rely on the version stored by dotconfig as the single source of truth for CLASI version information. This simplifies our storage and avoids potential inconsistencies between multiple version tracking locations.   

