---
source_paths:
- /Volumes/Proj/proj/ai-projects/clasi/src/clasi/platforms
readme_path: /Volumes/Proj/proj/ai-projects/clasi/src/clasi/platforms/README.md
---
# clasi.platforms

**Owner:** clasi maintainers · **Last reviewed:** 2026-07-16 · **Status:** stable

---

## 1. Purpose

`clasi.platforms` installs and uninstalls CLASI's file-based integration with a supported host AI coding tool (Claude Code, Codex, or GitHub Copilot) in a target repository. It exists as its own subsystem because "detect which platform(s) are in use and materialize that platform's specific file layout" is a self-contained problem with three near-identical instantiations (one per platform) that share underlying primitives (symlink/copy, marker-block writing, rule bodies) but must each independently know their platform's directory conventions. Nothing else in the codebase needs to know these conventions.

## 2. Orientation

One advisory entry point plus three parallel platform installers, sharing three leaf utility modules:

- `detect.py` — `detect_platforms(target)` scores observable signals (project files, installed commands, user config dirs, env var *names* only — never values) per platform and returns an advisory `PlatformSignals` recommendation. Never writes files or makes an irreversible decision itself.
- `claude.py`, `codex.py`, `copilot.py` — each exposes `install(target, mcp_config)` / `uninstall(target)` for its platform: writing the host markdown file (CLAUDE.md / AGENTS.md / copilot-instructions.md), copying skills/agents/hooks from `plugin/`, updating platform-specific settings and permissions files.
- `_links.py`, `_markers.py`, `_rules.py` — shared leaf utilities with no CLASI imports of their own: symlink-with-copy-fallback, idempotent named marker-block read/write in host markdown files, and the canonical prose bodies for CLASI's five path-scoped rules (single source of truth, both `claude.py` and `codex.py` import from here rather than hardcoding rule text).

## 3. Constraints and Invariants

- **`detect.py` never reads environment variable values, only names, and never writes anything:** it is explicitly advisory — a violation would make platform detection a covert credential-reading path, which the module's own docstring calls out as a hard boundary.
- **`_links.py`, `_markers.py`, `_rules.py` are leaf nodes:** no CLASI imports, no platform-specific knowledge. Adding a CLASI import to any of these re-couples modules the split was meant to decouple.
- **Rule content lives only in `_rules.py`:** neither `claude.py` nor `codex.py` may hardcode a rule body inline — drift between the two platforms' copies of the same rule is exactly what centralizing this was meant to prevent.
- **Marker blocks must preserve user content outside the block:** `_markers.py`'s create/update/append semantics are idempotent specifically so re-running install never destroys content a user added to CLAUDE.md/AGENTS.md outside the CLASI section.

## 4. Design

Each platform installer follows the same shape: copy `plugin/skills`, `plugin/agents`, `plugin/hooks` content into the platform's expected location (symlinked where the platform supports it, copied where it doesn't — see `_links.link_or_copy`'s `copy` fallback flag), write/update the host markdown file's CLASI-managed section via `_markers.write_named_section`, and write the five path-scoped rule files from `_rules.py`'s canonical bodies. `detect.py` is called by `init_command.py` (outside this subsystem) to recommend which installer(s) to run, not by the installers themselves — detection and installation are deliberately decoupled so a caller can override the recommendation.

## 5. Interfaces

### Exposes
- **`detect_platforms(target: Path) -> PlatformSignals`:** advisory-only platform recommendation; read-only, no side effects.
- **`install(target: Path, mcp_config: dict) -> None`** and **`uninstall(target: Path) -> None`**, one pair per platform module (`claude`, `codex`, `copilot`). Neither knows about shared scaffolding (TODO dirs, log dir, `.mcp.json`) — that remains `init_command.py`'s job.

### Consumes
- **`plugin/` (this repo's `clasi-core` narrative in `design.md`):** the source content every installer copies from — skills, agents, hooks, instructions, rules.
- **`init_command.py` (top-level, not its own subsystem):** the caller that orchestrates detection and installation together and owns shared scaffolding outside any single platform's concern.

## 6. Open Questions / Known Limitations

- `detect.py`'s "all scores zero -> default to claude" fallback is a backward-compatibility choice noted in its own docstring; whether that default should change as Codex/Copilot adoption grows is unresolved here.
