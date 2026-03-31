"""Tests for clasi.mcp_server module."""

from mcp.server.fastmcp import FastMCP

from clasi.mcp_server import server, content_path

# Trigger lazy tool registration (normally done by run_server)
import clasi.tools.process_tools  # noqa: F401
import clasi.tools.artifact_tools  # noqa: F401


class TestContentPath:
    def test_resolves_agents_directory(self):
        assert content_path("agents").is_dir()

    def test_resolves_skills_directory(self):
        assert content_path("skills").is_dir()

    def test_resolves_instructions_directory(self):
        assert content_path("instructions").is_dir()

    def test_resolves_nested_path(self):
        assert content_path("instructions", "languages").is_dir()

    def test_resolves_specific_file(self):
        # Agent files are now in the hierarchy: agents/main-controller/team-lead/agent.md
        assert content_path("agents", "main-controller", "team-lead", "agent.md").is_file()

    def test_resolves_rules_directory(self):
        assert content_path("rules").is_dir()


class TestServer:
    def test_server_instance_exists(self):
        assert server is not None

    def test_server_is_fastmcp(self):
        assert isinstance(server, FastMCP)

    def test_server_name(self):
        assert server.name == "clasi"


class TestToolRegistration:
    """Verify all expected MCP tools are registered on the server."""

    EXPECTED_PROCESS_TOOLS = {
        "get_se_overview",
        "list_agents",
        "list_skills",
        "list_instructions",
        "get_agent_definition",
        "get_agent_context",
        "get_skill_definition",
        "get_instruction",
        "list_language_instructions",
        "get_language_instruction",
        "get_activity_guide",
        "get_use_case_coverage",
        "get_version",
    }

    EXPECTED_ARTIFACT_TOOLS = {
        "create_sprint",
        "insert_sprint",
        "create_ticket",
        "create_overview",
        "list_sprints",
        "list_tickets",
        "get_sprint_status",
        "update_ticket_status",
        "move_ticket_to_done",
        "reopen_ticket",
        "close_sprint",
        "clear_sprint_recovery",
        "get_sprint_phase",
        "advance_sprint_phase",
        "record_gate_result",
        "acquire_execution_lock",
        "release_execution_lock",
        "list_todos",
        "move_todo_to_done",
        "create_github_issue",
        "close_github_issue",
        "list_github_issues",
        "read_artifact_frontmatter",
        "write_artifact_frontmatter",
        "tag_version",
        "review_sprint_pre_execution",
        "review_sprint_pre_close",
        "review_sprint_post_close",
    }

    EXPECTED_DISPATCH_TOOLS = {
        "dispatch_to_todo_worker",
        "dispatch_to_sprint_planner",
        "dispatch_to_sprint_executor",
        "dispatch_to_ad_hoc_executor",
        "dispatch_to_sprint_reviewer",
        "dispatch_to_architect",
        "dispatch_to_architecture_reviewer",
        "dispatch_to_technical_lead",
        "dispatch_to_code_monkey",
        "dispatch_to_code_reviewer",
    }

    EXPECTED_ALL = EXPECTED_PROCESS_TOOLS | EXPECTED_ARTIFACT_TOOLS | EXPECTED_DISPATCH_TOOLS

    def _registered_tool_names(self) -> set[str]:
        """Get the set of tool names registered on the server."""
        # FastMCP stores tools in _tool_manager._tools dict
        tools = server._tool_manager._tools
        return set(tools.keys())

    def test_all_expected_tools_registered(self):
        registered = self._registered_tool_names()
        missing = self.EXPECTED_ALL - registered
        assert not missing, f"Missing tools: {missing}"

    def test_no_unexpected_tools(self):
        registered = self._registered_tool_names()
        unexpected = registered - self.EXPECTED_ALL
        assert not unexpected, f"Unexpected tools: {unexpected}"

    def test_tool_count(self):
        registered = self._registered_tool_names()
        assert len(registered) == 51

    def test_process_tools_registered(self):
        registered = self._registered_tool_names()
        missing = self.EXPECTED_PROCESS_TOOLS - registered
        assert not missing, f"Missing process tools: {missing}"

    def test_artifact_tools_registered(self):
        registered = self._registered_tool_names()
        missing = self.EXPECTED_ARTIFACT_TOOLS - registered
        assert not missing, f"Missing artifact tools: {missing}"
