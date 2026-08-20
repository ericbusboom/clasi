---
status: done
type: bug
tags:
- reliability-campaign
- phase-2
- state-db
- state-machine
sprint: '030'
tickets:
- 030-001
---

# One sprint-stage vocabulary with one writer

## Description

A sprint's stage currently lives in four disagreeing vocabularies — DB
phase (`roadmap`…`done`), frontmatter `status:`
(`roadmap`/`planning-docs`/`closed`), computed machine state
(`open`/`planned`/`ticketed`/…), and directory location — plus a fifth set
(`planning`/`active`/`done`) advertised by `list_sprints` docs that nothing
writes. The stores are updated by separate non-transactional writes, the
drift detector compares two vocabularies that are disjoint by construction
(flagging every healthy sprint), and the checked-in rule telling agents to
call `list_sprints(status="active")` always returns an empty list. From the
reliability review (00-review.md RC-1, C7; 01-state-layer.md findings 2,
10, 14 and the state inventory).

## Acceptance criteria

- The DB phase list is the single stage vocabulary. Frontmatter `status:`
  is derived from it at write time by one `set_sprint_stage()` that updates
  DB and frontmatter together and raises loudly on partial completion.
- The other vocabulary strings are deleted from writers, templates, tool
  docstrings, and `.claude/rules/clasi-artifacts.md`.
- `detect_inconsistencies` compares like with like; a healthy active sprint
  produces zero drift entries (add a test).
- `list_sprints(status=...)` filters on values that actually exist.
