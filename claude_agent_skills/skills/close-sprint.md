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

- Active sprint directory in `docs/plans/sprints/NNN-slug/`
- All tickets for this sprint should be `done`

## Process

1. **Identify the sprint**: Read active sprint directories from
   `docs/plans/sprints/`. If multiple sprints are active, select from those that
   have all of their tickets done, then select the one with the lowest number. 

2. **Verify all tickets are done**: Read each ticket in the sprint's
   `tickets/` directory. Every ticket must:
   - Have status `done` in its YAML frontmatter
   - Be located in the sprint's `tickets/done/` directory
   - Satisfy the Definition of Done (see SE instructions)

   If any ticket is not done, report which tickets remain and stop.

3. **Confirm with stakeholder**: Present a summary of the sprint —
   list the completed tickets and key changes. Use `AskUserQuestion`:
   - "Close sprint and merge to main" (recommended)
   - "Review completed work first"

   If the stakeholder chooses to review, present the full sprint details
   and stop. Otherwise proceed with closing.

4. **Advance to closing phase**: Call `advance_sprint_phase` to move
   from `executing` to `closing`.

5. **Run final validation**: Ensure tests pass, no uncommitted changes
   exist on the sprint branch.

6. **Merge sprint branch**: Merge `sprint/NNN-slug` into main:
   ```
   git checkout main
   git merge sprint/NNN-slug
   ```
   If there are merge conflicts, resolve them or escalate to the
   stakeholder.

7. **Version the architecture document**: Copy the sprint's
   `architecture.md` to the project architecture directory:
   ```
   cp docs/plans/sprints/NNN-slug/architecture.md \
      docs/plans/architecture/architecture-NNN.md
   ```
   Move any previous architecture versions to `docs/plans/architecture/done/`:
   ```
   mkdir -p docs/plans/architecture/done
   mv docs/plans/architecture/architecture-*.md docs/plans/architecture/done/
   cp docs/plans/sprints/NNN-slug/architecture.md \
      docs/plans/architecture/architecture-NNN.md
   ```
   (Move first, then copy the new one, so only the latest is at the top level.)

8. **Close the sprint**: Call the `close_sprint` MCP tool. This
   atomically:
   - Updates the sprint document status to `done`
   - Moves the sprint directory to `docs/plans/sprints/done/NNN-slug/`
   - Advances the state database phase to `done`
   - Releases the execution lock

9. **Commit the archive**: The `close_sprint` tool moves files and bumps
   the version in the project's version file (e.g., `pyproject.toml` or
   `package.json`) but does not commit. Run `git add` for the moved sprint
   directory and the version file, then commit with a message like
   `chore: close sprint NNN — archive to done, tag vX.Y.Z`.

10. **Push tags**: `git push` does not push tags by default. Run
    `git push --tags` to ensure the version tag created by `tag_version`
    is pushed to the remote.

11. **Delete sprint branch**: Run `git branch -d sprint/NNN-slug`.

12. **Report completion**: Summarize what was accomplished in the sprint —
    list of completed tickets, key changes, any notes for follow-up.

## Output

- Sprint branch merged to main and deleted
- Sprint document moved to `docs/plans/sprints/done/`
- State database phase set to `done`, execution lock released
- Sprint completion summary reported to stakeholder
