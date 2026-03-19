---
name: close-sprint
description: Validates and closes a completed sprint — verifies tickets, merges branch, archives sprint document
---

# Close Sprint Skill

This skill closes a completed sprint: verify all tickets are done, merge
the sprint branch, and archive the sprint document.

## Agent Used

**project-manager**

## Inputs

- Active sprint directory in `docs/clasi/sprints/NNN-slug/`
- All tickets for this sprint should be `done`

## Process

1. **Identify the sprint**: Read active sprint directories from
   `docs/clasi/sprints/`. If multiple sprints are active, select from those that
   have all of their tickets done, then select the one with the lowest number. 

2. **Verify all tickets are done**: Read each ticket in the sprint's
   `tickets/` directory. Every ticket must:
   - Have status `done` in its YAML frontmatter
   - Be located in the sprint's `tickets/done/` directory
   - Satisfy the Definition of Done (see SE instructions)

   If any ticket is not done, report which tickets remain and stop.

3. **Verify TODO completion**: Scan the sprint's done tickets for any
   with a `todo` frontmatter field. For each referenced TODO, verify
   it has been moved to `docs/clasi/todo/done/` (or `docs/plans/todo/done/`).
   If any claimed TODOs are still in the active TODO directory, report
   them — they should either be moved to done or explicitly deferred.

4. **Confirm with stakeholder**: Present a summary of the sprint —
   list the completed tickets and key changes. Use `AskUserQuestion`:
   - "Close sprint and merge to main" (recommended)
   - "Review completed work first"

   If the stakeholder chooses to review, present the full sprint details
   and stop. Otherwise proceed with closing.

5. **Advance to closing phase**: Call `advance_sprint_phase` to move
   from `executing` to `closing`.

6. **Run final validation**: Run `uv run pytest` (or the project's test
   command) and confirm **ALL tests pass** before proceeding. Also verify
   no uncommitted changes exist on the sprint branch. If tests fail,
   report the failures and stop. Do not merge a branch with failing tests.
   See `instructions/git-workflow.md` § Commit Timing for the rationale.

7. **Close linked GitHub issues**: Read the sprint doc's `## GitHub
   Issues` section. For each `owner/repo#N` reference listed:
   - Call the `close_github_issue` MCP tool with the repo and issue number.
   - If closing fails for any issue, log the failure but continue with
     the remaining issues and the sprint closure.
   - If no `## GitHub Issues` section exists or it is empty, skip this step.

8. **Merge sprint branch**: Merge `sprint/NNN-slug` into main:
   ```
   git checkout main
   git merge sprint/NNN-slug
   ```
   If there are merge conflicts, resolve them or escalate to the
   stakeholder.

9. **Version the architecture document**: Copy the sprint's
    `architecture.md` to the project architecture directory:
    ```
    cp docs/clasi/sprints/NNN-slug/architecture.md \
       docs/clasi/architecture/architecture-NNN.md
    ```
    Move any previous architecture versions to `docs/clasi/architecture/done/`:
    ```
    mkdir -p docs/clasi/architecture/done
    mv docs/clasi/architecture/architecture-*.md docs/clasi/architecture/done/
    cp docs/clasi/sprints/NNN-slug/architecture.md \
       docs/clasi/architecture/architecture-NNN.md
    ```
    (Move first, then copy the new one, so only the latest is at the top level.)

10. **Close the sprint**: Call the `close_sprint` MCP tool. This
    atomically:
    - Updates the sprint document status to `done`
    - Moves the sprint directory to `docs/clasi/sprints/done/NNN-slug/`
    - Advances the state database phase to `done`
    - Releases the execution lock

11. **Version update** (conditional): Check `docs/clasi/settings.yaml`
    for `version_trigger`. If set to `every_sprint` or `every_change`
    (default), run `clasi version bump` (or call `tag_version`). If
    set to `manual`, skip versioning — the developer manages it.

12. **Commit the archive**: Run `git add` for the moved sprint directory
    and the version file (if changed), then commit with a message like
    `chore: close sprint NNN — archive to done, tag vX.Y.Z`.

13. **Push tags**: If a version tag was created, run `git push --tags`.

14. **Delete sprint branch**: Run `git branch -d sprint/NNN-slug`.

15. **Report completion**: Summarize what was accomplished in the sprint —
    list of completed tickets, key changes, any notes for follow-up.
    Include a summary of which GitHub issues were closed (if any) and
    which TODOs were completed.

## Output

- Sprint branch merged to main and deleted
- Sprint document moved to `docs/clasi/sprints/done/`
- State database phase set to `done`, execution lock released
- Sprint completion summary reported to stakeholder
