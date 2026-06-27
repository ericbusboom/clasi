# clasr — Cross-Platform Agent-Config Renderer

`clasr` renders an `asr/` (agent-source-root) directory into platform-specific agent
configuration installs for Claude Code (`.claude/`), Codex (`.codex/`), and GitHub
Copilot (`.github/`). A single `asr/` tree holds your agents, rules, skills, and
platform passthrough files; `clasr install` projects them into each target platform
using per-provider manifests so multiple providers can coexist and be independently
uninstalled.

## asr/ Directory Layout

```
asr/
  AGENTS.md               # Global agent instructions (written as marker block)
  agents/                 # Platform-projected agent definition files (*.md)
  rules/                  # Platform-projected rule files (*.md)
  skills/                 # Skill directories, each containing SKILL.md
  claude/                 # Claude-specific passthrough files (settings.json, etc.)
  codex/                  # Codex-specific passthrough files
  copilot/                # Copilot-specific passthrough files (.vscode/mcp.json, etc.)
```

## Usage

```
clasr install --source ./asr --provider myprovider [--claude] [--codex] [--copilot]
clasr uninstall --provider myprovider [--claude] [--codex] [--copilot]
clasr platforms list
clasr --instructions
```

### clasr platforms list

Prints the IDs of all registered platforms, one per line, in sorted order. Example:

```
claude
codex
copilot
cursor
```

See `clasr --help` and `clasr SCHEMA.md` for the union frontmatter format.
