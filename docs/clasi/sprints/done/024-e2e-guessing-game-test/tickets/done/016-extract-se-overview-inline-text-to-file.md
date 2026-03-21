---
id: "016"
title: "Extract SE overview inline text to file"
status: done
use-cases: [SUC-003]
depends-on: []
github-issue: ""
todo: "extract-se-overview-inline-text-to-file.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Extract SE overview inline text to file

## Description

`get_se_overview()` in `claude_agent_skills/process_tools.py` contains
hardcoded inline text for two sections: Process Stages (a numbered list
describing the five stages and which skills/agents map to each) and MCP
Tools Quick Reference (a categorized list of all MCP tools and their
signatures).

The stakeholder directive is: "get_se_overview() should not have any
inline process overview. All text like this must be removed from the
code and read from a file."

The dynamically generated sections (agent/skill/instruction listings)
are fine -- those are built from frontmatter at runtime. The problem is
the static prose that is baked into the Python source.

### Changes

#### 1. Create content files

Create content files in `claude_agent_skills/content/` (or a suitable
location within the package) for the static text sections:

- `process-stages.md` -- the Process Stages section text
- `tools-reference.md` -- the MCP Tools Quick Reference section text

#### 2. Update get_se_overview()

Modify `get_se_overview()` in `process_tools.py` to:
- Read the static text from the content files at runtime
- Interpolate the dynamic sections (agent/skill/instruction listings)
  into the appropriate positions
- Remove all inline static prose from the Python source

#### 3. Verify output is unchanged

The rendered output of `get_se_overview()` must remain identical after
the refactor. The change is purely structural -- extracting inline text
to files -- with no functional difference in the tool's return value.

## Acceptance Criteria

- [x] Static Process Stages text extracted from `process_tools.py` to a content file
- [x] Static MCP Tools Quick Reference text extracted from `process_tools.py` to a content file
- [x] `get_se_overview()` reads static text from files at runtime
- [x] `get_se_overview()` output is identical before and after the change
- [x] No inline static prose remains in the `get_se_overview()` function body
- [x] `uv run pytest` passes with no regressions

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**:
  - Unit test: `get_se_overview()` output matches a known-good snapshot (or diff against pre-refactor output)
  - Unit test: Content files exist and are non-empty
  - Unit test: `get_se_overview()` raises a clear error if content files are missing
- **Verification command**: `uv run pytest`
