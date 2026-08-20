# Review: Process flow & ceremony (agent report, verbatim)

Path key: `$R` = repo root, `$P` = `$R/src/clasi/plugin`, `$S` = `$R/src/clasi/schemas`.

## Sprint cost trace

Scenario: 1 issue, 3 tickets, compact tier, serial path, design-docs not opted in.

**Enforced phase order** (`_compute_phases()` over `$S/se-process/schema.yaml`; gates in `_GATE_REQUIREMENTS`, `state_db_class.py:116`): `roadmap → planning-docs → architecture-review →(gate: architecture_review)→ stakeholder-review →(gate: stakeholder_approval)→ ticketing →(lock)→ executing → closing → done`. `create_ticket` hard-rejects before `ticketing` (`artifact_tools.py:669-686`).

| Step | Actor | Dispatches | MCP calls | Notes |
|---|---|---|---|---|
| Session preflight | team-lead | — | 2-3 | every session |
| Issue capture | team-lead | — | 0 | direct write |
| Sprint creation | sprint-planner | **1** | 2 | forced dispatch: mcp-guard blocks tier-0 `create_sprint`; team-lead parses sprint id from free-text report |
| Re-link issues | team-lead | — | 1 | defensive duplicate ordered by agent.md |
| Detail planning | sprint-planner | **1** | ~6 | docs say create tickets in this dispatch; DB refuses → planner parks ticket table in sprint.md, returns blocked (sprint-026 incident) |
| Approval | stakeholder + team-lead | — | 2 | **human approval #1** |
| Ticket materialization | sprint-planner | **1** | ~5 | exists only because of the gate-order contradiction |
| Pre-execution | team-lead | — | 4 | review_sprint_pre_execution, lock, advance, status→active |
| Execute ×3 | programmer ×3 | **3** | ~9 + 3-6 | scoped foreground tests ×3; team-lead re-verifies every ticket (stall history) |
| Full-suite run #1 | team-lead | — | 0 | execution.md §5.2 |
| Sprint review | team-lead | — | ~2 | checklist re-runs full suite → **run #2** |
| Close | team-lead | — | 2 + ToolSearch | **human approval #2**; close_sprint internally: self-repair, **full-suite run #3**, archive, DB, overlay, bump+tag, merge, push, prune |

**Totals**: **6 subagent dispatches** (docs promise 2 planner; actual 3), **~35-40 MCP calls** + ToolSearch loads, 2 DB gates, 7 phase transitions (several silently self-repaired at close), 2 human approvals, **3 full-suite runs** (docs claim two is the total), ~10 artifact writes + bump/tag/merge commits.

**Where cost goes**: (1) three planner dispatches where one would do — planning context paid 3×; (2) three full-suite runs; (3) team-lead post-dispatch re-verification; (4) guard retry bursts — 68% of hard blocks in ≥2-retry bursts, OOP hatch carries more traffic (106 allows) than the gates block (68); (5) ToolSearch + `"NONE"` ceremony per call; (6) status-inject per prompt.

**Safety vs bookkeeping**: real safety = stakeholder plan approval, one full-suite gate at close, execution lock, foreground/scoped-test rule, exception protocol. Pure bookkeeping the server could do: all agent-driven `advance_sprint_phase` (close's self-repair already advances phases — the de facto design), `move_ticket_to_done` (fold into `update_ticket_status("done")`), in-progress at dispatch (SubagentStart hook already fires), issue sweeping (already automatic), `architecture_review: skipped` for trivial sprints, the duplicate `link_sprint_issues`.

## Doc/code contradictions

| What docs say | What's enforced / true | Where | Consequence |
|---|---|---|---|
| Planner creates tickets during planning dispatch; stakeholder reviews plan WITH tickets | `stakeholder_approval` gate required to reach `ticketing`; `create_ticket` rejects earlier | team-lead agent.md steps 4-5, sprint-planner agent.md Phase 4 vs `state_db_class.py:116`, `artifact_tools.py:669` | Planner blocked mid-dispatch; extra dispatch every sprint |
| "Advance to ticketing" one hop after arch review | `stakeholder-review` sits between | sprint-planner agent.md 8,10 vs schema.yaml | Planner believes it's in `ticketing` when not |
| `software-engineering.md` gate table agrees with the DB | — | `$P/instructions/software-engineering.md:358-398` | The docs that match enforcement are the peripheral ones |
| Sprint machine: `open/planned/pre-flight/ticketed/review/closed`, `sprint_review` gate, `close-report.md`, skip flags | DB phases differ; `VALID_GATE_NAMES` = {architecture_review, stakeholder_approval} — `record_gate` raises on `sprint_review` (`state_db_class.py:55,345`); nothing writes close-report.md or skip flags | `$S/state-machines/sprint.yaml` vs `state_db_class.py` | Status layer describes gates no tool can record; invariants never hold |
| Project machine: `is_any_sprint_ticketed` guards planning→in-sprint | predicate queries phase `"ticketed"`; DB only ever holds `"ticketing"`; errors → False silently | `predicates/project.py:76-79`, `reader.py:445-465` | Predicate permanently False; project machine can never report `in-sprint` |
| dispatch-subagent: "MUST call `log_subagent_dispatch`… If unavailable, STOP" | tool doesn't exist anywhere in src/clasi | `$P/skills/dispatch-subagent/SKILL.md` steps 4,6 | Skill followed literally = hard stop on every dispatch |
| `move_ticket_to_done(sprint_id, ticket_id)` | actual `move_ticket_to_done(path)` | team-lead agent.md #5 vs `artifact_tools.py:1035` | Wrong-arg calls; amplified by empty-args bug |
| `reconcile_worktrees(repo_root, sprint_dir)` | actual `reconcile_worktrees(sprint_id)` | execution.md vs `artifact_tools.py:1418` | Failed calls |
| Parallel path drives worktree functions as callable tools | Python functions only; no MCP surface | execution.md Parallel Path (~175 of 333 lines) | Path unusable as written |
| "Execution creates one worktree per ticket via `acquire_execution_lock`" | lock creates sprint branch only | close-sprint SKILL.md vs `artifact_tools.py:2145-2185` | Team-lead hunts for worktrees that never existed |
| plan-sprint/sprint-roadmap: team-lead uses `create_sprint` tool | mcp-guard blocks tier-0 `create_sprint` (matcher also misses `insert_sprint`) | sprint-plan.md:60 vs hooks | Team-lead follows skill, gets blocked, dispatches planner to run one tool |
| Planner is tier 1, model opus | `CLASI_AGENT_TIER=1` never observed live; agent.md says sonnet | contract.yaml vs agent.md; issue on file | Tier-1 write policy is fiction |
| Ticket status: contract `pending`; skills `open`; retired `todo` | `open/in-progress/done/exception` in practice | contract.yaml:62 vs create-tickets, ticket.yaml | Contract validation can't work |
| "planning artifacts live in `.clasi/`"; `docs/clasi/…` | actual `clasi/sprints/`, `clasi/issues/`, `docs/design/` | software-engineering.md:8, schema.yaml generates:, several skills | Three path generations coexist |
| source-code.md: "follow execute-ticket skill" | no such skill; rglob fallback (`process_tools.py:120-124`) lands in retired `agents/old/sprint-executor/execute-ticket.md` mandating per-ticket full pytest + code-monkey dispatch | rule vs programmer agent.md | Rule loaded on every source edit routes agents to the retired process |
| close.md: `test_command=""` to skip tests | `""` drops ALL args; `"NONE"` → None → default tests | close.md:42-49 vs empty-args rule | No working way to skip tests at close |
| Schema phases point at instruction docs | specification/tickets/usecases/overview.md are 1-line stubs | `$S/se-process/instructions/` | get_instruction for 4 of 8 phases returns nothing |
| Seven-agent roster; per-ticket code-reviewer; mandatory `-plan.md` | 3-agent model; optional review; embedded plan | software-engineering.md:29-57,400-457 | Largest instruction file describes a retired process |
| Installed team-lead agent.md (roadmap-arc flow) | plugin source lags (older flow) | `.claude/agents/` vs `$P/agents/` | Next plugin sync regresses the live process |

## Findings

1. **Critical / gate-order** — docs and DB disagree on when tickets may exist; every sprint eats a wasted planner dispatch + retry burst. Fix: move `stakeholder_approval` to gate the execution lock; delete `stakeholder-review` phase.
2. **Critical / mandatory instructions referencing dead machinery** — source-code.md → execute-ticket → `agents/old/` via rglob fallback; dispatch-subagent → nonexistent tool with hard-STOP wording. Fix: exclude `agents/old/` from lookup; rewrite/retire dispatch-subagent; point source-code.md at programmer agent.
3. **High / multi-sourced process text** — plan-sprint exists in four diverging forms; create-tickets/tdd-cycle/systematic-debugging agent-local copies differ from skills; installed vs plugin team-lead differ. Fix: one canonical file per topic; agent.md carries a pointer.
4. **High / descriptive state machines divorced from enforcement** — different phase vocabulary, unrecordable gate, never-written artifact, never-produced phase string; predicates fail-to-False silently. Fix: generate the YAMLs from the enforced phase list or delete them.
5. **High / tier system unverified** — planner tier-1 never observed; contract/model mismatch; mcp-guard forces dispatches whose only purpose is one tool call. Fix: ship the decided tier-0 relaxation; add the real-dispatch tier test.
6. **Medium / three full-suite runs** — execution.md §5.2 + sprint-review re-run + close_sprint internal. Fix: close_sprint's run is the single gate.
7. **Medium / review redundancy** — sprint-review skill ≈ `review_sprint_pre_close` (unreferenced by any doc); `review_sprint_post_close` orphaned; code-review skill duplicates retired per-ticket steps. Fix: sprint-review = call pre_close + interpret; wire or delete post-close.
8. **Medium / instructions stated 3+ places** — scoped-foreground-tests in 7 places; issue-linkage warnings in 6; bump cadence in 4; phase gates in 4.
9. **Medium / failure recovery is improvisation** — programmer death/stall: "fix in-process or re-dispatch" only; close_sprint recovery contract (`recovery_state`, `clear_sprint_recovery`, role-guard bypasses) exists in code but **no process doc mentions it**. Worktree recover/abandon machinery serves only the unusable parallel path. Fix: document close-recovery in close.md; add dead-ticket resume paragraph to execution.md.
10. **Low / stubs and vocabulary** — 4 of 8 phase instruction files are placeholders; ticket status pending/open/todo; `.clasi/` vs `docs/clasi/` vs `clasi/` path generations.

## Leaner-flow proposal

For trivial/compact sprints, keeping: human approves plan; tests gate close.

1. **Capture** — unchanged.
2. **Create + link, no dispatch** — team-lead calls `create_sprint` + `link_sprint_issues` itself (decided tier-0 relaxation). Roadmap-mode planner dispatch only for multi-sprint arcs.
3. **One planner dispatch: plan-and-ticket** — detail → architecture/use-cases → tickets in one pass. Gate order fixed: `stakeholder_approval` gates the **lock**. Server records `architecture_review` from the planner's sizing payload. Agents never call `advance_sprint_phase`/`record_gate_result(architecture_review)`: phases become event-derived (create_sprint→roadmap, detail_sprint→planning, first create_ticket→ticketed, acquire_execution_lock→executing, close_sprint→done). Close's self-repair loop already is this design — promote it to contract.
4. **One human approval** — plan + tickets; approval = gate; `acquire_execution_lock` verifies gate + runs pre_execution review internally.
5. **Execute** — per ticket: dispatch programmer (SubagentStart auto-records in-progress); programmer runs scoped tests, commits, sets done; `update_ticket_status(path, "done")` performs the done-dir move (absorb move_ticket_to_done). Team-lead keeps verification + exception check.
6. **One full-suite run, at close** — delete pre-close run and sprint-review re-run; sprint-review = interpret `review_sprint_pre_close`, optional.
7. **Close** — as today; with prior "close when green" consent, no second stop.

Net: **4 dispatches (was 6), ~15 MCP calls (was ~35-40), 1 full-suite run (was 3), 1-2 human stops (was 2-3), 0 agent-driven phase/gate calls (was 6-7)**.

## Top structural recommendations

1. **Event-derived phase machine + corrected gate order** — agents never advance phases; `stakeholder_approval` gates the lock. Eliminates "blocked mysteriously mid-sprint" outright.
2. **One canonical text per process topic** — exclude `agents/old/` from definition search; delete stale copies; rewrite software-engineering.md to 3-agent reality; sync installed team-lead agent.md into plugin source.
3. **Ship the tier-0 relaxation and verify tier wiring end-to-end** — real-dispatch tier test; surface write scope at SubagentStart instead of teaching by blocking.
4. **One full-suite run per sprint, owned by close_sprint** — sprint-review interprets `review_sprint_pre_close`; wire or delete orphaned pre/post-close tools.
5. **Push per-ticket/status bookkeeping into the server; align or delete descriptive state machines** — status transitions perform file moves; hooks record dispatch state; regenerate state-machine YAMLs from the enforced phase list or remove them; give the parallel path an MCP surface or cut its ~175 lines.
