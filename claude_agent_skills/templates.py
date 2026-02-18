"""
Artifact templates for sprints, tickets, briefs, technical plans, and use cases.

Templates use str.format() with named placeholders for dynamic values.
"""

import re
import unicodedata


def slugify(title: str) -> str:
    """Convert a title to a filesystem-safe slug.

    >>> slugify("Add User Authentication")
    'add-user-authentication'
    >>> slugify("MCP Server & Tools!")
    'mcp-server-tools'
    """
    # Normalize unicode, lowercase
    s = unicodedata.normalize("NFKD", title).lower()
    # Replace non-alphanumeric with hyphens
    s = re.sub(r"[^a-z0-9]+", "-", s)
    # Strip leading/trailing hyphens
    s = s.strip("-")
    return s


SPRINT_TEMPLATE = """\
---
id: "{id}"
title: {title}
status: planning
branch: sprint/{id}-{slug}
use-cases: []
---

# Sprint {id}: {title}

## Goals

(Describe what this sprint aims to accomplish.)

## Problem

(What problem does this sprint address?)

## Solution

(High-level description of the approach.)

## Success Criteria

(How will we know the sprint succeeded?)

## Scope

### In Scope

(List what is included in this sprint.)

### Out of Scope

(List what is explicitly excluded.)

## Test Strategy

(Describe the overall testing approach for this sprint: what types of tests,
what areas need coverage, any integration or system-level testing needed.)

## Architecture Notes

(Key design decisions and constraints.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, technical plan)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

(To be created after sprint approval.)
"""

SPRINT_BRIEF_TEMPLATE = """\
---
status: draft
---

# Sprint {id} Brief

## Problem

(What problem does this sprint address?)

## Solution

(High-level description of the approach.)

## Success Criteria

(How will we know the sprint succeeded?)
"""

SPRINT_USECASES_TEMPLATE = """\
---
status: draft
---

# Sprint {id} Use Cases

## SUC-001: (Title)
Parent: UC-XXX

- **Actor**: (Who)
- **Preconditions**: (What must be true before)
- **Main Flow**:
  1. (Step)
- **Postconditions**: (What is true after)
- **Acceptance Criteria**:
  - [ ] (Criterion)
"""

SPRINT_TECHNICAL_PLAN_TEMPLATE = """\
---
status: draft
from-architecture-version: null
to-architecture-version: null
---

# Sprint {id} Technical Plan

## Architecture Version

- **From version**: (current architecture version, e.g., architecture-014)
- **To version**: (target architecture version, or "no change" for bug-fix sprints)

## Architecture Overview

(How the components fit together.)

## Component Design

### Component: (Name)

**Use Cases**: (SUC-NNN)

(Description, key functions, interfaces.)

## Open Questions

(Unresolved design decisions.)
"""

TICKET_TEMPLATE = """\
---
id: "{id}"
title: {title}
status: todo
use-cases: []
depends-on: []
---

# {title}

## Description

(What needs to be done and why.)

## Acceptance Criteria

- [ ] (Criterion)

## Testing

- **Existing tests to run**: (list test files/commands to verify no regressions)
- **New tests to write**: (describe tests that validate this ticket's changes)
- **Verification command**: `uv run pytest`
"""

OVERVIEW_TEMPLATE = """\
---
status: draft
---

# Project Overview

## Project Name

(Name)

## Problem Statement

(What problem does this project solve? Who has this problem?)

## Target Users

(Who will use this system?)

## Key Constraints

(Timeline, technology, budget, team size.)

## High-Level Requirements

(Key scenarios the system must support. Detailed scenarios live in sprints.)

## Technology Stack

(Languages, frameworks, infrastructure.)

## Sprint Roadmap

(Rough plan of sprints — what will be tackled in what order.)

## Out of Scope

(What is explicitly excluded from this project.)
"""
