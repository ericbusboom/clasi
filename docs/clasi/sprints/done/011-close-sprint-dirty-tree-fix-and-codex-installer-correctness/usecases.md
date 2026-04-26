---
sprint: "011"
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Use Cases — Sprint 011

## Track A: close_sprint lifecycle fixes

---

### SUC-001: close_sprint succeeds when .clasi.db is git-tracked and dirty after db_update

- **Actor**: CLASI agent (or user) calling `close_sprint`
- **Preconditions**: Sprint is in `executing` phase; all tickets done; working tree is
  clean except for `docs/clasi/.clasi.db` written by earlier lifecycle steps.
- **Main Flow**:
  1. `close_sprint` runs precondition verification, tests, archive, db_update.
  2. `db_update` writes to `.clasi.db`, dirtying the working tree.
  3. The `version_bump` step stages and commits `.clasi.db` on the sprint branch,
     restoring a clean tree before rebase.
  4. The merge/rebase step proceeds with a clean tree and completes successfully.
  5. `close_sprint` returns `status: "ok"`.
- **Postconditions**: Sprint branch is merged into main; sprint is archived; working tree
  is clean.
- **Acceptance Criteria**:
  - [ ] `close_sprint` does not fail with "You have unstaged changes" when `.clasi.db`
        is git-tracked.
  - [ ] The committed `.clasi.db` state lands on the main branch after merge.

---

### SUC-002: Execution lock is released even when close_sprint merge fails

- **Actor**: CLASI agent calling `close_sprint` when merge encounters a runtime error
- **Preconditions**: Sprint has an execution lock; merge step raises `RuntimeError` or
  `MergeConflictError`.
- **Main Flow**:
  1. `close_sprint` begins the merge step.
  2. Merge fails (rebase error, conflict, or other git failure).
  3. The execution lock is released before `close_sprint` returns the error response.
  4. `close_sprint` returns `status: "error"` with merge step details.
- **Postconditions**: Lock is released; agent or user can retry without calling
  `release_execution_lock` manually.
- **Acceptance Criteria**:
  - [ ] After a simulated merge failure the lock is not held (verified by checking DB
        state).
  - [ ] The error response still includes the merge step details and remaining steps.

---

## Track B: Codex installer correctness

---

### SUC-003: clasi install --codex writes a hooks.json that Codex honors

- **Actor**: Developer running `clasi install --codex` in a project
- **Preconditions**: Project has no `.codex/hooks.json`, or has one with the old flat-object
  format.
- **Main Flow**:
  1. Developer runs `clasi install --codex`.
  2. Installer writes `.codex/hooks.json` with the correct wrapper structure:
     `{ "hooks": { "Stop": [ { "hooks": [ { "type": "command", "command": "clasi hook
     codex-plan-to-todo", "timeout": 30 } ] } ] } }`.
  3. If an existing hooks.json contains the old flat `{"command": "clasi", "args": [...]}` entry
     it is replaced (not duplicated) with the correct wrapper entry.
- **Postconditions**: `.codex/hooks.json` matches the Codex hooks spec; `codex-plan-to-todo`
  hook fires on Codex session stop.
- **Acceptance Criteria**:
  - [ ] `json.loads(hooks_json)["hooks"]["Stop"][0]["hooks"][0]["type"] == "command"`.
  - [ ] `"args"` key is absent from every hook entry.
  - [ ] Old-format entry is replaced, not duplicated.

---

### SUC-004: clasi install --codex installs sub-agent TOML files

- **Actor**: Developer running `clasi install --codex`
- **Preconditions**: `clasi/plugin/agents/` contains `team-lead`, `sprint-planner`,
  `programmer` subdirectories with `agent.md` files.
- **Main Flow**:
  1. Installer enumerates active agents.
  2. For each agent, reads `agent.md`, strips YAML frontmatter, and writes
     `.codex/agents/<name>.toml` with fields `name`, `description`,
     `developer_instructions` (body text).
- **Postconditions**: Codex can discover and invoke CLASI agents as sub-agents.
- **Acceptance Criteria**:
  - [ ] `team-lead.toml`, `sprint-planner.toml`, `programmer.toml` exist under
        `.codex/agents/`.
  - [ ] Each TOML round-trip parses successfully and contains `name`, `description`,
        `developer_instructions`.
  - [ ] `developer_instructions` is non-empty.

---

### SUC-005: clasi uninstall --codex removes sub-agent TOML files

- **Actor**: Developer running `clasi uninstall --codex`
- **Preconditions**: `.codex/agents/team-lead.toml` and siblings are present.
- **Main Flow**:
  1. Uninstaller removes each `<name>.toml` from `.codex/agents/`.
  2. If `.codex/agents/` is now empty, the directory is removed.
- **Postconditions**: No CLASI agent TOML files remain under `.codex/agents/`.
- **Acceptance Criteria**:
  - [ ] After uninstall, `.codex/agents/<name>.toml` files do not exist.
  - [ ] User-added TOML files in `.codex/agents/` are not affected.

---

### SUC-006: AGENTS.md CLASI section does not contain the /se pointer line

- **Actor**: Codex agent reading `AGENTS.md` at session start
- **Preconditions**: `clasi install --codex` has been run; AGENTS.md has a CLASI section.
- **Main Flow**:
  1. Codex reads `AGENTS.md`.
  2. The CLASI section contains the entry-point sentence pointing to the SE skill.
  3. The CLASI section does NOT contain "Available skills: run `/se` for a list."
- **Postconditions**: Agent is directed to the SE skill without a misleading command hint.
- **Acceptance Criteria**:
  - [ ] `"run `/se`"` does not appear in any CLASI-owned AGENTS.md section.
  - [ ] `"run \`/se\`"` does not appear in `clasi/templates/clasi-section.md`.

---

### SUC-007: clasi install --codex writes nested AGENTS.md rule files

- **Actor**: Developer running `clasi install --codex`
- **Preconditions**: Rule source content is available in the plugin.
- **Main Flow**:
  1. Installer writes `AGENTS.md` files at appropriate subdirectory roots containing rule
     content (e.g., `docs/clasi/AGENTS.md` with SE process rules, `clasi/AGENTS.md` with
     source-code modification rules).
  2. Each nested `AGENTS.md` uses standard instruction prose format.
  3. Uninstaller removes these files; the root `AGENTS.md` CLASI section is already
     managed separately.
- **Postconditions**: Rule content is available to Codex-compatible agents without relying
  on Claude-specific rule loading.
- **Acceptance Criteria**:
  - [ ] `docs/clasi/AGENTS.md` exists after install and contains SE-process rule content.
  - [ ] `clasi/AGENTS.md` exists after install and contains source-code rule content.
  - [ ] Both files are removed by `clasi uninstall --codex`.

---

### SUC-008: End-to-end Codex install produces all correct artifacts

- **Actor**: Test suite / CI
- **Preconditions**: `tmp_path` is an empty directory.
- **Main Flow**:
  1. `codex.install(tmp_path, mcp_config={...})` is called.
  2. Test parses every emitted file:
     - `.codex/config.toml` via `tomllib.loads` — asserts `[mcp_servers.clasi]` present.
     - `.codex/hooks.json` via `json.loads` — asserts exact wrapper structure.
     - `.codex/agents/team-lead.toml` via `tomllib.loads` — asserts required fields.
     - `AGENTS.md` — asserts CLASI section present, no `/se` line.
     - Nested `AGENTS.md` files — asserts rule content present.
  3. All assertions pass.
- **Postconditions**: Every emitted file is spec-compliant.
- **Acceptance Criteria**:
  - [ ] All five file-type assertions pass in a single test run.
  - [ ] Tests run without network access (all content is local).
