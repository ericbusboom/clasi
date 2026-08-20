---
status: done
type: bug
tags:
- reliability-campaign
- phase-1
- staleness
sprint: 029
tickets:
- 029-007
---

# Staleness: detect same-version source drift via mtime-vs-import-time

## Description

`check_staleness` cannot see the most common real drift: an editable
install whose source changed after the long-lived MCP server imported it,
with no version bump. Both existing signals depend on version strings or
path mismatches that editable installs never trip, so a long-lived
`clasi mcp` serves pre-fix code with a green staleness report — the exact
gap recorded in the project memory. From the reliability review
(04-cli-install-platforms.md F6).

Fix (about 12 lines): record `_IMPORT_TIME = time.time()` in
`clasi/__init__.py`; in `check_staleness`, flag stale if any
`Path(clasi.__file__).parent.rglob("*.py")` mtime is newer than
`_IMPORT_TIME`. No hashing needed; catches every post-import source edit
regardless of version strings.

## Acceptance criteria

- Touching a source file after import makes `get_version()` report
  `stale: true` with a reason naming the newer file.
- The existing signals are unchanged; the new signal has a unit test.
- The E2E stale-server scenario (rebuild wheel mid-run) trips the guard.
