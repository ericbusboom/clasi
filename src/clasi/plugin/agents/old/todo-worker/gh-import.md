---
name: gh-import
description: Import GitHub issues as CLASI TODOs with issue reference tracking
---

# GitHub Import Skill

This skill fetches open issues from a GitHub repository and creates
CLASI TODO files from them, with `github-issue` references for lifecycle
tracking.

## Process

1. **Parse arguments**: Extract optional repo name and label filter from
   the user's input. If no repo specified, use the current repository.

2. **Verify access**: Call `list_github_issues` with `limit: 1` to check
   `gh` CLI access. If it fails, report the error message to the user
   (it includes remediation steps like `gh auth login`) and stop.

3. **Fetch issues**: Call `list_github_issues` with the full parameters
   (repo, labels, state "open", limit 30).

4. **Bulk import gate**: If more than 5 issues are returned:
   - Present the list to the user (number, title, labels for each)
   - Ask the user to choose:
     - "Import all N issues"
     - "Select specific issues" (user provides issue numbers)
     - "Filter by label" (user provides a label, re-fetch)
     - "Cancel"
   - Do not proceed without user confirmation.

   If 5 or fewer issues, proceed directly.

5. **Create TODOs**: For each selected issue, create a TODO file in
   `docs/clasi/todo/` with:
   - Filename: slugified issue title (e.g., `fix-login-bug.md`)
   - YAML frontmatter:
     ```yaml
     status: pending
     github-issue: "owner/repo#N"
     ```
   - Heading: issue title
   - Body: issue body (truncated to first 2000 chars if very long)
   - Source line: `> Imported from [owner/repo#N](url)`

6. **Confirm**: Report to the user:
   - How many TODOs were created
   - List of issue numbers and corresponding TODO filenames
   - Any issues that were skipped or failed

## Example Usage

```
/se gh-import
/se gh-import ericbusboom/other-repo
/se gh-import --labels bug
/se gh-import ericbusboom/other-repo --labels "bug,enhancement"
```

## Notes

- The `github-issue` field uses the format `owner/repo#N` for
  unambiguous cross-repo references.
- When these TODOs are later consumed by a sprint, the `github-issue`
  field should be carried forward to tickets and the sprint doc's
  `## GitHub Issues` section.
- Issues are closed automatically when the sprint containing them is
  closed (see close-sprint skill).
