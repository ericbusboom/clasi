# clasr

`clasr` is a cross-platform agent-config renderer that installs an `asr/`
(agent-source-root) directory into Claude Code, Codex, GitHub Copilot, and Cursor
platform layouts. It supports multiple independent providers in the same target
directory via per-provider named marker blocks and JSON-manifests, enabling clean
coexistence and independent uninstall. Run `clasr --instructions` for usage guidance.

## Architecture: IntegrationBase hierarchy

Every platform is a subclass of `IntegrationBase` (defined in `clasr/integration.py`).
Three intermediate classes provide shared rendering logic:

- `MarkdownIntegration` — platforms that render agent files as YAML-frontmatter `.md`
  files (Claude, Cursor).
- `TomlIntegration` — platforms that use TOML-format agents and route scoped/unscoped
  rules to nested `AGENTS.md` files (Codex).
- `SkillsIntegration` — platforms that install SKILL.md files via symlinks or copies
  (Claude, Codex, Copilot).

Individual platform classes may inherit from more than one intermediate class (e.g.
`ClaudeIntegration` extends both `MarkdownIntegration` and `SkillsIntegration`).

## INTEGRATION_REGISTRY

`clasr.registry.INTEGRATION_REGISTRY` is the single source of truth for all
registered platforms:

```python
from clasr.registry import INTEGRATION_REGISTRY

# dict[str, type[IntegrationBase]]
# Keys: "claude", "codex", "copilot", "cursor"
```

### Adding a new platform

1. Create `clasr/platforms/<name>.py` with a class that subclasses `IntegrationBase`
   (and any applicable intermediate classes).
2. Set all class-level fields: `id`, `display_name`, `detect_files`, `target_root`,
   `companion_files`, etc.
3. Implement all abstract methods: `install`, `uninstall`, `render_agent`,
   `render_skill`, `render_rule`.
4. Register the class in `clasr/registry.py`:
   ```python
   INTEGRATION_REGISTRY["myplatform"] = MyPlatformIntegration
   ```
5. Add tests to `tests/clasr/` — the parametrized contract test in
   `test_integration_contract.py` will automatically pick up your new platform.

### Helper functions

```python
from clasr.registry import get, detect

# Get a fresh integration instance by id
integration = get("claude")

# Detect installed integrations in a project
integrations = detect(Path("/path/to/project"))  # returns list[IntegrationBase]
```
