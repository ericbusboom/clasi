---
id: "E"
title: "Integration registry — base class + registry for clasr platforms"
status: planning
branch: sprint/E-integration-registry
use-cases: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint E: Integration registry — base class + registry for clasr platforms

## Goals

Replace `clasr/platforms/{claude,codex,copilot}.py`'s ad-hoc shape with a typed `IntegrationBase` hierarchy and a single `INTEGRATION_REGISTRY` so adding a new agent target (Cursor, Gemini CLI, Windsurf, Aider, Zed, Continue) is "subclass + register," not "fork three modules and hope every call site got updated."

## Problem

Today CLASI ships three platform modules. They share scaffolding (`_links.py`, `_markers.py`, `_rules.py`) but no shape: each module exposes its own ad-hoc `install`/`uninstall` plus per-platform helpers, and `init_command.py` switches on platform name. Result:

- Adding a fourth target means writing a fourth module from scratch and editing every call site that enumerates the existing three.
- Per-platform behavior drift is invisible — there is no contract saying "every platform must return its installed-file manifest" or "every platform must expose its command directory." Drift is found by reading code.
- The recent done TODO `codex-install-parity-and-misleading-se-pointer` was a symptom: a typed contract would have caught the parity gap at refactor time.

spec-kit ships 25+ integrations off a four-class hierarchy and a single dict. Adding Aider was three lines and a markdown body. That's the trajectory CLASI needs to be more than a Claude-with-Codex-bolted-on tool.

## Solution

1. **Define `IntegrationBase`** in `clasr/integration.py` as an abstract class with `@abstractmethod` on the contract methods (mirrors spec-kit, gives early failures for missing implementations).
2. **Three intermediate classes** for shared rendering: `MarkdownIntegration`, `TomlIntegration`, `SkillsIntegration`.
3. **Single `INTEGRATION_REGISTRY: dict[str, type[IntegrationBase]]`** in `clasr/registry.py`. `detect()` walks the target dir and returns every integration whose `detect_files` are present; replaces today's hand-rolled `platforms/detect.py`.
4. **Convert ClaudeIntegration first**, then Codex, then Copilot. Existing tests stay green; `init_command.py`'s platform-name switch collapses to a registry lookup.
5. **Add CursorIntegration as the smoke test** — `.cursor/rules/` + `.mdc` extension is a small enough delta from Claude to fit the markdown shape; if it doesn't, the contract is wrong and we learn early.
6. **Contract test** parametrized over `INTEGRATION_REGISTRY.values()` runs install/uninstall/manifest-roundtrip/marker-blocks against every registered platform.
7. **`clasr platforms list` CLI subcommand** prints `INTEGRATION_REGISTRY.keys()`.

## Success Criteria

- `clasr/integration.py` defines `IntegrationBase` (ABC) + the three intermediate classes.
- `clasr/registry.py` defines `INTEGRATION_REGISTRY` and `get()` / `detect()` helpers.
- `ClaudeIntegration`, `CodexIntegration`, `CopilotIntegration` are subclasses. All three pass the contract test.
- `init_command.py` no longer switches on platform name — it iterates the registry.
- `CursorIntegration` exists and passes the contract test without modifications to `IntegrationBase`. (If Cursor forces a contract change, revisit before adding more.)
- `clasr platforms list` works.
- mypy/pyright clean — missing methods are caught at type-check time.
- All existing platform tests green; the contract-test parametrization adds coverage rather than replacing it.

## Scope

### In Scope

- `IntegrationBase` ABC + three intermediate classes.
- Registry module + `detect()` + `get()`.
- Conversion of all three existing platforms.
- One new platform (Cursor) as smoke test.
- Contract test parametrized over the registry.
- `clasr platforms list` CLI.

### Out of Scope

- Gemini CLI, Windsurf, Aider, Zed, Continue — defer; demand-driven after Cursor proves the abstraction.
- Per-platform health checks ("is the user's `.claude/settings.json` well-formed").
- Plugin auto-discovery via `entry_points` — registry is a literal dict for v1.
- Renaming `clasr` to anything else (recurring question; parking it).
- Settings-file merge generalization — each platform owns its merge method for v1; revisit if a fourth platform brings a divergent settings shape.
- Free-function vs base-class for `write_marker_blocks` — design choice during ticketing; recommend free function with `companion_files` config (nothing platform-specific about marker logic itself).

## Test Strategy

- Contract test parametrized: install → uninstall → manifest round-trip → marker blocks placed correctly. One parametrization per registered platform.
- Type-check pass — `IntegrationBase` declared with `@abstractmethod`; missing methods produce mypy errors.
- Integration test: install all three platforms in one target, verify multi-tenant manifests; uninstall one, verify others unaffected.
- Cursor smoke: install Cursor into a target, verify `.cursor/rules/` files render with `.mdc` extension and correct frontmatter.

## Architecture impact

`clasr/platforms/` becomes a flat list of subclass files plus the registry. Every platform addition is mechanically the same: write a subclass, register it, ship. The capability matrix is enforced at the type level.

## Dependencies / sequencing notes

- **Hard dependency**: `clasr` step 11 (CLASI is a clasr consumer). Don't start this sprint until that step is green; refactoring an unstable interface is wasted work.
- After Sprint A — paths pinned at `.clasi/` before integration platforms reference them.
- Independent of Sprints B, C, D, F.

## Source TODO

- `integration-registry-base-class-and-registry.md` (as-is)
