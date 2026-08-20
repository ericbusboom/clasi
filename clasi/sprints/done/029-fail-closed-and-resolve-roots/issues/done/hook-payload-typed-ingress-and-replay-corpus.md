---
status: done
type: task
tags:
- reliability-campaign
- phase-1
- hooks
- testing
sprint: 029
tickets:
- 029-008
---

# Hooks: one typed payload ingress and a captured-payload replay corpus

## Description

Six handlers each hand-roll payload extraction; the file-path rule exists
twice and drifted once already (the 876-event fail-open incident). And the
unit tests build payloads by hand — well-structured now, but structurally
unable to catch harness-side shape changes, which is the direction real
breakage comes from. From the reliability review (03-hooks-guards.md F6,
F7).

1. A frozen `HookPayload` dataclass built once in `handle_hook`
   (`from_stdin(raw)`), with fields `tool_name`, `tool_input`, `file_path`
   (the single nested-then-flat resolution), `caller_id` plus its source,
   `agent_type`, `transcript_path`, `plan_file_path`, and a
   `missing: list[str]` of expected-but-absent fields that `_exit_hook`
   appends to the log line. Plain dataclass, not pydantic — preserve the
   sprint-027 import-cost win.
2. `tests/fixtures/hook_payloads/*.json`: verbatim payloads captured from
   each real event type (the Phase 0 deny-capture supplies deny payloads;
   allow payloads captured via a temporary tee), replayed through
   `read_payload` → handler in a parametrized test asserting the decision.

## Acceptance criteria

- All six handlers consume `HookPayload`; no handler touches the raw dict.
- The replay test covers every hook event type with at least one captured
  fixture, including at least two deny-path fixtures.
- Deny-path assertions use real captured payloads per the
  enforcement-gates guidance in project memory.
