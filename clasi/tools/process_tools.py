"""SE Process Access tools for the CLASI MCP server.

Read-only tools that serve agent, skill, and instruction content
from the installed package.
"""

import json
from pathlib import Path

from clasi import __version__
from clasi.frontmatter import read_document
from clasi.mcp_server import server, content_path, get_project


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


def _list_agents_recursive(agents_dir: Path) -> list[dict[str, str]]:
    """Walk the three-tier agent directory tree and list all agents.

    Finds all agent.md files under agents/{tier}/{agent-name}/agent.md.
    """
    results = []
    if not agents_dir.exists():
        return results
    for agent_md in sorted(agents_dir.rglob("agent.md")):
        fm, _ = read_document(agent_md)
        # Agent name comes from the parent directory name
        agent_name = agent_md.parent.name
        results.append({
            "name": fm.get("name", agent_name),
            "description": fm.get("description", ""),
        })
    return results


def _find_agent_dir(agents_dir: Path, name: str) -> Path | None:
    """Find the directory for a named agent in the tree."""
    if not agents_dir.exists():
        return None
    for agent_md in agents_dir.rglob("agent.md"):
        agent_name = agent_md.parent.name
        fm, _ = read_document(agent_md)
        if agent_name == name or fm.get("name") == name:
            return agent_md.parent
    return None


def _list_all_skills(skills_dir: Path, agents_dir: Path) -> list[dict[str, str]]:
    """List skills from both global skills/ and agent subdirectories."""
    results = _list_definitions(skills_dir)
    # Also include skills in subdirectories (SKILL.md pattern)
    if skills_dir.exists():
        for skill_md in sorted(skills_dir.rglob("SKILL.md")):
            fm, _ = read_document(skill_md)
            if fm.get("name") or fm.get("description"):
                results.append({
                    "name": fm.get("name", skill_md.parent.name),
                    "description": fm.get("description", ""),
                })
    if agents_dir.exists():
        for md_path in sorted(agents_dir.rglob("*.md")):
            if md_path.name == "agent.md":
                continue
            if md_path.name.endswith("-legacy.md"):
                continue
            fm, _ = read_document(md_path)
            # Only include files that look like skills (have a name in frontmatter
            # or are .md files that aren't agent definitions)
            if fm.get("name") or fm.get("description"):
                results.append({
                    "name": fm.get("name", md_path.stem),
                    "description": fm.get("description", ""),
                })
    return sorted(results, key=lambda x: x["name"])


def _find_definition_in_tree(agents_dir: Path, skills_dir: Path,
                              instructions_dir: Path, name: str) -> str | None:
    """Search for a named definition across agents, skills, and instructions."""
    # Check global skills
    path = skills_dir / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    # Check global instructions
    path = instructions_dir / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    # Search agent directories
    if agents_dir.exists():
        for md_path in agents_dir.rglob(f"{name}.md"):
            return md_path.read_text(encoding="utf-8")
    return None


def _get_definition(directory: Path, name: str) -> str:
    """Read the full content of a named .md file.

    Searches the given directory first, then falls back to searching
    the agent tree if the directory is agents/.
    """
    # Direct lookup
    path = directory / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")

    # For agents, search the tree for agent.md in a matching directory
    if directory.name == "agents":
        agent_dir = _find_agent_dir(directory, name)
        if agent_dir:
            return (agent_dir / "agent.md").read_text(encoding="utf-8")

    # Search recursively in the directory
    matches = list(directory.rglob(f"{name}.md"))
    if matches:
        return matches[0].read_text(encoding="utf-8")

    # Build available list for error message
    if directory.name == "agents":
        available = [d["name"] for d in _list_agents_recursive(directory)]
    else:
        available = [p.stem for p in sorted(directory.glob("*.md"))]
    raise ValueError(
        f"'{name}' not found in {directory.name}/. "
        f"Available: {', '.join(available)}"
    )


_SE_OVERVIEW_TEMPLATE_PATH = Path(__file__).parent.parent / "se-overview-template.md"


def get_se_overview() -> str:
    """Get a curated overview of the CLASI SE process.

    Returns a summary of the process stages, available agents and skills,
    and guidance on which MCP tools to use for each activity.
    """
    if not _SE_OVERVIEW_TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"SE overview template not found: {_SE_OVERVIEW_TEMPLATE_PATH}"
        )

    template = _SE_OVERVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")

    agents = _list_definitions(content_path("plugin", "agents"))
    skills = _list_definitions(content_path("plugin", "skills"))
    instructions = _list_definitions(content_path("plugin", "instructions"))

    agent_lines = "\n".join(
        f"- **{a['name']}**: {a['description']}" for a in agents
    )
    skill_lines = "\n".join(
        f"- **{s['name']}**: {s['description']}" for s in skills
    )
    instruction_lines = "\n".join(
        f"- **{i['name']}**: {i['description']}" for i in instructions
    )

    return template.format(
        agent_lines=agent_lines,
        skill_lines=skill_lines,
        instruction_lines=instruction_lines,
    )


#@server.tool()
def list_agents() -> str:
    """List all available agent definitions.

    Walks the three-tier agent directory hierarchy to find all agent.md files.
    Returns a JSON array of objects with 'name' and 'description' fields.
    """
    return json.dumps(_list_agents_recursive(content_path("plugin", "agents")), indent=2)


#@server.tool()
def list_skills() -> str:
    """List all available skill definitions.

    Includes both global skills and agent-specific skills from the
    agent directory hierarchy.
    Returns a JSON array of objects with 'name' and 'description' fields.
    """
    return json.dumps(
        _list_all_skills(content_path("plugin", "skills"), content_path("plugin", "agents")),
        indent=2,
    )


#@server.tool()
def list_instructions() -> str:
    """List all available instruction files.

    Returns a JSON array of objects with 'name' and 'description' fields.
    """
    return json.dumps(_list_definitions(content_path("plugin", "instructions")), indent=2)


#@server.tool()
def get_agent_definition(name: str) -> str:
    """Get the full markdown content of a named agent definition.

    Returns the agent.md content. If a contract.yaml exists alongside
    the agent.md, its content is appended as a YAML-fenced section.

    Args:
        name: The agent name (e.g., 'code-monkey', 'sprint-planner')
    """
    agent_content = _get_definition(content_path("plugin", "agents"), name)

    # Try to find and append contract.yaml
    agents_dir = content_path("plugin", "agents")
    agent_dir = _find_agent_dir(agents_dir, name)
    if agent_dir:
        contract_path = agent_dir / "contract.yaml"
        if contract_path.exists():
            contract_text = contract_path.read_text(encoding="utf-8")
            agent_content += (
                "\n\n---\n\n"
                "## Contract\n\n"
                "```yaml\n"
                f"{contract_text}"
                "```\n"
            )

    return agent_content


#@server.tool()
def get_skill_definition(name: str) -> str:
    """Get the full markdown content of a named skill definition.

    Searches global skills first, then agent directories.

    Args:
        name: The skill name (e.g., 'execute-ticket', 'plan-sprint')
    """
    # Try global skills: direct .md file or subdirectory SKILL.md
    skills_dir = content_path("plugin", "skills")
    path = skills_dir / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    skill_md = skills_dir / name / "SKILL.md"
    if skill_md.exists():
        return skill_md.read_text(encoding="utf-8")
    # Search agent directories
    agents_dir = content_path("plugin", "agents")
    if agents_dir.exists():
        matches = list(agents_dir.rglob(f"{name}.md"))
        if matches:
            return matches[0].read_text(encoding="utf-8")
    raise ValueError(
        f"'{name}' not found in skills/ or agent directories."
    )



#@server.tool()
def get_instruction(name: str) -> str:
    """Get the full markdown content of a named instruction file.

    Args:
        name: The instruction name (e.g., 'software-engineering', 'coding-standards')
    """
    return _get_definition(content_path("plugin", "instructions"), name)


#@server.tool()
def list_language_instructions() -> str:
    """List all available language instruction files.

    Returns a JSON array of objects with 'name' and 'description' fields.
    """
    return json.dumps(_list_definitions(content_path("plugin", "instructions", "languages")), indent=2)


#@server.tool()
def get_language_instruction(language: str) -> str:
    """Get the full markdown content of a language instruction file.

    Args:
        language: The language name (e.g., 'python')
    """
    return _get_definition(content_path("plugin", "instructions", "languages"), language)


# Activity guide configuration: maps activity names to their relevant
# agent, skill, and instruction files.
ACTIVITY_GUIDES: dict[str, dict[str, list[str]]] = {
    "requirements": {
        "agents": ["project-manager"],
        "skills": [],
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
        "agents": ["programmer", "technical-lead"],
        "skills": ["execute-ticket"],
        "instructions": ["software-engineering", "coding-standards", "testing", "git-workflow"],
    },
    "testing": {
        "agents": ["programmer"],
        "skills": ["execute-ticket"],
        "instructions": ["testing", "coding-standards"],
    },
    "code-review": {
        "agents": ["code-reviewer"],
        "skills": ["execute-ticket"],
        "instructions": ["coding-standards", "testing"],
    },
    "sprint-planning": {
        "agents": ["sprint-planner", "architecture-reviewer"],
        "skills": ["plan-sprint"],
        "instructions": ["software-engineering", "git-workflow"],
    },
    "sprint-closing": {
        "agents": ["sprint-executor"],
        "skills": ["close-sprint"],
        "instructions": ["software-engineering", "git-workflow"],
    },
}


#@server.tool()
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
        try:
            content = _get_definition(content_path("plugin", "agents"), agent_name)
            sections.append(f"## Agent: {agent_name}\n\n{content}")
        except ValueError:
            sections.append(f"## Agent: {agent_name}\n\n(Agent definition not found)")

    # Skill workflows
    for skill_name in guide["skills"]:
        try:
            content = get_skill_definition(skill_name)
            sections.append(f"## Skill: {skill_name}\n\n{content}")
        except ValueError:
            sections.append(f"## Skill: {skill_name}\n\n(Skill definition not found)")

    # Instructions
    for instr_name in guide["instructions"]:
        content = _get_definition(content_path("plugin", "instructions"), instr_name)
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
    project = get_project()
    plans_dir = project.clasi_dir
    if not plans_dir.is_dir():
        legacy = project.root / "docs" / "plans"
        if legacy.is_dir():
            legacy.rename(plans_dir)
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

            from clasi.frontmatter import read_frontmatter
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
