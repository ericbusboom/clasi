---
id: "004"
title: "Create path-scoped rules and init integration"
status: todo
use-cases: [SUC-001, SUC-003]
depends-on: []
---

# Create path-scoped rules and init integration

## Description

Create four `.claude/rules/` files and update `init_command.py` to
install them.

### Rules to create

1. `clasi-artifacts.md` — paths: `docs/clasi/**`
2. `source-code.md` — paths: `claude_agent_skills/**`, `tests/**`
3. `todo-dir.md` — paths: `docs/clasi/todo/**`
4. `git-commits.md` — paths: `**/*.py`, `**/*.md`

See pc-architecture.md § "Path-Scoped Rules" for content of each rule.

### Init changes

Add `_create_rules()` to `init_command.py`:
- Creates `.claude/rules/` directory
- Writes each rule file
- Idempotent — compares content, skips unchanged
- Preserves custom rules the developer has added
- Called from `run_init()` after hooks installation

## Acceptance Criteria

- [ ] Four rule files created with correct paths frontmatter
- [ ] Rules are short (3-5 sentences each)
- [ ] `clasi init` creates rules (new function in init_command.py)
- [ ] Re-running init is idempotent
- [ ] Custom rules in `.claude/rules/` are preserved
- [ ] Unit tests for rules creation and idempotency

## Testing

- **Existing tests to run**: `tests/unit/test_init_command.py`
- **New tests to write**: test rules creation, idempotency, preservation
- **Verification command**: `uv run pytest`
