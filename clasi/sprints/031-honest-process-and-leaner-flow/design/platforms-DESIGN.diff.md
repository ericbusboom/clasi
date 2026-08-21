---
source_file: platforms-DESIGN.md
source_hash: 2016440be438c8e1a57fb805d2b77304b3790c7e549a4be798dd2b56210501ec
---
# Diff: platforms-DESIGN.md

Comparison of the sprint overlay copy of `platforms-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- platforms-DESIGN.md (pristine)
+++ platforms-DESIGN.md (current)
@@ -14,7 +14,7 @@
 
 - `detect.py` — `detect_platforms(target)` scores observable signals (project files, installed commands, user config dirs, env var *names* only — never values) per platform and returns an advisory `PlatformSignals` recommendation. Never writes files or makes an irreversible decision itself.
 - `claude.py`, `codex.py`, `copilot.py` — each exposes `install(target, mcp_config)` / `uninstall(target)` for its platform: writing the host markdown file (CLAUDE.md / AGENTS.md / copilot-instructions.md), copying skills/agents/hooks from `plugin/`, updating platform-specific settings and permissions files.
-- `_links.py`, `_markers.py`, `_rules.py` — shared leaf utilities with no CLASI imports of their own: symlink-with-copy-fallback, idempotent named marker-block read/write in host markdown files, and the canonical prose bodies for CLASI's five path-scoped rules (single source of truth, both `claude.py` and `codex.py` import from here rather than hardcoding rule text).
+- `_links.py`, `_markers.py`, `_rules.py` — shared leaf utilities with no CLASI imports of their own: symlink-with-copy-fallback, idempotent named marker-block read/write in host markdown files, and the canonical prose bodies for CLASI's five path-scoped rules (single source of truth, both `claude.py` and `codex.py` import from here rather than hardcoding rule text). **As of sprint 031**: `_rules.py`'s `source-code.md` body — loaded on every source edit — no longer points at "the execute-ticket skill" (a skill that does not exist anywhere under `plugin/skills/`; the only file by that name lives under the retired `plugin/agents/old/sprint-executor/`) — it points at the programmer agent definition instead. This is the single canonical source both `claude.py` and (per this module's own invariant, see `## 3`) any other platform installer read; fixing it here, not in a generated copy, is what keeps the fix from drifting the next time a platform installer re-runs.
 
 ## 3. Constraints and Invariants
 
```
