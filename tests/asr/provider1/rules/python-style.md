---
description: Python code style guidance.
claude:
  paths: ["**/*.py"]
copilot:
  applyTo: "**/*.py"
codex: {}
---

When editing Python:

- Run `ruff check` and `ruff format` before committing.
- Prefer pathlib over os.path.
- Type-hint public functions.
- Don't add docstrings that just restate the function name.
