"""SE Process Access tools for the CLASI MCP server.

Read-only tools that serve agent, skill, and instruction content
from the installed package.
"""

import json
from pathlib import Path

from claude_agent_skills import __version__
from claude_agent_skills.frontmatter import read_document
from claude_agent_skills.mcp_server import server, content_path


def _list_definitions(directory: Path) -> list[dict[str, str]]:
    """List all .md files in a directory, returning name and description from frontmatter."""
    results = []
    if not directory.exists():
        return results
    for path in sorted(directory.glob("*.md")):
        fm, _ = read_document(path)
        results.append({
            "name": fm.get("name", path.stem),
            "description": fm.get("description", ""),
        })
    return results


def _get_definition(directory: Path, name: str) -> str:
    """Read the full content of a named .md file from a directory."""
    path = directory / f"{name}.md"
    if not path.exists():
        available = [p.stem for p in sorted(directory.glob("*.md"))]
        raise ValueError(
            f"'{name}' not found in {directory.name}/. "
            f"Available: {', '.join(available)}"
        )
    return path.read_text(encoding="utf-8")


@server.tool()
def get_se_overview() -> str:
    """Get a curated overview of the CLASI SE process.

    Returns a summary of the process stages, available agents and skills,
    and guidance on which MCP tools to use for each activity.
    """
    agents = _list_definitions(content_path("agents"))
    skills = _list_definitions(content_path("skills"))
    instructions = _list_definitions(content_path("instructions"))

    agent_lines = "\n".join(
        f"- **{a['name']}**: {a['description']}" for a in agents
    )
    skill_lines = "\n".join(
        f"- **{s['name']}**: {s['description']}" for s in skills
    )
    instruction_lines = "\n".join(
        f"- **{i['name']}**: {i['description']}" for i in instructions
    )

    return f"""# CLASI SE Process Overview

## Process Stages

1. **Stage 1a — Requirements**: Elicit requirements, produce brief and use cases
   - Skill: `elicit-requirements` | Agent: `requirements-analyst`
2. **Stage 1b — Architecture**: Design architecture, produce architecture document
   - Skill: `plan-sprint` (architecture step) | Agent: `architect`
3. **Sprints**: Organize work into sprint directories with planning docs and tickets
   - Skills: `plan-sprint`, `close-sprint` | Agent: `project-manager`
4. **Stage 2 — Ticketing**: Break plan into numbered tickets
   - Skill: `create-tickets` | Agent: `technical-lead`
5. **Stage 3 — Implementation**: Execute tickets (plan → implement → test → review → done)
   - Skill: `execute-ticket` | Agents: `python-expert`, `code-reviewer`, `documentation-expert`

## Available Agents

{agent_lines}

## Available Skills

{skill_lines}

## Available Instructions

{instruction_lines}

## MCP Tools Quick Reference

### SE Process Access (this tool group)
- `get_se_overview()` — This overview
- `get_activity_guide(activity)` — Tailored guidance for a specific activity
- `list_agents()` / `get_agent_definition(name)` — Agent definitions
- `list_skills()` / `get_skill_definition(name)` — Skill definitions
- `list_instructions()` / `get_instruction(name)` — Instruction files

### Artifact Management
- `create_sprint(title)` / `list_sprints()` / `get_sprint_status(sprint_id)` — Sprint management
- `create_ticket(sprint_id, title)` / `list_tickets()` — Ticket management
- `update_ticket_status(path, status)` / `move_ticket_to_done(path)` — Ticket lifecycle
- `close_sprint(sprint_id)` — Sprint closure
- `create_brief()` / `create_use_cases()` — Top-level artifacts
"""


@server.tool()
def list_agents() -> str:
    """List all available agent definitions.

    Returns a JSON array of objects with 'name' and 'description' fields.
    """
    return json.dumps(_list_definitions(content_path("agents")), indent=2)


@server.tool()
def list_skills() -> str:
    """List all available skill definitions.

    Returns a JSON array of objects with 'name' and 'description' fields.
    """
    return json.dumps(_list_definitions(content_path("skills")), indent=2)


@server.tool()
def list_instructions() -> str:
    """List all available instruction files.

    Returns a JSON array of objects with 'name' and 'description' fields.
    """
    return json.dumps(_list_definitions(content_path("instructions")), indent=2)


@server.tool()
def get_agent_definition(name: str) -> str:
    """Get the full markdown content of a named agent definition.

    Args:
        name: The agent name (e.g., 'project-manager', 'python-expert')
    """
    return _get_definition(content_path("agents"), name)


@server.tool()
def get_skill_definition(name: str) -> str:
    """Get the full markdown content of a named skill definition.

    Args:
        name: The skill name (e.g., 'execute-ticket', 'plan-sprint')
    """
    return _get_definition(content_path("skills"), name)


@server.tool()
def get_instruction(name: str) -> str:
    """Get the full markdown content of a named instruction file.

    Args:
        name: The instruction name (e.g., 'software-engineering', 'coding-standards')
    """
    return _get_definition(content_path("instructions"), name)


@server.tool()
def list_language_instructions() -> str:
    """List all available language instruction files.

    Returns a JSON array of objects with 'name' and 'description' fields.
    """
    return json.dumps(_list_definitions(content_path("instructions", "languages")), indent=2)


@server.tool()
def get_language_instruction(language: str) -> str:
    """Get the full markdown content of a language instruction file.

    Args:
        language: The language name (e.g., 'python')
    """
    return _get_definition(content_path("instructions", "languages"), language)


# Activity guide configuration: maps activity names to their relevant
# agent, skill, and instruction files.
ACTIVITY_GUIDES: dict[str, dict[str, list[str]]] = {
    "requirements": {
        "agents": ["requirements-analyst"],
        "skills": ["elicit-requirements"],
        "instructions": ["software-engineering"],
    },
    "architecture": {
        "agents": ["architect"],
        "skills": ["plan-sprint"],
        "instructions": ["software-engineering"],
    },
    "ticketing": {
        "agents": ["technical-lead"],
        "skills": ["create-tickets"],
        "instructions": ["software-engineering"],
    },
    "implementation": {
        "agents": ["python-expert", "technical-lead"],
        "skills": ["execute-ticket"],
        "instructions": ["software-engineering", "coding-standards", "languages/python", "testing", "git-workflow"],
    },
    "testing": {
        "agents": ["python-expert"],
        "skills": ["execute-ticket"],
        "instructions": ["testing", "coding-standards", "languages/python"],
    },
    "code-review": {
        "agents": ["code-reviewer"],
        "skills": ["execute-ticket"],
        "instructions": ["coding-standards", "languages/python", "testing"],
    },
    "sprint-planning": {
        "agents": ["project-manager", "architecture-reviewer"],
        "skills": ["plan-sprint"],
        "instructions": ["software-engineering", "git-workflow"],
    },
    "sprint-closing": {
        "agents": ["project-manager"],
        "skills": ["close-sprint"],
        "instructions": ["software-engineering", "git-workflow"],
    },
}


@server.tool()
def get_activity_guide(activity: str) -> str:
    """Get tailored guidance for a specific SE activity.

    Combines the relevant agent definition(s), skill workflow, and
    instruction content into a single curated response.

    Args:
        activity: One of: requirements, architecture, ticketing,
            implementation, testing, code-review, sprint-planning,
            sprint-closing
    """
    if activity not in ACTIVITY_GUIDES:
        available = ", ".join(sorted(ACTIVITY_GUIDES.keys()))
        raise ValueError(
            f"Unknown activity '{activity}'. "
            f"Available activities: {available}"
        )

    guide = ACTIVITY_GUIDES[activity]
    sections = []

    sections.append(f"# Activity Guide: {activity}\n")

    # Agent definitions
    for agent_name in guide["agents"]:
        content = _get_definition(content_path("agents"), agent_name)
        sections.append(f"## Agent: {agent_name}\n\n{content}")

    # Skill workflows
    for skill_name in guide["skills"]:
        content = _get_definition(content_path("skills"), skill_name)
        sections.append(f"## Skill: {skill_name}\n\n{content}")

    # Instructions
    for instr_name in guide["instructions"]:
        content = _get_definition(content_path("instructions"), instr_name)
        sections.append(f"## Instruction: {instr_name}\n\n{content}")

    return "\n\n---\n\n".join(sections)


# --- Use case traceability (ticket 009, sprint 002) ---


def _parse_parent_refs(content: str) -> list[str]:
    """Extract Parent: UC-XXX references from use case content."""
    import re
    return re.findall(r"Parent:\s*((?:UC|SC)-\d+)", content)


@server.tool()
def get_use_case_coverage() -> str:
    """Report use case coverage across sprints.

    Reads top-level use cases and each sprint's use cases,
    matching parent references to report which top-level use cases
    are covered by completed, active, or planned sprints.

    Returns JSON with coverage data.
    """
    plans_dir = Path.cwd() / "docs" / "plans"
    sprints_dir = plans_dir / "sprints"

    # Read top-level use cases
    top_level = {}
    top_uc_file = plans_dir / "usecases.md"
    if top_uc_file.exists():
        _, content = read_document(top_uc_file)
        import re
        for match in re.finditer(r"##\s+(UC-\d+):\s*(.+)", content):
            top_level[match.group(1)] = {
                "title": match.group(2).strip(),
                "covered_by": [],
            }

    # Scan sprint use cases for parent references
    for location in [sprints_dir, sprints_dir / "done"]:
        if not location.exists():
            continue
        for sprint_dir in sorted(location.iterdir()):
            if not sprint_dir.is_dir():
                continue
            sprint_file = sprint_dir / "sprint.md"
            uc_file = sprint_dir / "usecases.md"
            if not sprint_file.exists():
                continue

            from claude_agent_skills.frontmatter import read_frontmatter
            sprint_fm = read_frontmatter(sprint_file)
            sprint_id = sprint_fm.get("id", "")
            sprint_status = sprint_fm.get("status", "unknown")

            if uc_file.exists():
                _, uc_content = read_document(uc_file)
                parents = _parse_parent_refs(uc_content)
                for parent_id in set(parents):
                    if parent_id in top_level:
                        top_level[parent_id]["covered_by"].append({
                            "sprint_id": sprint_id,
                            "sprint_status": sprint_status,
                        })

    # Build coverage report
    covered = []
    uncovered = []
    for uc_id, info in sorted(top_level.items()):
        entry = {"id": uc_id, "title": info["title"], "sprints": info["covered_by"]}
        if info["covered_by"]:
            covered.append(entry)
        else:
            uncovered.append(entry)

    return json.dumps({
        "total_use_cases": len(top_level),
        "covered": covered,
        "uncovered": uncovered,
    }, indent=2)


@server.tool()
def get_version() -> str:
    """Return the installed CLASI package version.

    Useful for verifying which version of the MCP server is running.
    """
    return json.dumps({
        "version": __version__,
    }, indent=2)
