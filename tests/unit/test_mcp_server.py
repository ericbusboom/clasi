"""Tests for clasi.mcp_server module.

NONE-sentinel stripping, the mcp-calls.jsonl trace, and the uniform tool
envelope moved to clasi.tools._common (@clasi_tool) in sprint 030 ticket
005 -- their tests moved with them, to tests/unit/test_tools_common.py.
This file no longer imports or tests them; the old
_build_logged_call_tool wrapper they were reachable through was removed
from mcp_server.py in the same ticket (its NONE-stripping/call-logging
duties are now @clasi_tool's).
"""

from mcp.server.mcpserver import MCPServer

from clasi.mcp_server import server, content_path

# Trigger lazy tool registration (normally done by run_server)
import clasi.tools.process_tools  # noqa: F401
import clasi.tools.artifact_tools  # noqa: F401
import clasi.tools.design_tools  # noqa: F401


class TestContentPath:
    def test_resolves_agents_directory(self):
        assert content_path("plugin", "agents").is_dir()

    def test_resolves_skills_directory(self):
        assert content_path("plugin", "skills").is_dir()

    def test_resolves_instructions_directory(self):
        assert content_path("plugin", "instructions").is_dir()

    def test_resolves_nested_path(self):
        assert content_path("plugin", "instructions", "languages").is_dir()

    def test_resolves_specific_file(self):
        # Agent files are now in the flat hierarchy: plugin/agents/team-lead/agent.md
        assert content_path("plugin", "agents", "team-lead", "agent.md").is_file()

    def test_resolves_rules_directory(self):
        assert content_path("plugin", "rules").is_dir()

    def test_tool_call_empty_args_rule_exists(self):
        rule = content_path("plugin", "rules", "tool-call-empty-args.md")
        assert rule.is_file()
        content = rule.read_text(encoding="utf-8")
        assert 'paths: ["**"]' in content
        assert "NONE" in content


class TestServer:
    def test_server_instance_exists(self):
        assert server is not None

    def test_server_is_mcpserver(self):
        assert isinstance(server, MCPServer)

    def test_server_name(self):
        assert server.name == "clasi"


class TestToolRegistration:
    """Verify all expected MCP tools are registered on the server."""

    EXPECTED_PROCESS_TOOLS = {
        "get_use_case_coverage",
        "get_version",
        "get_status",
        "list_agents",
        "list_skills",
        "list_instructions",
        "get_agent_definition",
        "get_skill_definition",
        "get_instruction",
        "list_language_instructions",
        "get_language_instruction",
        "get_activity_guide",
    }

    EXPECTED_ARTIFACT_TOOLS = {
        "create_sprint",
        "detail_sprint",
        "seed_sprint_design_overlay",
        "insert_sprint",
        "create_ticket",
        "list_sprints",
        "list_tickets",
        "get_sprint_status",
        "update_ticket_status",
        "move_ticket_to_done",
        "reopen_ticket",
        "throw_ticket_exception",
        "close_sprint",
        "clear_sprint_recovery",
        "get_sprint_phase",
        "advance_sprint_phase",
        "record_gate_result",
        "acquire_execution_lock",
        "release_execution_lock",
        "list_issues",
        "move_issue_to_done",
        "split_issue",
        "link_sprint_issues",
        "add_issue_ref",
        "create_github_issue",
        "close_github_issue",
        "list_github_issues",
        "read_artifact_frontmatter",
        "write_artifact_frontmatter",
        "tag_version",
        "review_sprint_pre_execution",
        "review_sprint_pre_close",
        "review_sprint_post_close",
        "reconcile_worktrees",
    }

    EXPECTED_DISPATCH_TOOLS: set[str] = set()

    EXPECTED_DESIGN_TOOLS = {
        "validate_design",
    }

    EXPECTED_ALL = EXPECTED_PROCESS_TOOLS | EXPECTED_ARTIFACT_TOOLS | EXPECTED_DESIGN_TOOLS

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
        assert len(registered) == 47

    def test_process_tools_registered(self):
        registered = self._registered_tool_names()
        missing = self.EXPECTED_PROCESS_TOOLS - registered
        assert not missing, f"Missing process tools: {missing}"

    def test_artifact_tools_registered(self):
        registered = self._registered_tool_names()
        missing = self.EXPECTED_ARTIFACT_TOOLS - registered
        assert not missing, f"Missing artifact tools: {missing}"

    def test_every_tool_carries_clasi_tool(self):
        """SUC-005 / sprint 030 ticket 005: no tool is left on the old
        contract -- every @server.tool() function across artifact_tools.py,
        process_tools.py, and design_tools.py also carries @clasi_tool.
        Detected via functools.wraps' __wrapped__ attribute, which
        @clasi_tool sets and a bare tool function would not have."""
        tools = server._tool_manager._tools
        unwrapped = [name for name, tool in tools.items() if not hasattr(tool.fn, "__wrapped__")]
        assert not unwrapped, f"Tools missing @clasi_tool: {unwrapped}"
