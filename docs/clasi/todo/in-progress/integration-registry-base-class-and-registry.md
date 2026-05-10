---
status: in-progress
sprint: '021'
tickets:
- 021-001
---

# Integration registry — base class + registry, not three ad-hoc modules

Replace `clasi/platforms/{claude,codex,copilot}.py` with a typed
`IntegrationBase` hierarchy and a single `INTEGRATION_REGISTRY` so
adding a new agent target (Cursor, Gemini, Windsurf, Aider, Zed,
Continue, …) is "subclass + register," not "fork three modules and
hope you covered every call site."

## Why we cared

Today CLASI ships three platform modules. They share scaffolding
(`_links.py`, `_markers.py`, `_rules.py`) but no shape: each module
exposes its own `install(target, mcp_config) -> None` plus
ad-hoc helpers, and `init_command.py` switches on platform name to
call the right one. The result:

- Adding a fourth target (e.g. Cursor, Gemini CLI) means writing a
  fourth module from scratch and editing every call site that
  enumerates the existing three.
- Per-platform behaviour drift is invisible. There is no contract
  saying "every platform must return its installed-file manifest"
  or "every platform must expose its command directory." Whether a
  feature exists for Codex but not Copilot is found by reading code.
- The Codex install has parity gaps with the Claude install (a
  recent done TODO: `codex-install-parity-and-misleading-se-pointer`).
  A typed contract would have caught this at refactor time.

spec-kit ships 25+ integrations off a four-class hierarchy
(`IntegrationBase`, `MarkdownIntegration`, `TomlIntegration`,
`SkillsIntegration`) and a single `INTEGRATION_REGISTRY` dict. Adding
Aider was three lines and a markdown body. That's the trajectory
CLASI needs if it wants to be more than a Claude-with-Codex-bolted-on
tool.

## Relationship to the in-progress clasr work

This TODO is **not** parallel to clasr (sprint 014). clasr is the
file-rendering engine: union frontmatter in, per-platform files out,
manifests, marker blocks, symlink-vs-copy decisions. It already
proposes a `clasr/platforms/{claude,codex,copilot}.py` layout.

The integration-registry pattern lives **inside clasr**. clasr's
`platforms/` modules become subclasses of an `IntegrationBase`
defined in `clasr/integration.py`. The registry pattern is what
turns clasr from "we have three platform modules" into "we have a
plug-in surface for new platforms" — which is the explicit
"out of scope (for the first cut)" list in the clasr TODO ("Cursor
`.mdc` rendering — add later as another platform module").

So: clasr lands the engine; this TODO lands the abstraction that
lets the engine grow past three platforms without churn. Sequence
this **after** the clasr migration step (clasr step 11) is green,
not in parallel — refactoring an unstable interface is wasted
work.

## Proposed shape

```python
# clasr/integration.py

class IntegrationBase:
    """Contract every clasr platform must satisfy."""

    # --- identity ---
    id: str                              # "claude", "codex", "copilot"
    display_name: str                    # "Claude Code"
    detect_files: list[str]              # files whose presence implies
                                         # "this platform is installed in
                                         # the target repo"

    # --- where files go ---
    target_root: Path                    # ".claude" / ".codex" / ".github"
    command_dir: Path | None             # ".claude/commands" or None
    skill_dir: Path | None
    agent_dir: Path | None
    rule_dir: Path | None
    settings_file: Path | None           # ".claude/settings.json"

    # --- format details ---
    command_format: Literal["md", "toml", "yaml"]
    frontmatter_dialect: Literal["yaml", "toml", "none"]
    invoke_separator: str                # "/" for Claude slash commands;
                                         # ":" for some others
    companion_files: list[str]           # AGENTS.md, CLAUDE.md, etc.

    # --- behaviour ---
    def render_agent(self, source: AgentSource) -> RenderedFile: ...
    def render_skill(self, source: SkillSource) -> RenderedFile: ...
    def render_rule(self, source: RuleSource) -> RenderedFile: ...
    def write_marker_blocks(self, target: Path, body: str,
                            provider: str) -> list[ManifestEntry]: ...
    def install(self, target: Path, source: AsrSource,
                provider: str) -> Manifest: ...
    def uninstall(self, target: Path, provider: str) -> None: ...
```

Three intermediate classes carry common rendering logic:

```python
class MarkdownIntegration(IntegrationBase):
    """Platforms whose commands are .md with YAML frontmatter
    (Claude, Cursor, Continue, Aider)."""

class TomlIntegration(IntegrationBase):
    """Platforms whose commands are .toml fragments
    (Codex, possibly Copilot's mcp.json adjacent)."""

class SkillsIntegration(IntegrationBase):
    """Platforms with a SKILL.md convention
    (Claude Code skills; future: Gemini if/when they ship a skill
    spec)."""
```

A single registry:

```python
# clasr/registry.py

INTEGRATION_REGISTRY: dict[str, type[IntegrationBase]] = {
    "claude":   ClaudeIntegration,
    "codex":    CodexIntegration,
    "copilot":  CopilotIntegration,
    # additions land here, one line each:
    # "cursor":   CursorIntegration,
    # "gemini":   GeminiIntegration,
    # "windsurf": WindsurfIntegration,
    # "aider":    AiderIntegration,
}

def get(id: str) -> IntegrationBase: ...
def detect(target: Path) -> list[IntegrationBase]: ...
```

`detect()` walks the target dir and returns every integration whose
`detect_files` are present. That replaces today's hand-rolled
`platforms/detect.py`.

## What this enables that today's shape doesn't

- **One-line platform additions.** Cursor, Gemini, Windsurf, Aider,
  Continue, Zed each become a subclass file plus a registry line.
- **Capability matrix in code.** `IntegrationBase` declares the
  required interface; mypy/pyright flag the platform that forgets
  to implement `render_agent`. Today's drift becomes a type error.
- **Test scaffolding for free.** A single
  `test_integration_contract.py` parametrised over
  `INTEGRATION_REGISTRY.values()` runs the same battery of "install,
  uninstall, manifest round-trips, marker blocks placed correctly"
  tests against every platform.
- **Community presets.** A future `clasr presets install <name>`
  command can ship third-party integration subclasses without forking
  CLASI.

## Migration sequence

Pre-req: clasr sprint 014 work is landed and CLASI is a clasr
consumer (clasr step 11 done). Don't start until then.

1. **Define `IntegrationBase`** plus the three intermediate classes
   in `clasr/integration.py`. No subclasses converted yet. Add the
   contract test file with no parametrisation.
2. **Convert `ClaudeIntegration`.** Move `clasr/platforms/claude.py`
   to subclass `MarkdownIntegration`/`SkillsIntegration`. Existing
   tests stay green. `init_command.py` keeps calling the same entry
   point but now via `INTEGRATION_REGISTRY["claude"]`.
3. **Convert `CodexIntegration`.** Same drill. Now the contract
   test parametrises over two platforms.
4. **Convert `CopilotIntegration`.** All three through the registry.
   The platform-name switch in `init_command.py` collapses to a loop
   over `--claude/--codex/--copilot` flags resolving to registry
   entries.
5. **Cursor as the smoke test.** Add `CursorIntegration` to prove
   "subclass + register" actually works. Cursor's `.cursor/rules/`
   directory + `.mdc` extension is a small enough delta from Claude
   to fit the markdown shape; if it doesn't, the contract is wrong
   and we learn that early.
6. **Gemini, Windsurf, Aider** — defer to follow-ons. The point of
   step 5 is validating the abstraction; steps after that are
   demand-driven.

## Validation

- Type-check passes with `IntegrationBase` declared as
  `typing.Protocol` or abstract class with `@abstractmethod` on the
  contract methods.
- Contract test runs the full install/uninstall round trip for every
  registered platform.
- `clasr platforms list` CLI subcommand prints
  `INTEGRATION_REGISTRY.keys()`.
- Adding Cursor (step 5) passes the contract test without changes
  to the contract itself. If the contract has to change to fit
  Cursor, revisit before adding more.

## Open questions

- **`Protocol` vs `ABC`.** `Protocol` is more Pythonic for a
  contract; `ABC` gives runtime errors for missing methods. spec-kit
  uses concrete base classes with `NotImplementedError`. Suggest:
  `ABC` with `@abstractmethod`, mirrors spec-kit, gives early
  failures, and there's no inheritance constraint cost we'd pay.
- **What lives on the base vs intermediate classes.**
  `render_skill` is identical for any markdown-based platform;
  `render_agent` diverges (Claude wants YAML frontmatter, Codex
  wants TOML). Avoid stuffing logic into the base; let each
  intermediate own its rendering.
- **Per-platform settings files.** Claude has
  `.claude/settings.json` and `settings.local.json`; Codex has
  `config.toml`; Copilot has `.vscode/mcp.json`. These don't
  generalise cleanly. Either each platform owns its own
  settings-merge method (current), or we model
  `settings_file: Path` plus a `merge_settings(file, additions)`
  hook. Suggest: own-method for v1; revisit if a fourth platform
  adds a fourth divergent shape.
- **Where does AGENTS.md / CLAUDE.md handling live?** The clasr
  TODO already specifies marker-block writes. Confirm
  `write_marker_blocks` lives on `IntegrationBase` (every platform
  writes some companion file) vs being a free function with
  per-platform `companion_files` config. Suggest: free function +
  config; nothing platform-specific about the marker logic itself.

## Out of scope

- Per-platform validation of *what's installed* (e.g. checking the
  user's `.claude/settings.json` is well-formed). That's a separate
  health-check feature.
- Integration auto-discovery from a plugin directory. Today's
  registry is a literal dict in source; future is `entry_points` in
  `pyproject.toml`. Defer.
- Renaming `clasr` to anything (this question keeps coming up;
  parking it).

## Origin

Comparative analysis of CLASI vs github/spec-kit vs Fission-AI/
OpenSpec, 2026-05-07
(`clasi-spec-kit-openspec-analysis.md`). Suggestion #2, ranked
second: "if two changes: schema-driven workflow + integration-
registry refactor — that gets CLASI to spec-kit-level breadth on
the install surface."

The analysis specifically called out the four base-class fields to
copy: `command_dir`, `command_format`, `companion_files`,
`invoke_separator`. Those names are preserved in the
`IntegrationBase` sketch above.
