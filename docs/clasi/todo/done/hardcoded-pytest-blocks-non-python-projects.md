---
status: done
sprint: '007'
tickets:
- '002'
- '003'
---

# Hardcoded pytest in close_sprint blocks non-Python projects

`close_sprint` in `artifact_tools.py` hardcodes `uv run pytest` as the
test command. Non-Python projects (Java, JS, etc.) that have `uv`
installed will get spurious test failures when closing sprints.

The `FileNotFoundError` fallback only covers the case where `uv` is
missing — not where `uv` exists but `pytest` is irrelevant.

## Proposed fix

1. Add a `test_command` parameter to `close_sprint` (default: `None`
   means `uv run pytest`; empty string `""` means skip tests).
2. Update `_close_sprint_full` to use the parameter.
3. Update close-sprint skill docs.
4. Make rules installed by `clasi init` language-neutral (remove
   hardcoded `uv run pytest` references from `source-code.md` and
   `git-commits.md` rules).
5. Add `.gitignore` to `docs/clasi/log/` during `clasi init` so logs
   don't get committed in any project type.
