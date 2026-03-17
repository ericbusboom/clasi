---
id: "003"
title: "Create review-checklist template"
status: todo
use-cases: [SUC-002]
depends-on: ["002"]
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Create review-checklist template

## Description

Create a structured template for code review output that aligns with
the two-stage review process defined in ticket 002.

1. **templates/review-checklist.md** — A Markdown template with two
   sections matching the review phases:
   - **Correctness** section: table or checklist of acceptance criteria
     with pass/fail status and notes for each criterion
   - **Quality** section: table of issues ranked by severity (critical,
     major, minor, suggestion) with description, location, and
     recommended fix

2. **Update templates.py** — Add a `REVIEW_CHECKLIST_TEMPLATE` constant
   that loads `review-checklist.md`, following the same pattern used by
   existing template constants in the module.

This template gives reviewers a consistent output format and makes
review results machine-parseable and auditable alongside ticket files.

## Acceptance Criteria

- [ ] `templates/review-checklist.md` exists with correctness and quality sections
- [ ] Correctness section has pass/fail fields for each acceptance criterion
- [ ] Quality section has severity-ranked issue fields (critical, major, minor, suggestion)
- [ ] `REVIEW_CHECKLIST_TEMPLATE` constant added to `templates.py`
- [ ] Template is loadable via the templates module (follows existing pattern)

## Testing

- **Existing tests to run**: `uv run pytest` — template listing and loading tests must find the new template
- **New tests to write**: Test that `REVIEW_CHECKLIST_TEMPLATE` is non-empty and contains expected section headers
- **Verification command**: `uv run pytest`
