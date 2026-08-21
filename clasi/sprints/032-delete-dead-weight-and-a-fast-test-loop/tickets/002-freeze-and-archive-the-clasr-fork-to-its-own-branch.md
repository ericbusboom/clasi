---
id: "002"
title: "Freeze and archive the clasr fork to its own branch"
status: open
use-cases: ["SUC-007"]
depends-on: []
github-issue: ""
issue: ""
# completes_issue: Controls whether linked issues are archived when this ticket
# is moved to done. Default: true (archive when all referencing tickets are done).
# Set to false (scalar) to suppress archival for ALL linked issues on this ticket.
# Set to a mapping {filename.md: false} to suppress archival per issue filename.
# Use false for tickets that partially address a multi-sprint umbrella issue.
completes_issue: true
# exception: Written by a lower agent when it cannot proceed (see architecture §exception-protocol).
# exception:
#   thrown_by: "programmer"          # "programmer" | "sprint-planner"
#   thrown_at: "2026-05-07T14:23:00Z"
#   attempted: |
#     Description of what was attempted before giving up.
#   conflict: "architecture-update.md §3 — reason the agent is blocked"
#   surface: "internal"              # "user-visible" | "internal"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Freeze and archive the clasr fork to its own branch

## Description

Stakeholder decision (Eric, 2026-08-21, recorded in sprint.md's
"Stakeholder Decisions Needed"): freeze `clasr` and archive it out of
this repo onto its own branch. `src/clasi/platforms` is authoritative
going forward. This knowingly gives up clasr's manifest-based uninstall
model (better than clasi's name-based one) — that tradeoff is recorded,
and a follow-up issue for possibly porting it into `clasi.platforms`
later is part of this ticket's own acceptance criteria, not deferred to
someone else.

Verified during planning: nothing under `src/clasi` imports `clasr`
(`grep -rn "import clasr\|from clasr" src/clasi/` returns nothing), so
this is a clean subtraction with no import-graph repair needed inside
`src/clasi`. `tests/asr/` (19 files, `provider1`/`provider2` example
dirs) is exclusively `clasr` demonstration fixture data — its own
`justfile`'s `demo`/`demo-single` recipes shell out to `clasr
install`/`clasr uninstall`, and its `README.md` states its purpose is
to "demonstrate `clasr` and exercise multi-tenant install behavior."
`tests/clasr/conftest.py`'s `make_asr_dir` fixture generates its own
synthetic `asr/` tree at test time and does not read the on-disk
`tests/asr/` directory at all — nothing automated consumes it. It moves
with clasr to the archive branch, not "relocated" within master (this
supersedes the `05-e2e-test-infra.md` finding 11 / issue Part C
suggestion to relocate it under `tests/clasr/fixtures/`, written before
the clasr archival decision existed — see sprint.md's Design Rationale).

No linked issue owns this ticket — it implements the review's Part 6
decision 1, not one of this sprint's six tracked issues. It traces to
SUC-007 in `sprint.md`. Ticket 007 (e2e coverage harness) and ticket
008 (test-suite speed) both depend on this ticket landing first — their
`.coveragerc`/audit scope assumes `clasr` no longer exists in the tree.

## Acceptance Criteria

- [ ] An `archive/clasr` branch exists on `origin`, created at a commit
      that still has the full pre-deletion content of `src/clasr/`,
      `tests/clasr/`, and `tests/asr/` — created and pushed **before**
      the deletion commit lands on the sprint branch (same sequencing
      as ticket 001; see Implementation Plan).
- [ ] `src/clasr/` (entire directory), `tests/clasr/` (entire
      directory), and `tests/asr/` (entire directory) are deleted from
      master.
- [ ] `pyproject.toml`'s `clasr` references are removed:
      `[project.scripts]`'s `clasr = "clasr.cli:main"` entry,
      `[tool.setuptools.packages.find]`'s `include = ["clasi*",
      "clasr*"]` (becomes `["clasi*"]`), `[tool.setuptools.package-data]`'s
      `clasr = ["*.md", "platforms/*.md"]` entry, `[tool.pytest.ini_options]`
      `addopts`'s `--cov=src/clasr` flag, and `[tool.coverage.run]`'s
      `source = ["src/clasi", "src/clasr"]` (becomes `["src/clasi"]`).
      Verify no other `pyproject.toml` line references `clasr` before
      calling this criterion done — this planning pass's grep found
      these five, not necessarily all.
- [ ] A `clasi/issues/` file (this project's own issue-file convention,
      not a GitHub issue) is created recording the manifest-based
      -uninstall-porting idea: the observation that clasr's uninstall
      model (per-provider manifest tracking exactly what it installed)
      is more correct than `clasi.platforms`'s name-based uninstall
      (which can orphan files from an older clasi whose names have
      since changed — finding F14), with a pointer to the `archive/clasr`
      branch as the reference implementation. Use the `issue` skill's
      normal format; tag it so a future roadmap pass can find it (e.g.
      `tags: [clasr, uninstall, follow-up]`).
- [ ] Full suite passes with the deletion in place.

## Implementation Plan

### Approach

1. **Cut and verify the archive branch first, before any deletion.**
   ```
   git branch archive/clasr
   git show archive/clasr:src/clasr/cli.py | head -20
   git show archive/clasr:tests/asr/README.md | head -5
   git push origin archive/clasr
   ```
   If `git push` fails (no push access to `origin` from this
   environment), STOP and report — same as ticket 001's Open Question 1
   handling; do not proceed with an unpushed, only-locally-recoverable
   archive.
2. **Delete `src/clasr/`, `tests/clasr/`, `tests/asr/` wholesale.** No
   file-by-file audit is needed here the way ticket 001 needed one —
   nothing in `src/clasi` imports `clasr` (verified above), and nothing
   in `tests/` outside `tests/clasr/` references `tests/clasr/conftest.py`
   or `tests/asr/` (verify this still holds at execution time with a
   fresh grep, since ticket 001 may have touched adjacent test files
   first depending on execution order).
3. **Edit `pyproject.toml`** per the acceptance criteria's five call
   sites.
4. **File the follow-up issue** (see acceptance criteria) — do this as
   part of this ticket, not a separate step delegated elsewhere.
5. **Run the full suite** and fix any surprises (there should be very
   few, given the verified zero-import state).

### Files to Modify

- **Delete**: `src/clasr/` (entire tree — `cli.py`, `frontmatter.py`,
  `integration.py`, `platforms/`, `links.py`, `markers.py`, `SCHEMA.md`,
  `README.md`, `instructions.md`, and everything else under it),
  `tests/clasr/` (entire tree — `conftest.py`, `test_cli.py`,
  `test_frontmatter.py`, `test_integration_contract.py`,
  `test_markers.py`, `test_links.py`, `test_multi_tenant.py`,
  `test_merge.py`, `test_manifest.py`, `test_three_platform_roundtrip.py`,
  `test_platform_{claude,codex,copilot,detect}.py`, everything else
  under it), `tests/asr/` (entire tree — `justfile`, `README.md`,
  `provider1/`, `provider2/`).
- **Modify**: `pyproject.toml` (the five call sites listed in
  Acceptance Criteria).
- **Create**: one `clasi/issues/*.md` file (the manifest-uninstall
  follow-up).
- **No change**: anything under `src/clasi` (verified zero imports).

### Testing Plan

- **Existing tests to run**: `uv run pytest tests/unit/ -k "not clasr"
  -v` as a sanity pass before the deletion (confirms the baseline), then
  a full `uv run pytest` after the deletion — this ticket's deletion
  touches `pyproject.toml`'s collection/coverage config, so a targeted
  subset isn't sufficient to prove `pyproject.toml` itself is still
  valid; run the full suite for this ticket specifically as an
  exception to the usual scoped-run rule, since `pyproject.toml` syntax
  errors or a bad `packages.find` entry only surface at collection/build
  time, not in a subset run.
- **New tests to write**: none required — this is a pure deletion plus
  config cleanup; no new behavior to test. If desired, a smoke check
  that `python -c "import clasi"` and `uv build --wheel` (or equivalent)
  still succeed after the `packages.find` change is cheap insurance.
- **Verification command**: `uv run pytest` (full suite, per the
  pyproject.toml-touching exception above) plus `uv run python3 -c
  "import clasi"`.

### Documentation Updates

- The follow-up issue file (acceptance criteria).
- `docs/architecture/architecture-update-019.md` and
  `clasi/reflections/active-todo-queue-analysis.md` mention `clasr` —
  both are historical sprint-scoped records (sprint 019's own
  architecture doc, a past reflection); leave them untouched, they
  describe what was true when written, not current state.

## Process Notes

- Guards fail closed. If a role-guard or mcp-guard block is hit while
  working this ticket, **STOP and report it** — do not route around it.
  Reporting a block is a successful outcome of this ticket's work, not
  a failure.
- Tier-2 (in-progress-ticket) write scope covers this ticket's own file
  under the locked sprint's `tickets/` tree for status/frontmatter
  updates, plus `src/`, `tests/`, and `pyproject.toml` (root-level
  config file, not under a `protected_paths` directory — verify at
  execution time whether root-level files need separate tier
  clearance, since this sprint's protected_paths is `[src, tests]`
  only).
- Deleting `tests/asr/` and `src/clasr/README.md`/`instructions.md`
  removes markdown files, but this is not the `clasi-artifacts.md`
  rule's territory (that rule governs CLASI planning artifacts under
  `clasi/sprints/`, not arbitrary project docs) — no special gate
  beyond the normal source-code ticket-in-progress requirement applies.
