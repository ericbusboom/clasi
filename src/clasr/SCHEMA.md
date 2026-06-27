# clasr Union Frontmatter Schema

Agent and rule files in `asr/agents/` and `asr/rules/` may carry *union frontmatter*
that includes keys for all platforms in a single YAML block. When `clasr install`
renders a file for a specific platform, it projects the frontmatter to include only the
shared keys plus that platform's nested keys, dropping all other platform sections.

## Example

```yaml
---
name: code-review
description: Review a pull request
claude:
  tools: [Read, Grep, Bash]
copilot:
  applyTo: "**/*.ts"
codex: {}
---
```

## Projection Rules

1. All top-level keys that are NOT platform names (`claude`, `codex`, `copilot`) are
   treated as *shared* keys and included in every projected output.
2. The target platform's nested dict (e.g. `claude: {...}`) is extracted and merged into
   the shared keys. Platform-specific keys override shared keys with the same name.
3. All other platform keys are dropped.

Full specification will be expanded in a later sprint.
