---
source_file: DESIGN.md
source_hash: d90609a96df89ee954434f8c4ab443523a428dc834236365964f2bc8d1e2ddae
---
# Diff: DESIGN.md

Comparison of the sprint overlay copy of `DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- DESIGN.md (pristine)
+++ DESIGN.md (current)
@@ -53,6 +53,19 @@
   execution locks, gate results, and OOP records.
 - `hook_handlers.py`, `plan_to_issue.py`, `staleness.py` — hook-time
   behavior (role/mcp guards, plan-mode capture, running-build drift).
+  As of sprint 026, `handle_role_guard` resolves `Project`, its parsed
+  config, and its sqlite connection once per hook invocation and reuses
+  them across every check inside that call, rather than reconstructing
+  each per check; its ticket-state gate applies to tier-2 writes only
+  (issues/reflections directories are exempt for every tier); its
+  recovery-state lookup matches directory-prefix entries in addition to
+  exact paths; and its tier-1 branch consults the same artifact-dir
+  allow list tier 0 does. `__init__.py` resolves `__version__` lazily
+  via module `__getattr__` instead of an eager `importlib.metadata`
+  call at import time — see this doc set's `status-DESIGN.md`/
+  `state_machine-DESIGN.md` overlay entries for the matching per-prompt
+  status-path caching, and `plugin-DESIGN.md` for the corresponding
+  `hooks.json` cleanup.
 - `init_command.py`, `migrate_command.py`, `uninstall_command.py`,
   `versioning.py`, `worktree.py`, `contracts.py`, `agent.py`,
   `dispatch_log.py` — installation, migration, versioning, worktree, and
@@ -90,6 +103,12 @@
   out-of-root work:** `hook_handlers.py`'s role/mcp guards govern writes to
   this repo's own source and process artifacts; paths outside the project
   root are not CLASI's to police.
+- **A hook invocation is a single process lifetime; expensive per-call
+  work is memoized within it, not across invocations:** `handle_role_guard`
+  and the status-inject path (sprint 026) cache `Project`/config/sqlite
+  and git-subprocess results for the duration of one hook process, then
+  discard the cache — there is no cross-invocation cache to invalidate,
+  which keeps the caching addition free of staleness concerns.
 
 ## 4. See Also
 
```
