<!-- CLASI:START -->
# CLASI Software Engineering Process

This project uses the CLASI SE process. Read `.github/agents/team-lead.agent.md` at session start and follow the team-lead role definition.

## Global Rules

### MCP Server Required

This project uses the CLASI MCP server. Before doing ANY work:

1. **Check for the OOP override first.** If the file `docs/clasi/oop`
   exists in the project root, ignore CLASI entirely for this session:
   skip MCP verification, skip all CLASI process gates (sprints,
   tickets, TODOs, artifact rules), and proceed with the user's
   request as you would in any non-CLASI repo. Do not call
   `get_version()` or any other CLASI MCP tool. The stakeholder has
   explicitly opted out for this checkout.
2. Otherwise, call `get_version()` to verify the MCP server is running.
3. If the call fails, STOP. Do not proceed. Tell the stakeholder:
   "The CLASI MCP server is not available. Check .mcp.json and
   restart the session, or create `docs/clasi/oop` to bypass CLASI
   for this session."
4. Do NOT create sprint directories, tickets, TODOs, or planning
   artifacts manually. Do NOT improvise workarounds. All SE process
   operations require the MCP server.

### Git Commits

Before committing, verify:
1. All tests pass (run the project's test suite).
2. If on a sprint branch, the sprint has an execution lock.
3. Commit message references the ticket ID if working on a ticket.

After committing substantive changes, run `clasi version bump` to
advance the version, then commit that change (`chore: bump version`).
Tools are installed editable, so the version is how sessions tell
which code is live — bump per commit, not just at sprint close.
Skip the manual bump right before `close_sprint` (it bumps + tags).

See `instructions/git-workflow` for full rules.

<!-- CLASI:END -->
