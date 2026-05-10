---
sprint: '021'
status: done
---

# Use Cases — Sprint 021: Integration registry: base class and registry for clasr platforms

## SUC-001: Define a typed IntegrationBase contract

**Actor**: clasr developer (library author)
**Goal**: Establish a single abstract base class that every clasr platform module must satisfy, so that capability drift between platforms is caught by the type checker rather than discovered by reading code.

**Preconditions**: clasr sprint 014 is landed; the three existing platform modules (`claude.py`, `codex.py`, `copilot.py`) exist as standalone functions.

**Main flow**:
1. Developer defines `IntegrationBase` in `clasr/integration.py` as an ABC with `@abstractmethod` on all contract methods (`render_agent`, `render_skill`, `render_rule`, `write_marker_blocks`, `install`, `uninstall`).
2. Developer declares all required class-level fields (`id`, `display_name`, `detect_files`, `target_root`, `command_dir`, `skill_dir`, `agent_dir`, `rule_dir`, `settings_file`, `command_format`, `frontmatter_dialect`, `invoke_separator`, `companion_files`).
3. Three intermediate classes (`MarkdownIntegration`, `TomlIntegration`, `SkillsIntegration`) are defined as concrete subclasses carrying shared rendering logic.
4. mypy/pyright report no violations when the contract is imported; any platform that omits a required method produces a type error at class-definition time.

**Outcome**: The contract exists in source; no platform is wired to it yet.

---

## SUC-002: Parametrize contract tests over the integration registry

**Actor**: CI / developer running tests
**Goal**: A single test file (`test_integration_contract.py`) automatically runs the install/uninstall round-trip for every platform registered in `INTEGRATION_REGISTRY`, so a new platform is automatically tested without editing the test file.

**Preconditions**: `INTEGRATION_REGISTRY` exists in `clasr/registry.py`; at least one integration is registered.

**Main flow**:
1. `pytest.mark.parametrize` reads `INTEGRATION_REGISTRY.values()` at collection time.
2. For each integration class, the test fixture creates a temporary source and target directory, instantiates the integration, calls `install()`, verifies the manifest is present and all declared files exist, calls `uninstall()`, verifies the manifest and installed files are gone.
3. Adding a new integration class to the registry automatically adds a new parametrized test run with no change to the test file.

**Outcome**: Contract test suite covers all registered platforms; adding Cursor or any future platform does not require editing the test.

---

## SUC-003: Convert ClaudeIntegration to a typed subclass

**Actor**: clasr developer
**Goal**: `clasr/platforms/claude.py` is refactored to expose a `ClaudeIntegration` class that subclasses `MarkdownIntegration` and `SkillsIntegration`, satisfying the `IntegrationBase` contract with no behavioral change.

**Preconditions**: `IntegrationBase`, `MarkdownIntegration`, and `SkillsIntegration` are defined; existing Claude unit tests pass.

**Main flow**:
1. Developer moves the install/uninstall logic from module-level functions into `ClaudeIntegration.install()` and `ClaudeIntegration.uninstall()`.
2. Class-level fields (`id = "claude"`, `display_name = "Claude Code"`, `detect_files`, `target_root`, etc.) are declared.
3. mypy passes with no `IntegrationBase` violations.
4. Existing tests (`test_platform_claude.py`) remain green without modification.

**Outcome**: Claude is the first platform through the registry pattern; its behavior is unchanged.

---

## SUC-004: Convert CodexIntegration to a typed subclass

**Actor**: clasr developer
**Goal**: `clasr/platforms/codex.py` is refactored to expose a `CodexIntegration` class satisfying the contract, matching the Claude conversion pattern.

**Preconditions**: `ClaudeIntegration` conversion complete; `CodexIntegration` test suite passes.

**Main flow**:
1. Codex-specific rendering logic (scoped rules to nested AGENTS.md, TOML format decisions) moves into class methods.
2. `command_format = "toml"` and other Codex-specific fields are declared.
3. mypy and existing tests pass.
4. Contract test parametrization now covers two platforms.

**Outcome**: Codex is the second platform through the registry; all existing behaviour is preserved.

---

## SUC-005: Convert CopilotIntegration to a typed subclass

**Actor**: clasr developer
**Goal**: `clasr/platforms/copilot.py` is refactored to expose a `CopilotIntegration` class satisfying the contract.

**Preconditions**: `CodexIntegration` conversion complete.

**Main flow**:
1. Copilot-specific rendering (`.agent.md` suffix, `.instructions.md` suffix, `.github/copilot-instructions.md` marker block) moves into class methods.
2. All three platforms are now through the registry.
3. Existing tests pass.

**Outcome**: All three original platforms satisfy the typed contract; the migration sequence is complete.

---

## SUC-006: Expose INTEGRATION_REGISTRY with get() and detect() helpers

**Actor**: Application code (CLI, `init_command.py`, external consumers)
**Goal**: A single dict `INTEGRATION_REGISTRY` in `clasr/registry.py` maps platform IDs to integration classes. `get(id)` returns an instance; `detect(target)` returns all integrations whose `detect_files` are present in the target directory.

**Preconditions**: At least ClaudeIntegration is defined as a subclass.

**Main flow**:
1. `INTEGRATION_REGISTRY = {"claude": ClaudeIntegration, "codex": CodexIntegration, "copilot": CopilotIntegration}` is declared.
2. `get(id: str) -> IntegrationBase` raises `KeyError` for unknown IDs.
3. `detect(target: Path) -> list[IntegrationBase]` walks `detect_files` for each registered integration and returns instances for those whose files are present.
4. `clasr/platforms/detect.py` is replaced by `registry.detect()`.

**Outcome**: Any call site that previously switched on a platform name string can now resolve via `INTEGRATION_REGISTRY`.

---

## SUC-007: Wire init_command (CLI) to use registry

**Actor**: clasr CLI user (`clasr install`, `clasr uninstall`)
**Goal**: The CLI's platform-name switch collapses to a registry lookup. Adding `--cursor` to the CLI requires only adding `CursorIntegration` to the registry, not editing the install/uninstall dispatch logic.

**Preconditions**: All three conversions complete; `INTEGRATION_REGISTRY` populated.

**Main flow**:
1. `_cmd_install` and `_cmd_uninstall` in `cli.py` are updated to resolve platforms via `INTEGRATION_REGISTRY[name]` rather than importing each platform module by name.
2. The `--claude`, `--codex`, `--copilot` flags map to registry keys.
3. Existing install/uninstall CLI behaviour is unchanged.

**Outcome**: No platform-name switch remains in `cli.py`; registry is the sole dispatch mechanism.

---

## SUC-008: Add CursorIntegration as a smoke-test subclass

**Actor**: clasr developer validating the extension surface
**Goal**: Prove that "subclass + register" adds a new platform without changes to the contract, the registry helpers, or the contract test. If the contract must change to accommodate Cursor, the abstraction is wrong.

**Preconditions**: `INTEGRATION_REGISTRY` and the contract test are operational.

**Main flow**:
1. Developer writes `CursorIntegration` in `clasr/platforms/cursor.py`, subclassing `MarkdownIntegration`.
2. Cursor-specific fields: `id = "cursor"`, `target_root = Path(".cursor")`, `command_dir = Path(".cursor/rules")`, `command_format = "md"`, `detect_files = [".cursor/"]`.
3. `"cursor": CursorIntegration` is added to `INTEGRATION_REGISTRY`.
4. Contract test parametrization automatically picks up Cursor and runs the install/uninstall round-trip.
5. No changes required in the contract, registry helpers, CLI dispatch logic, or test file.

**Outcome**: Cursor passes the contract test; the abstraction is validated as genuinely extensible.

---

## SUC-009: clasr platforms list CLI subcommand

**Actor**: Developer or integrator inspecting an installation
**Goal**: `clasr platforms list` prints the IDs of all registered platforms to stdout, one per line, so tooling and users can discover what platforms clasr supports without reading source code.

**Preconditions**: `INTEGRATION_REGISTRY` is populated.

**Main flow**:
1. User runs `clasr platforms list`.
2. CLI iterates `INTEGRATION_REGISTRY.keys()` in sorted order and prints each ID.
3. Exit code is 0.
4. Example output: `claude`, `codex`, `copilot`, `cursor` (one per line).

**Outcome**: Platform discovery is a first-class CLI operation; no code reading required to enumerate supported targets.
