---
type: review
date: 2026-05-07
scope: active TODO queue
---

# Analysis of active CLASI TODOs

Review of all 9 active top-level TODOs, the 1 in-progress (`clasr`), and 2 `later/` reference TODOs against the current state of the product. Looking for conflicts, redundancy, opportunities to combine, and ways to re-frame the queue before sending anything to a sprint.

## Map of the active queue

| TODO | Theme | Size |
|---|---|---|
| `consolidate-the-clasi-version-marker-into-clasi-clasi-version` | Layout/install | XS |
| `rename-clasi-todos-to-issues` | Rename | M |
| `sprint-scoped-issues-directory` | Layout | S–M |
| `move-clasi-artifact-root-from-docs-clasi-to-dot-clasi` | Layout | L |
| `sprint-process-changes` | Process | M |
| `delta-specs-for-brownfield-architecture-changes` | Process/format | L |
| `schema-driven-workflow-yaml-dag` | Architecture | XL |
| `integration-registry-base-class-and-registry` | Architecture | L |
| `define-proper-worktree-process-for-parallel-ticket-execution` | Process | M (design-only) |
| `clasr-settings-json-multi-provider-uninstall-overlapping-top-level-keys` | Bug | S |

The queue cleanly splits into **three thematic clusters** plus two singletons:

- **Cluster A — `.clasi/` layout migration**: version-marker, rename-todos-to-issues, sprint-scoped-issues, root-move. Four TODOs, all editing the same files (`Project` properties, `Todo`/`Issue` class, hooks, MCP tools, tests, every rule file's path glob). Heavy mutual overlap.
- **Cluster B — Sprint process restructuring**: sprint-process-changes, delta-specs, schema-driven-workflow. Three TODOs, all touching the phase machine and the artifact ordering inside a sprint.
- **Cluster C — Engine refactor toward many platforms**: clasr (in-progress), integration-registry. Already sequenced.
- **Singletons**: worktree process and clasr settings.json bug. Independent.

## 1. Conflicts

### Conflict 1.1 — Architecture-update file: location and format being changed simultaneously (HIGH)

`sprint-process-changes` moves the architecture update **to the front of sprint planning** (between use cases and TODOs/issues). `delta-specs` rewrites the architecture-update **format** from free prose to OpenSpec-style ADDED/MODIFIED/REMOVED/RENAMED, renames the file to `architecture-delta.md`, and adds a **merge-back-into-source-of-truth** step at sprint close.

These two TODOs talk about the same artifact but in different vocabularies. They're not strictly incompatible (a delta-formatted document can be authored at planning time), but they need to be reconciled before either lands or the second one will rewrite work the first one just shipped.

**Recommendation**: merge them into one TODO: *"Architecture as forcing-function delta spec at sprint planning"*. The combined story is coherent — author a delta at sprint start as the structural plan, validate it at planning gate, accumulate deltas as the historical record, no separate snapshot doc. The sprint-process-changes "diff between successive architecture updates is the sprint's contract" line becomes literally true under delta format.

### Conflict 1.2 — Sprint planning order vs schema-driven workflow (LOW–MEDIUM)

`sprint-process-changes` defines a hardcoded planning order (overview → use cases → architecture → issues → tickets). `schema-driven-workflow` makes the planning order a property of a YAML schema. If both ship, the order needs to be expressed *only* in the schema, not hardcoded in skill bodies.

**Recommendation**: keep both, but explicitly note in `sprint-process-changes` that "the new order is realized by editing the SE-process schema once `schema-driven-workflow` lands; until then, edit the skills directly." Sequence schema-driven-workflow first if it lands at all, otherwise the order change is going to be applied twice.

### Conflict 1.3 — Issue lifecycle described in two TODOs with different state (HIGH)

`rename-clasi-todos-to-issues` says: directory layout `issues/` with `in-progress/` and `done/` subdirs; on completion the file moves to `done/`.

`sprint-scoped-issues-directory` says: drop the `in-progress/` and `done/` subdirs entirely; the file moves into `<sprint>/issues/` when claimed and stays there. `move_to_done` becomes frontmatter-only.

The rename TODO's directory description is now stale. `move-clasi-artifact-root-from-docs-clasi-to-dot-clasi` carries yet a third version of the layout (a hybrid).

**Recommendation**: delete the directory-layout sections from the rename TODO and from the root-move TODO. Make `sprint-scoped-issues-directory` the single source of truth for issue lifecycle. The rename TODO becomes purely about *vocabulary* (terms, filenames as types, status enum). See "Combine" below.

### Conflict 1.4 — Skill renames overlap with schema-driven (LOW)

`schema-driven-workflow` proposes that skill bodies "shrink to a stub plus the load call" — instructions get lifted into `clasi/schemas/se-process/instructions/*.md`. Meanwhile `rename-clasi-todos-to-issues` renames `clasi/plugin/skills/todo/` → `issue/`. If schema-driven lands first, the rename is editing files that have just been gutted; if rename lands first, schema-driven still has to relocate `issue/` to its new home. No real conflict — just sequencing tax.

## 2. TODOs that need revision

### 2.1 — `rename-clasi-todos-to-issues`: drop the directory layout claims

Action: remove sections about `docs/clasi/issues/in-progress/` and `docs/clasi/issues/done/` subdirectories. The new home for issue-lifecycle decisions is `sprint-scoped-issues-directory`. Keep: vocabulary changes, MCP tool renames, CLI rename, skill rename, frontmatter field renames, status enum collision fix.

### 2.2 — `move-clasi-artifact-root-from-docs-clasi-to-dot-clasi`: trim and re-aim

This TODO has grown into a half-summary of the other three layout TODOs. Strip out everything except: (a) the `docs/clasi/` → `.clasi/` path move itself, (b) `Project.design_dir` correction, (c) one-shot `clasi migrate` subcommand, (d) repo-self-migration steps, (e) `.gitignore` edits. Stop describing issue lifecycle and version-marker placement here — those are owned by their dedicated TODOs.

### 2.3 — `sprint-process-changes`: missing frontmatter, missing acceptance criteria

This TODO has no frontmatter (no `status: pending`) and no acceptance criteria. It's also written more as a manifesto than a sprint plan. It works as a design memo but isn't directly sprint-plannable in this form. Add frontmatter, an explicit list of files to change (the skills under `clasi/plugin/skills/` that encode the planning order), and acceptance criteria (e.g. "running `clasi sprint create` walks the new order; `architecture-update.md` is gone from the ticketing-phase output and present at planning gate").

### 2.4 — `consolidate-the-clasi-version-marker-into-clasi-clasi-version`: tiny but flagged ambiguity

Two open questions noted at the bottom ("Stale markers from prior installs", "Uninstall cleanup"). Decide both before sprint planning so the planner doesn't re-litigate them. Recommended answer for both: yes, opportunistically delete old `.clasi-version` files inside `write_version_stamp`, and yes, have uninstall remove `.clasi/clasi-version` and the `.clasi/` directory if empty.

### 2.5 — `delta-specs-for-brownfield-architecture-changes`: too many open questions to be sprint-ready

Five open questions in §"Open questions" — item identity, BDD format adoption, specification deltas day 1 vs deferred, skills/rules as delta categories, 3-way merge for parallel sprints. Resolve at least item identity and BDD adoption before sprint-planning, or this becomes a 4-week sprint that designs in flight.

### 2.6 — `define-proper-worktree-process-for-parallel-ticket-execution`: deliverable is a design doc, not code

This TODO's deliverable is "a concrete CLASI process and implementation plan." That's a **planning artifact**, not a sprint of code changes. Either (a) reframe as "produce a design TODO that becomes a future sprint" (keep it small, deliverable is markdown) or (b) reframe with a concrete code-shaped target (e.g. "implement Sprint.acquire_worktree() / release_worktree() with the lifecycle defined inline"). Right now it's a meta-task that risks looping.

Recent commit history says `chore: disable parallel ticket execution and worktrees, mandate serial-only` — which makes this TODO low-priority unless parallel execution is being reintroduced.

## 3. TODOs to combine

### Recommended consolidation: **one Layout-Migration TODO** replacing the cluster of four

Combine into a single TODO titled `migrate-clasi-artifact-layout-to-dot-clasi`:

- Path move `docs/clasi/` → `.clasi/`
- Rename `todo` → `issue` (vocabulary, files, MCP tools, CLI, skill)
- Sprint-scoped issues directory (issue lifecycle move into `<sprint>/issues/`)
- Single version marker at `.clasi/clasi-version`
- Status enum `todo` → `open`
- One-shot `clasi migrate` subcommand
- `Project.design_dir` correction
- `.gitignore` edits

**Why combine**: every one of these touches the same files. The Explore agent's count of *160 references* in the root-move TODO was already the union; doing them in one sprint amortizes test churn and avoids three rounds of cascading rule-file/installer/test edits. The locked-in decisions from the four separate TODOs all hold.

**Sprint sequencing inside the combined TODO** (still useful as ticket order):

1. Tickets that introduce the new symbols/paths in code while keeping old ones working? **No** — hard cut, per the locked-in decisions. Skip backward-compat.
2. Vocabulary rename (cheapest, no path moves yet): symbols, MCP tool names, status enum.
3. Path constants: `Project` properties, hook handlers, installers, init.
4. Issue lifecycle: sprint-scoped move logic, `Sprint.issues_dir`, `move_to_done` becomes frontmatter-only.
5. Version marker single-write.
6. `clasi migrate` subcommand + repo self-migration commit.
7. Re-render rule files / agent prompts / installer-templated files. README updates.

### Recommended consolidation: **delta-specs + sprint-process-changes**

Merge into `architecture-as-delta-spec-at-sprint-planning`. The delta format provides the *machinery* for what sprint-process-changes describes as the new front-loaded planning artifact. The "exception cord" idea from sprint-process-changes is genuinely separate and should be split out into its own TODO (see below).

### Recommended split: **exception cord out of sprint-process-changes**

The "Exception cord for lower-level agents" half of `sprint-process-changes` is unrelated to architecture-update positioning. It's a runtime escalation pattern — programmer/sprint-planner can throw a structured "I can't proceed" signal that the team-lead routes. Pull it into its own TODO `lower-agent-exception-protocol` with: payload schema, where it gets recorded (ticket frontmatter? new artifact?), team-lead routing rules, and tests.

## 4. A more sensible re-framing

After the consolidation/split above, the active queue becomes:

| TODO | Cluster | Status |
|---|---|---|
| `migrate-clasi-artifact-layout-to-dot-clasi` | Layout | Combined from 4 |
| `architecture-as-delta-spec-at-sprint-planning` | Process | Combined from 2 |
| `lower-agent-exception-protocol` | Process | Split out |
| `schema-driven-workflow-yaml-dag` | Architecture | As-is |
| `integration-registry-base-class-and-registry` | Architecture | As-is, post-clasr |
| `clasr-settings-json-multi-provider-uninstall-overlapping-top-level-keys` | Bug | As-is |
| `define-proper-worktree-process-for-parallel-ticket-execution` | Process | Defer or reframe (parallel execution currently disabled) |

That's 7 TODOs instead of 9, with cleaner thematic boundaries and zero cross-TODO conflicts on the same files.

### Suggested sprint sequence

1. **Layout migration** first. It unblocks the rename-related decisions in every other TODO and the test suite churns once. Big sprint, but contained.
2. **clasr settings.json bug** as a small fast-follow (independent surface area).
3. **Architecture-as-delta-spec** before `schema-driven-workflow`. Why: schema-driven references `architecture-delta` as one of its declared artifacts; landing the delta format first lets schema-driven slot it in cleanly.
4. **Schema-driven workflow** — the largest architectural TODO, depends on (1) and (3) for clean integration.
5. **Lower-agent exception protocol** — independent, can land in parallel with (4) if both fit.
6. **Integration-registry refactor** — explicitly post-clasr (clasr step 11 must be done first).
7. **Worktree process** — only revisit if/when serial-only is being reverted.

## 5. Concrete edits to execute this restructuring

If executed, the operations are:

1. **Edit** `rename-clasi-todos-to-issues.md`: strip directory-layout sections, narrow scope to vocabulary.
2. **Edit** `move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md`: strip issue-lifecycle and version-marker sections, narrow scope to path move + migration tool.
3. **Edit** `consolidate-the-clasi-version-marker-into-clasi-clasi-version.md`: lock in answers to the two trailing questions.
4. **Create** combined TODO `migrate-clasi-artifact-layout-to-dot-clasi.md` that supersedes those three plus `sprint-scoped-issues-directory.md`. Move all four superseded files to `done/` (or a `superseded/` subdir) so the planner only sees the combined version.
5. **Edit** `sprint-process-changes.md`: add frontmatter, narrow to architecture-positioning only, point at delta-specs as the format.
6. **Create** `lower-agent-exception-protocol.md` from the second half of `sprint-process-changes.md`.
7. **Edit** `delta-specs-for-brownfield-architecture-changes.md`: resolve item-identity and BDD-format open questions; reference sprint-process-changes for the planning-time positioning.
8. **Optional**: combine #5 and #7 into a single `architecture-as-delta-spec-at-sprint-planning.md`.

Recommended starting subset: **#1 + #2 + #4** (the layout consolidation), since that's the largest source of conflict and produces the highest planning leverage.
