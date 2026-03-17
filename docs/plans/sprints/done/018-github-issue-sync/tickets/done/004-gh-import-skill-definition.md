---
id: '004'
title: gh-import skill definition
status: done
use-cases:
- SUC-001
depends-on:
- '001'
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# gh-import skill definition

## Description

Create the `gh-import` skill definition that instructs agents to fetch
GitHub issues and create CLASI TODOs from them.

### Implementation

Create `claude_agent_skills/content/skills/gh-import.md` with:

- **Name**: gh-import
- **Description**: Import GitHub issues as CLASI TODOs with issue
  reference tracking

- **Process**:
  1. Parse arguments — optional repo, optional label filter
  2. Verify `gh` access using `list_github_issues` with `limit: 1`
  3. If access fails, report error with remediation steps and stop
  4. Fetch open issues via `list_github_issues`
  5. **Bulk import gate**: If >5 issues returned, present the list to
     the user and ask them to:
     - Confirm importing all
     - Select specific issues by number
     - Filter by label
     - Cancel
  6. For each selected issue, create a TODO file in `docs/plans/todo/`:
     - Frontmatter: `status: pending`, `github-issue: "owner/repo#N"`
     - Heading: issue title
     - Body: issue body (trimmed if very long)
  7. Confirm what was imported (count, issue numbers, TODO filenames)

- **Example usage**:
  ```
  /se gh-import
  /se gh-import ericbusboom/other-repo
  /se gh-import --labels bug
  ```

Also update the `/se` dispatcher skill
(`claude_agent_skills/content/skills/se.md`) to include `gh-import`
in its command table.

## Acceptance Criteria

- [ ] Skill file exists at `content/skills/gh-import.md`
- [ ] Skill includes `gh` access verification step
- [ ] Skill includes >5 issue gate with user options
- [ ] Skill creates TODOs with `github-issue` frontmatter field
- [ ] `/se` dispatcher updated with `gh-import` command

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_process_tools.py`
  (skill listing tests)
- **New tests to write**: None — skill definitions are static markdown,
  tested via `list_skills` coverage
- **Verification command**: `uv run pytest`
