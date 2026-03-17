---
ticket: "{ticket_id}"
title: "{ticket_title}"
reviewer: code-reviewer
date: "{date}"
---

# Code Review: {ticket_title}

## Phase 1 — Correctness

**Verdict**: {phase1_verdict}

### Acceptance Criteria

| # | Criterion | Status | Notes |
|---|-----------|--------|-------|
| 1 | (criterion text) | PASS / FAIL | (explanation if FAIL) |
| 2 | (criterion text) | PASS / FAIL | (explanation if FAIL) |
| 3 | (criterion text) | PASS / FAIL | (explanation if FAIL) |

### Test Verification

- [ ] Tests exist for each acceptance criterion
- [ ] All tests pass (`{verification_command}`)
- [ ] No acceptance criteria silently skipped

### Phase 1 Summary

(If FAIL: describe what needs to change and where. Be specific —
include file paths and line numbers. Phase 2 is skipped.)

(If PASS: proceed to Phase 2.)

---

## Phase 2 — Quality

**Verdict**: {phase2_verdict}

### Issues

| # | Severity | Description | Location | Recommended Fix |
|---|----------|-------------|----------|----------------|
| 1 | critical / major / minor / suggestion | (issue description) | (file:line) | (what to change) |

### Severity Definitions

- **Critical**: Security vulnerability, data loss risk, or broken functionality
- **Major**: Standards violation, missing error handling, or significant maintainability concern
- **Minor**: Style inconsistency, suboptimal naming, or minor code smell
- **Suggestion**: Improvement idea that is not a defect

### Phase 2 Summary

(Summary of quality findings. Note any patterns or recurring issues.)

---

## Overall Verdict

**{overall_verdict}**

(Brief justification for the overall verdict.)
