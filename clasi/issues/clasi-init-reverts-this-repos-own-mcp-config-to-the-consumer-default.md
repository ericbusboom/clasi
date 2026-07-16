---
status: pending
type: bug
tags:
- install
- mcp
- dogfooding
- staleness
---

# clasi init reverts this repo's own .mcp.json to the consumer default

## Description

Running `clasi init` (or the update path that invokes it) inside the CLASI repo
overwrites `.mcp.json` with the consumer-project default — bare
`{"command": "clasi", "args": ["mcp"]}` — reverting ticket `020-002`'s
dogfooding fix, which pointed this repo's server at the editable install via
`uv run clasi mcp`.

**Observed 2026-07-16**: the stakeholder updated CLASI in the morning
(`.clasi/clasi-version` stamped `0.20260716.1` at 08:07). The on-disk
`.mcp.json` afterwards said bare `clasi`, while `git diff HEAD -- .mcp.json`
showed the committed file still carrying `uv run`. The next MCP session
therefore connected to the pipx build at `0.20260715.3` — new enough to mostly
work, old enough to be missing the nine process-content tools (`list_skills`,
`get_skill_definition`, ...) and the staleness fields in `get_version()`. This
silently invalidated the first attempt to rerun the MCP skill-discovery
experiment: the tools existed on master but not on the server the session was
talking to.

This is the same failure class as the original stale-pipx incident
(`mcp-server-runs-stale-pipx-build-not-the-working-tree.md`, fixed by 020-002),
recurring through a different door: 020-002 corrected the config once, but
nothing stops the installer from stamping the consumer default back over it.
The correction and the thing that undoes it are both working as designed.

Note the near-miss asymmetry: the nine hook commands in
`.claude/settings.json` were NOT reverted (all still `uv run clasi hook ...`),
only `.mcp.json` was. Worth understanding why during the fix — either the hook
path is skipped on re-init, or it preserves existing values where the MCP path
overwrites.

## Cause

`init_command._update_mcp_json()` (`src/clasi/init_command.py`) merges
`_detect_mcp_command(target)` into `.mcp.json` unconditionally when the
existing value differs. `_detect_mcp_command` deliberately returns bare
`clasi` for all targets — correct for consumers (documented rationale: `uv run`
broke projects without uv or a `[project]` table), wrong for this repo, and the
function has no way to know the difference.

## Proposed fix

Options, roughly in order of preference:

1. **Detect the dogfooding case.** If the target repo *is* the CLASI source
   repo (e.g. `pyproject.toml` declares `name = "clasi"`, or
   `src/clasi/mcp_server.py` exists), `_detect_mcp_command` returns the
   `uv run` form instead. One conditional, keeps consumer behavior untouched.
2. **Never overwrite a differing existing entry silently.** If `.mcp.json`
   already has a `clasi` server entry that differs from the default, leave it
   and print a notice, rather than replacing it. Safer for any customized
   config, not just this repo's.
3. Both — (1) fixes the known case, (2) protects unknown ones.

Whatever is chosen, add the regression test that was missing from 020-002:
run `clasi init` against a checkout that already carries the `uv run` config
and assert it survives. 020-002's acceptance criterion "this repo's config
corrected" was true at commit time and un-done by the next init — a test that
only checks the corrected state once cannot catch that.

## Verification

- `clasi init` in this repo leaves (or produces) the `uv run clasi mcp` form in
  `.mcp.json`.
- `clasi init` in a scratch consumer project (no uv, no `[project]` table)
  still produces bare `clasi` — the consumer rationale must hold.
- After init in this repo, a fresh MCP session's `get_version()` reports the
  working tree's version with the `stale` field present.

## Related

- `020-002` made the original correction and added the staleness detection;
  this issue is its missing durability half.
- `mcp-server-runs-stale-pipx-build-not-the-working-tree.md` (closed by
  020-002) — same failure class, different trigger.
- Blocked the first clean rerun of the MCP skill-discovery experiment
  (issue-re-enable-the-mcp-process-content-tools step 2).
