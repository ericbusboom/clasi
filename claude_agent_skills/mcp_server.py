"""CLASI MCP server — stdio transport.

Provides SE Process Access and Artifact Management tools via MCP.
"""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Create the MCP server instance
server = FastMCP(
    "clasi",
    instructions=(
        "CLASI. "
        "Provides SE process access tools (agents, skills, instructions) "
        "and artifact management tools (sprints, tickets, briefs)."
    ),
)


_CONTENT_ROOT = Path(__file__).parent.resolve()


def content_path(*parts: str) -> Path:
    """Resolve a relative content path to an absolute path inside the package.

    Examples:
        content_path("agents")                       → .../claude_agent_skills/agents/
        content_path("agents", "technical-lead.md")   → .../claude_agent_skills/agents/technical-lead.md
        content_path("instructions", "languages")     → .../claude_agent_skills/instructions/languages/
    """
    return _CONTENT_ROOT.joinpath(*parts)


def run_server() -> None:
    """Start the CLASI MCP server (stdio transport)."""
    # Import tool modules to register their tools with the server
    import claude_agent_skills.process_tools  # noqa: F401
    import claude_agent_skills.artifact_tools  # noqa: F401
    import claude_agent_skills.dispatch_tools  # noqa: F401

    server.run(transport="stdio")
