---
name: close-sprint
description: Validates and closes a completed sprint — verifies tickets, merges branch, archives sprint document
---

# Close Sprint Skill

This skill closes a completed sprint using the `close_sprint` MCP tool,
which handles the full lifecycle: pre-condition verification with
self-repair, test run, archive, state DB update, version bump, git
merge, push tags, and branch deletion.

## Agent Used

**project-manager**

## Inputs

- Active sprint directory in `docs/clasi/sprints/NNN-slug/`
- All tickets for this sprint should be `done`

## Process

1. **Confirm with stakeholder**: Present a summary of the sprint —
   list the completed tickets and key changes. Ask whether to proceed:
   - "Close sprint and merge to main" (recommended)
   - "Review completed work first"

   If the stakeholder chooses to review, present the full sprint details
   and stop. Otherwise proceed with closing.

2. **Call close_sprint**: Invoke the `close_sprint` MCP tool with the
   full parameter set:
   ```
   close_sprint(
       sprint_id="NNN",
       branch_name="sprint/NNN-slug",
       main_branch="master",
       push_tags=True,
       delete_branch=True,
   )
   ```

   The tool handles all lifecycle steps internally:
   - Pre-condition verification with self-repair (tickets in done/,
     TODOs resolved, state DB in sync, execution lock held)
   - Run `uv run pytest` to verify tests pass
   - Archive sprint directory to `sprints/done/`
   - Update state DB phase to `done`, release execution lock
   - Version bump and create git tag
   - `git checkout master && git merge --no-ff sprint/NNN-slug`
   - `git push --tags`
   - `git branch -d sprint/NNN-slug`

   Each step is idempotent — retrying after a failure skips
   already-completed steps.

3. **Report result**: Parse the structured JSON response.

   **On success** (`status: "success"`): Report the completed sprint
   summary including version tag, merged branch, and any self-repairs
   that were performed.

   **On error** (`status: "error"`): Report the specific blocker:
   - Which step failed (`error.step`)
   - What went wrong (`error.message`)
   - What the agent or stakeholder should do (`error.recovery.instruction`)
   - Which files can be edited to fix it (`error.recovery.allowed_paths`)

   After the blocker is resolved, call `close_sprint` again — it will
   resume from the failure point.

## Output

- Sprint branch merged to main and deleted
- Sprint document moved to `docs/clasi/sprints/done/`
- State database phase set to `done`, execution lock released
- Sprint completion summary reported to stakeholder
