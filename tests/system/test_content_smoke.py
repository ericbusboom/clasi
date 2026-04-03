"""Smoke tests for MCP content access.

Verifies that the packaged content (agents, skills, instructions) is
accessible through the MCP tool functions and content_path resolver.
"""

import json

from clasi.mcp_server import content_path
from clasi.tools.process_tools import (
    list_agents,
    list_skills,
    list_instructions,
    get_agent_definition,
    get_instruction,
    get_skill_definition,
)


class TestContentSmoke:
    def test_agents_directory_has_md_files(self):
        agents_dir = content_path("plugin", "agents")
        md_files = list(agents_dir.rglob("agent.md"))
        assert len(md_files) > 0, "No agent.md files in agents directory tree"

    def test_list_agents_returns_content(self):
        result = json.loads(list_agents())
        assert isinstance(result, list)
        assert len(result) > 0
        assert all("name" in a and "description" in a for a in result)

    def test_list_skills_returns_content(self):
        result = json.loads(list_skills())
        assert isinstance(result, list)
        assert len(result) > 0
        assert all("name" in s and "description" in s for s in result)

    def test_list_instructions_returns_content(self):
        result = json.loads(list_instructions())
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_agent_returns_markdown(self):
        content = get_agent_definition("team-lead")
        assert "# " in content
        assert len(content) > 100

    def test_get_instruction_returns_markdown(self):
        content = get_instruction("coding-standards")
        assert "# " in content
        assert len(content) > 100

    def test_get_skill_returns_markdown(self):
        content = get_skill_definition("execute-ticket")
        assert "# " in content
        assert len(content) > 100

    def test_report_skill_exists(self):
        """Verify the report skill is discoverable and has proper content."""
        result = json.loads(list_skills())
        report_skills = [s for s in result if s["name"] == "report"]
        assert len(report_skills) == 1, "Report skill should exist"
        assert "GitHub issue" in report_skills[0]["description"]

    def test_report_skill_content(self):
        """Verify the report skill has proper markdown content."""
        content = get_skill_definition("report")
        assert "# Report Issue Skill" in content
        assert "gh issue create" in content
        assert "ericbusboom/clasi" in content
        assert len(content) > 500
