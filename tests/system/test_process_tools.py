"""Tests for clasi.tools.process_tools module."""

import json

import pytest

from clasi.tools.process_tools import (
    _list_definitions,
    _get_definition,
    _parse_parent_refs,
    get_se_overview,
    get_use_case_coverage,
    get_version,
    list_agents,
    list_skills,
    list_instructions,
    get_agent_definition,
    get_skill_definition,
    get_instruction,
    get_activity_guide,
    list_language_instructions,
    get_language_instruction,
    ACTIVITY_GUIDES,
)
from clasi.mcp_server import content_path, set_project


class TestListDefinitions:
    def test_lists_agents(self):
        from clasi.tools.process_tools import _list_agents_recursive
        results = _list_agents_recursive(content_path("plugin", "agents"))
        names = [r["name"] for r in results]
        assert "team-lead" in names or "project-manager" in names
        assert "programmer" in names or "architect" in names
        assert all(r["description"] for r in results)

    def test_empty_dir(self, tmp_path):
        results = _list_definitions(tmp_path / "nonexistent")
        assert results == []


class TestGetDefinition:
    def test_gets_agent(self):
        content = _get_definition(content_path("plugin", "agents"), "team-lead")
        assert "team-lead" in content

    def test_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            _get_definition(content_path("plugin", "agents"), "nonexistent-agent")


class TestMCPTools:
    def test_get_se_overview(self):
        result = get_se_overview()
        assert "CLASI SE Process Overview" in result
        # Check for agents (may be old or new names depending on migration)
        assert "execute-ticket" in result

    def test_list_agents(self):
        result = json.loads(list_agents())
        assert isinstance(result, list)
        assert any(a["name"] == "team-lead" for a in result)

    def test_list_skills(self):
        result = json.loads(list_skills())
        assert isinstance(result, list)
        assert any(s["name"] == "execute-ticket" for s in result)

    def test_list_instructions(self):
        result = json.loads(list_instructions())
        assert isinstance(result, list)
        assert any(i["name"] == "software-engineering" for i in result)

    def test_get_agent_definition(self):
        result = get_agent_definition("team-lead")
        assert "team-lead" in result

    def test_get_skill_definition(self):
        result = get_skill_definition("execute-ticket")
        assert "Execute Ticket" in result

    def test_get_instruction(self):
        result = get_instruction("software-engineering")
        assert "Software Engineering" in result


class TestLanguageInstructions:
    def test_list_language_instructions(self):
        result = json.loads(list_language_instructions())
        assert isinstance(result, list)
        assert any(lang["name"] == "python" for lang in result)
        python_entry = next(l for l in result if l["name"] == "python")
        assert python_entry["description"]

    def test_get_language_instruction_python(self):
        result = get_language_instruction("python")
        assert "Python Language Instructions" in result
        assert "Virtual Environments" in result
        assert "uv" in result
        assert "pyproject.toml" in result
        assert "Type Hints" in result
        assert "pytest" in result

    def test_get_language_instruction_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            get_language_instruction("nonexistent-language")


class TestActivityGuide:
    def test_all_activities_valid(self):
        for activity in ACTIVITY_GUIDES:
            result = get_activity_guide(activity)
            assert f"Activity Guide: {activity}" in result

    def test_unknown_activity(self):
        with pytest.raises(ValueError, match="Unknown activity"):
            get_activity_guide("nonexistent")

    def test_implementation_guide_contains_all_sections(self):
        result = get_activity_guide("implementation")
        assert "Agent: programmer" in result
        assert "Skill: execute-ticket" in result
        assert "Instruction: coding-standards" in result
        assert "Instruction: testing" in result


class TestParseParentRefs:
    def test_parses_uc_refs(self):
        content = "Parent: UC-001\nSome text\nParent: UC-002\n"
        assert _parse_parent_refs(content) == ["UC-001", "UC-002"]

    def test_parses_sc_refs(self):
        content = "Parent: SC-001\n"
        assert _parse_parent_refs(content) == ["SC-001"]

    def test_no_refs(self):
        assert _parse_parent_refs("No parent references here.") == []

    def test_mixed_content(self):
        content = "## SUC-001: Feature\nParent: UC-003\n\n- Step 1\n"
        assert _parse_parent_refs(content) == ["UC-003"]


class TestGetUseCaseCoverage:
    def _setup_project(self, tmp_path, *, top_level_ucs, sprints=None):
        """Create a project structure for use case coverage testing."""
        plans = tmp_path / "docs" / "clasi"
        plans.mkdir(parents=True)

        # Write top-level use cases
        uc_lines = []
        for uc_id, title in top_level_ucs.items():
            uc_lines.append(f"## {uc_id}: {title}\n\nDescription.\n")
        (plans / "usecases.md").write_text(
            "---\nstatus: draft\n---\n\n# Use Cases\n\n" + "\n".join(uc_lines)
        )

        # Create sprint directories
        if sprints:
            for sprint in sprints:
                loc = sprint.get("location", "active")
                if loc == "done":
                    sprint_dir = plans / "sprints" / "done" / sprint["dir"]
                else:
                    sprint_dir = plans / "sprints" / sprint["dir"]
                sprint_dir.mkdir(parents=True)
                (sprint_dir / "sprint.md").write_text(
                    f"---\nid: \"{sprint['id']}\"\nstatus: {sprint['status']}\n---\n"
                )
                if sprint.get("parents"):
                    parent_lines = "\n".join(
                        f"Parent: {p}" for p in sprint["parents"]
                    )
                    (sprint_dir / "usecases.md").write_text(
                        f"---\nstatus: draft\n---\n\n## SUC-001\n{parent_lines}\n"
                    )

    def test_covered_and_uncovered(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        self._setup_project(tmp_path, top_level_ucs={
            "UC-001": "Authentication",
            "UC-002": "Authorization",
            "UC-003": "Logging",
        }, sprints=[
            {
                "dir": "001-auth",
                "id": "001",
                "status": "planning",
                "parents": ["UC-001"],
            },
        ])

        result = json.loads(get_use_case_coverage())
        assert result["total_use_cases"] == 3
        assert len(result["covered"]) == 1
        assert result["covered"][0]["id"] == "UC-001"
        assert result["covered"][0]["sprints"][0]["sprint_id"] == "001"
        assert len(result["uncovered"]) == 2
        uncovered_ids = [u["id"] for u in result["uncovered"]]
        assert "UC-002" in uncovered_ids
        assert "UC-003" in uncovered_ids

    def test_done_sprint_coverage(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        self._setup_project(tmp_path, top_level_ucs={
            "UC-001": "Feature A",
        }, sprints=[
            {
                "dir": "001-done-sprint",
                "id": "001",
                "status": "done",
                "location": "done",
                "parents": ["UC-001"],
            },
        ])

        result = json.loads(get_use_case_coverage())
        assert result["total_use_cases"] == 1
        assert len(result["covered"]) == 1
        assert result["covered"][0]["sprints"][0]["sprint_status"] == "done"

    def test_no_usecases_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        (tmp_path / "docs" / "clasi").mkdir(parents=True)
        result = json.loads(get_use_case_coverage())
        assert result["total_use_cases"] == 0
        assert result["covered"] == []
        assert result["uncovered"] == []

    def test_empty_usecases_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)
        plans = tmp_path / "docs" / "clasi"
        plans.mkdir(parents=True)
        (plans / "usecases.md").write_text("---\nstatus: draft\n---\n\n# Use Cases\n")
        result = json.loads(get_use_case_coverage())
        assert result["total_use_cases"] == 0


class TestSeOverviewTemplate:
    """Tests for the SE overview template extraction (ticket 016)."""

    def test_template_file_exists_and_non_empty(self):
        from clasi.tools.process_tools import _SE_OVERVIEW_TEMPLATE_PATH
        assert _SE_OVERVIEW_TEMPLATE_PATH.exists(), "SE overview template file must exist"
        content = _SE_OVERVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert len(content) > 0, "SE overview template file must not be empty"

    def test_template_contains_placeholders(self):
        from clasi.tools.process_tools import _SE_OVERVIEW_TEMPLATE_PATH
        content = _SE_OVERVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "{agent_lines}" in content
        assert "{skill_lines}" in content
        assert "{instruction_lines}" in content

    def test_template_contains_static_sections(self):
        from clasi.tools.process_tools import _SE_OVERVIEW_TEMPLATE_PATH
        content = _SE_OVERVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "## Process Stages" in content
        assert "## MCP Tools Quick Reference" in content
        assert "Sprint Execution" in content

    def test_overview_output_contains_expected_sections(self):
        result = get_se_overview()
        assert "# CLASI SE Process Overview" in result
        assert "## Process Stages" in result
        assert "## Available Agents" in result
        assert "## Available Skills" in result
        assert "## Available Instructions" in result
        assert "## MCP Tools Quick Reference" in result

    def test_no_inline_static_prose_in_function(self):
        """Verify the function body no longer contains static prose."""
        import inspect
        source = inspect.getsource(get_se_overview)
        # Should not contain the literal static text anymore
        assert "Sprint Execution" not in source
        assert "Artifact Management" not in source

    def test_missing_template_raises_clear_error(self, tmp_path, monkeypatch):
        """get_se_overview raises FileNotFoundError if template is missing."""
        import clasi.tools.process_tools as pt
        original = pt._SE_OVERVIEW_TEMPLATE_PATH
        monkeypatch.setattr(pt, "_SE_OVERVIEW_TEMPLATE_PATH", tmp_path / "nonexistent.md")
        with pytest.raises(FileNotFoundError, match="SE overview template not found"):
            get_se_overview()
        monkeypatch.setattr(pt, "_SE_OVERVIEW_TEMPLATE_PATH", original)


class TestGetVersion:
    def test_returns_version_json(self):
        result = json.loads(get_version())
        assert "version" in result
        # Version should be a non-empty string
        assert isinstance(result["version"], str)
        assert len(result["version"]) > 0
