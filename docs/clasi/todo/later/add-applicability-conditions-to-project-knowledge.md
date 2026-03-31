---
status: pending
---

# Add applicability conditions to project-knowledge skill

The project-knowledge skill should prompt agents to record the conditions
under which the captured knowledge applies. Much of the knowledge
discovered during debugging is situational — it may depend on a specific
library version, OS, configuration, or architectural context. Without
noting those conditions, future agents risk applying old knowledge to
new situations where it doesn't hold.

## Proposed changes

- Add an **Applicability** section to the knowledge file format, between
  "Why It Works" and "Future Guidance". This section should describe:
  - What conditions must be true for this knowledge to apply (e.g.,
    specific versions, platforms, configurations, architectural patterns).
  - Known situations where this knowledge does NOT apply or where the
    fix would be different.
- Update the "Gather context" step in the process to include identifying
  the scope/conditions of applicability.
- Consider adding an `applies-when` or `conditions` field to the YAML
  frontmatter for machine-searchable filtering (e.g.,
  `conditions: [python>=3.12, macOS, MCP-server]`).
