---
source_file: design.md
source_hash: b3cf05572a4d891e501230bb2238f9dbe570bfed6e6a366118fd7fa958149b6e
---
# Diff: design.md

Comparison of the sprint overlay copy of `design.md` against its pristine (seed-commit) canonical version.

```diff
--- design.md (pristine)
+++ design.md (current)
@@ -1,11 +1,13 @@
 # CLASI: System Design
 
-**Owner:** clasi maintainers · **Last reviewed:** 2026-07-17 · **Status:** in-flux
+**Owner:** clasi maintainers · **Last reviewed:** 2026-08-21 (sprint 032) · **Status:** in-flux
 
 CLASI is a Software Engineering process tool: an MCP server plus CLI plus
-installable platform integration (Claude Code / Codex / Copilot) that
-drives a structured issue -> sprint -> ticket -> execution -> close
-lifecycle for AI-agent-assisted software development. This document is the
+installable platform integration (Claude Code — the only platform
+adapter in master as of sprint 032; see `platforms/DESIGN.md` for the
+Codex/Copilot archival) that drives a structured issue -> sprint ->
+ticket -> execution -> close lifecycle for AI-agent-assisted software
+development. This document is the
 entry point into the persistent per-subsystem design-doc set. As of sprint
 022, each subsystem's design doc is **co-located with its code** as
 `DESIGN.md` inside the subsystem's own source directory — see
@@ -75,9 +77,23 @@
 install by comparing in-process `__version__` and installed-package
 metadata against the serving project's source), `dispatch_log.py`
 (structured logging of subagent dispatch prompts), `worktree.py`
-(parallel-ticket-execution worktree lifecycle API — currently unused;
-serial-only execution is mandated by
-`schemas/se-process/instructions/execution.md`).
+(**as of sprint 032**: the parallel-ticket-execution lifecycle this
+module used to expose — `create_worktree`, `create_ticket_branch`,
+`validate_worktree`, `merge_ticket_branch`, `check_independence`, and
+their parsing/topo-sort helpers — is deleted, not merely unused; it was
+never wired into the controller and every real sprint ran serial-only.
+What remains is a reconcile/cleanup/audit core —
+`reconcile_worktrees`, `cleanup_worktree`, `write_audit_record`,
+`read_audit_record`, and their two live parsing helpers — genuinely
+called by `close.py`'s worktree-pruning step and the `reconcile_worktrees`
+MCP tool to clean up git worktrees left behind by other tooling.
+`schemas/se-process/instructions/execution.md` now describes exactly one
+execution path, with no `worktree`-flag branch; the sprint `worktree:`
+frontmatter field is no longer written for new sprints (existing
+sprints that still carry `worktree: false` are unaffected and untouched).
+The design intent for the deleted parallel-execution half is preserved,
+not erased, in `docs/design/worktree-process.md`, now marked `status:
+retired` rather than removed).
 
 **Agent definitions** — `agent.py` (`Agent` class hierarchy: loads agent
 definitions/contracts/dispatch templates from disk; does not execute
@@ -131,7 +147,15 @@
   no source directory to co-locate into and stay where they are. This
   document (`design.md`) also stays in `docs/design/`, as the one
   system-level design document with no single owning subsystem directory
-  of its own.
+  of its own. **As of sprint 032**: `worktree-process.md` carries
+  `status: retired` — its specified parallel-execution lifecycle was
+  deleted from `worktree.py`, not merely left unimplemented, so the doc
+  now records design intent for code that no longer exists rather than
+  code "not yet wired in." It stays in this list (still frozen,
+  project-level, no source directory to co-locate into) rather than
+  being deleted, so the design rationale it captured — the independence-
+  check algorithm, the audit-format tradeoffs — remains readable rather
+  than only recoverable from git history.
 
 ## Sprint-Change Linkage
 
```
