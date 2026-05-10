---
id: '021'
title: 'Integration registry: base class and registry for clasr platforms'
status: done
branch: sprint/021-integration-registry-base-class-and-registry-for-clasr-platforms
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
- SUC-005
- SUC-006
- SUC-007
- SUC-008
- SUC-009
source-todos:
- integration-registry-base-class-and-registry.md
---

# Sprint 021: Integration registry: base class and registry for clasr platforms

## Goals

Replace clasr's three ad-hoc platform modules with a typed `IntegrationBase`
hierarchy and a single `INTEGRATION_REGISTRY` dict so that adding a new agent
target (Cursor, Gemini, Windsurf, Aider, etc.) is "subclass + register" rather
than "fork three modules and edit every call site." The refactor also establishes
a capability contract that mypy/pyright can check, and a single parametrised
contract test that runs the install/uninstall round-trip for every registered
platform automatically.

## Problem

clasr ships three platform modules (`claude.py`, `codex.py`, `copilot.py`).
They share utility helpers (`_links.py`, `_markers.py`, `_rules.py`) but no
enforced contract. Each module exposes its own `install()` with ad-hoc helpers,
and `init_command.py` uses a name-switch to call the right one.

Consequences:
- Adding a fourth platform means writing a new module from scratch and editing
  every call site that enumerates the existing three.
- Per-platform behavior drift is invisible. No contract enforces "every platform
  must return its installed-file manifest" or "every platform must expose its
  command directory."
- Parity gaps (e.g. Codex vs Claude install features) are found by reading code,
  not by type errors.

The TODO cites spec-kit's four-class hierarchy and `INTEGRATION_REGISTRY` as
the target shape: adding Aider there was three lines and a markdown body.

## Solution outline

- Define `IntegrationBase` (ABC with `@abstractmethod`) in `clasr/integration.py`.
  Contract fields: `id`, `display_name`, `detect_files`, `target_root`,
  `command_dir`, `skill_dir`, `agent_dir`, `rule_dir`, `settings_file`,
  `command_format`, `frontmatter_dialect`, `invoke_separator`,
  `companion_files`. Contract methods: `render_agent`, `render_skill`,
  `render_rule`, `write_marker_blocks`, `install`, `uninstall`.
- Three intermediate classes: `MarkdownIntegration`, `TomlIntegration`,
  `SkillsIntegration`, carrying shared rendering logic.
- `INTEGRATION_REGISTRY: dict[str, type[IntegrationBase]]` in `clasr/registry.py`.
  `get(id)` and `detect(target)` replace today's hand-rolled `platforms/detect.py`.
- Convert Claude, Codex, Copilot to subclasses, in order. `init_command.py`
  name-switch collapses to a registry lookup.
- Add `CursorIntegration` as the smoke test that "subclass + register" actually
  works for a new platform.
- `clasr platforms list` CLI subcommand prints `INTEGRATION_REGISTRY.keys()`.
- Parametrised contract test covering every registered platform.

## Success criteria

- `clasr/integration.py` defines `IntegrationBase` with full ABC contract.
- `clasr/registry.py` defines `INTEGRATION_REGISTRY` with all three existing
  platforms registered.
- Claude, Codex, and Copilot platform modules are subclasses; mypy/pyright
  pass with no `IntegrationBase` violations.
- Adding `CursorIntegration` passes the contract test without changes to the
  contract itself.
- `clasr platforms list` prints registered platform IDs.
- Single parametrised contract test (`test_integration_contract.py`) runs
  install/uninstall round-trip for every registered platform.
- `init_command.py` no longer contains a platform-name switch; it resolves via
  the registry.
- Existing test suite stays green through each conversion step.

## In Scope

- `clasr/integration.py`: `IntegrationBase` + three intermediate classes.
- `clasr/registry.py`: `INTEGRATION_REGISTRY`, `get()`, `detect()`.
- Converting `clasr/platforms/claude.py`, `codex.py`, `copilot.py` to subclasses.
- `clasr/platforms/detect.py`: replace with `registry.detect()`.
- `init_command.py`: replace name-switch with registry lookup.
- `CursorIntegration` smoke-test subclass.
- `clasr platforms list` CLI subcommand.
- `tests/unit/test_integration_contract.py`: parametrised contract test.

## Out of Scope

- Gemini, Windsurf, Aider, Zed integrations beyond Cursor (demand-driven,
  proven by Cursor smoke test).
- Integration auto-discovery via `entry_points` (future).
- Per-platform validation of installed file health.
- Renaming `clasr`.
- Settings-merge abstraction beyond "each platform owns its own method for v1."

## Dependencies and sequencing

- Hard dependency: clasr sprint 014 must be landed and CLASI must be a clasr
  consumer (clasr step 11 done). The source TODO is explicit: "Do not start
  until then." Refactoring an unstable interface is wasted work.
- Independent of sprint 017 (two-phase planning), 018 (exception protocol),
  019 (uninstall fix), 020 (schema-driven workflow), 022 (worktree process).
- Sprint 019 (uninstall fix) touches overlapping code in `clasr/merge.py`
  (or wherever `merge_json_files` lives). Coordinate to avoid merge conflicts
  if both are in flight simultaneously; otherwise run them in sequence with
  019 first (it's a bug fix, smaller surface).

## Source TODOs

- `docs/clasi/todo/integration-registry-base-class-and-registry.md`

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Define IntegrationBase ABC and three intermediate classes in clasr/integration.py | — |
| 002 | Scaffold parametrized contract test with empty registry placeholder | 001 |
| 003 | Convert ClaudeIntegration to IntegrationBase subclass with module-level shims | 001 |
| 004 | Convert CodexIntegration to IntegrationBase subclass with module-level shims | 001, 003 |
| 005 | Convert CopilotIntegration to IntegrationBase subclass with module-level shims | 001, 004 |
| 006 | Create INTEGRATION_REGISTRY in clasr/registry.py with get() and detect() helpers | 003, 004, 005 |
| 007 | Wire clasr/cli.py install and uninstall to use INTEGRATION_REGISTRY dispatch | 006 |
| 008 | Add CursorIntegration smoke-test subclass and register in INTEGRATION_REGISTRY | 006 |
| 009 | Add clasr platforms list CLI subcommand | 008 |
| 010 | Deprecate clasr/platforms/detect.py as a wrapper around registry.detect() | 006 |
| 011 | Remove module-level shims and confirm full registry dispatch end-to-end | 007, 009, 010 |
| 012 | Update tests for registry dispatch and run full test suite green | 011 |
