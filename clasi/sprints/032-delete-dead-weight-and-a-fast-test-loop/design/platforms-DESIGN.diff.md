---
source_file: platforms-DESIGN.md
source_hash: 97c9b9c367df587fbf93d246f3ecf3062fc40d8145e80ff7e0a4ad6fe77e50ea
---
# Diff: platforms-DESIGN.md

Comparison of the sprint overlay copy of `platforms-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- platforms-DESIGN.md (pristine)
+++ platforms-DESIGN.md (current)
@@ -1,42 +1,45 @@
 # clasi.platforms
 
-**Owner:** clasi maintainers · **Last reviewed:** 2026-07-16 · **Status:** stable
+**Owner:** clasi maintainers · **Last reviewed:** 2026-08-21 (sprint 032) · **Status:** stable
 
 ---
 
 ## 1. Purpose
 
-`clasi.platforms` installs and uninstalls CLASI's file-based integration with a supported host AI coding tool (Claude Code, Codex, or GitHub Copilot) in a target repository. It exists as its own subsystem because "detect which platform(s) are in use and materialize that platform's specific file layout" is a self-contained problem with three near-identical instantiations (one per platform) that share underlying primitives (symlink/copy, marker-block writing, rule bodies) but must each independently know their platform's directory conventions. Nothing else in the codebase needs to know these conventions.
+`clasi.platforms` installs and uninstalls CLASI's file-based integration with a supported host AI coding tool in a target repository. **As of sprint 032**, Claude Code is the only platform adapter in master — `codex.py` and `copilot.py` were archived to the `archive/codex-copilot-adapters` branch (never dogfooded, reachable only via explicit `--codex`/`--copilot` flags, carrying a live bug where installing Codex after Claude overwrote Claude's resolved skill canonical). It remains its own subsystem — even at one adapter — because "detect which platform is in use and materialize its file layout" stays a self-contained problem or, if Codex/Copilot are ever un-archived, again becomes the "N near-identical instantiations sharing primitives" problem this subsystem was originally split out to hold. Nothing else in the codebase needs to know Claude's directory conventions.
 
 ## 2. Orientation
 
-One advisory entry point plus three parallel platform installers, sharing three leaf utility modules:
+One advisory entry point plus one platform installer, sharing three leaf utility modules (the leaf/installer split was built for N platforms and is retained even at N=1, since it is what makes restoring an archived adapter additive rather than a redesign):
 
-- `detect.py` — `detect_platforms(target)` scores observable signals (project files, installed commands, user config dirs, env var *names* only — never values) per platform and returns an advisory `PlatformSignals` recommendation. Never writes files or makes an irreversible decision itself.
-- `claude.py`, `codex.py`, `copilot.py` — each exposes `install(target, mcp_config)` / `uninstall(target)` for its platform: writing the host markdown file (CLAUDE.md / AGENTS.md / copilot-instructions.md), copying skills/agents/hooks from `plugin/`, updating platform-specific settings and permissions files.
-- `_links.py`, `_markers.py`, `_rules.py` — shared leaf utilities with no CLASI imports of their own: symlink-with-copy-fallback, idempotent named marker-block read/write in host markdown files, and the canonical prose bodies for CLASI's five path-scoped rules (single source of truth, both `claude.py` and `codex.py` import from here rather than hardcoding rule text). **As of sprint 031**: `_rules.py`'s `source-code.md` body — loaded on every source edit — no longer points at "the execute-ticket skill" (a skill that does not exist anywhere under `plugin/skills/`; the only file by that name lives under the retired `plugin/agents/old/sprint-executor/`) — it points at the programmer agent definition instead. This is the single canonical source both `claude.py` and (per this module's own invariant, see `## 3`) any other platform installer read; fixing it here, not in a generated copy, is what keeps the fix from drifting the next time a platform installer re-runs.
+- `detect.py` — `detect_platforms(target)` scores observable signals (project files, installed commands, user config dirs, env var *names* only — never values) and returns an advisory `PlatformSignals` recommendation. **As of sprint 032**: with Codex/Copilot archived, live scoring and the CLI's install-choice prompt cover Claude only; the module's scoring fields for the archived platforms are inert dead weight pending ticket 001's cleanup pass, not a live three-way decision. Never writes files or makes an irreversible decision itself.
+- `claude.py` — exposes `install(target, mcp_config)` / `uninstall(target)`: writing the host markdown file (CLAUDE.md/AGENTS.md), copying skills/agents/hooks from `plugin/`, updating Claude-specific settings and permissions files. **As of sprint 032**: `install`'s hooks step merges per event type instead of replacing `settings["hooks"]` wholesale (fixing F3 — a full-object replace previously deleted any user-defined hook silently on every `clasi init`), `uninstall`'s CLAUDE.md step strips CLASI's marker block via `strip_section` instead of `_links.unlink_alias`-ing the whole file (fixing F2 — matching what the AGENTS.md step two lines below it already did correctly), and `_create_rules` compares existing file content before writing and skips unchanged files, matching its own docstring's pre-existing claim (fixing F13).
+- `_links.py`, `_markers.py`, `_rules.py` — shared leaf utilities with no CLASI imports of their own: symlink-with-copy-fallback, idempotent named marker-block read/write in host markdown files, and the canonical prose bodies for CLASI's five path-scoped rules (single source of truth). **As of sprint 031**: `_rules.py`'s `source-code.md` body — loaded on every source edit — no longer points at "the execute-ticket skill" (a skill that does not exist anywhere under `plugin/skills/`; the only file by that name lives under the retired `plugin/agents/old/sprint-executor/`) — it points at the programmer agent definition instead. **As of sprint 032**: with only `claude.py` reading from `_rules.py`, the "both `claude.py` and `codex.py` import from here" framing in this doc's prior revision is obsolete — the single-canonical-source property still holds, now trivially (one reader), and is worth re-establishing rather than dropping if Codex is ever un-archived.
 
 ## 3. Constraints and Invariants
 
 - **`detect.py` never reads environment variable values, only names, and never writes anything:** it is explicitly advisory — a violation would make platform detection a covert credential-reading path, which the module's own docstring calls out as a hard boundary.
 - **`_links.py`, `_markers.py`, `_rules.py` are leaf nodes:** no CLASI imports, no platform-specific knowledge. Adding a CLASI import to any of these re-couples modules the split was meant to decouple.
-- **Rule content lives only in `_rules.py`:** neither `claude.py` nor `codex.py` may hardcode a rule body inline — drift between the two platforms' copies of the same rule is exactly what centralizing this was meant to prevent.
+- **Rule content lives only in `_rules.py`:** `claude.py` may not hardcode a rule body inline.
 - **Marker blocks must preserve user content outside the block:** `_markers.py`'s create/update/append semantics are idempotent specifically so re-running install never destroys content a user added to CLAUDE.md/AGENTS.md outside the CLASI section.
+- **`claude.py`'s writes merge or compare; none may overwrite wholesale (sprint 032):** the `.mcp.json` server entry (owned by `init_command.py`, see below), hooks, CLAUDE.md, and rule files each follow a "leave what's already there unless it's ours to update" rule. A future write site in this subsystem that replaces a whole file or a whole JSON object instead of merging/comparing reintroduces exactly the F1-F4/F13 failure class sprint 032 fixed — the CLASI-owned this-repo `.mcp.json` incident (2026-07-16) is the concrete cost of getting this wrong once already.
 
 ## 4. Design
 
-Each platform installer follows the same shape: copy `plugin/skills`, `plugin/agents`, `plugin/hooks` content into the platform's expected location (symlinked where the platform supports it, copied where it doesn't — see `_links.link_or_copy`'s `copy` fallback flag), write/update the host markdown file's CLASI-managed section via `_markers.write_named_section`, and write the five path-scoped rule files from `_rules.py`'s canonical bodies. `detect.py` is called by `init_command.py` (outside this subsystem) to recommend which installer(s) to run, not by the installers themselves — detection and installation are deliberately decoupled so a caller can override the recommendation.
+The one remaining platform installer follows the same shape a multi-platform version would: copy `plugin/skills`, `plugin/agents`, `plugin/hooks` content into Claude's expected location (symlinked where supported, copied where not — see `_links.link_or_copy`'s `copy` fallback flag), write/update CLAUDE.md/AGENTS.md's CLASI-managed section via `_markers.write_named_section`, and write the five path-scoped rule files from `_rules.py`'s canonical bodies, comparing before writing. `detect.py` is called by `init_command.py` (outside this subsystem) to recommend which installer to run, not by the installer itself — detection and installation stay deliberately decoupled so a caller can override the recommendation, the same reason this held when there were three installers to choose among.
 
 ## 5. Interfaces
 
 ### Exposes
-- **`detect_platforms(target: Path) -> PlatformSignals`:** advisory-only platform recommendation; read-only, no side effects.
-- **`install(target: Path, mcp_config: dict) -> None`** and **`uninstall(target: Path) -> None`**, one pair per platform module (`claude`, `codex`, `copilot`). Neither knows about shared scaffolding (TODO dirs, log dir, `.mcp.json`) — that remains `init_command.py`'s job.
+- **`detect_platforms(target: Path) -> PlatformSignals`:** advisory-only platform recommendation; read-only, no side effects. Codex/Copilot scoring fields remain in the return shape (harmless, unused) pending ticket 001's cleanup pass.
+- **`install(target: Path, mcp_config: dict) -> None`** and **`uninstall(target: Path) -> None`**, `claude.py`'s pair (the only one in master as of sprint 032). Neither knows about shared scaffolding (TODO dirs, log dir, `.mcp.json`) — that remains `init_command.py`'s job.
 
 ### Consumes
-- **`plugin/` (this repo's `clasi-core` narrative in `design.md`):** the source content every installer copies from — skills, agents, hooks, instructions, rules.
-- **`init_command.py` (top-level, not its own subsystem):** the caller that orchestrates detection and installation together and owns shared scaffolding outside any single platform's concern.
+- **`plugin/` (this repo's `clasi-core` narrative in `design.md`):** the source content the installer copies from — skills, agents, hooks, instructions, rules.
+- **`init_command.py` (top-level, not its own subsystem):** the caller that orchestrates detection and installation together, owns shared scaffolding outside any single platform's concern, and (as of sprint 032) leaves an existing `.mcp.json` `clasi` server entry untouched rather than unconditionally rewriting it to the consumer default.
 
 ## 6. Open Questions / Known Limitations
 
-- `detect.py`'s "all scores zero -> default to claude" fallback is a backward-compatibility choice noted in its own docstring; whether that default should change as Codex/Copilot adoption grows is unresolved here.
+- Whether to fully remove `detect.py`'s Codex/Copilot scoring fields now versus leaving them as inert dead weight until/unless the adapters are un-archived is left to ticket 001's implementer — either is safe; this doc doesn't mandate one.
+- If Codex/Copilot are ever restored from `archive/codex-copilot-adapters`, the shared canonical-skill-writer requirement this doc's pre-032 revision described (install order must not change the resolved-skill result) becomes live again and should be re-ticketed at that time — it was deliberately not built speculatively in sprint 032 (see sprint 032's `sprint.md` Design Rationale).
+- `detect.py`'s "all scores zero -> default to claude" fallback is now closer to "the only meaningful default," but the fallback logic itself is unchanged by sprint 032.
```
